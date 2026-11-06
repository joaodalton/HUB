# backend/services/platform_worker_service.py
"""
CRUD de contas platform_worker (User.is_platform_worker) -- exclusivo de
platform_admin. Paralelo a services/user_service.py mas deliberadamente
nao reaproveita suas funcoes: aquelas sao tenant-scoped (filtradas por
empresa_id) e isto e uma preocupacao global da plataforma.

Workers nao pertencem a nenhuma empresa cliente real -- User.empresa_id
fica None.
"""
from extensions import db
from models.user import User
from services.log_service import LogService, NO_EMPRESA
from utils.auth import hash_password


def list_platform_workers() -> list[dict]:
    workers = User.query.filter_by(is_platform_worker=True).order_by(User.created_at.desc()).all()
    return [worker.to_dict() for worker in workers]


def create_platform_worker(data: dict) -> dict:
    email = (data.get('email') or '').strip().lower()
    nome = (data.get('nome') or '').strip()
    senha = data.get('senha') or ''

    if 'is_platform_admin' in data or 'isPlatformAdmin' in data:
        raise ValueError('Campo nao permitido.')

    if not email or not senha or not nome:
        raise ValueError('Nome, email e senha sao obrigatorios.')
    if len(senha) < 6:
        raise ValueError('Senha precisa ter pelo menos 6 caracteres.')

    existing = User.query.filter(db.func.lower(User.email) == email).first()
    if existing:
        raise ValueError('Ja existe um usuario com esse email (email e unico em toda a base, entre empresas).')

    worker = User(
        empresa_id=None,
        nome=nome,
        email=email,
        password_hash=hash_password(senha),
        role='viewer',
        status='ativo',
        email_verified=False,
        must_change_password=True,
        is_platform_worker=True,
    )
    db.session.add(worker)
    db.session.commit()

    LogService.info(
        acao='create',
        mensagem=f'Funcionario da plataforma {email} criado',
        entidade='User',
        metadados={'userId': worker.id},
        empresa_id=NO_EMPRESA,
    )
    return worker.to_dict()


def update_platform_worker(user_id: int, data: dict) -> dict | None:
    worker = User.query.filter_by(id=user_id, is_platform_worker=True).first()
    if not worker:
        return None

    if {'is_platform_admin', 'isPlatformAdmin', 'is_platform_worker', 'isPlatformWorker'} & set(data):
        raise ValueError('Campo nao permitido.')

    if 'nome' in data:
        nome = (data['nome'] or '').strip()
        if not nome:
            raise ValueError('Nome nao pode ser vazio.')
        worker.nome = nome

    if 'email' in data:
        email = (data['email'] or '').strip().lower()
        if not email:
            raise ValueError('Email nao pode ser vazio.')
        existing = User.query.filter(db.func.lower(User.email) == email, User.id != worker.id).first()
        if existing:
            raise ValueError('Ja existe um usuario com esse email (email e unico em toda a base, entre empresas).')
        worker.email = email

    if 'senha' in data:
        senha = data['senha'] or ''
        if len(senha) < 6:
            raise ValueError('Senha precisa ter pelo menos 6 caracteres.')
        worker.password_hash = hash_password(senha)
        worker.session_version += 1

    db.session.commit()

    LogService.info(
        acao='update',
        mensagem=f'Funcionario da plataforma {worker.email} atualizado',
        entidade='User',
        metadados={'userId': worker.id},
        empresa_id=worker.empresa_id if worker.empresa_id is not None else NO_EMPRESA,
    )
    return worker.to_dict()


def revoke_platform_worker(user_id: int) -> dict | None:
    worker = User.query.filter_by(id=user_id, is_platform_worker=True).first()
    if not worker:
        return None

    worker.is_platform_worker = False
    worker.status = 'inativo'
    worker.session_version += 1
    db.session.commit()

    LogService.info(
        acao='delete',
        mensagem=f'Funcionario da plataforma {worker.email} revogado',
        entidade='User',
        metadados={'userId': worker.id},
        empresa_id=worker.empresa_id if worker.empresa_id is not None else NO_EMPRESA,
    )
    return worker.to_dict()
