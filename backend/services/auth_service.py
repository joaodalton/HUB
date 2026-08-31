# backend/services/auth_service.py
from extensions import db
from models.user import User
from models.empresa import Empresa
from services.log_service import LogService
from utils.auth import generate_token, hash_password, verify_password


# Mantém o custo do hash mesmo se o e-mail não existir, evitando que o tempo
# de resposta revele quais endereços têm conta cadastrada.
_DUMMY_PASSWORD_HASH = hash_password('not-a-real-password')


def authenticate(email: str, senha: str) -> dict | None:
    user = User.query.filter(db.func.lower(User.email) == email.strip().lower()).first()
    password_hash = user.password_hash if user else _DUMMY_PASSWORD_HASH
    password_is_valid = verify_password(senha, password_hash)

    if not user or user.status != 'ativo' or not password_is_valid:
        LogService.warning(acao='login_failed', mensagem=f'Tentativa de login falhou para {email}', entidade='User')
        return None

    token = generate_token(user.id)
    LogService.info(
        acao='login', mensagem='Login realizado', entidade='User',
        metadados={'userId': user.id, 'empresaId': user.empresa_id}
    )

    user_data = user.to_dict()
    empresa = db.session.get(Empresa, user.empresa_id)
    user_data['empresaNome'] = empresa.nome if empresa else None
    return {
        'token': token,
        'user': user_data
    }


def change_password(user: User, senha_atual: str, nova_senha: str) -> dict:
    """Troca autenticada de senha, inclusive no primeiro acesso forçado."""
    if not isinstance(senha_atual, str) or not verify_password(senha_atual, user.password_hash):
        raise ValueError('Senha atual invalida.')
    if not isinstance(nova_senha, str) or len(nova_senha) < 6:
        raise ValueError('Nova senha precisa ter pelo menos 6 caracteres.')
    if verify_password(nova_senha, user.password_hash):
        raise ValueError('Nova senha deve ser diferente da senha atual.')

    user.password_hash = hash_password(nova_senha)
    user.must_change_password = False
    user.session_version += 1
    db.session.commit()

    LogService.info(
        acao='password_changed',
        mensagem=f'Senha alterada para {user.email}',
        entidade='User',
        metadados={'userId': user.id, 'empresaId': user.empresa_id},
    )
    return {'token': generate_token(user.id), 'user': user.to_dict()}
