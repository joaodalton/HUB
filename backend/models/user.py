# backend/models/user.py
from datetime import datetime

from extensions import db


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    papel = db.Column(db.String(30), nullable=False, default='admin')
    ativo = db.Column(db.Boolean, nullable=False, default=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self) -> dict:
        # Nunca inclui password_hash na resposta.
        return {
            'id': self.id,
            'email': self.email,
            'papel': self.papel,
            'ativo': self.ativo
        }