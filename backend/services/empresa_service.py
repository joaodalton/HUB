# backend/services/empresa_service.py
"""
Servico para criar Empresa + Owner em uma unica transacao.
Usado no fluxo de cadastro inicial.
"""
import re
import secrets
from contextlib import contextmanager

from flask import g

from sqlalchemy.exc import IntegrityError
from extensions import db
from models.agenda_event import AgendaEvent
from models.api_credential import ApiCredential
from models.assinatura import Assinatura
from models.calculo_cobranca import BillingCalculationExecution, BillingCalculationSnapshot
from models.client import Client
from models.consumer_unit import ConsumerUnit, PlantConnection
from models.document import Document
from models.empresa import Empresa
from models.fatura import Fatura
from models.fatura_concessionaria import FaturaConcessionaria
from models.google_account import GoogleAccount
from models.grupo_regra_cobranca import GrupoRegraCobranca
from models.import_preview import ImportPreview
from models.invitation import Invitation
from models.limite_contratado import LimiteContratado
from models.log_entry import LogEntry
from models.message_template import MessageTemplate
from models.payment_webhook_event import PaymentWebhookEvent
from models.pendencia import Pendencia, PendenciaComentario
from models.plant import Plant
from models.rateio_historico import RateioHistorico
from models.regra_cobranca_assignment import RegraCobrancaAssignment
from models.setting import Setting
from models.user import User
from models.whatsapp import WhatsappConversation, WhatsappIntegration, WhatsappMessage
from services.log_service import NO_EMPRESA, LogService
from utils.auth import hash_password


# Models cuja presenca de registros bloqueia a exclusao da empresa (dados
# reais inseridos pelo tenant). Nao inclui MessageTemplate/Setting/LogEntry:
# sao seedados ou gravados automaticamente (ex.: seed_for_empresa na criacao,
# estado de OAuth em Setting) e bloqueariam a exclusao de qualquer empresa,
# mesmo uma nunca usada de fato.
_MODELOS_BLOQUEIO_EXCLUSAO = (
    (Client, 'clientes'),
    (ConsumerUnit, 'unidades consumidoras'),
    (PlantConnection, 'conexoes de usina'),
    (Plant, 'usinas'),
    (Document, 'documentos'),
    (Pendencia, 'pendencias'),
    (PendenciaComentario, 'comentarios de pendencia'),
    (User, 'usuarios'),
    (Invitation, 'convites'),
    (Assinatura, 'assinatura'),
    (LimiteContratado, 'limites contratados'),
    (AgendaEvent, 'eventos de agenda'),
    (ApiCredential, 'credenciais de API'),
    (Fatura, 'faturas'),
    (FaturaConcessionaria, 'faturas de concessionaria'),
    (GoogleAccount, 'contas Google'),
    (GrupoRegraCobranca, 'grupos de regra de cobranca'),
    (ImportPreview, 'importacoes pendentes'),
    (BillingCalculationSnapshot, 'calculos de cobranca'),
    (BillingCalculationExecution, 'execucoes de calculo'),
    (PaymentWebhookEvent, 'eventos de pagamento'),
    (RegraCobrancaAssignment, 'atribuicoes de regra de cobranca'),
    (RateioHistorico, 'historico de rateio'),
    (WhatsappIntegration, 'integracoes WhatsApp'),
    (WhatsappConversation, 'conversas WhatsApp'),
    (WhatsappMessage, 'mensagens WhatsApp'),
)


@contextmanager
def _sem_filtro_de_tenant_ambiente():
    """As queries de exclusao de empresa miram um empresa_id explicito,
    qualquer que seja a empresa que o platform_admin esteja "visualizando"
    no momento (cookie hub_platform_view). Sem isso, o filtro automatico de
    tenant (extensions.py) combinaria os dois empresa_id com AND e sempre
    daria "vazio", mascarando dados reais de uma empresa diferente da
    visualizada."""
    anterior = getattr(g, 'current_empresa_id', None)
    g.current_empresa_id = None
    try:
        yield
    finally:
        g.current_empresa_id = anterior


def encontrar_dados_vinculados(empresa_id: int) -> str | None:
    """Retorna o rotulo da primeira tabela com registros vinculados a
    empresa, ou None se a empresa estiver vazia."""
    with _sem_filtro_de_tenant_ambiente():
        for modelo, rotulo in _MODELOS_BLOQUEIO_EXCLUSAO:
            existe = db.session.query(modelo.query.filter_by(empresa_id=empresa_id).exists()).scalar()
            if existe:
                return rotulo
    return None


