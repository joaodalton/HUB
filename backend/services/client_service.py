from extensions import db
from sqlalchemy.exc import IntegrityError
from models.client import Client
from models.consumer_unit import ConsumerUnit, PlantConnection


def list_clients() -> list[dict]:
    clients = Client.query.order_by(Client.created_at.desc()).all()
    return [client.to_dict() for client in clients]


def get_client(client_id: int) -> dict | None:
    client = Client.query.get(client_id)
    return client.to_dict() if client else None


def create_client(data: dict) -> dict:
    client = Client(
        nome=data.get('nome', '').strip(),
        cpf=data.get('cpf', '').strip(),
        email=data.get('email', '').strip(),
        concessionaria=data.get('concessionaria', 'Copel'),
        status=_resolve_status(data.get('ucs', []))
    )
    db.session.add(client)

    try:
        db.session.flush()
        _sync_ucs(client, data.get('ucs', []))
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise ValueError('Já existe um cliente cadastrado com este CPF.')

    return client.to_dict()


def update_client(client_id: int, data: dict) -> dict | None:
    client = Client.query.get(client_id)

    if not client:
        return None

    client.nome = data.get('nome', client.nome).strip()
    client.cpf = data.get('cpf', client.cpf).strip()
    client.email = data.get('email', client.email).strip()
    client.concessionaria = data.get('concessionaria', client.concessionaria)
    client.status = _resolve_status(data.get('ucs', []))

    _sync_ucs(client, data.get('ucs', []))

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise ValueError('Já existe um cliente cadastrado com este CPF.')

    return client.to_dict()


def delete_client(client_id: int) -> bool:
    client = Client.query.get(client_id)

    if not client:
        return False

    db.session.delete(client)
    db.session.commit()
    return True


def _resolve_status(ucs: list[dict]) -> str:
    if any(len(uc.get('conexoes', [])) > 1 for uc in ucs):
        return 'Esperando rateio'
    if any(len(uc.get('conexoes', [])) > 0 for uc in ucs):
        return 'Concluido'
    return 'Esperando usina'


def _sync_ucs(client: Client, ucs_data: list[dict]) -> None:
    existing_ids = {uc.id for uc in client.ucs}
    sent_ids = {int(uc['id']) for uc in ucs_data if _is_persisted_id(uc.get('id'))}

    for uc_id in existing_ids - sent_ids:
        uc = ConsumerUnit.query.get(uc_id)
        if uc:
            db.session.delete(uc)

    for uc_data in ucs_data:
        uc_id = uc_data.get('id')
        uc = ConsumerUnit.query.get(int(uc_id)) if _is_persisted_id(uc_id) else None

        if not uc:
            uc = ConsumerUnit(client_id=client.id)
            db.session.add(uc)

        uc.codigo = uc_data.get('codigo', '')
        uc.apelido = uc_data.get('apelido', '')
        uc.consumo = uc_data.get('consumo', '')
        uc.base_tarifaria = uc_data.get('baseTarifaria', 'B1')
        uc.desconto = uc_data.get('desconto', '')
        uc.tipo_ligacao = uc_data.get('tipoLigacao', 'Monofasico')

        db.session.flush()
        _sync_connections(uc, uc_data.get('conexoes', []))


def _sync_connections(uc: ConsumerUnit, conexoes_data: list[dict]) -> None:
    from models.plant import Plant

    for conexao in list(uc.conexoes):
        db.session.delete(conexao)
    db.session.flush()

    for conexao_data in conexoes_data:
        nome_usina = (conexao_data.get('usina') or '').strip()
        plant = Plant.query.filter(
            db.func.lower(Plant.nome) == nome_usina.lower()
        ).first()

        if not plant:
            # TODO: substituir por logging estruturado quando o modelo Log existir
            print(f'[aviso] Usina "{nome_usina}" nao encontrada ao vincular UC {uc.id}. Conexao ignorada.')
            continue

        db.session.add(PlantConnection(
            consumer_unit_id=uc.id,
            plant_id=plant.id,
            percentual=conexao_data.get('percentual', '')
        ))

def _is_persisted_id(value) -> bool:
    """UUIDs gerados no front (crypto.randomUUID()) são strings não-numéricas
    e representam UCs novas; apenas ids numéricos (vindos do banco) contam
    como UC já existente."""
    if isinstance(value, int):
        return True
    if isinstance(value, str):
        return value.isdigit()
    return False