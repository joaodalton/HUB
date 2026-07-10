# backend/models/client.py
from datetime import datetime

from app import db


class Client(db.Model):
    __tablename__ = 'clients'

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), nullable=False)
    cpf = db.Column(db.String(20), nullable=False, unique=True)
    email = db.Column(db.String(150), nullable=False)
    concessionaria = db.Column(db.String(50), nullable=False, default='Copel')
    status = db.Column(db.String(30), nullable=False, default='Esperando usina')

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'nome': self.nome,
            'cpf': self.cpf,
            'email': self.email,
            'concessionaria': self.concessionaria,
            'status': self.status
        }