def excluir_empresa(empresa_id: int) -> bool:
    """Exclui uma empresa vazia (sem nenhum dado vinculado). Retorna False se
    a empresa nao existir, levanta ValueError se houver dados vinculados.

    MessageTemplate e Setting sao config auxiliar seedada/gravada
    automaticamente (nao contam como "dado da empresa" na checagem acima) mas
    tem FK NOT NULL pra empresas, entao precisam ser removidos aqui pra nao
    violar a constraint ao excluir a empresa. LogEntry (auditoria) e
    preservado: so desvincula o empresa_id (fica NULL) em vez de apagar o
    historico.
    """
    empresa = Empresa.query.get(empresa_id)
    if not empresa:
        return False

    rotulo = encontrar_dados_vinculados(empresa_id)
    if rotulo:
        raise ValueError(f'Empresa possui dados vinculados ({rotulo}) e nao pode ser excluida.')

    nome = empresa.nome
    with _sem_filtro_de_tenant_ambiente():
        MessageTemplate.query.filter_by(empresa_id=empresa_id).delete()
        Setting.query.filter_by(empresa_id=empresa_id).delete()
        LogEntry.query.filter_by(empresa_id=empresa_id).update({'empresa_id': None})
        db.session.delete(empresa)
        db.session.commit()

    LogService.info(
        acao='empresa_deleted',
        mensagem=f'Empresa {nome} excluida pela plataforma.',
        entidade='Empresa',
        entidade_id=empresa_id,
        metadados={'empresaIdExcluida': empresa_id, 'nome': nome},
        empresa_id=NO_EMPRESA,
        strict=True,
    )
    return True


_EMPRESA_PROFILE_FIELDS = frozenset({'nome', 'razaoSocial', 'cnpj', 'email', 'telefone'})
_CNPJ_DIGITS = re.compile(r'\D')
_EMAIL_PATTERN = re.compile(r'^[^\s@]+@[^\s@]+\.[^\s@]+$')


def _empresa_profile_dict(empresa: Empresa) -> dict:
    """Contrato de perfil; não inclui slug, status ou identificadores internos."""
    return {
        'nome': empresa.nome,
        'razaoSocial': empresa.razao_social,
        'cnpj': empresa.cnpj,
        'email': empresa.email,
        'telefone': empresa.telefone,
    }


def get_empresa_atual() -> dict | None:
    empresa = Empresa.query.filter_by(id=g.current_empresa_id).first()
    return _empresa_profile_dict(empresa) if empresa else None


def update_empresa_atual(data: dict) -> dict | None:
    campos_enviados = set(data)
    desconhecidos = campos_enviados - _EMPRESA_PROFILE_FIELDS
    if desconhecidos:
        raise ValueError('Campos nao permitidos para atualizacao da empresa.')
    if not campos_enviados:
        raise ValueError('Informe ao menos um campo para atualizar.')

    empresa = Empresa.query.filter_by(id=g.current_empresa_id).first()
    if not empresa:
        return None

    if 'nome' in data:
        nome = _validar_texto(data['nome'], 'Nome', 150, obrigatorio=True)
        empresa.nome = nome
    if 'razaoSocial' in data:
        empresa.razao_social = _validar_texto(data['razaoSocial'], 'Razao social', 200)
    if 'cnpj' in data:
        empresa.cnpj = _validar_cnpj(data['cnpj'])
    if 'email' in data:
        empresa.email = _validar_email(data['email'])
    if 'telefone' in data:
        empresa.telefone = _validar_texto(data['telefone'], 'Telefone', 20)

    db.session.commit()
    LogService.info(
        acao='empresa_profile_update',
        mensagem='Dados cadastrais da empresa atualizados',
        entidade='Empresa',
        entidade_id=empresa.id,
        metadados={'campos': sorted(campos_enviados)},
    )
    return _empresa_profile_dict(empresa)


