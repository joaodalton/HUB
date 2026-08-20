# backend/services/empresa_service.py
"""
Servico para criar Empresa + Owner em uma unica transacao.
Usado no fluxo de cadastro inicial.
"""
import re
import secrets

from sqlalchemy.exc import IntegrityError
from extensions import db
from models.empresa import Empresa
from models.user import User
from services.log_service import LogService
from utils.auth import hash_password


def gerar_slug(nome: str) -> str:
    """Gera um slug simples a partir do nome da empresa."""
    slug = re.sub(r'[^a-zA-Z0-9\s-]', '', nome.lower())
    slug = re.sub(r'[\s-]+', '-', slug).strip('-')
    # Adiciona um sufixo aleatorio para garantir unicidade
    sufixo = secrets.token_hex(2)
    return f'{slug}-{sufixo}'


def criar_empresa_com_owner(data: dict) -> dict:
    """
    Cria Empresa + Owner na mesma transacao.

    Args:
        data: {
            'empresa': {
                'nome': str (obrigatorio),
                'razao_social': str (opcional),
                'cnpj': str (opcional),
                'email': str (opcional),
                'telefone': str (opcional),
            },
            'owner': {
                'nome': str (obrigatorio),
                'email': str (obrigatorio),
                'senha': str (obrigatorio, min 6 chars),
            }
        }

    Returns:
        dict com 'empresa' e 'owner'

    Raises:
        ValueError se dados invalidos
    """
    empresa_data = data.get('empresa', {})
    owner_data = data.get('owner', {})

    # Validacoes da empresa
    nome = (empresa_data.get('nome') or '').strip()
    if not nome:
        raise ValueError('Nome da empresa e obrigatorio.')

    # Validacoes do owner
    owner_nome = (owner_data.get('nome') or '').strip()
    owner_email = (owner_data.get('email') or '').strip().lower()
    owner_senha = owner_data.get('senha') or ''

    if not owner_nome:
        raise ValueError('Nome do responsavel e obrigatorio.')
    if not owner_email:
        raise ValueError('Email do responsavel e obrigatorio.')
    if not owner_senha:
        raise ValueError('Senha e obrigatoria.')
    if len(owner_senha) < 6:
        raise ValueError('Senha precisa ter pelo menos 6 caracteres.')

    # Verifica se email ja existe
    existing_user = User.query.filter(db.func.lower(User.email) == owner_email).first()
    if existing_user:
        raise ValueError('Ja existe um usuario com esse email no sistema.')

    # Gera slug unico
    slug = gerar_slug(nome)
    attempts = 0
    while Empresa.query.filter_by(slug=slug).first() and attempts < 10:
        slug = gerar_slug(nome)
        attempts += 1

    if Empresa.query.filter_by(slug=slug).first():
        raise ValueError('Nao foi possivel criar um slug unico para a empresa.')

    try:
        # Cria empresa
        empresa = Empresa(
            nome=nome,
            razao_social=empresa_data.get('razao_social') or None,
            cnpj=empresa_data.get('cnpj') or None,
            email=empresa_data.get('email') or None,
            telefone=empresa_data.get('telefone') or None,
            status='ativa',
            slug=slug
        )
        db.session.add(empresa)
        db.session.flush()  # Obtem o ID da empresa antes de criar o user

        # Cria owner
        owner = User(
            empresa_id=empresa.id,
            nome=owner_nome,
            email=owner_email,
            password_hash=hash_password(owner_senha),
            role='owner',
            status='ativo',
            email_verified=False,
            must_change_password=False  # Owner definiu sua propria senha
        )
        db.session.add(owner)
        db.session.flush()

        db.session.commit()

        LogService.info(
            acao='create',
            mensagem=f'Empresa {nome} criada com owner {owner_email}',
            entidade='Empresa',
            metadados={'empresaId': empresa.id, 'ownerId': owner.id}
        )

        return {
            'empresa': empresa.to_dict(),
            'owner': owner.to_dict()
        }

    except IntegrityError as exc:
        db.session.rollback()
        raise ValueError('Não foi possível criar a empresa: dado duplicado (slug ou e-mail já em uso).') from exc
