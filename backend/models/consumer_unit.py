# backend/models/consumer_unit.py
from datetime import datetime

from extensions import db


class ConsumerUnit(db.Model):
    __tablename__ = 'consumer_units'

    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)

    codigo = db.Column(db.String(30), nullable=False)
    apelido = db.Column(db.String(100), nullable=True, default='')
    consumo = db.Column(db.String(30), nullable=True, default='')
    base_tarifaria = db.Column(db.String(10), nullable=False, default='B1')
    desconto = db.Column(db.String(20), nullable=True, default='')
    tipo_ligacao = db.Column(db.String(20), nullable=False, default='Monofasico')

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    client = db.relationship('Client', backref=db.backref('ucs', cascade='all, delete-orphan'))
    conexoes = db.relationship(
        'PlantConnection',
        back_populates='consumer_unit',
        cascade='all, delete-orphan'
    )

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'codigo': self.codigo,
            'apelido': self.apelido,
            'consumo': self.consumo,
            'baseTarifaria': self.base_tarifaria,
            'desconto': self.desconto,
            'tipoLigacao': self.tipo_ligacao,
            'conexoes': [conexao.to_dict() for conexao in self.conexoes]
        }


class PlantConnection(db.Model):
    __tablename__ = 'plant_connections'

    id = db.Column(db.Integer, primary_key=True)
    consumer_unit_id = db.Column(db.Integer, db.ForeignKey('consumer_units.id'), nullable=False)
    plant_id = db.Column(db.Integer, db.ForeignKey('plants.id'), nullable=False)
    percentual = db.Column(db.String(10), nullable=False, default='')

    consumer_unit = db.relationship('ConsumerUnit', back_populates='conexoes')
    plant = db.relationship('Plant', back_populates='connections')

    def to_dict(self) -> dict:
        return {
        "id": self.id,
        "plantId": self.plant_id,
        "usina": self.plant.nome if self.plant else "",
        "percentual": self.percentual,
    }