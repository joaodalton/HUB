# backend/services/financeiro_service.py
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from extensions import db
from models.calculo_cobranca import BillingCalculationExecution
from models.consumer_unit import ConsumerUnit, PlantConnection
from models.fatura import Fatura
from models.fatura_concessionaria import FaturaConcessionaria
from models.pendencia import Pendencia
from models.plant import Plant
from services.billing_calculation_service import blocked_stage
from services.fatura_service import snapshot_billing_mode

ORIGEM_PAGAR_CONCESSIONARIA = 'pagar_concessionaria'
ORIGEM_REPASSE_USINEIRO = 'repasse_usineiro'


def criar_pendencia_pagar_concessionaria(fatura: Fatura) -> None:
    """Cria (idempotente) a pendencia de pagar a concessionaria referente
    a fatura do cliente, quando houver uma FaturaConcessionaria correspondente
    pela mesma UC e competencia."""
    invoice = FaturaConcessionaria.query.filter_by(
        empresa_id=fatura.empresa_id,
        consumer_unit_id=fatura.consumer_unit_id,
        competencia=fatura.competencia,
        deleted_at=None,
    ).first()
    if invoice is None:
        return

    cliente_nome = fatura.client.nome if fatura.client else None
    try:
        with db.session.begin_nested():
            db.session.add(Pendencia(
                empresa_id=fatura.empresa_id,
                categoria='Financeiro',
                origem=ORIGEM_PAGAR_CONCESSIONARIA,
                fatura_concessionaria_id=invoice.id,
                client_id=fatura.client_id,
                consumer_unit_id=fatura.consumer_unit_id,
                titulo=f'Pagar concessionaria - {cliente_nome} ({fatura.competencia})',
                descricao=(
                    f'Fatura do cliente {cliente_nome} na competencia {fatura.competencia} '
                    'recebida; pagamento a concessionaria pendente.'
                ),
            ))
            db.session.flush()
    except IntegrityError:
        pass


def _soma_recebido_uc_ids(uc_ids: list, competencia: str) -> Decimal:
    """Soma Fatura.valor das UCs informadas, na competencia, ja recebidas
    (asaas_status='received')."""
    if not uc_ids:
        return Decimal('0')
    faturas = Fatura.query.filter(
        Fatura.consumer_unit_id.in_(uc_ids),
        Fatura.competencia == competencia,
        Fatura.asaas_status == 'received',
    ).all()
    return sum((f.valor for f in faturas), Decimal('0'))


def calcular_repasse(plant: Plant, competencia: str) -> Optional[Decimal]:
    """Calcula o valor a repassar ao usineiro na competencia, com base no
    contrato configurado em Plant.repasse_tipo/repasse_valor. Retorna None
    se nenhum contrato estiver configurado."""
    if not plant.repasse_tipo or plant.repasse_valor is None:
        return None

    uc_ids = [c.consumer_unit_id for c in plant.connections]
    soma = _soma_recebido_uc_ids(uc_ids, competencia)

    if plant.repasse_tipo == 'valor_fixo':
        return plant.repasse_valor
    return soma * plant.repasse_valor / Decimal('100')


def _formatar_valor(valor: Decimal) -> str:
    return str(valor.quantize(Decimal('0.01')))


def _todas_ucs_pagaram(plant: Plant, competencia: str) -> bool:
    """True se todas as UCs conectadas a usina ja pagaram (Fatura received)
    na competencia. False se a usina nao tiver nenhuma UC conectada."""
    if not plant.connections:
        return False
    for conexao in plant.connections:
        pagou = Fatura.query.filter_by(
            consumer_unit_id=conexao.consumer_unit_id,
            competencia=competencia,
            asaas_status='received',
        ).first()
        if pagou is None:
            return False
    return True


