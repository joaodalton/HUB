# backend/models/google_account.py
from datetime import datetime

from extensions import db
from utils.crypto import decrypt_value, encrypt_value


class GoogleAccount(db.Model):
    __tablename__ = 'google_accounts'

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), nullable=False, default='Conta Google')
    email = db.Column(db.String(150), nullable=False, unique=True)
    # Nunca guardar o refresh token em texto puro -- sempre passar por
    # set_refresh_token()/get_refresh_token(), que criptografam via utils/crypto.py.
    refresh_token_encrypted = db.Column(db.Text, nullable=True)
    scopes = db.Column(db.String(500), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def set_refresh_token(self, raw_token: str | None) -> None:
        self.refresh_token_encrypted = encrypt_value(raw_token)

    def get_refresh_token(self) -> str | None:
        return decrypt_value(self.refresh_token_encrypted)

    def to_dict(self) -> dict:
        # Token (criptografado ou não) nunca vai pro frontend -- só metadados.
        return {
            'id': self.id,
            'nome': self.nome,
            'email': self.email,
            'scopes': self.scopes.split(',') if self.scopes else [],
            'ativa': self.is_active
        }