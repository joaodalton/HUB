# backend/services/platform_worker_service.py
"""
CRUD de contas platform_worker (User.is_platform_worker) -- exclusivo de
platform_admin. Paralelo a services/user_service.py mas deliberadamente
nao reaproveita suas funcoes: aquelas sao tenant-scoped (filtradas por
empresa_id) e isto e uma preocupacao global da plataforma.

Workers nao pertencem a nenhuma empresa cliente real -- todos compartilham
uma empresa interna "casca vazia" (criada sob demanda) so para satisfazer
o FK nao-nulo de User.empresa_id.
"""
from extensions import db
from models.empresa import Empresa
from models.user import User
from services.log_service import LogService
from utils.auth import hash_password

INTERNAL_EMPRESA_SLUG = 'plataforma-interna'


def _get_or_create_internal_empresa() -> Empresa:
    empresa = Empresa.query.filter_by(slug=INTERNAL_EMPRESA_SLUG).first()
    if empresa:
        return empresa
    empresa = Empresa(nome='Plataforma (interno)', slug=INTERNAL_EMPRESA_SLUG, status='ativa')
    db.session.add(empresa)
    db.session.commit()
    return empresa


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

    internal_empresa = _get_or_create_internal_empresa()

    worker = User(
        empresa_id=internal_empresa.id,
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
        metadados={'userId': worker.id}
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
        metadados={'userId': worker.id}
    )
    return worker.to_dict()
