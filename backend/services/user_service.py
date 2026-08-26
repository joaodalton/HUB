# backend/services/user_service.py
"""
Servicos de usuario:
  create_user, list_users, update_user, delete_user, set_user_active, get_user_by_id
"""

import secrets

from extensions import db
from models.user import User
from services.invitation_service import criar_convite
from services.log_service import LogService
from utils.auth import hash_password


from services.valid_roles import VALID_ROLES


def list_users(empresa_id: int) -> list[dict]:
    users = User.query.filter_by(empresa_id=empresa_id).order_by(User.created_at.desc()).all()
    return [user.to_dict() for user in users]


def get_user_by_id(user_id: int) -> User | None:
    return User.query.get(user_id)


def create_user(data: dict, empresa_id: int, invited_by_id: int | None = None) -> dict:
    """
    Se senha estiver presente, cria o usuario diretamente.
    Se ausente, chama criar_convite (envia email com link de aceite).
    """
    email = (data.get('email') or '').strip().lower()
    nome = (data.get('nome') or '').strip()
    senha = data.get('senha') or ''
    role = data.get('role') or 'viewer'

    if not email or not nome:
        raise ValueError('Nome e email sao obrigatorios.')

    role = role.lower()
    if role not in {'admin', 'operator', 'financial', 'viewer'}:
        raise ValueError('Papel invalido. Use um de: admin, operator, financial, viewer.')

    # Ja existe usuario com esse email?
    existing = User.query.filter(db.func.lower(User.email) == email).first()
    if existing:
        raise ValueError('Ja existe um usuario com esse email (email e unico em toda a base, entre empresas).')

    if senha:
        # -- Criação direta com senha --
        if len(senha) < 6:
            raise ValueError('Senha precisa ter pelo menos 6 caracteres.')

        user = User(
            empresa_id=empresa_id,
            nome=nome,
            email=email,
            password_hash=hash_password(senha),
            role=role,
            status='ativo',
            email_verified=False,
            must_change_password=False,
        )
        db.session.add(user)
        db.session.commit()

        LogService.info(
            acao='create',
            mensagem=f'Usuario {email} criado com papel "{role}"',
            entidade='User',
            metadados={'userId': user.id, 'empresaId': empresa_id},
        )
        return user.to_dict()
    else:
        # -- Convite (sem senha): reutiliza o fluxo existente --
        convite_dict, token_cru = criar_convite(empresa_id, email, role, g.current_user.id)

        # O convite ja enviou o email (ou tentou). Retornamos os dados para
        # o frontend mostrar ao admin.
        return {
            'inviteId': convite_dict['id'],
            'email': email,
            'role': role,
            'message': 'Usuario convidado. Um email foi enviado para ele definir sua senha.',
        }


def update_user(user_id: int, data: dict, empresa_id: int) -> dict | None:
    user = User.query.filter_by(id=user_id, empresa_id=empresa_id).first()
    if not user:
        return None

    if 'nome' in data and data['nome']:
        user.nome = data['nome']
    if 'email' in data and data['email']:
        user.email = data['email'].strip().lower()
    if 'role' in data and data['role']:
        role = data['role'].lower()
        if role not in {'admin', 'operator', 'financial', 'viewer'}:
            raise ValueError('Papel invalido.')
        user.role = role
    db.session.commit()
    return user.to_dict()


def delete_user(user_id: int, empresa_id: int) -> None:
    user = User.query.filter_by(id=user_id, empresa_id=empresa_id).first()
    if not user:
        raise ValueError('Usuario nao encontrado.')
    if user.role == 'owner':
        raise ValueError('Nao e possivel excluir o owner da empresa.')
    db.session.delete(user)
    db.session.commit()
    LogService.info(
        acao='delete',
        mensagem=f'Usuario {user.email} excluido',
        entidade='User',
        metadados={'userId': user.id},
    )


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
        metadados={'userId': user.id},
    )
    return user.to_dict()
