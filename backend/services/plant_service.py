# backend/services/plant_service.py
from extensions import db
from models.plant import Plant


def list_plants() -> list[dict]:
    plants = Plant.query.order_by(Plant.created_at.desc()).all()
    return [plant.to_dict() for plant in plants]


def get_plant(plant_id: int) -> dict | None:
    plant = Plant.query.get(plant_id)
    return plant.to_dict() if plant else None


def create_plant(data: dict) -> dict:
    plant = Plant(
        nome=data.get('nome', '').strip(),
        uc=data.get('uc', '').strip(),
        kw_pico=data.get('kwPico', 0),
        status=data.get('status', 'Implantacao'),
        percentual_disponivel=int(data.get('percentualDisponivel', 0)),
        marca_inversor=data.get('marcaInversor'),
        telefone_proprietario=data.get('telefoneProprietario'),
        email_proprietario=data.get('emailProprietario')
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

    db.session.commit()
    return plant.to_dict()


def delete_plant(plant_id: int) -> bool:
    plant = Plant.query.get(plant_id)
    if not plant:
        return False

    db.session.delete(plant)
    db.session.commit()
    return True