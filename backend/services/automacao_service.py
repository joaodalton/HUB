# backend/services/automacao_service.py
"""
Motor de automação de pendências do HUB.

Este serviço implementa as regras automáticas descritas em PENDENCIAS.md:
- UC sem usina vinculada há 7 dias
- Cliente sem UC cadastrada
- Campos obrigatórios faltando no cliente
- Documentos obrigatórios faltando

As verificações são executadas sob demanda (ao abrir a tela de Pendências
ou via botão "Verificar agora"), sem necessidade de scheduler.
"""
from datetime import datetime, timedelta

from flask import g
from sqlalchemy.exc import IntegrityError

from extensions import db
from models.client import Client
from models.consumer_unit import ConsumerUnit, PlantConnection
from models.document import Document
from models.pendencia import Pendencia
from models.plant import Plant
from services.log_service import LogService
from services.pendencia_service import criar_alerta, criar_erro


# Documentos obrigatórios por cliente (nomes parciais para busca case-insensitive)
DOCUMENTOS_OBRIGATORIOS = [
    'identidade',
    'cpf',
    'rg',
    'fatura',
    'termo',
    'contrato',
]

# Prazo em dias para UC ficar sem usina antes de gerar alerta
PRAZO_DIAS_SEM_USINA = 7


# Chave estruturada de cada regra automatica. Fica em Pendencia.metadados['regra']
# e e o que a deduplicacao e a auto-resolucao usam -- antes dependiam do texto
# do titulo (`ilike('%sem usina%')`): renomear a mensagem desligava a regra.
# Pendencias legadas (sem 'regra') continuam reconhecidas pelo titulo.
REGRA_UC_SEM_USINA = 'uc_sem_usina'
REGRA_CLIENTE_SEM_UC = 'cliente_sem_uc'
REGRA_CAMPOS_OBRIGATORIOS = 'campos_obrigatorios'
REGRA_DOCUMENTOS_OBRIGATORIOS = 'documentos_obrigatorios'
REGRA_FATURA_GERACAO_USINA = 'fatura_geracao_usina'
_TITULO_LEGADO = {
    REGRA_UC_SEM_USINA: 'sem usina',
    REGRA_CLIENTE_SEM_UC: 'sem uc',
    REGRA_CAMPOS_OBRIGATORIOS: 'falta ',
    REGRA_DOCUMENTOS_OBRIGATORIOS: 'falta documento',
}


def _regra_de(pendencia: Pendencia) -> str | None:
    metadados = pendencia.metadados or {}
    regra = metadados.get('regra') if isinstance(metadados, dict) else None
    if regra:
        return regra
    titulo = (pendencia.titulo or '').lower()
    # Ordem importa: 'falta documento' e mais especifico que 'falta '
    for chave in (REGRA_DOCUMENTOS_OBRIGATORIOS, REGRA_CAMPOS_OBRIGATORIOS, REGRA_UC_SEM_USINA, REGRA_CLIENTE_SEM_UC):
        if _TITULO_LEGADO[chave] in titulo:
            return chave
    return None


def _pendencias_abertas_por_regra() -> dict[str, list[Pendencia]]:
    """Uma query para todas as pendencias abertas de automacao, agrupadas por regra."""
    abertas = Pendencia.query.filter(Pendencia.status == 'aberta').all()
    grupos: dict[str, list[Pendencia]] = {}
    for pendencia in abertas:
        regra = _regra_de(pendencia)
        if regra:
            grupos.setdefault(regra, []).append(pendencia)
    return grupos


def verificar_e_criar_pendencias():
    """
    Executa todas as verificações automáticas e cria pendências/alertas/erros
    conforme necessário. Chamado pela tela de Pendências (sincronização automática)
    e pelo botão "Verificar agora".

    Retorna um dict com a contagem de cada tipo de verificação realizada.
    """
    resultado = {
        'ucs_sem_usina': 0,
        'clientes_sem_uc': 0,
        'campos_faltando': 0,
        'documentos_faltando': 0,
        'fatura_geracao_usina': 0,
    }

    # 1. UC sem usina vinculada
    resultado['ucs_sem_usina'] = _verificar_ucs_sem_usina()

    # 2. Cliente sem UC
    resultado['clientes_sem_uc'] = _verificar_clientes_sem_uc()

    # 3. Campos obrigatórios faltando
    resultado['campos_faltando'] = _verificar_campos_obrigatorios()

    # 4. Documentos obrigatórios faltando
    resultado['documentos_faltando'] = _verificar_documentos_obrigatorios()

    # 5. Fatura de geracao da usina a partir do dia de emissao configurado
    resultado['fatura_geracao_usina'] = _verificar_fatura_geracao_usina()

    LogService.info(
        acao='automacao',
        mensagem=f'Verificacao automatica concluida: {resultado}',
        entidade='Pendencia'
    )

    return resultado


