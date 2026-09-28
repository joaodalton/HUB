from flask import g
import re

from extensions import db
from sqlalchemy.exc import IntegrityError
from models.client import Client
from models.consumer_unit import ConsumerUnit
from services.uc_service import apply_uc_fields, sync_connections, _parse_date
from services.cad_identity import normalize_name, normalize_phone, normalize_cpf

def _client(client_id): return Client.query.filter_by(id=client_id, empresa_id=g.current_empresa_id).first()
def _uc(uc_id): return ConsumerUnit.query.filter_by(id=uc_id, empresa_id=g.current_empresa_id).first()


def list_clients() -> list[dict]:
    # Filtro automatico via TenantMixin (extensions.py)
    clients = Client.query.order_by(Client.created_at.desc()).all()
    return [client.to_dict() for client in clients]


def get_client(client_id: int) -> dict | None:
    # Filtro automatico via TenantMixin
    client = _client(client_id)
    return client.to_dict() if client else None


def create_client(data: dict) -> dict:
    client = Client(
        empresa_id=g.current_empresa_id,
        nome=normalize_name(data.get('nome')),
        cpf=normalize_cpf(data.get('cpf')),
        email=data.get('email', '').strip(),
        telefone=normalize_phone(data['telefone']) if data.get('telefone') else None,
        concessionaria=data.get('concessionaria', 'Copel'),
        status=_resolve_status(data.get('ucs', [])),
        data_nascimento=_parse_date(data.get('dataNascimento'))
    )
    db.session.add(client)

    try:
        db.session.flush()
        _sync_ucs(client, data.get('ucs', []))
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise ValueError('Ja existe um cliente cadastrado com este CPF.')

    return client.to_dict()


def update_client(client_id: int, data: dict) -> dict | None:
    client = _client(client_id)

    if not client:
        return None

    if 'nome' in data and data['nome'] != client.nome:
        client.nome = normalize_name(data['nome'])
    if 'cpf' in data and re.sub(r'\D', '', str(data['cpf'])) != re.sub(r'\D', '', str(client.cpf)):
        client.cpf = normalize_cpf(data['cpf'])
    client.email = data.get('email', client.email).strip()
    if 'telefone' in data and data['telefone'] != client.telefone:
        client.telefone = normalize_phone(data['telefone']) if data['telefone'] else None
    client.concessionaria = data.get('concessionaria', client.concessionaria)
    if 'ucs' in data:
        client.status = _resolve_status(data['ucs'])
    client.data_nascimento = _parse_date(data['dataNascimento']) if 'dataNascimento' in data else client.data_nascimento

    if 'ucs' in data:
        _sync_ucs(client, data['ucs'])

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise ValueError('Ja existe um cliente cadastrado com este CPF.')

    return client.to_dict()


def delete_client(client_id: int) -> bool:
    client = _client(client_id)

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
    if not sent_ids.issubset(existing_ids):
        raise ValueError('UC nao encontrada para este cliente.')

    for uc_id in existing_ids - sent_ids:
        uc = _uc(uc_id)
        if uc:
            db.session.delete(uc)

    for uc_data in ucs_data:
        uc_id = uc_data.get('id')
        uc = _uc(int(uc_id)) if _is_persisted_id(uc_id) else None

        if not uc:
            uc = ConsumerUnit(empresa_id=g.current_empresa_id, client_id=client.id)
            db.session.add(uc)

        apply_uc_fields(uc, uc_data)

        db.session.flush()
        if 'conexoes' in uc_data:
            sync_connections(uc, uc_data.get('conexoes', []))


def _is_persisted_id(value) -> bool:
    """UUIDs gerados no front (crypto.randomUUID()) são strings não-numéricas
    e representam UCs novas; apenas ids numéricos (vindos do banco) contam
    como UC já existente."""
    if isinstance(value, int):
        return True
    if isinstance(value, str):
        return value.isdigit()
    return False
