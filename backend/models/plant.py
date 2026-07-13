# backend/models/plant.py
from datetime import datetime

from extensions import db


class Plant(db.Model):
    __tablename__ = 'plants'

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), nullable=False)
    uc = db.Column(db.String(30), nullable=False)
    kw_pico = db.Column(db.Numeric(10, 2), nullable=False)
    status = db.Column(db.String(30), nullable=False, default='Implantacao')
    percentual_disponivel = db.Column(db.Integer, nullable=False, default=0)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    connections = db.relationship(
        'PlantConnection',
        back_populates='plant',
        cascade='all, delete-orphan'
    )

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'nome': self.nome,
            'uc': self.uc,
            'kwPico': str(self.kw_pico),
            'mediaGeracao': f'{self.kw_pico} kWp',
            'status': self.status,
            'percentualDisponivel': self.percentual_disponivel
        }