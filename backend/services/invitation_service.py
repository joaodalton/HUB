# backend/services/invitation_service.py
"""
Convite por link -- substitui "criar usuario com senha na mao" tanto pro
primeiro owner de uma empresa nova (criado pelo scripts/criar_empresa.py)
quanto pra Owner/Admin convidando gente pra dentro da propria empresa.

Token nunca fica salvo em texto puro (token_hash = sha256 do token cru) --
so quem recebeu o link consegue usar. Uso unico: aceitar marca status como
'accepted', link nao funciona de novo.
"""
import hashlib
import secrets
from datetime import datetime, timedelta

from config import Config
from extensions import db
from models.empresa import Empresa
from models.invitation import Invitation
from models.user import User
from services.email_service import send_email
from services.email_template_service import renderizar as renderizar_template
from services.log_service import LogService
from services.user_service import VALID_ROLES
from utils.auth import hash_password

INVITE_TTL_DAYS = 7


def _gerar_token() -> tuple[str, str]:
    token_cru = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token_cru.encode()).hexdigest()
    return token_cru, token_hash


def criar_convite(empresa_id: int, email: str, role: str, invited_by_id: int | None) -> tuple[dict, str]:
    """Retorna (convite.to_dict(), token_cru) -- o token cru so existe nesse
    retorno, nunca e persistido nem logado (so o hash fica salvo)."""
    email = email.strip().lower()

    if not email:
        raise ValueError('Email e obrigatorio.')

    if role == 'owner':
        if invited_by_id is not None:
            raise ValueError('Convite de owner so pode ser criado na criacao da empresa (scripts/criar_empresa.py).')
    elif role not in VALID_ROLES:
        raise ValueError(f'Papel invalido. Use um de: {", ".join(sorted(VALID_ROLES))}.')

    if User.query.filter(db.func.lower(User.email) == email).first():
        raise ValueError('Ja existe um usuario com esse email.')

    # Convite pendente anterior pro mesmo email/empresa fica revogado --
    # evita dois links validos ao mesmo tempo pra mesma pessoa.
    Invitation.query.filter_by(empresa_id=empresa_id, email=email, status='pending').update({'status': 'revoked'})

    token_cru, token_hash = _gerar_token()
    convite = Invitation(
        empresa_id=empresa_id,
        email=email,
        role=role,
        token_hash=token_hash,
        expires_at=datetime.utcnow() + timedelta(days=INVITE_TTL_DAYS),
        invited_by=invited_by_id,
        status='pending'
    )
    db.session.add(convite)
    db.session.commit()

    LogService.info(
        acao='convite_criado',
        mensagem=f'Convite criado para {email} (papel "{role}")',
        entidade='Invitation',
        metadados={'invitationId': convite.id, 'empresaId': empresa_id}
    )

    _enviar_email_convite(convite, token_cru)

    return convite.to_dict(), token_cru


def _enviar_email_convite(convite: Invitation, token_cru: str) -> None:
    """Sem RESEND_API_KEY configurada, send_email() vira no-op com warning
    (nao quebra a criacao do convite) -- o link continua disponivel no
    retorno da API pra copiar na mao, mesmo se o e-mail nao sair."""
    empresa = Empresa.query.get(convite.empresa_id)
    link = f'{Config.FRONTEND_URL}/aceitar-convite?token={token_cru}'

    renderizado = renderizar_template('convite', {
        'papel': convite.role,
        'empresa': empresa.nome if empresa else 'HUB',
        'link': link
    })

    if not renderizado:
        LogService.warning(
            acao='email_template_missing',
            mensagem='Template "convite" não encontrado -- e-mail de convite não enviado.',
            entidade='EmailTemplate'
        )
        return

    assunto, html, text = renderizado
    send_email(to=convite.email, subject=assunto, html=html, text=text)


def listar_convites(empresa_id: int) -> list[dict]:
    convites = Invitation.query.filter_by(empresa_id=empresa_id).order_by(Invitation.created_at.desc()).all()
    return [c.to_dict() for c in convites]


def _buscar_convite_valido(token_cru: str) -> Invitation:
    token_hash = hashlib.sha256(token_cru.encode()).hexdigest()
    convite = Invitation.query.filter_by(token_hash=token_hash).first()

    if not convite:
        raise ValueError('Convite invalido.')
    if convite.status == 'accepted':
        raise ValueError('Esse convite ja foi usado.')
    if convite.status == 'revoked':
        raise ValueError('Esse convite foi revogado.')
    if convite.expires_at < datetime.utcnow():
        convite.status = 'expired'
        db.session.commit()
        raise ValueError('Convite expirado. Peca um novo.')

    return convite


def verificar_convite(token_cru: str) -> dict:
    """Usado pela tela de aceite pra mostrar 'voce foi convidado pra <empresa>
    como <papel>' antes da pessoa preencher nome/senha."""
    convite = _buscar_convite_valido(token_cru)
    empresa = Empresa.query.get(convite.empresa_id)

    return {
        'email': convite.email,
        'role': convite.role,
        'empresaNome': empresa.nome if empresa else None
    }


def aceitar_convite(token_cru: str, nome: str, senha: str) -> dict:
    if not nome.strip():
        raise ValueError('Nome e obrigatorio.')
    if len(senha) < 6:
        raise ValueError('Senha precisa ter pelo menos 6 caracteres.')

    convite = _buscar_convite_valido(token_cru)

    if User.query.filter(db.func.lower(User.email) == convite.email).first():
        raise ValueError('Ja existe um usuario com esse email.')

    user = User(
        empresa_id=convite.empresa_id,
        nome=nome.strip(),
        email=convite.email,
        password_hash=hash_password(senha),
        role=convite.role,
        status='ativo',
        email_verified=True,  # o convite chegou nesse email/whatsapp, entao ja confirma
        must_change_password=False  # a pessoa ja escolheu a propria senha agora
    )
    db.session.add(user)

    convite.status = 'accepted'
    convite.accepted_at = datetime.utcnow()

    db.session.commit()

    LogService.info(
        acao='convite_aceito',
        mensagem=f'Convite aceito por {user.email}',
        entidade='User',
        metadados={'userId': user.id, 'empresaId': user.empresa_id}
    )
    return user.to_dict()