def update_empresa_platform(empresa_id: int, data: dict) -> dict | None:
    allowed = _EMPRESA_PROFILE_FIELDS | {'status'}
    if not data or set(data) - allowed:
        raise ValueError('Campos nao permitidos para atualizacao da empresa.')
    empresa = Empresa.query.filter_by(id=empresa_id).first()
    if not empresa:
        return None
    if 'nome' in data:
        empresa.nome = _validar_texto(data['nome'], 'Nome', 150, obrigatorio=True)
    if 'razaoSocial' in data:
        empresa.razao_social = _validar_texto(data['razaoSocial'], 'Razao social', 200)
    if 'cnpj' in data:
        empresa.cnpj = _validar_cnpj(data['cnpj'])
    if 'email' in data:
        empresa.email = _validar_email(data['email'])
    if 'telefone' in data:
        empresa.telefone = _validar_texto(data['telefone'], 'Telefone', 20)
    if 'status' in data:
        if data['status'] not in ('ativa', 'inativa', 'suspensa'):
            raise ValueError('Status invalido.')
        empresa.status = data['status']
    db.session.commit()
    LogService.info(acao='empresa_platform_update', mensagem=f'Empresa {empresa.id} atualizada pela plataforma', entidade='Empresa', entidade_id=empresa.id, metadados={'campos': sorted(data)})
    return empresa.to_dict()


def _validar_texto(valor, campo: str, limite: int, *, obrigatorio: bool = False) -> str | None:
    if valor is None:
        if obrigatorio:
            raise ValueError(f'{campo} e obrigatorio.')
        return None
    if not isinstance(valor, str):
        raise ValueError(f'{campo} deve ser texto.')
    resultado = valor.strip()
    if obrigatorio and not resultado:
        raise ValueError(f'{campo} e obrigatorio.')
    if len(resultado) > limite:
        raise ValueError(f'{campo} excede o tamanho permitido.')
    return resultado or None


def _validar_cnpj(valor) -> str | None:
    texto = _validar_texto(valor, 'CNPJ', 20)
    if texto is None:
        return None
    digitos = _CNPJ_DIGITS.sub('', texto)
    if len(digitos) != 14:
        raise ValueError('CNPJ deve conter 14 digitos.')
    return digitos


def _validar_email(valor) -> str | None:
    email = _validar_texto(valor, 'Email', 150)
    if email is not None and not _EMAIL_PATTERN.fullmatch(email):
        raise ValueError('Email invalido.')
    return email.lower() if email else None


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
        # Defaults globais existem antes da transação do novo tenant; as cópias
        # tenant-scoped abaixo entram no mesmo commit da empresa/owner.
        from services.email_template_service import ensure_seeded
        from services.message_template_service import seed_for_empresa
        ensure_seeded()
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
        seed_for_empresa(empresa.id, commit=False)

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


# --- Documentos fixos (CNPJ / Estatuto) usados na geracao do formulario Copel ---

TIPOS_DOCUMENTO_EMPRESA = {
    'cnpj': ('documento_cnpj_id', 'Cartão CNPJ'),
    'estatuto': ('documento_estatuto_id', 'Estatuto da associação')
}


def get_empresa_documentos(empresa_id: int) -> dict:
    empresa = Empresa.query.get(empresa_id)
    if not empresa:
        raise ValueError('Empresa não encontrada.')

    return {
        'cnpj': empresa.documento_cnpj.to_dict() if empresa.documento_cnpj else None,
        'estatuto': empresa.documento_estatuto.to_dict() if empresa.documento_estatuto else None
    }


def set_empresa_documento(empresa_id: int, tipo: str, file_storage) -> dict:
    """Faz upload do arquivo (CNPJ ou Estatuto) e substitui o documento atual
    daquele tipo. O documento anterior (se houver) e excluido em seguida, pra
    nao acumular lixo na lista de Documentos -- mesma logica de 'trocar' que
    a tela de Aparencia ja usa pro logo, so que aqui persiste via Document
    (Drive) em vez de base64 direto no Setting."""
    if tipo not in TIPOS_DOCUMENTO_EMPRESA:
        raise ValueError('Tipo de documento inválido. Use "cnpj" ou "estatuto".')

    campo_id, nome_padrao = TIPOS_DOCUMENTO_EMPRESA[tipo]

    empresa = Empresa.query.get(empresa_id)
    if not empresa:
        raise ValueError('Empresa não encontrada.')

    documento_anterior_id = getattr(empresa, campo_id)

    # import tardio: evita ciclo (document_service nao precisa saber de empresa_service)
    from services.document_service import create_document, delete_document

    novo_documento = create_document({'nome': nome_padrao}, file_storage)

    setattr(empresa, campo_id, novo_documento['id'])
    db.session.commit()

    if documento_anterior_id:
        delete_document(documento_anterior_id)

    LogService.info(
        acao='update',
        mensagem=f'Documento "{nome_padrao}" atualizado para a empresa {empresa.nome}',
        entidade='Empresa',
        metadados={'empresaId': empresa.id, 'tipo': tipo, 'documentoId': novo_documento['id']}
    )

    return get_empresa_documentos(empresa_id)
