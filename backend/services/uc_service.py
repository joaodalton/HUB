# backend/services/uc_service.py
from datetime import date, datetime

from flask import g

from extensions import db
from models.client import Client
from models.consumer_unit import ConsumerUnit, PlantConnection
from models.plant import Plant
from services.log_service import LogService

def _uc(uc_id): return ConsumerUnit.query.filter_by(id=uc_id, empresa_id=g.current_empresa_id).first()
def _client(client_id): return Client.query.filter_by(id=client_id, empresa_id=g.current_empresa_id).first()
def _plant(plant_id): return Plant.query.filter_by(id=plant_id, empresa_id=g.current_empresa_id).first()


def list_ucs() -> list[dict]:
    # Filtro automatico via TenantMixin (extensions.py)
    # Por updated_at, nao created_at -- assim uma UC editada agora aparece no
    # topo, mesmo se foi criada ha meses. updated_at ja e mantido sozinho pelo
    # SQLAlchemy (onupdate=datetime.utcnow no model) a cada save.
    ucs = ConsumerUnit.query.order_by(ConsumerUnit.updated_at.desc()).all()
    return [uc.to_dict() for uc in ucs]


def get_uc(uc_id: int) -> dict | None:
    # Filtro automatico via TenantMixin
    uc = _uc(uc_id)
    return uc.to_dict() if uc else None


def create_uc(data: dict) -> dict:
    client = _client(data.get('clienteId'))

    if not client:
        raise ValueError('Cliente informado nao existe.')

    uc = ConsumerUnit(
        empresa_id=g.current_empresa_id,
        client_id=client.id
    )
    apply_uc_fields(uc, data)
    db.session.add(uc)
    db.session.flush()

    sync_connections(uc, data.get('conexoes', []))
    db.session.commit()

    LogService.info(acao='create', mensagem=f'UC {uc.codigo} criada', entidade='ConsumerUnit', metadados={'id': uc.id})
    return uc.to_dict()


def update_uc(uc_id: int, data: dict) -> dict | None:
    uc = _uc(uc_id)

    if not uc:
        return None

    if data.get('clienteId') and data['clienteId'] != uc.client_id:
        novo_cliente = _client(data['clienteId'])
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
    uc = _uc(uc_id)

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
    uc.consumo = _parse_consumo(data['consumo']) if 'consumo' in data else uc.consumo
    uc.base_tarifaria = data.get('baseTarifaria', uc.base_tarifaria or 'B1')
    uc.desconto = data.get('desconto', uc.desconto)
    uc.tipo_ligacao = data.get('tipoLigacao', uc.tipo_ligacao or 'Monofasico')
    uc.inicio_contrato = _parse_date(data.get('inicioContrato')) if 'inicioContrato' in data else uc.inicio_contrato
    uc.termino_contrato = _parse_date(data.get('terminoContrato')) if 'terminoContrato' in data else uc.termino_contrato
    uc.carencia_meses = data.get('carenciaMeses', uc.carencia_meses)
    uc.percentual_desconto_carencia = data.get('percentualDescontoCarencia', uc.percentual_desconto_carencia)
    uc.documentacao_completa = bool(data.get('documentacaoCompleta', uc.documentacao_completa))
    uc.sem_pendencia_financeira = bool(data.get('semPendenciaFinanceira', uc.sem_pendencia_financeira))
    uc.cliente_estrategico = bool(data.get('clienteEstrategico', uc.cliente_estrategico))
    if 'bufferPercentual' in data:
        uc.buffer_percentual = data['bufferPercentual']


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return datetime.strptime(value, '%Y-%m-%d').date()


def _parse_consumo(value) -> float | None:
    if value is None or value == '':
        return None
    return float(value)

def remove_connection(plant_id: int, connection_id: int) -> bool:
    """Desconecta uma UC de uma usina (exclui a PlantConnection). Esse é o
    único caminho pra desfazer uma conexão hoje -- o checkbox antigo em
    ClientCard/UcCard não cria mais conexão nova (isso passou a ser
    exclusivo do wizard de Rateio), então também não é o lugar certo de
    remover. A ação vive na tela de Usina, perto de onde a lista de UCs
    conectadas já é mostrada."""
    connection = PlantConnection.query.filter_by(id=connection_id, plant_id=plant_id).first()

    if not connection:
        return False

    uc_codigo = connection.consumer_unit.codigo if connection.consumer_unit else str(connection.consumer_unit_id)
    db.session.delete(connection)
    db.session.commit()

    LogService.info(
        acao='remove_connection',
        mensagem=f'UC {uc_codigo} desconectada da usina {plant_id}',
        entidade='PlantConnection',
        metadados={'plantId': plant_id, 'connectionId': connection_id}
    )
    return True


def sync_connections(uc: ConsumerUnit, conexoes_data: list[dict]) -> None:
    """Reconcilia as conexoes UC<->Usina com a lista enviada -- SEM apagar e
    recriar tudo (bug corrigido: isso destruia percentual/percentual_manual
    de conexoes ja confirmadas pelo wizard de Rateio toda vez que a UC era
    salva por qualquer outro motivo, ex.: editar telefone).

    Regra: so remove conexao que SUMIU da lista enviada; so cria conexao que
    e NOVA na lista; conexao que ja existia e continua na lista NAO e tocada
    (percentual e percentual_manual dela permanecem intactos).

    Reaproveitado pelo client_service.py ao salvar UCs aninhadas dentro de um
    cliente -- nao duplicar essa logica lá, importar daqui."""
    existentes_por_usina = {conexao.plant_id: conexao for conexao in uc.conexoes}

    ids_enviados = set()
    for conexao_data in conexoes_data:
        plant_id = conexao_data.get('plantId')
        if plant_id:
            ids_enviados.add(int(plant_id))

    # Remove só o que foi explicitamente tirado da lista.
    for plant_id, conexao in list(existentes_por_usina.items()):
        if plant_id not in ids_enviados:
            db.session.delete(conexao)

    # Cria só o que é novo -- conexão que já existia (mesmo plant_id) é
    # ignorada aqui de propósito, pra não sobrescrever percentual/manual.
    for conexao_data in conexoes_data:
        plant_id = conexao_data.get('plantId')

        if not plant_id:
            continue

        plant_id = int(plant_id)

        if plant_id in existentes_por_usina:
            continue  # já existe -- preserva como está

        plant = _plant(plant_id)

        if not plant:
            LogService.warning(
                acao='sync_connections',
                mensagem=f'Usina id={plant_id} nao encontrada ao vincular UC {uc.id}. Conexao ignorada.',
                entidade='PlantConnection'
            )
            continue  # usina foi excluida; ignora conexao orfa

        db.session.add(PlantConnection(
            empresa_id=g.current_empresa_id,
            consumer_unit_id=uc.id,
            plant_id=plant.id,
            percentual=conexao_data.get('percentual', '')
        ))
