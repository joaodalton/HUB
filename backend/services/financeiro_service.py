# backend/services/financeiro_service.py
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy.exc import IntegrityError

from extensions import db
from models.fatura import Fatura
from models.fatura_concessionaria import FaturaConcessionaria
from models.pendencia import Pendencia
from models.plant import Plant

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
    if not plant.repasse_tipo:
        return None

    uc_ids = [c.consumer_unit_id for c in plant.connections]
    soma = _soma_recebido_uc_ids(uc_ids, competencia)

    if plant.repasse_tipo == 'valor_fixo':
        return plant.repasse_valor
    return soma * plant.repasse_valor / Decimal('100')


def _formatar_valor(valor: Decimal) -> str:
    return str(valor.quantize(Decimal('0.01')))


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
        else:
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
        por_usina.append({
            'usinaId': plant.id,
            'usinaNome': plant.nome,
            'recebido': _formatar_valor(recebido),
            'repasseCalculado': _formatar_valor(repasse) if repasse is not None else None,
            'contratoPendente': repasse is None,
        })

    return {'porCliente': por_cliente, 'porUsina': por_usina}


def verificar_e_criar_pendencia_repasse(plant_id: int, competencia: str) -> None:
    """Cria (idempotente) a pendencia de repasse ao usineiro quando todas as
    UCs conectadas a usina ja pagaram (Fatura received) na competencia."""
    plant = Plant.query.filter_by(id=plant_id).first()
    if plant is None or not plant.connections:
        return

    for conexao in plant.connections:
        pagou = Fatura.query.filter_by(
            consumer_unit_id=conexao.consumer_unit_id,
            competencia=competencia,
            asaas_status='received',
        ).first()
        if pagou is None:
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
                metadados={'valor': str(valor)},
            ))
            db.session.flush()
    except IntegrityError:
        pass
