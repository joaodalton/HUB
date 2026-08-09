# backend/services/user_service.py
from extensions import db
from models.user import User
from services.log_service import LogService
from utils.auth import hash_password

VALID_ROLES = {'admin', 'viewer'}


def list_users() -> list[dict]:
    users = User.query.order_by(User.created_at.desc()).all()
    return [user.to_dict() for user in users]


def create_user(data: dict) -> dict:
    email = (data.get('email') or '').strip().lower()
    senha = data.get('senha') or ''
    papel = data.get('papel') or 'viewer'

    if not email or not senha:
        raise ValueError('Email e senha sao obrigatorios.')
    if len(senha) < 6:
        raise ValueError('Senha precisa ter pelo menos 6 caracteres.')
    if papel not in VALID_ROLES:
        raise ValueError(f'Papel invalido. Use um de: {", ".join(sorted(VALID_ROLES))}.')

    existing = User.query.filter(db.func.lower(User.email) == email).first()
    if existing:
        raise ValueError('Ja existe um usuario com esse email.')

    user = User(email=email, password_hash=hash_password(senha), papel=papel, ativo=True)
    db.session.add(user)
    db.session.commit()

    LogService.info(
        acao='create',
        mensagem=f'Usuario {email} criado com papel "{papel}"',
        entidade='User',
        metadados={'userId': user.id}
    )
    return user.to_dict()


def set_user_active(user_id: int, ativo: bool) -> dict | None:
    user = User.query.get(user_id)
    if not user:
        return None

    user.ativo = ativo
    db.session.commit()

    LogService.info(
        acao='update',
        mensagem=f'Usuario {user.email} {"ativado" if ativo else "desativado"}',
        entidade='User',
        metadados={'userId': user.id}
    )
    return user.to_dict()