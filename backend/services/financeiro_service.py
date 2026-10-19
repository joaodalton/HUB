# backend/services/financeiro_service.py
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


def calcular_repasse(plant: Plant, competencia: str) -> Optional[Decimal]:
    """Calcula o valor a repassar ao usineiro na competencia, com base no
    contrato configurado em Plant.repasse_tipo/repasse_valor. Retorna None
    se nenhum contrato estiver configurado."""
    if not plant.repasse_tipo:
        return None

    uc_ids = [c.consumer_unit_id for c in plant.connections]
    soma = Decimal('0')
    if uc_ids:
        faturas = Fatura.query.filter(
            Fatura.consumer_unit_id.in_(uc_ids),
            Fatura.competencia == competencia,
            Fatura.asaas_status == 'received',
        ).all()
        soma = sum((f.valor for f in faturas), Decimal('0'))

    if plant.repasse_tipo == 'valor_fixo':
        return plant.repasse_valor
    return soma * plant.repasse_valor / Decimal('100')


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
