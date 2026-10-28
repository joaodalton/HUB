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

As regras de cliente/UC/documento (sem dependência de data) vivem em
automacao_cliente_service.py; a deduplicação e chaves de regra vivem em
automacao_regras.py. Este arquivo mantém a orquestração e as regras que
dependem da data corrente (datetime.utcnow()), reexportando os nomes
públicos para preservar o import `from services.automacao_service import ...`
usado pelo resto do projeto e pelos testes.
"""
import calendar
from datetime import datetime, timedelta

from flask import g
from sqlalchemy.exc import IntegrityError

from extensions import db
from models.client import Client
from models.consumer_unit import ConsumerUnit, PlantConnection
from models.fatura import Fatura
from models.pendencia import Pendencia
from models.plant import Plant
from services.automacao_cliente_service import (  # noqa: F401 (reexport)
    DOCUMENTOS_OBRIGATORIOS,
    criar_pendencia_alerta,
    _cliente_cadastro_completo,
    _cliente_tem_documentos_obrigatorios,
    _verificar_campos_obrigatorios,
    _verificar_clientes_sem_uc,
    _verificar_documentos_obrigatorios,
)
from services.automacao_regras import (  # noqa: F401 (reexport)
    REGRA_CAMPOS_OBRIGATORIOS,
    REGRA_CLIENTE_SEM_UC,
    REGRA_DOCUMENTOS_OBRIGATORIOS,
    REGRA_FATURA_ERRO_EMISSAO,
    REGRA_FATURA_GERACAO_USINA,
    REGRA_UC_SEM_USINA,
    _ja_existe_pendencia_ativa,
    _pendencias_abertas_por_regra,
    _regra_de,
)
from services.financeiro_service import ORIGEM_REPASSE_USINEIRO, verificar_e_criar_pendencia_repasse
from services.log_service import LogService
from services.pendencia_service import criar_alerta, criar_erro

# Prazo em dias para UC ficar sem usina antes de gerar alerta
PRAZO_DIAS_SEM_USINA = 7


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
        'repasses_pendentes': 0,
        'faturas_erro_emissao': 0,
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

    # 6. Repasses ao usineiro perdidos por corrida entre webhooks concorrentes
    resultado['repasses_pendentes'] = _verificar_repasses_pendentes()

    # 7. Faturas (cobranca Asaas) que falharam na emissao/consulta
    resultado['faturas_erro_emissao'] = _verificar_faturas_erro_emissao()

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

    ultimo_dia_mes = calendar.monthrange(hoje.year, hoje.month)[1]

    for plant in usinas:
        if hoje.day < min(plant.dia_emissao_usina, ultimo_dia_mes):
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


def _verificar_repasses_pendentes() -> int:
    """Re-checa, pra cada usina com contrato de repasse configurado, se a
    pendencia de repasse ao usineiro da competencia corrente deveria existir.
    Cobre a corrida entre webhooks concorrentes do Asaas: duas UCs da mesma
    usina pagando quase ao mesmo tempo podem, sob READ COMMITTED, cada uma
    ver a fatura da outra ainda como pendente e nenhuma criar a pendencia.
    Idempotente via constraint unica (empresa_id, plant_id, origem,
    competencia) -- rodar de novo so preenche o que ficou perdido na corrida.
    """
    criados = 0
    competencia = datetime.utcnow().strftime('%Y-%m')

    usinas = Plant.query.filter(Plant.repasse_tipo.isnot(None)).all()

    for plant in usinas:
        antes = Pendencia.query.filter_by(
            plant_id=plant.id, origem=ORIGEM_REPASSE_USINEIRO, competencia=competencia
        ).count()
        verificar_e_criar_pendencia_repasse(plant.id, competencia)
        depois = Pendencia.query.filter_by(
            plant_id=plant.id, origem=ORIGEM_REPASSE_USINEIRO, competencia=competencia
        ).count()
        criados += depois - antes

    if criados > 0:
        db.session.commit()

    return criados


def _verificar_faturas_erro_emissao() -> int:
    """Cria um erro em Pendencias pra cada Fatura (cobranca Asaas) que ficou
    com status_interno='erro_emissao' (ver fatura_service.py::emitir()).
    Dedupe por faturaId em metadados (Fatura nao tem FK propria em Pendencia,
    so FaturaConcessionaria tem)."""
    criados = 0
    abertas = Pendencia.query.filter_by(status='aberta', categoria='Financeiro').all()
    ja_notificadas = {
        p.metadados.get('faturaId') for p in abertas
        if isinstance(p.metadados, dict) and p.metadados.get('regra') == REGRA_FATURA_ERRO_EMISSAO
    }

    faturas = Fatura.query.filter(Fatura.status_interno == 'erro_emissao').all()
    for fatura in faturas:
        if fatura.id in ja_notificadas:
            continue

        db.session.add(Pendencia(
            empresa_id=fatura.empresa_id,
            tipo='erro',
            categoria='Financeiro',
            origem='Automacao',
            titulo=f'Falha na emissao da fatura {fatura.id} ({fatura.competencia})',
            descricao=(
                f'A fatura {fatura.id}, competencia {fatura.competencia}, falhou '
                f'na emissao ou consulta junto ao Asaas (status_interno=erro_emissao).'
            ),
            client_id=fatura.client_id,
            consumer_unit_id=fatura.consumer_unit_id,
            competencia=fatura.competencia,
            prioridade='alta',
            metadados={'regra': REGRA_FATURA_ERRO_EMISSAO, 'faturaId': fatura.id},
        ))
        criados += 1

    if criados > 0:
        db.session.commit()

    return criados


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

    # 4. Fatura com erro de emissao - resolve se a fatura saiu do erro_emissao
    for pendencia in por_regra.get(REGRA_FATURA_ERRO_EMISSAO, []):
        metadados = pendencia.metadados or {}
        fatura_id = metadados.get('faturaId') if isinstance(metadados, dict) else None
        if not fatura_id:
            continue

        fatura = Fatura.query.filter_by(id=fatura_id, empresa_id=g.current_empresa_id).first()
        if not fatura or fatura.status_interno == 'erro_emissao':
            continue

        pendencia.status = 'resolvida'
        pendencia.resolved_at = datetime.utcnow()
        LogService.info(
            acao='auto_resolver',
            mensagem=f'Pendencia "{pendencia.titulo}" resolvida automaticamente (fatura saiu de erro_emissao)',
            entidade='Pendencia',
            entidade_id=pendencia.id
        )
        resolvidas += 1

    if resolvidas > 0:
        db.session.commit()

    return resolvidas