def _verificar_ucs_sem_usina() -> int:
    """
    Para cada UC vinculada a um cliente com cadastro completo e documentos OK,
    cria um alerta se não tiver conexão a usina há mais de 7 dias.

    Cadastro completo = todos os campos obrigatórios preenchidos.
    """
    criados = 0
    hoje = datetime.utcnow().date()
    prazo = hoje - timedelta(days=PRAZO_DIAS_SEM_USINA)

    # Busca UCs que não têm conexão com usina
    ucs_sem_conexao = ConsumerUnit.query.outerjoin(
        PlantConnection,
        PlantConnection.consumer_unit_id == ConsumerUnit.id
    ).filter(
        PlantConnection.id.is_(None)
    ).all()

    for uc in ucs_sem_conexao:
        # Só cria se o cliente existir e estiver ativo
        if not uc.client:
            continue

        cliente = uc.client

        # Verifica se o cliente tem cadastro completo
        if not _cliente_cadastro_completo(cliente):
            continue

        # Verifica se tem documentos obrigatórios
        if not _cliente_tem_documentos_obrigatorios(cliente.id):
            continue

        # Verifica se já existe pendência aberta para esta UC
        if _ja_existe_pendencia_ativa(uc_id=uc.id, regra=REGRA_UC_SEM_USINA):
            continue

        inicio_sem_usina = uc.sem_usina_desde or uc.created_at
        dias_sem_usina = (datetime.utcnow().date() - inicio_sem_usina.date()).days

        if dias_sem_usina >= PRAZO_DIAS_SEM_USINA:
            criar_alerta({
                'categoria': 'Usinas',
                'titulo': f'UC {uc.codigo} sem usina vinculada há {dias_sem_usina} dias',
                'descricao': (
                    f'A Unidade Consumidora {uc.codigo} ({uc.apelido or "sem apelido"}) '
                    f'está vinculada ao cliente {cliente.nome}, mas não possui conexão '
                    f'com nenhuma usina há {dias_sem_usina} dias.'
                ),
                'clienteId': cliente.id,
                'ucId': uc.id,
                'prioridade': 'alta',
                'metadados': {
                    'regra': REGRA_UC_SEM_USINA,
                    'diasSemUsina': dias_sem_usina,
                    'semUsinaDesde': inicio_sem_usina.isoformat(),
                }
            })
            criados += 1

    return criados

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


def _verificar_fatura_geracao_usina() -> int:
    """
    Para cada usina com dia de emissao configurado, cria uma pendencia de
    buscar a fatura de geracao assim que o dia do mes corrente alcancar o
    dia de emissao. Idempotente por competencia via constraint unica
    (empresa_id, plant_id, origem, competencia).
    """
    criados = 0
    hoje = datetime.utcnow().date()
    competencia = hoje.strftime('%Y-%m')

    usinas = Plant.query.filter(Plant.dia_emissao_usina.isnot(None)).all()

    for plant in usinas:
        if hoje.day < plant.dia_emissao_usina:
            continue

        try:
            with db.session.begin_nested():
                db.session.add(Pendencia(
                    empresa_id=plant.empresa_id,
                    categoria='Usinas',
                    origem=REGRA_FATURA_GERACAO_USINA,
                    plant_id=plant.id,
                    competencia=competencia,
                    titulo=f'Buscar fatura de geracao da usina {plant.nome} ({competencia})',
                    descricao=(
                        f'A usina {plant.nome} atingiu o dia de emissao configurado '
                        f'({plant.dia_emissao_usina}); buscar fatura de geracao da '
                        f'competencia {competencia}.'
                    ),
                    prioridade='alta',
                ))
                db.session.flush()
            criados += 1
        except IntegrityError:
            pass

    if criados > 0:
        db.session.commit()

    return criados


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


