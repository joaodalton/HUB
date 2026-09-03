# backend/models/client.py
from datetime import datetime

from extensions import db
from extensions import TenantMixin


class Client(TenantMixin, db.Model):
    __tablename__ = 'clients'
    __table_args__ = (db.UniqueConstraint('empresa_id', 'cpf', name='uq_clients_empresa_cpf'),)

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), nullable=False)
    cpf = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(150), nullable=False)
    telefone = db.Column(db.String(20), nullable=True)
    concessionaria = db.Column(db.String(50), nullable=False, default='Copel')
    status = db.Column(db.String(30), nullable=False, default='Esperando usina')
    data_nascimento = db.Column(db.Date, nullable=True)
    asaas_customer_id = db.Column(db.String(100), nullable=True, index=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self) -> dict:
        first_uc = self.ucs[0] if self.ucs else None
        first_connection = first_uc.conexoes[0] if first_uc and first_uc.conexoes else None

        return {
            'id': self.id,
            'empresaId': self.empresa_id,
            'nome': self.nome,
            'cpf': self.cpf,
            'email': self.email,
            'telefone': self.telefone,
            'concessionaria': self.concessionaria,
            'status': self.status,
            'dataNascimento': self.data_nascimento.isoformat() if self.data_nascimento else None,
            'uc': first_uc.codigo if first_uc else '',
            'usina': first_connection.plant.nome if first_connection and first_connection.plant else 'A definir',
            'consumo': first_uc.consumo if first_uc else '',
            'ucs': [uc.to_dict() for uc in self.ucs],
            'documentos': []
        }
