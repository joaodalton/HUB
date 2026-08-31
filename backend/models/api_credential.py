from datetime import datetime

from extensions import TenantMixin, db
from utils.crypto import decrypt_value, encrypt_value


class ApiCredential(TenantMixin, db.Model):
    """Credencial de integracao por empresa; segredo nunca e serializado."""
    __tablename__ = 'api_credentials'
    __table_args__ = (
        db.UniqueConstraint('empresa_id', 'provider', 'nome', name='uq_api_credentials_empresa_provider_nome'),
    )

    id = db.Column(db.Integer, primary_key=True)
    provider = db.Column(db.String(40), nullable=False)
    nome = db.Column(db.String(100), nullable=False)
    segredo_encrypted = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def set_segredo(self, segredo: str) -> None:
        self.segredo_encrypted = encrypt_value(segredo)

    def get_segredo(self) -> str:
        return decrypt_value(self.segredo_encrypted) or ''

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'provider': self.provider,
            'nome': self.nome,
            'configurada': bool(self.segredo_encrypted),
            'criadaEm': self.created_at.isoformat() if self.created_at else None,
            'atualizadaEm': self.updated_at.isoformat() if self.updated_at else None,
        }
