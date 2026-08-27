# backend/services/permission_service.py
"""
Camada central de RBAC para Sprint 01.

Permissões por role:
- owner  -> controle total da propria empresa/usuarios
- admin  -> administra a propria empresa/usuarios, mas nao ownership
- operator -> operacao, nao administra usuarios
- financial -> financeiro, nao administra usuarios
- viewer -> somente leitura
"""
from functools import wraps
from typing import Callable
from flask import g
from flask.wrappers import Response
from utils.api_response import error_response

# Permissões por role: role -> set de ações permitidas
ROLE_PERMISSIONS: dict[str, set[str]] = {
    'owner': {
        # Empresa
        'empresa.read',
        'empresa.update',
        # Usuarios
        'users.read',
        'users.create',
        'users.invite',
        'users.update',
        'users.change_role',
        'users.deactivate',
        'users.reactivate',
        # Convites
        'invitations.read',
        'invitations.create',
        'invitations.revoke',
        # Clients
        'clients.read',
        'clients.create',
        'clients.update',
        'clients.delete',
        # Plants
        'plants.read',
        'plants.create',
        'plants.update',
        'plants.delete',
        # Consumer Units
        'consumer_units.read',
        'consumer_units.create',
        'consumer_units.update',
        'consumer_units.delete',
        # Documents
        'documents.read',
        'documents.create',
        'documents.update',
        'documents.delete',
        # Pendencias
        'pendencias.read',
        'pendencias.create',
        'pendencias.update',
        'pendencias.delete',
        # Rateios
        'rateios.read',
        'rateios.calculate',
        'rateios.update',
        # Categories
        'categories.read',
        'categories.create',
        'categories.update',
        'categories.delete',
        # Settings
        'settings.read',
        'settings.update',
    },
    'admin': {
        # Empresa
        'empresa.read',
        'empresa.update',
        # Usuarios
        'users.read',
        'users.create',
        'users.invite',
        'users.update',
        'users.change_role',
        'users.deactivate',
        'users.reactivate',
        # Convites
        'invitations.read',
        'invitations.create',
        'invitations.revoke',
        # Clients
        'clients.read',
        'clients.create',
        'clients.update',
        'clients.delete',
        # Plants
        'plants.read',
        'plants.create',
        'plants.update',
        'plants.delete',
        # Consumer Units
        'consumer_units.read',
        'consumer_units.create',
        'consumer_units.update',
        'consumer_units.delete',
        # Documents
        'documents.read',
        'documents.create',
        'documents.update',
        'documents.delete',
        # Pendencias
        'pendencias.read',
        'pendencias.create',
        'pendencias.update',
        'pendencias.delete',
        # Rateios
        'rateios.read',
        'rateios.calculate',
        'rateios.update',
        # Categories
        'categories.read',
        'categories.create',
        'categories.update',
        'categories.delete',
        # Settings
        'settings.read',
        'settings.update',
    },
    'operator': {
        # Empresa - leitura
        'empresa.read',
        # Clients
        'clients.read',
        'clients.create',
        'clients.update',
        'clients.delete',
        # Plants
        'plants.read',
        'plants.create',
        'plants.update',
        'plants.delete',
        # Consumer Units
        'consumer_units.read',
        'consumer_units.create',
        'consumer_units.update',
        'consumer_units.delete',
        # Documents
        'documents.read',
        'documents.create',
        'documents.update',
        'documents.delete',
        # Pendencias
        'pendencias.read',
        'pendencias.create',
        'pendencias.update',
        'pendencias.delete',
        # Categories
        'categories.read',
        # Rateios
        'rateios.read',
        'rateios.calculate',
        'rateios.update',
    },
    'financial': {
        # Empresa - leitura
        'empresa.read',
        # Clients
        'clients.read',
        # Consumer Units
        'consumer_units.read',
        # Documents
        'documents.read',
        # Pendencias
        'pendencias.read',
        'pendencias.create',
        'pendencias.update',
        'pendencias.delete',
        # Rateios
        'rateios.read',
        'rateios.calculate',
        'rateios.update',
        # Categories
        'categories.read',
    },
    'viewer': {
        # Empresa - leitura
        'empresa.read',
        # Clients
        'clients.read',
        # Plants
        'plants.read',
        # Consumer Units
        'consumer_units.read',
        # Documents
        'documents.read',
        # Pendencias
        'pendencias.read',
        # Rateios
        'rateios.read',
        # Categories
        'categories.read',
    },
}

def get_user_permissions(user) -> set[str]:
    """Retorna o conjunto de permissões para um usuário."""
    if not user or not hasattr(user, 'role'):
        return set()
    return ROLE_PERMISSIONS.get(user.role, set())

def can(user, action: str) -> bool:
    """Verifica se o usuário tem permissão para uma ação."""
    if not user:
        return False
    return action in ROLE_PERMISSIONS.get(user.role, set())

def can_any(user, actions: list[str]) -> bool:
    """Verifica se o usuário tem pelo menos uma das ações."""
    if not user:
        return False
    user_perms = ROLE_PERMISSIONS.get(user.role, set())
    return any(a in user_perms for a in actions)

def require_permission(*permissions: str) -> Callable:
    """
    Decorador que exige pelo menos uma das permissões especificadas.

    Uso:
        @require_permission('users.create', 'users.invite')
        def create_user():
            ...
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def wrapper(*args, **kwargs) -> Response | None:
            if not hasattr(g, 'current_user') or not g.current_user:
                return error_response('Autenticacao obrigatoria.', 401)

            if not can_any(g.current_user, list(permissions)):
                return error_response(
                    f'Voce nao tem permissao para esta acao ({", ".join(permissions)}).',
                    403
                )

            return f(*args, **kwargs)
        return wrapper
    return decorator

def require_role(*roles: str) -> Callable:
    """
    Decorador que exige um dos roles especificados.

    Uso:
        @require_role('owner', 'admin')
        def admin_only():
            ...
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def wrapper(*args, **kwargs) -> Response | None:
            if not hasattr(g, 'current_user') or not g.current_user:
                return error_response('Autenticacao obrigatoria.', 401)

            if g.current_user.role not in roles:
                return error_response(
                    f'Esta acao requer um dos seguintes perfis: {", ".join(roles)}.',
                    403
                )

            return f(*args, **kwargs)
        return wrapper
    return decorator

def require_ownership() -> Callable:
    """
    Decorador que exige role 'owner'.

    Uso:
        @require_ownership()
        def owner_only():
            ...
    """
    return require_role('owner')

def is_owner(user) -> bool:
    """Verifica se o usuário é owner."""
    return user and user.role == 'owner'

def is_admin_or_owner(user) -> bool:
    """Verifica se o usuário é admin ou owner."""
    return user and user.role in ('owner', 'admin')

def is_active(user) -> bool:
    """Verifica se o usuário está ativo."""
    return user and user.status == 'ativo'

def require_platform_admin() -> Callable:
    """
    Decorador que exige que o usuário logado seja administrador da
    plataforma (User.is_platform_admin = True) -- fora do RBAC por
    empresa de propósito, usado só pelas rotas /platform/*.

    Uso:
        @require_platform_admin()
        def listar_empresas():
            ...
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def wrapper(*args, **kwargs) -> Response | None:
            if not hasattr(g, 'current_user') or not g.current_user:
                return error_response('Autenticacao obrigatoria.', 401)

            if not getattr(g.current_user, 'is_platform_admin', False):
                return error_response('Acesso restrito a administradores da plataforma.', 403)

            return f(*args, **kwargs)
        return wrapper
    return decorator