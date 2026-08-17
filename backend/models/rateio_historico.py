# backend/models/rateio_historico.py
from datetime import datetime

from extensions import db


class RateioHistorico(db.Model):
    __tablename__ = 'rateio_historico'

    id = db.Column(db.Integer, primary_key=True)
    competencia = db.Column(db.String(7), nullable=False)  # 'YYYY-MM'
    plant_id = db.Column(db.Integer, db.ForeignKey('plants.id'), nullable=False)
    consumer_unit_id = db.Column(db.Integer, db.ForeignKey('consumer_units.id'), nullable=False)
    percentual = db.Column(db.Numeric(5, 2), nullable=False)
    consumo_considerado = db.Column(db.Numeric(10, 2), nullable=True)
    producao_considerada = db.Column(db.Numeric(10, 2), nullable=True)
    manual = db.Column(db.Boolean, nullable=False, default=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    plant = db.relationship('Plant')
    consumer_unit = db.relationship('ConsumerUnit')

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'competencia': self.competencia,
            'plantId': self.plant_id,
            'usinaNome': self.plant.nome if self.plant else None,
            'ucId': self.consumer_unit_id,
            'ucCodigo': self.consumer_unit.codigo if self.consumer_unit else None,
            'percentual': float(self.percentual),
            'consumoConsiderado': float(self.consumo_considerado) if self.consumo_considerado is not None else None,
            'producaoConsiderada': float(self.producao_considerada) if self.producao_considerada is not None else None,
            'manual': self.manual,
            'criadoEm': self.created_at.isoformat() if self.created_at else None
        }