"""Isolamento de estado global para fixtures que criam uma aplicacao Flask."""
import os

from config import Config
from extensions import limiter


class IsolatedTestRuntime:
    """Captura o ambiente/configuracao antes de preparar um app de teste."""

    @classmethod
    def prepare_test_runtime(cls, database_url, secret_key, encryption_key=None, limiter_enabled=None):
        cls._saved_environ = os.environ.copy()
        cls._saved_config = {
            key: value for key, value in Config.__dict__.items()
            if not key.startswith('__') and not callable(value)
        }
        cls._saved_limiter_enabled = limiter.enabled

        os.environ.update({
            'DATABASE_URL': database_url,
            'SECRET_KEY': secret_key,
            'FLASK_DEBUG': 'true',
        })
        # Config e' avaliada no import; configure-a explicitamente para este
        # app em vez de depender da ordem em que modulos de teste sao importados.
        Config.SQLALCHEMY_DATABASE_URI = database_url
        Config.SECRET_KEY = secret_key
        Config.DEBUG = True
        if encryption_key is not None:
            Config.SECRET_ENCRYPTION_KEY = encryption_key
        if limiter_enabled is not None:
            limiter.enabled = limiter_enabled

    @classmethod
    def restore_test_runtime(cls):
        os.environ.clear()
        os.environ.update(cls._saved_environ)
        for key in tuple(Config.__dict__):
            if not key.startswith('__') and key not in cls._saved_config:
                delattr(Config, key)
        for key, value in cls._saved_config.items():
            setattr(Config, key, value)
        limiter.enabled = cls._saved_limiter_enabled
