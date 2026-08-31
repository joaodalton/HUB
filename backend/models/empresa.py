# backend/models/empresa.py
from datetime import datetime

from extensions import db


class Empresa(db.Model):
    __tablename__ = 'empresas'

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), nullable=False)
    razao_social = db.Column(db.String(200), nullable=True)
    cnpj = db.Column(db.String(20), nullable=True)
    email = db.Column(db.String(150), nullable=True)
    telefone = db.Column(db.String(20), nullable=True)
    status = db.Column(db.String(20), nullable=False, default='ativa')
    slug = db.Column(db.String(60), nullable=False, unique=True)

    # Documentos fixos usados na geracao do formulario Copel de rateio
    # (cartao CNPJ + estatuto da associacao) -- reaproveita o model Document
    # ja existente (mesmo storage/upload que ja serve Cliente/UC), so guarda
    # a referencia de "qual e o documento atual de cada tipo" aqui.
    documento_cnpj_id = db.Column(db.Integer, db.ForeignKey('documents.id'), nullable=True)
    documento_estatuto_id = db.Column(db.Integer, db.ForeignKey('documents.id'), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    documento_cnpj = db.relationship('Document', foreign_keys=[documento_cnpj_id])
    documento_estatuto = db.relationship('Document', foreign_keys=[documento_estatuto_id])

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'nome': self.nome,
            'razaoSocial': self.razao_social,
            'cnpj': self.cnpj,
            'email': self.email,
            'telefone': self.telefone,
            'status': self.status,
            'slug': self.slug,
            'documentoCnpj': self.documento_cnpj.to_dict() if self.documento_cnpj else None,
            'documentoEstatuto': self.documento_estatuto.to_dict() if self.documento_estatuto else None
        }