def obter_dashboard(empresa_id: int, competencia: Optional[str] = None) -> dict:
    """Agrega as Faturas da competencia por cliente (recebido vs. pendente)
    e por usina (recebido das UCs conectadas + repasse calculado ao
    usineiro). Retorna {'porCliente': [...], 'porUsina': [...]}."""
    if not competencia:
        competencia = datetime.utcnow().strftime('%Y-%m')

    faturas = Fatura.query.filter_by(empresa_id=empresa_id, competencia=competencia).all()
    por_cliente_map: dict = {}
    for fatura in faturas:
        entry = por_cliente_map.setdefault(fatura.client_id, {
            'clienteId': fatura.client_id,
            'clienteNome': fatura.client.nome if fatura.client else None,
            'recebido': Decimal('0'),
            'pendente': Decimal('0'),
        })
        if fatura.asaas_status == 'received':
            entry['recebido'] += fatura.valor
        elif fatura.asaas_status not in ('canceled', 'refunded'):
            entry['pendente'] += fatura.valor
    por_cliente = [{
        'clienteId': entry['clienteId'],
        'clienteNome': entry['clienteNome'],
        'recebido': _formatar_valor(entry['recebido']),
        'pendente': _formatar_valor(entry['pendente']),
    } for entry in por_cliente_map.values()]

    plants = Plant.query.filter_by(empresa_id=empresa_id).all()
    por_usina = []
    for plant in plants:
        if not plant.connections:
            por_usina.append({
                'usinaId': plant.id,
                'usinaNome': plant.nome,
                'recebido': '0.00',
                'repasseCalculado': None,
                'contratoPendente': False,
                'semClientesConectados': True,
            })
            continue

        uc_ids = [c.consumer_unit_id for c in plant.connections]
        recebido = _soma_recebido_uc_ids(uc_ids, competencia)
        repasse = calcular_repasse(plant, competencia)
        contrato_pendente = repasse is None
        aguardando_pagamentos = repasse is not None and not _todas_ucs_pagaram(plant, competencia)
        if aguardando_pagamentos:
            repasse = None
        item = {
            'usinaId': plant.id,
            'usinaNome': plant.nome,
            'recebido': _formatar_valor(recebido),
            'repasseCalculado': _formatar_valor(repasse) if repasse is not None else None,
            'contratoPendente': contrato_pendente,
        }
        if aguardando_pagamentos:
            item['aguardandoPagamentos'] = True
        por_usina.append(item)

    return {'porCliente': por_cliente, 'porUsina': por_usina}


def _bloqueio(invoice, client, execution):
    """Primeiro bloqueio aplicavel a fatura (ou None), na ordem do contrato."""
    if not (client.email or '').strip():
        return {'code': 'CLIENT_EMAIL_MISSING', 'message': 'Cliente sem e-mail cadastrado.'}
    missing = [name for name, empty in (('dataVencimento', invoice.data_vencimento is None),
                                        ('valor', invoice.valor_total_concessionaria is None or invoice.valor_total_concessionaria <= 0)) if empty]
    if missing:
        return {'code': 'INVOICE_DATA_INCOMPLETE', 'message': f"Faltou na fatura: {', '.join(missing)}."}
    if execution is None:
        return {'code': 'NOT_CALCULATED', 'message': 'Cobrança ainda não calculada.'}
    if execution.snapshot is None:
        stage = blocked_stage(execution.auditoria) or {}
        if stage.get('stage') == 'RULE_RESOLUTION':
            return {'code': 'RULE_MISSING', 'message': 'Cliente sem regra de cobrança.'}
        return {'code': 'CALCULATION_BLOCKED',
                'message': f"Cálculo bloqueado em {stage.get('stage')}: {', '.join(stage.get('blockers', []))}."}
    return None


