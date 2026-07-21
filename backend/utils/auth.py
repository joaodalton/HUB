# backend/utils/auth.py
"""
Autenticacao simples por token assinado (nao-JWT, usa itsdangerous que ja
vem junto com o Flask -- sem dependencia nova). Um usuario so por enquanto,
sem checagem de papel/permissao: token valido = pode usar a API.
"""
from flask import g, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.security import check_password_hash, generate_password_hash

from config import Config
from utils.api_response import error_response

TOKEN_MAX_AGE_SECONDS = 60 * 60 * 24 * 7  # token expira em 7 dias, precisa logar de novo depois


def hash_password(raw_password: str) -> str:
    return generate_password_hash(raw_password)


def verify_password(raw_password: str, password_hash: str) -> bool:
    return check_password_hash(password_hash, raw_password)


def _get_serializer() -> URLSafeTimedSerializer:
    if not Config.SECRET_KEY:
        raise RuntimeError(
            'SECRET_KEY nao configurada no .env. Gere uma com: '
            'python -c "import secrets; print(secrets.token_hex(32))"'
        )
    return URLSafeTimedSerializer(Config.SECRET_KEY)


def generate_token(user_id: int) -> str:
    return _get_serializer().dumps({'user_id': user_id})


def decode_token(token: str) -> int | None:
    try:
        data = _get_serializer().loads(token, max_age=TOKEN_MAX_AGE_SECONDS)
        return data.get('user_id')
    except (BadSignature, SignatureExpired):
        return None


def register_auth_middleware(app, public_paths: set[str]) -> None:
    """Bloqueia toda rota da API que nao estiver em public_paths sem token valido.
    Registrar em create_app() depois que os blueprints existirem."""

    @app.before_request
    def _require_auth():
        if request.method == 'OPTIONS':
            return None

        if request.path in public_paths:
            return None

        auth_header = request.headers.get('Authorization', '')

        if not auth_header.startswith('Bearer '):
            return error_response('Token de autenticacao ausente.', 401)

        token = auth_header[len('Bearer '):]
        user_id = decode_token(token)

        if not user_id:
            return error_response('Token invalido ou expirado.', 401)

        from models.user import User
        user = User.query.get(user_id)

        if not user or not user.ativo:
            return error_response('Usuario invalido ou inativo.', 401)

        g.current_user = user
        return None