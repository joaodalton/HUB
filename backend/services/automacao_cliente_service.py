# backend/services/automacao_cliente_service.py
"""
Regras de automacao de pendencias relacionadas a cadastro de cliente:
cliente sem UC, campos obrigatorios faltando e documentos obrigatorios
faltando.

Extraido de automacao_service.py (split por responsabilidade, sem mudanca de
comportamento). Ver automacao_service.py para a orquestracao principal.
"""
from models.client import Client
from models.document import Document
from services.automacao_regras import (
    REGRA_CAMPOS_OBRIGATORIOS,
    REGRA_CLIENTE_SEM_UC,
    REGRA_DOCUMENTOS_OBRIGATORIOS,
    _ja_existe_pendencia_ativa,
)

# Documentos obrigatórios por cliente (nomes parciais para busca case-insensitive)
DOCUMENTOS_OBRIGATORIOS = [
    'identidade',
    'cpf',
    'rg',
    'fatura',
    'termo',
    'contrato',
]


def criar_pendencia_alerta(data: dict) -> dict:
    """Cria uma pendência do tipo 'pendencia' (não alerta automático)."""
    from services.pendencia_service import criar_pendencia_manual
    return criar_pendencia_manual({
        **data,
        'origem': 'Automacao'
    })


def _cliente_cadastro_completo(cliente: Client) -> bool:
    """Verifica se o cliente tem todos os campos obrigatórios preenchidos."""
    if not cliente.nome or not cliente.nome.strip():
        return False
    if not cliente.cpf or not cliente.cpf.strip():
        return False
    if not cliente.email or not cliente.email.strip():
        return False
    if not cliente.telefone or not cliente.telefone.strip():
        return False
    if not cliente.data_nascimento:
        return False
    return True


def _cliente_tem_documentos_obrigatorios(cliente_id: int) -> bool:
    """Verifica se o cliente tem pelo menos alguns documentos."""
    documentos = Document.query.filter_by(client_id=cliente_id).all()
    return len(documentos) > 0


def _verificar_clientes_sem_uc() -> int:
    """
    Para cada cliente que não possui UC vinculada, cria uma pendência de alta prioridade.
    """
    criados = 0

    clientes = Client.query.all()

    for cliente in clientes:
        # Verifica se tem pelo menos uma UC
        if cliente.ucs and len(cliente.ucs) > 0:
            continue

        # Verifica se já existe pendência aberta para este cliente
        if _ja_existe_pendencia_ativa(cliente_id=cliente.id, regra=REGRA_CLIENTE_SEM_UC):
            continue

        criar_pendencia_alerta({
            'categoria': 'UCs',
            'metadados': {'regra': REGRA_CLIENTE_SEM_UC},
            'titulo': f'Cliente {cliente.nome} sem UC cadastrada',
            'descricao': (
                f'O cliente {cliente.nome} foi criado, porém ainda não possui '
                f'Unidade Consumidora vinculada.'
            ),
            'clienteId': cliente.id,
            'prioridade': 'alta',
        })
        criados += 1

    return criados


def _verificar_campos_obrigatorios() -> int:
    """
    Verifica campos obrigatórios faltando no cliente:
    Nome, CPF, Email, Telefone, Data de nascimento.
    """
    criados = 0

    clientes = Client.query.all()

    for cliente in clientes:
        campos_faltando = []

        # Verifica cada campo obrigatório
        if not cliente.nome or not cliente.nome.strip():
            campos_faltando.append('nome')
        if not cliente.cpf or not cliente.cpf.strip():
            campos_faltando.append('CPF')
        if not cliente.email or not cliente.email.strip():
            campos_faltando.append('e-mail')
        if not cliente.telefone or not cliente.telefone.strip():
            campos_faltando.append('telefone')
        if not cliente.data_nascimento:
            campos_faltando.append('data de nascimento')

        if not campos_faltando:
            continue

        # Verifica se já existe pendência aberta para este cliente + campos
        if _ja_existe_pendencia_ativa(cliente_id=cliente.id, regra=REGRA_CAMPOS_OBRIGATORIOS):
            continue

        campos_str = ', '.join(campos_faltando)
        criar_pendencia_alerta({
            'categoria': 'UCs',
            'titulo': f'Falta {campos_str} do cliente {cliente.nome}',
            'descricao': (
                f'O cliente {cliente.nome} está com os seguintes campos obrigatórios '
                f'pendentes de preenchimento: {campos_str}.'
            ),
            'clienteId': cliente.id,
            'prioridade': 'alta',
            'metadados': {
                'regra': REGRA_CAMPOS_OBRIGATORIOS,
                'camposFaltando': campos_faltando,
            }
        })
        criados += 1

    return criados


def _verificar_documentos_obrigatorios() -> int:
    """
    Verifica se o cliente possui os documentos obrigatórios:
    Documento de identidade, Fatura, Termo de adesão.
    """
    criados = 0

    clientes = Client.query.all()

    for cliente in clientes:
        documentos_cliente = [d.nome.lower() for d in cliente.documentos]
        documentos_faltando = []

        for doc_obrigatorio in DOCUMENTOS_OBRIGATORIOS:
            encontrado = any(doc_obrigatorio in doc for doc in documentos_cliente)
            if not encontrado:
                # Nome amigável para exibição
                nome_exibicao = {
                    'identidade': 'Documento de identidade',
                    'cpf': 'CPF',
                    'rg': 'RG',
                    'fatura': 'Fatura',
                    'termo': 'Termo de adesão',
                    'contrato': 'Contrato',
                }.get(doc_obrigatorio, doc_obrigatorio)
                documentos_faltando.append(nome_exibicao)

        if not documentos_faltando:
            continue

        # Verifica se já existe pendência aberta para este cliente + documentos
        if _ja_existe_pendencia_ativa(cliente_id=cliente.id, regra=REGRA_DOCUMENTOS_OBRIGATORIOS):
            continue

        docs_str = ', '.join(documentos_faltando)
        criar_pendencia_alerta({
            'categoria': 'Documentos',
            'titulo': f'Falta documento obrigatório do cliente {cliente.nome}',
            'descricao': (
                f'O cliente {cliente.nome} está com os seguintes documentos '
                f'obrigatórios pendentes: {docs_str}.'
            ),
            'clienteId': cliente.id,
            'prioridade': 'alta',
            'metadados': {
                'regra': REGRA_DOCUMENTOS_OBRIGATORIOS,
                'documentosFaltando': documentos_faltando,
            }
        })
        criados += 1

    return criados