def listar_pendentes_boleto(empresa_id: int) -> list[dict]:
    """Faturas validas com UC e sem boleto ativo, agrupadas por usina (sem usina por ultimo)."""
    invoices = FaturaConcessionaria.query.filter(
        FaturaConcessionaria.empresa_id == empresa_id, FaturaConcessionaria.deleted_at.is_(None),
        FaturaConcessionaria.consumer_unit_id.isnot(None), FaturaConcessionaria.status_validacao == 'valida',
    ).options(selectinload(FaturaConcessionaria.client)).all()
    if not invoices:
        return []
    uc_ids = {i.consumer_unit_id for i in invoices}
    ucs = {u.id: u for u in ConsumerUnit.query.filter(
        ConsumerUnit.empresa_id == empresa_id, ConsumerUnit.id.in_(uc_ids))}
    boletos = Fatura.query.filter(Fatura.empresa_id == empresa_id, Fatura.consumer_unit_id.in_(uc_ids)).all()
    ativos = {(f.consumer_unit_id, f.competencia) for f in boletos
              if f.asaas_id is not None and f.asaas_status not in ('canceled', 'refunded')}
    pendentes = {(f.consumer_unit_id, f.competencia): f for f in boletos
                 if f.asaas_id is None and f.status_interno in ('aguardando_emissao', 'erro_emissao')}
    invoices = [i for i in invoices if (i.consumer_unit_id, i.competencia) not in ativos]
    # Ultima execucao = maior id; uma consulta IN, ordenada para a ultima sobrescrever.
    execucoes = {e.fatura_concessionaria_id: e for e in BillingCalculationExecution.query.filter(
        BillingCalculationExecution.empresa_id == empresa_id,
        BillingCalculationExecution.fatura_concessionaria_id.in_([i.id for i in invoices]),
    ).options(selectinload(BillingCalculationExecution.snapshot)).order_by(BillingCalculationExecution.id)}
    plantas = {}
    for conn in PlantConnection.query.filter(
            PlantConnection.empresa_id == empresa_id, PlantConnection.consumer_unit_id.in_(uc_ids)
    ).options(selectinload(PlantConnection.plant)):
        if conn.plant is not None:  # conexao orfa cai no grupo "Sem usina"
            plantas.setdefault(conn.consumer_unit_id, {})[conn.plant_id] = conn.plant.nome
    grupos = {}
    for invoice in invoices:
        uc, execution = ucs.get(invoice.consumer_unit_id), execucoes.get(invoice.id)
        if uc is None or invoice.client is None:  # linha inconsistente: nao derruba a listagem
            continue
        pendente = pendentes.get((invoice.consumer_unit_id, invoice.competencia))
        snapshot = execution.snapshot if execution else None
        valor_hub = valor_cobrar = modo = None
        if snapshot is not None:
            valor_hub = snapshot.valor_final
            try:
                modo = snapshot_billing_mode(snapshot, bool(uc.debito_automatico))
            except ValueError:  # regra com modo invalido: linha sem valor a cobrar
                modo = None
            if modo is not None:
                valor_cobrar = valor_hub + (invoice.valor_total_concessionaria or 0) if modo == 'unified' else valor_hub
        if pendente is not None:  # o retry reaproveita valor e modo gravados
            valor_cobrar, modo = pendente.valor, pendente.billing_mode
        valor = invoice.valor_total_concessionaria
        item = {
            'invoiceId': invoice.id, 'clienteId': invoice.client_id, 'clienteNome': invoice.client.nome,
            'ucId': uc.id, 'ucCodigo': uc.codigo, 'competencia': invoice.competencia,
            'dataVencimento': invoice.data_vencimento.isoformat() if invoice.data_vencimento else None,
            'valorConcessionaria': None if valor is None else _formatar_valor(valor),
            'valorHub': None if valor_hub is None else _formatar_valor(valor_hub),
            'valorCobrar': None if valor_cobrar is None else _formatar_valor(valor_cobrar),
            'billingMode': modo, 'emissaoPendente': pendente is not None,
            'bloqueio': _bloqueio(invoice, invoice.client, execution),
        }
        for plant_id, nome in (plantas.get(uc.id) or {None: None}).items():
            grupos.setdefault((plant_id, nome), []).append(item)
    ordem = sorted(grupos, key=lambda k: (k[0] is None, k[1] or '', k[0] or 0))
    return [{'usinaId': k[0], 'usinaNome': k[1], 'itens': sorted(grupos[k], key=lambda i: (i['clienteNome'], i['invoiceId']))}
            for k in ordem]


def verificar_e_criar_pendencia_repasse(plant_id: int, competencia: str) -> None:
    """Cria (idempotente) a pendencia de repasse ao usineiro quando todas as
    UCs conectadas a usina ja pagaram (Fatura received) na competencia."""
    plant = Plant.query.filter_by(id=plant_id).first()
    if plant is None or not _todas_ucs_pagaram(plant, competencia):
        return

    valor = calcular_repasse(plant, competencia)
    if valor is None:
        return

    try:
        with db.session.begin_nested():
            db.session.add(Pendencia(
                empresa_id=plant.empresa_id,
                categoria='Financeiro',
                origem=ORIGEM_REPASSE_USINEIRO,
                plant_id=plant.id,
                competencia=competencia,
                titulo=f'Repassar usineiro - {plant.nome} ({competencia})',
                descricao=(
                    f'Todas as UCs conectadas a usina {plant.nome} pagaram na competencia '
                    f'{competencia}; repasse ao usineiro pendente.'
                ),
                metadados={'valor': str(valor.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))},
            ))
            db.session.flush()
    except IntegrityError:
        pass
