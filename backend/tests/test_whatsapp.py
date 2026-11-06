import hashlib
import hmac
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cryptography.fernet import Fernet

_DB = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_DB.close()
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app  # noqa: E402
from config import Config  # noqa: E402
from extensions import db  # noqa: E402
from models.empresa import Empresa  # noqa: E402
from models.message_template import MessageTemplate  # noqa: E402
from models.user import User  # noqa: E402
from models.whatsapp import WhatsappMessage  # noqa: E402
from utils.auth import generate_token  # noqa: E402
try:
    from .support import IsolatedTestRuntime  # noqa: E402
except ImportError:
    from support import IsolatedTestRuntime  # noqa: E402


class WhatsappTest(IsolatedTestRuntime, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prepare_test_runtime(f"sqlite:///{_DB.name.replace(chr(92), '/')}", 'whatsapp-test', encryption_key=Fernet.generate_key().decode())
        Config.META_APP_SECRET = 'meta-app-secret'
        Config.META_WEBHOOK_VERIFY_TOKEN = 'verify-token'
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        with cls.app.app_context():
            db.create_all()
            a, b = Empresa(nome='Empresa A', slug='whatsapp-a'), Empresa(nome='Empresa B', slug='whatsapp-b')
            db.session.add_all([a, b]); db.session.flush()
            a_user = User(empresa_id=a.id, nome='A', email='a@whatsapp.test', password_hash='x', role='owner')
            b_user = User(empresa_id=b.id, nome='B', email='b@whatsapp.test', password_hash='x', role='owner')
            db.session.add_all([a_user, b_user]); db.session.commit()
            cls.a, cls.b, cls.empresa_a = a_user.id, b_user.id, a.id

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove(); db.drop_all(); db.engine.dispose()
        os.unlink(_DB.name)
        cls.restore_test_runtime()

    def request(self, user, path, method='GET', body=None):
        with self.app.app_context():
            headers = {'Authorization': f'Bearer {generate_token(user)}'}
        return self.app.test_client().open(path, method=method, headers=headers, json=body)

    def configure(self, user, phone='5511999999999'):
        return self.request(user, '/api/v1/whatsapp/integracao', 'PUT', {
            'phoneNumberId': phone, 'businessAccountId': 'waba-1', 'accessToken': 'never-return-this-token', 'displayPhoneNumber': '+55 11 99999-9999',
        })

    def test_configuration_is_scoped_and_secret_is_never_returned(self):
        made = self.configure(self.a)
        self.assertEqual(made.status_code, 200)
        self.assertNotIn('never-return-this-token', made.get_data(as_text=True))
        self.assertIsNone(self.request(self.b, '/api/v1/whatsapp/integracao').get_json()['data'])
        self.assertEqual(self.configure(self.b).status_code, 400)  # mesmo numero nao pode cruzar tenants

    def test_template_submission_and_conversation_send_are_scoped(self):
        self.configure(self.a)
        template = self.request(self.a, '/api/v1/message-templates', 'POST', {
            'canal': 'whatsapp', 'chave': 'lembrete', 'nome': 'Lembrete', 'corpo': 'Ola {{ nome }}',
            'variaveisPermitidas': ['nome'], 'metaCategory': 'UTILITY',
        }).get_json()['data']
        with patch('services.whatsapp_service._meta_request', return_value={'id': 'meta-template-1', 'status': 'PENDING'}) as meta_request:
            submitted = self.request(self.a, f"/api/v1/whatsapp/templates/{template['id']}/submeter", 'POST')
        self.assertEqual(submitted.status_code, 200)
        self.assertEqual(submitted.get_json()['data']['metaStatus'], 'pending')
        self.assertEqual(meta_request.call_args.kwargs['json']['components'][0]['text'], 'Ola {{1}}')
        self.assertEqual(self.request(self.b, f"/api/v1/whatsapp/templates/{template['id']}/submeter", 'POST').status_code, 404)

        conversation = self.request(self.a, '/api/v1/whatsapp/conversas', 'POST', {'phoneNumber': '55 (11) 99999-0000', 'contactName': 'Cliente'}).get_json()['data']
        with patch('services.whatsapp_service._meta_request', return_value={'messages': [{'id': 'wamid-1'}]}):
            sent = self.request(self.a, f"/api/v1/whatsapp/conversas/{conversation['id']}/mensagens", 'POST', {'body': 'Ola'})
        self.assertEqual(sent.status_code, 200)
        self.assertEqual(sent.get_json()['data']['status'], 'sent')
        self.assertEqual(self.request(self.b, f"/api/v1/whatsapp/conversas/{conversation['id']}/mensagens").status_code, 404)
        with self.app.app_context():
            self.assertIsNotNone(WhatsappMessage.query.filter_by(empresa_id=self.empresa_a, meta_message_id='wamid-1').first())

    def test_signed_webhook_records_only_the_matching_company(self):
        self.configure(self.a)
        payload = {'entry': [{'changes': [{'value': {
            'metadata': {'phone_number_id': '5511999999999'},
            'contacts': [{'wa_id': '5511999999999', 'profile': {'name': 'Contato'}}],
            'messages': [{'id': 'wamid-inbound', 'from': '5511999999999', 'timestamp': '1700000000', 'type': 'text', 'text': {'body': 'Oi'}}],
        }}]}]}
        import json
        raw = json.dumps(payload).encode()
        signature = 'sha256=' + hmac.new(Config.META_APP_SECRET.encode(), raw, hashlib.sha256).hexdigest()
        response = self.app.test_client().post('/api/v1/webhooks/whatsapp', data=raw, content_type='application/json', headers={'X-Hub-Signature-256': signature})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.request(self.a, '/api/v1/whatsapp/conversas').get_json()['data'][0]['unreadCount'], 1)
        self.assertEqual(self.request(self.b, '/api/v1/whatsapp/conversas').get_json()['data'], [])
        self.assertEqual(self.app.test_client().post('/api/v1/webhooks/whatsapp', json=payload).status_code, 403)


if __name__ == '__main__':
    unittest.main()
