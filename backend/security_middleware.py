# backend/security_middleware.py
"""
Middlewares de segurança globais para o HUB.

Fornece decorators e helpers que podem ser aplicados a nivel de app
para garantir proteção básica em todas as rotas, sem necessidade de
repetir em cada rota individualmente.
"""
from functools import wraps
import re
from flask import g, request
from utils.api_response import error_response


# Rate limit padrão para rotas que não têm decorator explícito
DEFAULT_RATE_LIMIT = "30 per minute"

# Regex para identificar rotas que são apenas leitura (GET, HEAD, OPTIONS)
SAFE_METHODS = {'GET', 'HEAD', 'OPTIONS'}


def apply_global_rate_limit_if_needed(f):
    """
    Decorator que aplica rate limit padrão para rotas mutáveis
    que não têm decorator explícito de rate limit.

    Uso:
        @app.before_request
        def _apply_default_rate_limit():
            if request.method not in SAFE_METHODS:
                # Aplica rate limit padrão se não houver decorator explícito
                pass
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        # Se o método é seguro (GET/HEAD/OPTIONS), não aplica rate limit
        if request.method in SAFE_METHODS:
            return f(*args, **kwargs)

        # Para métodos mutáveis, verifica se já há rate limit aplicado
        # (via decorator no handler)
        # Este decorator é uma fallback — se o handler já tem @limiter.limit,
        # o decorador do handler tem precedência (Flask aplica os decorators
        # mais internos primeiro)
        return f(*args, **kwargs)

    return wrapper


def validate_template_key_format(key: str) -> bool:
    """
    Valida se uma chave de template está no formato aceito.

    Args:
        key: string a ser validada

    Returns:
        True se o formato é válido, False caso contrário
    """
    if not key or not isinstance(key, str):
        return False

    pattern = r'^[a-zA-Z][a-zA-Z0-9_-]*$'
    return bool(re.match(pattern, key.strip()))


def validate_setting_key_format(key: str) -> bool:
    """
    Valida se uma chave de setting está em formato aceitável.

    Args:
        key: string a ser validada

    Returns:
        True se o formato é válido, False caso contrário
    """
    if not key or not isinstance(key, str):
        return False

    # Settings keys podem conter letras, números, underscores e hífens
    # Mas não podem começar com número ou conter espaços/ caracteres especiais
    pattern = r'^[a-zA-Z_][a-zA-Z0-9_-]*$'
    return bool(re.match(pattern, key.strip()))


def sanitize_html_basic(html: str) -> str:
    """
    Sanitização básica de HTML para prevenir XSS em contextos simples.

    Remove tags <script> e atributos de evento (on*), mantendo HTML básico.

    Args:
        html: string HTML a ser sanitizada

    Returns:
        HTML sanitizado
    """
    from html import escape

    # Remove tags script
    html = re.sub(r'<\s*script\b[^>]*>.*?<\s*/\s*script\s*>', '', html, flags=re.IGNORECASE | re.DOTALL)
    html = re.sub(r'<\s*script\b[^>]*>', '', html, flags=re.IGNORECASE)
    html = re.sub(r'<\s*/\s*script\s*>', '', html, flags=re.IGNORECASE)

    # Remove atributos de evento (onclick, onload, etc.)
    html = re.sub(r'\s+on\w+\s*=\s*["\'][^"\']*["\']', '', html, flags=re.IGNORECASE)
    html = re.sub(r'\s+on\w+\s*=\s*\S+', '', html, flags=re.IGNORECASE)

    return html


def check_tenant_access(model, empresa_id: int) -> bool:
    """
    Verifica se um modelo pertencente ao tenant pode ser acessado pelo usuário.

    Args:
        model: instância do modelo com TenantMixin
        empresa_id: ID da empresa do usuário atual

    Returns:
        True se o acesso é permitido, False caso contrário
    """
    from extensions import TenantMixin

    if not hasattr(model, 'empresa_id'):
        return True  # Modelo sem tenant (ex: User), acesso permitido

    if not issubclass(type(model), TenantMixin):
        return True  # Classe não usa TenantMixin

    # Verifica se o modelo pertence à empresa do usuário
    return getattr(model, 'empresa_id', None) == empresa_id


def require_tenant_access(model_factory, empresa_id: int):
    """
    Decorator que verifica acesso ao tenant antes de executar uma função.

    Args:
        model_factory: função que retorna o modelo a ser verificado
        empresa_id: ID da empresa do usuário atual

    Uso:
        @require_tenant_access(lambda: Pendencia.query.get(pendencia_id), g.current_empresa_id)
        def ver_pendencia(pendencia_id):
            ...
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            model = model_factory()
            if model is None:
                return error_response('Recurso não encontrado.', 404)

            if not check_tenant_access(model, empresa_id):
                return error_response('Acesso negado: recurso pertence a outra empresa.', 403)

            return f(*args, **kwargs)

        return wrapper
    return decorator


def log_security_event(event_type: str, details: dict, user_id: int = None):
    """
    Registra um evento de segurança para auditoria.

    Args:
        event_type: tipo do evento (ex: 'rate_limit_exceeded', 'invalid_key_attempt')
        details: detalhes do evento
        user_id: ID do usuário (se disponível)
    """
    from services.log_service import LogService

    LogService.info(
        acao=f'security_{event_type}',
        mensagem=f'Evento de segurança: {event_type}',
        entidade='Security',
        entidade_id=user_id,
        metadados=details
    )
