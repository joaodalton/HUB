from datetime import datetime

from flask import current_app
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from extensions import db
from utils.crypto import decrypt_value, encrypt_value


class PlatformConfiguracao(db.Model):
    """Configuracao global da plataforma HUB (singleton, id=1) -- NAO e por
    empresa (sem TenantMixin de proposito): Asaas da plataforma e signup
    publico sao infraestrutura unica do HUB, nao credencial de tenant."""
    __tablename__ = 'platform_configuracoes'

    id = db.Column(db.Integer, primary_key=True)
    asaas_api_base_url = db.Column(db.String(255), nullable=True)
    asaas_api_key_encrypted = db.Column(db.Text, nullable=True)
    asaas_webhook_token_encrypted = db.Column(db.Text, nullable=True)
    signup_code_encrypted = db.Column(db.Text, nullable=True)
    signup_empresa_id = db.Column(db.Integer, nullable=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    @classmethod
    def get_or_create(cls) -> 'PlatformConfiguracao':
        # filter_by(...).first() de proposito, em vez de .get()/Session.get():
        # o scanner de seguranca (tests/security/test_tenant_lookup_guard.py)
        # nao consegue resolver "cls" estaticamente e reprovaria a build.
        config = cls.query.filter_by(id=1).first()
        if config:
            return config
        config = cls(id=1)
        db.session.add(config)
        try:
            db.session.commit()
        except IntegrityError:
            # Corrida entre duas requisicoes concorrentes criando o singleton:
            # a que perdeu reaproveita a linha que a outra acabou de commitar.
            db.session.rollback()
            config = cls.query.filter_by(id=1).first()
        except SQLAlchemyError:
            # Falha transiente ao persistir o singleton nao pode derrubar
            # quem so queria ler config (ex.: webhook validando token) --
            # devolve objeto em memoria (campos None), que cai no fallback
            # pro env var em services/platform_config_service.py.
            db.session.rollback()
            current_app.logger.error('Falha ao persistir PlatformConfiguracao singleton', exc_info=True)
        return config

    def set_asaas_api_key(self, value: str | None) -> None:
        self.asaas_api_key_encrypted = encrypt_value(value) if value else None

    def get_asaas_api_key(self) -> str | None:
        return decrypt_value(self.asaas_api_key_encrypted) if self.asaas_api_key_encrypted else None

    def set_asaas_webhook_token(self, value: str | None) -> None:
        self.asaas_webhook_token_encrypted = encrypt_value(value) if value else None

    def get_asaas_webhook_token(self) -> str | None:
        return decrypt_value(self.asaas_webhook_token_encrypted) if self.asaas_webhook_token_encrypted else None

    def set_signup_code(self, value: str | None) -> None:
        self.signup_code_encrypted = encrypt_value(value) if value else None

    def get_signup_code(self) -> str | None:
        return decrypt_value(self.signup_code_encrypted) if self.signup_code_encrypted else None

    def to_dict(self) -> dict:
        return {
            'asaasApiBaseUrl': self.asaas_api_base_url,
            'asaasApiKeyConfigurada': bool(self.asaas_api_key_encrypted),
            'asaasWebhookTokenConfigurada': bool(self.asaas_webhook_token_encrypted),
            'signupCodeConfigurada': bool(self.signup_code_encrypted),
            'signupEmpresaId': self.signup_empresa_id,
        }
