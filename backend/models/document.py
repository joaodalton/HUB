# backend/models/document.py
from datetime import datetime

from extensions import db


class Document(db.Model):
    __tablename__ = 'documents'

    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)
    consumer_unit_id = db.Column(db.Integer, db.ForeignKey('consumer_units.id'), nullable=True)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False)

    nome = db.Column(db.String(255), nullable=False)
    # 'local' (arquivo salvo pelo backend) ou 'google_drive' (referencia a um file id do Drive).
    storage_provider = db.Column(db.String(30), nullable=False, default='local')
    storage_ref = db.Column(db.String(500), nullable=True)
    mime_type = db.Column(db.String(100), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Cascade só no Cliente (dono real do documento). UC e Categoria são
    # referências que podem sumir sem apagar o documento -- decisão
    # deliberada pra não perder documento por causa de reorganização de UC
    # ou remoção de categoria. Revisar se o comportamento esperado for outro.
    client = db.relationship('Client', backref=db.backref('documentos', cascade='all, delete-orphan'))
    consumer_unit = db.relationship('ConsumerUnit', backref=db.backref('documentos', lazy=True))
    category = db.relationship('Category', backref=db.backref('documentos', lazy=True))

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'nome': self.nome,
            'clienteId': self.client_id,
            'ucId': self.consumer_unit_id,
            'categoriaId': self.category_id,
            'categoria': self.category.nome if self.category else None,
            'storageProvider': self.storage_provider,
            'storageRef': self.storage_ref,
            'mimeType': self.mime_type
        }