# backend/services/user_service.py
import secrets

from config import Config
from extensions import db
from models.user import User
from services.log_service import LogService
from utils.auth import hash_password

# 'owner' de proposito fora daqui -- so nasce junto com a Empresa (ver
# scripts/criar_empresa.py). Criar usuario "normal" (Owner/Admin convidando
# alguem) nunca cria outro owner.
VALID_ROLES = {'admin', 'operator', 'financial', 'viewer'}


def list_users(empresa_id: int) -> list[dict]:
    users = User.query.filter_by(empresa_id=empresa_id).order_by(User.created_at.desc()).all()
    return [user.to_dict() for user in users]


def create_user(data: dict, empresa_id: int) -> dict:
    email = (data.get('email') or '').strip().lower()
    nome = (data.get('nome') or '').strip()
    senha = data.get('senha') or ''
    role = data.get('role') or 'viewer'

    if not email or not senha or not nome:
        raise ValueError('Nome, email e senha sao obrigatorios.')
    if len(senha) < 6:
        raise ValueError('Senha precisa ter pelo menos 6 caracteres.')
    if role not in VALID_ROLES:
        raise ValueError(f'Papel invalido. Use um de: {", ".join(sorted(VALID_ROLES))}.')

    existing = User.query.filter(db.func.lower(User.email) == email).first()
    if existing:
        raise ValueError('Ja existe um usuario com esse email (email e unico em toda a base, entre empresas).')

    user = User(
        empresa_id=empresa_id,
        nome=nome,
        email=email,
        password_hash=hash_password(senha),
        role=role,
        status='ativo',
        email_verified=False,
        # Senha foi definida por outra pessoa (Owner/Admin), nao pelo
        # proprio usuario -- forca troca no primeiro acesso (spec secao 6).
        must_change_password=True
    )
    db.session.add(user)
    db.session.commit()

    LogService.info(
        acao='create',
        mensagem=f'Usuario {email} criado com papel "{role}"',
        entidade='User',
        metadados={'userId': user.id, 'empresaId': empresa_id}
    )
    return user.to_dict()


def register_with_code(data: dict, provided_code: str) -> dict:
    """Auto-cadastro publico (tela de login) -- so funciona se SIGNUP_CODE
    estiver configurado E o codigo mandado bater. SEMPRE cria 'viewer', nunca
    'admin' -- forcado aqui, independente do que vier em data['papel']. Um
    auto-cadastro nao deve conseguir se dar poder de admin sozinho."""
    if not Config.SIGNUP_CODE:
        raise ValueError('Cadastro publico desativado.')

    if not provided_code or not secrets.compare_digest(provided_code, Config.SIGNUP_CODE):
        raise ValueError('Codigo de acesso invalido.')

    return create_user({**data, 'role': 'viewer'}, empresa_id)


def set_user_active(user_id: int, empresa_id: int, ativo: bool) -> dict | None:
    user = User.query.filter_by(id=user_id, empresa_id=empresa_id).first()
    if not user:
        return None

    if user.role == 'owner' and not ativo:
        raise ValueError('Nao e possivel desativar o owner da empresa.')

    user.status = 'ativo' if ativo else 'inativo'
    db.session.commit()

    LogService.info(
        acao='update',
        mensagem=f'Usuario {user.email} {"ativado" if ativo else "desativado"}',
        entidade='User',
        metadados={'userId': user.id}
    )
    return user.to_dict()