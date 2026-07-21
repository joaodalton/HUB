# backend/services/auth_service.py
from extensions import db
from models.user import User
from services.log_service import LogService
from utils.auth import generate_token, hash_password, verify_password


def authenticate(email: str, senha: str) -> dict | None:
    user = User.query.filter(db.func.lower(User.email) == email.strip().lower()).first()

    if not user or not user.ativo or not verify_password(senha, user.password_hash):
        LogService.warning(acao='login_failed', mensagem=f'Tentativa de login falhou para {email}', entidade='User')
        return None

    token = generate_token(user.id)
    LogService.info(acao='login', mensagem='Login realizado', entidade='User', metadados={'userId': user.id})

    return {
        'token': token,
        'user': user.to_dict()
    }


def create_first_admin(email: str, senha: str) -> User:
    """So funciona se ainda nao existir nenhum usuario -- ver rota /auth/bootstrap.
    Depois do primeiro uso, essa funcao nunca mais e chamada com sucesso (a rota
    se tranca sozinha), entao nao precisa desabilitar nada aqui."""
    user = User(
        email=email.strip().lower(),
        password_hash=hash_password(senha),
        papel='admin',
        ativo=True
    )
    db.session.add(user)
    db.session.commit()

    LogService.info(acao='bootstrap', mensagem='Usuario admin inicial criado', entidade='User', metadados={'userId': user.id})
    return user