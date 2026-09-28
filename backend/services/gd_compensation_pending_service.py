"""Creates one operational pending item when expected GD compensation is unverified."""
from datetime import date

from sqlalchemy.exc import IntegrityError

from extensions import db
from models.consumer_unit import ConsumerUnit, PlantConnection
from models.fatura_concessionaria import FaturaConcessionaria
from models.pendencia import Pendencia
from models.plant import Plant
from services.log_service import LogService


ORIGIN = 'GD_COMPENSATION_UNVERIFIED'


def register(invoice_id, normalized, validation):
    """No-op unless the persisted invoice has an exact UC and proven expectation."""
    invoice = FaturaConcessionaria.query.filter_by(id=invoice_id, empresa_id=normalized.empresa_id).first()
    if invoice is None or validation.consumer_unit_id is None or invoice.consumer_unit_id != validation.consumer_unit_id:
        return None
    energy = normalized.billing_energy_input
    if energy is None or energy.status.value == 'VALID':
        return None
    competencia = invoice.competencia
    try:
        reference = date.fromisoformat(f'{competencia}-01')
    except (TypeError, ValueError):
        return None
    uc = ConsumerUnit.query.filter_by(id=invoice.consumer_unit_id, empresa_id=invoice.empresa_id).first()
    if uc is None or uc.client_id != invoice.client_id:
        return None
    plants = (db.session.query(Plant)
              .join(PlantConnection, PlantConnection.plant_id == Plant.id)
              .filter(PlantConnection.consumer_unit_id == uc.id,
                      PlantConnection.empresa_id == invoice.empresa_id,
                      Plant.empresa_id == invoice.empresa_id,
                      Plant.status == 'Ativa',
                      Plant.data_ativacao.isnot(None),
                      Plant.data_ativacao <= reference)
              .order_by(Plant.id).all())
    if not plants:
        return None
    plant_id = plants[0].id if len(plants) == 1 else None
    issue_codes = [issue.code for issue in energy.issues]
    metadata = {
        'evento': ORIGIN,
        'faturaId': invoice.id,
        'competencia': competencia,
        'blockerCode': issue_codes[0] if issue_codes else 'GD_COMPENSATION_UNVERIFIED',
        'blockerCodes': issue_codes,
        'energyStatus': energy.status.value,
        'plantIds': [plant.id for plant in plants],
        'expectativa': 'comprovada_por_usina_ativa_na_competencia',
    }
    pending = Pendencia(
        empresa_id=invoice.empresa_id, tipo='pendencia', categoria='Operacional', origem=ORIGIN,
        titulo='Compensação GD não comprovada',
        descricao='A fatura processada não comprovou energia compensada elegível para cobrança.',
        client_id=invoice.client_id, consumer_unit_id=uc.id, plant_id=plant_id,
        document_id=invoice.document_id, fatura_concessionaria_id=invoice.id,
        prioridade='alta', metadados=metadata,
    )
    try:
        db.session.add(pending)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return Pendencia.query.filter_by(empresa_id=invoice.empresa_id,
                                         fatura_concessionaria_id=invoice.id, origem=ORIGIN).first()
    LogService.warning(acao='gd_compensation_unverified',
                       mensagem='Pendência de compensação GD criada.', entidade='Pendencia',
                       entidade_id=pending.id, metadados={'empresaId': invoice.empresa_id,
                                                           'faturaId': invoice.id, 'competencia': competencia})
    return pending
