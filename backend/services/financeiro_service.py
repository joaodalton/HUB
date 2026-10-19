# backend/services/financeiro_service.py
from sqlalchemy.exc import IntegrityError

from extensions import db
from models.fatura import Fatura
from models.fatura_concessionaria import FaturaConcessionaria
from models.pendencia import Pendencia

ORIGEM_PAGAR_CONCESSIONARIA = 'pagar_concessionaria'


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
