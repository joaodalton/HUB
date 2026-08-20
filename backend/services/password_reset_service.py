# backend/services/password_reset_service.py
"""
Fluxo de "esqueci minha senha" -- mesmo padrao de token hasheado + TTL que
Invitation ja usa (services/invitation_service.py). Token cru so existe no
link mandado por e-mail, nunca fica persistido.
"""
import hashlib
import secrets
from datetime import datetime, timedelta

from extensions import db
from config import Config
from models.password_reset_token import PasswordResetToken
from models.user import User
from services.email_service import send_email
from services.email_template_service import renderizar as renderizar_template
from services.log_service import LogService
from utils.auth import hash_password

RESET_TTL_MINUTES = 60


def _gerar_token() -> tuple[str, str]:
    token_cru = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token_cru.encode()).hexdigest()
    return token_cru, token_hash


def solicitar_reset(email: str) -> None:
    """Sempre retorna sem erro (mesmo se o e-mail nao existir) -- nao revela
    pra quem esta pedindo se aquele endereco tem conta ou nao, mesma logica
    ja aplicada no login (ver auth_service.py, _DUMMY_PASSWORD_HASH)."""
    email = (email or '').strip().lower()
    if not email:
        return

    user = User.query.filter(db.func.lower(User.email) == email).first()
    if not user or user.status != 'ativo':
        return

    # Invalida qualquer pedido de reset anterior ainda pendente.
    PasswordResetToken.query.filter_by(user_id=user.id, used=False).update({'used': True})

    token_cru, token_hash = _gerar_token()
    reset = PasswordResetToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=datetime.utcnow() + timedelta(minutes=RESET_TTL_MINUTES),
        used=False
    )
    db.session.add(reset)
    db.session.commit()

    reset_link = f'{Config.FRONTEND_URL}/redefinir-senha?token={token_cru}'
    renderizado = renderizar_template('password_reset', {'nome': user.nome or user.email, 'link': reset_link})

    if renderizado:
        subject, html, text = renderizado
        send_email(to=user.email, subject=subject, html=html, text=text)
    else:
        LogService.warning(
            acao='email_template_missing',
            mensagem='Template "password_reset" não encontrado -- e-mail de redefinição não enviado.',
            entidade='EmailTemplate'
        )

    LogService.info(
        acao='password_reset_solicitado',
        mensagem=f'Reset de senha solicitado para {user.email}',
        entidade='User',
        metadados={'userId': user.id}
    )


def redefinir_senha(token_cru: str, nova_senha: str) -> None:
    if len(nova_senha) < 6:
        raise ValueError('Senha precisa ter pelo menos 6 caracteres.')

    token_hash = hashlib.sha256(token_cru.encode()).hexdigest()
    reset = PasswordResetToken.query.filter_by(token_hash=token_hash).first()

    if not reset or reset.used:
        raise ValueError('Link de redefinição inválido ou já utilizado.')
    if reset.expires_at < datetime.utcnow():
        raise ValueError('Link de redefinição expirado. Solicite um novo.')

    user = User.query.get(reset.user_id)
    if not user:
        raise ValueError('Usuário não encontrado.')

    user.password_hash = hash_password(nova_senha)
    reset.used = True
    db.session.commit()

    LogService.info(
        acao='password_reset_concluido',
        mensagem=f'Senha redefinida para {user.email}',
        entidade='User',
        metadados={'userId': user.id}
    )