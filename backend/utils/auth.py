# backend/utils/auth.py
"""
Autenticacao simples por token assinado (nao-JWT, usa itsdangerous que ja
vem junto com o Flask -- sem dependencia nova). Um usuario so por enquanto,
sem checagem de papel/permissao: token valido = pode usar a API.
"""
import secrets

from flask import g, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.security import check_password_hash, generate_password_hash

from config import Config
from extensions import db
from utils.api_response import error_response

TOKEN_MAX_AGE_SECONDS = 60 * 60 * 24 * 7

COOKIE_NAME = 'hub_token'
CSRF_COOKIE_NAME = 'hub_csrf'
# Cookie separado do de sessão -- só existe pra platform admin que "entrou"
# numa empresa (ver routes/platform_routes.py). Guarda so o empresa_id
# escolhido, nunca é lido/confiado por si só: o middleware sempre confere
# de novo que o dono do cookie é is_platform_admin antes de usar o valor.
VIEW_COOKIE_NAME = 'hub_platform_view'
_SAFE_METHODS = {'GET', 'HEAD', 'OPTIONS'}
_PASSWORD_CHANGE_SAFE_PATHS = {
    '/api/v1/auth/me',
    '/api/v1/auth/logout',
    '/api/v1/auth/alterar-senha',
}


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
    from models.user import User
    user = db.session.get(User, user_id)
    if not user:
        raise ValueError('Usuario nao encontrado.')
    return _get_serializer().dumps({'user_id': user_id, 'session_version': user.session_version})


def decode_token(token: str) -> dict | None:
    try:
        data = _get_serializer().loads(token, max_age=TOKEN_MAX_AGE_SECONDS)
        return data
    except (BadSignature, SignatureExpired):
        return None


def set_auth_cookies(response, token: str, remember: bool = False) -> None:
    is_prod = not Config.DEBUG

    # remember=False -> nao manda max_age nenhum -- vira "session cookie" de
    # verdade (o navegador apaga sozinho ao fechar), sem precisar de
    # localStorage/sessionStorage no frontend pra controlar isso. remember=True
    # usa o mesmo TTL que o proprio token ja tem (7 dias, TOKEN_MAX_AGE_SECONDS)
    # -- nao faz sentido o cookie durar mais que o token seria valido de qualquer jeito.
    cookie_max_age = TOKEN_MAX_AGE_SECONDS if remember else None

    response.set_cookie(
        COOKIE_NAME, token, httponly=True, secure=is_prod,
        samesite='Lax', max_age=cookie_max_age, path='/'
    )
    response.set_cookie(
        CSRF_COOKIE_NAME, secrets.token_urlsafe(32), httponly=False, secure=is_prod,
        samesite='Lax', max_age=cookie_max_age, path='/'
    )


def clear_auth_cookies(response) -> None:
    is_prod = not Config.DEBUG
    response.delete_cookie(COOKIE_NAME, path='/', samesite='Lax', secure=is_prod)
    response.delete_cookie(CSRF_COOKIE_NAME, path='/', samesite='Lax', secure=is_prod)

def set_platform_view_cookie(response, empresa_id: int) -> None:
    is_prod = not Config.DEBUG
    response.set_cookie(
        VIEW_COOKIE_NAME, str(empresa_id), httponly=True, secure=is_prod,
        samesite='Lax', max_age=TOKEN_MAX_AGE_SECONDS, path='/'
    )

def clear_platform_view_cookie(response) -> None:
    is_prod = not Config.DEBUG
    response.delete_cookie(VIEW_COOKIE_NAME, path='/', samesite='Lax', secure=is_prod)

