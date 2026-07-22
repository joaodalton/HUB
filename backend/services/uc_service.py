# backend/services/uc_service.py
from datetime import date, datetime

from extensions import db
from models.client import Client
from models.consumer_unit import ConsumerUnit, PlantConnection
from models.plant import Plant
from services.log_service import LogService


def list_ucs() -> list[dict]:
    ucs = ConsumerUnit.query.order_by(ConsumerUnit.created_at.desc()).all()
    return [uc.to_dict() for uc in ucs]


def get_uc(uc_id: int) -> dict | None:
    uc = ConsumerUnit.query.get(uc_id)
    return uc.to_dict() if uc else None


def create_uc(data: dict) -> dict:
    client = Client.query.get(data.get('clienteId'))

    if not client:
        raise ValueError('Cliente informado nao existe.')

    uc = ConsumerUnit(client_id=client.id)
    apply_uc_fields(uc, data)
    db.session.add(uc)
    db.session.flush()

    sync_connections(uc, data.get('conexoes', []))
    db.session.commit()

    LogService.info(acao='create', mensagem=f'UC {uc.codigo} criada', entidade='ConsumerUnit', metadados={'id': uc.id})
    return uc.to_dict()


def update_uc(uc_id: int, data: dict) -> dict | None:
    uc = ConsumerUnit.query.get(uc_id)

    if not uc:
        return None

    if data.get('clienteId') and data['clienteId'] != uc.client_id:
        novo_cliente = Client.query.get(data['clienteId'])
        if not novo_cliente:
            raise ValueError('Cliente informado nao existe.')
        uc.client_id = novo_cliente.id

    apply_uc_fields(uc, data)

    if 'conexoes' in data:
        sync_connections(uc, data.get('conexoes', []))

    db.session.commit()

    LogService.info(acao='update', mensagem=f'UC {uc.codigo} atualizada', entidade='ConsumerUnit', metadados={'id': uc.id})
    return uc.to_dict()


def delete_uc(uc_id: int) -> bool:
    uc = ConsumerUnit.query.get(uc_id)

    if not uc:
        return False

    db.session.delete(uc)
    db.session.commit()

    LogService.info(acao='delete', mensagem=f'UC {uc_id} excluida', entidade='ConsumerUnit', metadados={'id': uc_id})
    return True


def apply_uc_fields(uc: ConsumerUnit, data: dict) -> None:
    """Aplica os campos simples (nao-relacionamento) de uma UC a partir do payload.
    Compartilhado entre uc_service (CRUD avulso) e client_service (UC aninhada no
    cliente) -- nao duplicar essa lista de campos em outro lugar."""
    uc.codigo = data.get('codigo', uc.codigo or '').strip()
    uc.codigo_aneel = data.get('codigoAneel', uc.codigo_aneel)
    uc.apelido = data.get('apelido', uc.apelido)
    uc.documento = data.get('documento', uc.documento)
    uc.endereco = data.get('endereco', uc.endereco)
    uc.cep = data.get('cep', uc.cep)
    uc.concessionaria = data.get('concessionaria', uc.concessionaria)
    uc.geracao_propria = bool(data.get('geracaoPropria', uc.geracao_propria))
    uc.dia_emissao_fatura = data.get('diaEmissaoFatura', uc.dia_emissao_fatura)
    uc.consumo = data.get('consumo', uc.consumo)
    uc.base_tarifaria = data.get('baseTarifaria', uc.base_tarifaria or 'B1')
    uc.desconto = data.get('desconto', uc.desconto)
    uc.tipo_ligacao = data.get('tipoLigacao', uc.tipo_ligacao or 'Monofasico')
    uc.inicio_contrato = _parse_date(data.get('inicioContrato')) if 'inicioContrato' in data else uc.inicio_contrato
    uc.termino_contrato = _parse_date(data.get('terminoContrato')) if 'terminoContrato' in data else uc.termino_contrato
    uc.carencia_meses = data.get('carenciaMeses', uc.carencia_meses)
    uc.percentual_desconto_carencia = data.get('percentualDescontoCarencia', uc.percentual_desconto_carencia)


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return datetime.strptime(value, '%Y-%m-%d').date()


def sync_connections(uc: ConsumerUnit, conexoes_data: list[dict]) -> None:
    """Reaplica as conexoes UC<->Usina a partir da lista enviada (substitui tudo).
    Reaproveitado pelo client_service.py ao salvar UCs aninhadas dentro de um cliente --
    nao duplicar essa logica lá, importar daqui."""
    for conexao in list(uc.conexoes):
        db.session.delete(conexao)
    db.session.flush()

    for conexao_data in conexoes_data:
        plant_id = conexao_data.get('plantId')

        if not plant_id:
            continue

        plant = Plant.query.get(int(plant_id))

        if not plant:
            LogService.warning(
                acao='sync_connections',
                mensagem=f'Usina id={plant_id} nao encontrada ao vincular UC {uc.id}. Conexao ignorada.',
                entidade='PlantConnection'
            )
            continue  # usina foi excluida; ignora conexao orfa

        db.session.add(PlantConnection(
            consumer_unit_id=uc.id,
            plant_id=plant.id,
            percentual=conexao_data.get('percentual', '')
        ))