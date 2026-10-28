"""send_email(): mensagem de erro visivel ao tenant nao vaza detalhe tecnico
de fornecedor externo (nome/URL de configuracao) -- detalhe bruto fica so em
metadados, pra debug."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_DB = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_DB.close()
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flask import g  # noqa: E402

from app import create_app  # noqa: E402
from config import Config  # noqa: E402
from extensions import db  # noqa: E402
from models.empresa import Empresa  # noqa: E402
from models.log_entry import LogEntry  # noqa: E402
from services import email_service  # noqa: E402
try:
    from .support import IsolatedTestRuntime  # noqa: E402
except ImportError:
    from support import IsolatedTestRuntime  # noqa: E402


class EmailServiceTest(IsolatedTestRuntime, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prepare_test_runtime(f"sqlite:///{_DB.name.replace(chr(92), '/')}", 'email-service-test')
        cls.app = create_app()
        with cls.app.app_context():
            db.create_all()
            db.session.add(Empresa(nome='A', slug='email-a'))
            db.session.commit()

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()
        os.unlink(_DB.name)
        cls.restore_test_runtime()

    def setUp(self):
        self.original_key = Config.RESEND_API_KEY
        Config.RESEND_API_KEY = 'test-key'

    def tearDown(self):
        Config.RESEND_API_KEY = self.original_key

    def test_send_failure_logs_friendly_message_without_vendor_detail(self):
        erro_resend = (
            'You can only send testing emails to your own email address. '
            'To send emails to other recipients, please verify a domain at resend.com/domains, '
            'and change the `from` address to an email using this domain.'
        )
        with self.app.test_request_context('/'):
            g.current_empresa_id = 1
            with patch('services.email_service.resend.Emails.send', side_effect=Exception(erro_resend)):
                email_service.send_email('publico@x.test', 'Assunto', '<p>x</p>')
            log = LogEntry.query.filter_by(acao='email_failed').order_by(LogEntry.id.desc()).first()
            self.assertIsNotNone(log)
            self.assertNotIn('resend.com', log.mensagem)
            self.assertNotIn('domain', log.mensagem.lower())
            self.assertEqual(log.metadados.get('erro'), erro_resend)


if __name__ == '__main__':
    unittest.main()