def resolve_current_user_optional():
    """Mesma checagem de token de _require_auth, mas sem forçar 401 se não
    autenticado -- usada pelas rotas PÚBLICAS de OAuth (/authorize,
    /callback), que ficam de fora do middleware (o /callback é chamado
    pelo próprio Google, não dá pra exigir token nele) mas ainda assim
    precisam saber a empresa de quem iniciou o fluxo, quando disponível."""
    token = request.cookies.get(COOKIE_NAME)

    if not token:
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            token = auth_header[len('Bearer '):]

    if not token:
        return None

    token_data = decode_token(token)
    if not token_data:
        return None

    from models.user import User
    user = db.session.get(User, token_data.get('user_id'))
    return user if user and user.status == 'ativo' and user.session_version == token_data.get('session_version') else None

def register_auth_middleware(app, public_paths: set[str], public_path_prefixes: set[str] = frozenset()) -> None:
    @app.before_request
    def _require_auth():
        if request.method == 'OPTIONS':
            return None
        if request.path in public_paths:
            return None
        # Cobre rotas com parametro dinamico no path (ex.: /empresas/<slug>),
        # que nunca batem contra o set exato acima (ver comentario em app.py).
        # count('/') == 4 garante que so casa exatamente UM segmento depois
        # do prefixo (ex.: /api/v1/empresas/select), nao /api/v1/empresas/x/y.
        if any(
            request.path.startswith(prefix) and request.path.count('/') == prefix.count('/') + 1
            for prefix in public_path_prefixes
        ):
            return None

        token_from_cookie = request.cookies.get(COOKIE_NAME)
        token = token_from_cookie

        if not token:
            auth_header = request.headers.get('Authorization', '')
            if auth_header.startswith('Bearer '):
                token = auth_header[len('Bearer '):]

        if not token:
            return error_response('Token de autenticacao ausente.', 401)

        token_data = decode_token(token)
        if not token_data:
            return error_response('Token invalido ou expirado.', 401)

        from models.user import User
        from models.empresa import Empresa

        user = db.session.get(User, token_data.get('user_id'))
        if not user or user.status != 'ativo' or user.session_version != token_data.get('session_version'):
            return error_response('Usuario invalido ou inativo.', 401)

        # A partir daqui, toda query contra um model com TenantMixin
        # (Client, ConsumerUnit, Plant etc.) já vem filtrada por essa
        # empresa automaticamente -- ver extensions.py.
        g.current_user = user
        g.current_empresa_id = user.empresa_id
        g.current_role = user.role
        g.current_empresa = db.session.get(Empresa, user.empresa_id)
        g.platform_view_empresa_id = None

        # Platform admin "dentro" de uma empresa (ver routes/platform_routes.py):
        # sobrescreve g.current_empresa_id só pra esta requisição -- toda rota
        # existente (clients, plants, ucs, documents...) passa a enxergar a
        # empresa escolhida automaticamente, sem precisar de rota duplicada.
        # Cookie sozinho nunca é suficiente: só vale se o USUÁRIO LOGADO
        # (não o cookie) for is_platform_admin de verdade.
        if user.is_platform_admin:
            view_cookie = request.cookies.get(VIEW_COOKIE_NAME)
            if view_cookie and view_cookie.isdigit():
                empresa_visualizada = db.session.get(Empresa, int(view_cookie))
                if empresa_visualizada:
                    g.current_empresa_id = empresa_visualizada.id
                    g.current_empresa = empresa_visualizada
                    g.platform_view_empresa_id = empresa_visualizada.id

        if user.must_change_password and request.path not in _PASSWORD_CHANGE_SAFE_PATHS:
            return error_response(
                'Troca de senha obrigatoria antes de continuar.',
                403,
                code='PASSWORD_CHANGE_REQUIRED',
            )

        if token_from_cookie and request.method not in _SAFE_METHODS:
            csrf_cookie = request.cookies.get(CSRF_COOKIE_NAME)
            csrf_header = request.headers.get('X-CSRF-Token')
            if not csrf_cookie or not csrf_header or csrf_cookie != csrf_header:
                return error_response('Token CSRF ausente ou invalido.', 403)

        return None