def _ja_existe_pendencia_ativa(
    cliente_id: int = None,
    uc_id: int = None,
    regra: str = None
) -> bool:
    """
    Verifica se já existe uma pendência/alerta/erro ativa (não resolvida, não cancelada)
    para o cliente ou UC especificada, opcionalmente da mesma regra automática.
    """
    query = Pendencia.query.filter(
        Pendencia.status == 'aberta'
    )

    if cliente_id:
        query = query.filter(Pendencia.client_id == cliente_id)
    if uc_id:
        query = query.filter(Pendencia.consumer_unit_id == uc_id)

    pendencias = query.all()

    if not regra:
        return len(pendencias) > 0

    return any(_regra_de(p) == regra for p in pendencias)


def criar_pendencia_alerta(data: dict) -> dict:
    """Cria uma pendência do tipo 'pendencia' (não alerta automático)."""
    from services.pendencia_service import criar_pendencia_manual
    return criar_pendencia_manual({
        **data,
        'origem': 'Automacao'
    })


def resolver_pendencias_resolvidas():
    """
    Verifica pendências que devem ser resolvidas automaticamente:
    - UC sem usina: se ganhou conexão com usina
    - Campos faltando: se foram preenchidos
    - Documentos faltando: se foram adicionados
    """
    resolvidas = 0
    por_regra = _pendencias_abertas_por_regra()

    # 1. UC sem usina - resolve se agora tem conexão
    for pendencia in por_regra.get(REGRA_UC_SEM_USINA, []):
        if not pendencia.consumer_unit_id:
            continue

        uc = ConsumerUnit.query.filter_by(
            id=pendencia.consumer_unit_id, empresa_id=g.current_empresa_id
        ).first()
        if not uc:
            continue

        # Verifica se tem conexão ativa com alguma usina
        conexoes_ativas = [
            c for c in uc.conexoes
            if c.plant_id is not None
        ]

        if conexoes_ativas:
            pendencia.status = 'resolvida'
            pendencia.resolved_at = datetime.utcnow()
            LogService.info(
                acao='auto_resolver',
                mensagem=f'Pendencia "{pendencia.titulo}" resolvida automaticamente (UC now tem usina)',
                entidade='Pendencia',
                entidade_id=pendencia.id
            )
            resolvidas += 1

    # 2. Campos faltando - resolve se foram preenchidos
    for pendencia in por_regra.get(REGRA_CAMPOS_OBRIGATORIOS, []):
        if not pendencia.client_id:
            continue

        cliente = Client.query.filter_by(
            id=pendencia.client_id, empresa_id=g.current_empresa_id
        ).first()
        if not cliente:
            continue

        # Verifica se todos os campos estão preenchidos agora
        campos_ok = (
            cliente.nome and cliente.nome.strip() and
            cliente.cpf and cliente.cpf.strip() and
            cliente.email and cliente.email.strip() and
            cliente.telefone and cliente.telefone.strip() and
            cliente.data_nascimento is not None
        )

        if campos_ok:
            pendencia.status = 'resolvida'
            pendencia.resolved_at = datetime.utcnow()
            LogService.info(
                acao='auto_resolver',
                mensagem=f'Pendencia "{pendencia.titulo}" resolvida automaticamente (campos preenchidos)',
                entidade='Pendencia',
                entidade_id=pendencia.id
            )
            resolvidas += 1

    # 3. Cliente sem UC - resolve se ganhou UC
    for pendencia in por_regra.get(REGRA_CLIENTE_SEM_UC, []):
        if not pendencia.client_id:
            continue

        cliente = Client.query.filter_by(
            id=pendencia.client_id, empresa_id=g.current_empresa_id
        ).first()
        if not cliente:
            continue

        if cliente.ucs and len(cliente.ucs) > 0:
            pendencia.status = 'resolvida'
            pendencia.resolved_at = datetime.utcnow()
            LogService.info(
                acao='auto_resolver',
                mensagem=f'Pendencia "{pendencia.titulo}" resolvida automaticamente (cliente ganhou UC)',
                entidade='Pendencia',
                entidade_id=pendencia.id
            )
            resolvidas += 1

    if resolvidas > 0:
        db.session.commit()

    return resolvidas
