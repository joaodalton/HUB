# backend/models/client.py
from datetime import datetime

from extensions import db


class Client(db.Model):
    __tablename__ = 'clients'

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), nullable=False)
    cpf = db.Column(db.String(20), nullable=False, unique=True)
    email = db.Column(db.String(150), nullable=False)
    telefone = db.Column(db.String(20), nullable=True)
    concessionaria = db.Column(db.String(50), nullable=False, default='Copel')
    status = db.Column(db.String(30), nullable=False, default='Esperando usina')

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self) -> dict:
        first_uc = self.ucs[0] if self.ucs else None
        first_connection = first_uc.conexoes[0] if first_uc and first_uc.conexoes else None

        return {
            'id': self.id,
            'nome': self.nome,
            'cpf': self.cpf,
            'email': self.email,
            'telefone': self.telefone,
            'concessionaria': self.concessionaria,
            'status': self.status,
            'uc': first_uc.codigo if first_uc else '',
            'usina': first_connection.plant.nome if first_connection and first_connection.plant else 'A definir',
            'consumo': first_uc.consumo if first_uc else '',
            'ucs': [uc.to_dict() for uc in self.ucs],
            'documentos': []
        }