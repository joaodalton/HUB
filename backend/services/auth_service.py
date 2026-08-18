# backend/services/auth_service.py
from extensions import db
from models.user import User
from services.log_service import LogService
from utils.auth import generate_token, verify_password


def authenticate(email: str, senha: str) -> dict | None:
    user = User.query.filter(db.func.lower(User.email) == email.strip().lower()).first()

    if not user or user.status != 'ativo' or not verify_password(senha, user.password_hash):
        LogService.warning(acao='login_failed', mensagem=f'Tentativa de login falhou para {email}', entidade='User')
        return None

    token = generate_token(user.id)
    LogService.info(acao='login', mensagem='Login realizado', entidade='User', metadados={'userId': user.id})

    return {
        'token': token,
        'user': user.to_dict()
    }