# backend/services/plant_service.py
from datetime import date, datetime

from flask import g

from extensions import db
from models.plant import Plant


def list_plants() -> list[dict]:
    # Filtro automatico via TenantMixin (extensions.py)
    plants = Plant.query.order_by(Plant.created_at.desc()).all()
    return [plant.to_dict() for plant in plants]


def get_plant(plant_id: int) -> dict | None:
    # Filtro automatico via TenantMixin
    plant = Plant.query.get(plant_id)
    return plant.to_dict() if plant else None


def create_plant(data: dict) -> dict:
    plant = Plant(
        empresa_id=g.current_empresa_id,
        nome=data.get('nome', '').strip(),
        uc=data.get('uc', '').strip(),
        kw_pico=data.get('kwPico', 0),
        status=data.get('status', 'Implantacao'),
        percentual_disponivel=int(data.get('percentualDisponivel', 0)),
        marca_inversor=data.get('marcaInversor'),
        telefone_proprietario=data.get('telefoneProprietario'),
        email_proprietario=data.get('emailProprietario'),
        cidade=data.get('cidade'),
        uf=data.get('uf'),
        endereco=data.get('endereco'),
        data_ativacao=_parse_date(data.get('dataAtivacao')),
        responsavel=data.get('responsavel'),
        cep=data.get('cep'),
        latitude=data.get('latitude'),
        longitude=data.get('longitude'),
        num_modulos=data.get('numModulos'),
        potencia_modulo_w=data.get('potenciaModuloW'),
        reserva_percentual=data.get('reservaPercentual', 0),
        producao_media_manual=data.get('producaoMediaManual'),
        dia_emissao_usina=data.get('diaEmissaoUsina'),
        is_coringa=bool(data.get('isCoringa', False)),
        concessionaria=data.get('concessionaria'),
        **_producao_mensal_fields(data)
    )
    db.session.add(plant)
    db.session.commit()
    return plant.to_dict()


def update_plant(plant_id: int, data: dict) -> dict | None:
    plant = Plant.query.get(plant_id)
    if not plant:
        return None

    plant.nome = data.get('nome', plant.nome).strip()
    plant.uc = data.get('uc', plant.uc).strip()
    plant.kw_pico = data.get('kwPico', plant.kw_pico)
    plant.status = data.get('status', plant.status)
    plant.percentual_disponivel = int(data.get('percentualDisponivel', plant.percentual_disponivel))
    plant.marca_inversor = data.get('marcaInversor', plant.marca_inversor)
    plant.telefone_proprietario = data.get('telefoneProprietario', plant.telefone_proprietario)
    plant.email_proprietario = data.get('emailProprietario', plant.email_proprietario)
    plant.cidade = data.get('cidade', plant.cidade)
    plant.uf = data.get('uf', plant.uf)
    plant.endereco = data.get('endereco', plant.endereco)
    plant.data_ativacao = _parse_date(data.get('dataAtivacao')) if 'dataAtivacao' in data else plant.data_ativacao
    plant.responsavel = data.get('responsavel', plant.responsavel)
    plant.cep = data.get('cep', plant.cep)
    plant.latitude = data.get('latitude', plant.latitude)
    plant.longitude = data.get('longitude', plant.longitude)
    plant.num_modulos = data.get('numModulos', plant.num_modulos)
    plant.potencia_modulo_w = data.get('potenciaModuloW', plant.potencia_modulo_w)
    plant.reserva_percentual = data.get('reservaPercentual', plant.reserva_percentual)
    if 'producaoMediaManual' in data:
        plant.producao_media_manual = data['producaoMediaManual']
    plant.dia_emissao_usina = data.get('diaEmissaoUsina', plant.dia_emissao_usina)
    plant.is_coringa = bool(data.get('isCoringa', plant.is_coringa))
    plant.concessionaria = data.get('concessionaria', plant.concessionaria)

    for mes, valor in _producao_mensal_fields(data, only_present=True).items():
        setattr(plant, mes, valor)

    db.session.commit()
    return plant.to_dict()


def delete_plant(plant_id: int) -> bool:
    plant = Plant.query.get(plant_id)
    if not plant:
        return False

    db.session.delete(plant)
    db.session.commit()
    return True

def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return datetime.strptime(value, '%Y-%m-%d').date()


_MESES_KEYS = {
    'jan': 'producaoJan', 'fev': 'producaoFev', 'mar': 'producaoMar', 'abr': 'producaoAbr',
    'mai': 'producaoMai', 'jun': 'producaoJun', 'jul': 'producaoJul', 'ago': 'producaoAgo',
    'set': 'producaoSet', 'out': 'producaoOut', 'nov': 'producaoNov', 'dez': 'producaoDez'
}


def _producao_mensal_fields(data: dict, only_present: bool = False) -> dict:
    """Converte producaoJan..producaoDez do payload pra producao_jan..producao_dez
    do model. only_present=True (update) só inclui o que veio no body -- não
    zera mês que o usuário não mandou."""
    result = {}
    for mes, chave_json in _MESES_KEYS.items():
        if only_present and chave_json not in data:
            continue
        result[f'producao_{mes}'] = data.get(chave_json, 0)
    return result