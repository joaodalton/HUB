"""C5.5-D: PDF em memória sem vínculo cadastral ou efeitos operacionais."""
import sys
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app
from extensions import db
from models.calculo_cobranca import BillingCalculationExecution, BillingCalculationSnapshot
from models.client import Client
from models.consumer_unit import ConsumerUnit
from models.empresa import Empresa
from models.fatura_concessionaria import FaturaConcessionaria
from models.pendencia import Pendencia
from models.user import User
from services.fatura_concessionaria_upload_service import _validate_pdf
from utils.auth import generate_token

try:
    from .support import IsolatedTestRuntime
    from .fixtures.invoices.copel.build_fixture import ITEMS, make_pdf
except ImportError:
    from support import IsolatedTestRuntime
    from fixtures.invoices.copel.build_fixture import ITEMS, make_pdf


class BillingPdfLabRoutesTest(IsolatedTestRuntime, unittest.TestCase):
    url = '/api/v1/platform/billing-diagnostics/pdf'

    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.prepare_test_runtime('sqlite:///' + (Path(cls.temp.name) / 'lab.db').as_posix(),
                                 'billing-pdf-lab-test', limiter_enabled=False)
        cls.app = create_app()

    @classmethod
    def tearDownClass(cls):
        cls.restore_test_runtime()
        cls.temp.cleanup()

    def setUp(self):
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        for tenant in (10, 20):
            db.session.add(Empresa(id=tenant, nome=f'Empresa {tenant}', slug=f'lab-{tenant}'))
        db.session.add(User(id=1, empresa_id=10, nome='admin', email='admin@example.test',
                            password_hash='x', role='viewer', is_platform_admin=True))
        db.session.add(User(id=2, empresa_id=20, nome='viewer', email='viewer@example.test',
                            password_hash='x', role='viewer', is_platform_admin=False))
        db.session.commit()
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.rollback()
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        self.ctx.pop()

    def headers(self, user_id):
        return {'Authorization': f'Bearer {generate_token(user_id)}'}

    def upload(self, payload, *, user_id=1, filename='copel.pdf', mimetype='application/pdf'):
        return self.client.post(self.url, headers=self.headers(user_id),
            data={'arquivo': (BytesIO(payload), filename, mimetype)})

    def test_preflight_and_authorization(self):
        response = self.client.options(self.url, headers={
            'Origin': 'http://localhost:5173',
            'Access-Control-Request-Method': 'POST',
            'Access-Control-Request-Headers': 'Content-Type',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get('Access-Control-Allow-Origin'), 'http://localhost:5173')
        self.assertIsNone(self.client.options(self.url, headers={
            'Origin': 'https://untrusted.example', 'Access-Control-Request-Method': 'POST',
        }).headers.get('Access-Control-Allow-Origin'))
        self.assertEqual(self.client.post(self.url).status_code, 401)
        self.assertEqual(self.upload(b'%PDF-invalid', user_id=2).status_code, 403)

    def test_real_anon_fixture_is_diagnosed_without_database_writes(self):
        document = (Path(__file__).parent / 'fixtures/invoices/copel/core_anon.pdf').read_bytes()
        response = self.upload(document, filename='../copel.pdf')
        self.assertEqual(response.status_code, 200)
        data = response.json['data']
        self.assertEqual(data['pdf']['name'], 'copel.pdf')
        self.assertEqual(data['pdf']['sizeBytes'], len(document))
        self.assertEqual(data['normalized']['empresa_id'], None)
        self.assertEqual(data['normalized']['client_id'], None)
        self.assertEqual(data['normalized']['consumer_unit_id'], None)
        self.assertEqual(data['extracted']['identity']['parser_name'], 'copel')
        self.assertEqual(data['extractionStatus'], 'SUCCESS')
        self.assertEqual(data['normalizationStatus'], 'NORMALIZED')
        self.assertEqual(data['billingEligibility']['status'], 'UNSUPPORTED')
        self.assertFalse(data['billingEligibility']['eligible'])
        self.assertEqual(data['status'], 'NORMALIZED')
        self.assertEqual([row['stage'] for row in data['stages']], [
            'UPLOAD', 'EXTRACTION', 'NORMALIZATION', 'UC_MATCHING', 'RULE_RESOLUTION',
            'TARIFF_RESOLUTION', 'ENERGY_RESOLUTION', 'COMMERCIAL_DEDUCTIONS',
            'FIO_B', 'FINAL_CALCULATION', 'SNAPSHOT',
        ])
        self.assertEqual(next(row for row in data['stages'] if row['stage'] == 'RULE_RESOLUTION')['status'],
                         'NOT_EXECUTED')
        self.assertEqual(next(row for row in data['stages'] if row['stage'] == 'UC_MATCHING')['status'],
                         'SKIPPED')
        self.assertTrue(all(row['status'] == 'NOT_EXECUTED' for row in data['stages'][7:]))
        for model in (Client, ConsumerUnit, FaturaConcessionaria,
                      BillingCalculationExecution, BillingCalculationSnapshot, Pendencia):
            self.assertEqual(db.session.query(model).count(), 0)

    def test_missing_fields_and_invalid_upload(self):
        response = self.upload(make_pdf(omitted=('classification',)))
        self.assertEqual(response.status_code, 200)
        self.assertIn('classe_tarifaria', response.json['data']['missingFields'])
        invalid = self.upload(b'%PDF-invalid')
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(invalid.json['code'], 'INVALID_PDF')
        self.assertEqual(self.upload(b'not a pdf', filename='bad.txt').json['code'],
                         'INVALID_FILE_TYPE')

    def test_limit_cleanup_and_sanitized_parser_failure(self):
        document = (Path(__file__).parent / 'fixtures/invoices/copel/core_anon.pdf').read_bytes()
        original_limit = self.app.config['FATURA_CONCESSIONARIA_MAX_BYTES']
        self.app.config['FATURA_CONCESSIONARIA_MAX_BYTES'] = 10
        try:
            self.assertEqual(self.upload(document).status_code, 413)
        finally:
            self.app.config['FATURA_CONCESSIONARIA_MAX_BYTES'] = original_limit
        captured = []

        def validate(uploaded):
            captured.append(uploaded)
            return _validate_pdf(uploaded)

        with patch('routes.billing_pdf_lab_routes._validate_pdf', side_effect=validate), \
             patch('services.billing_pdf_lab_service.MinimalExtractor.extract',
                   side_effect=RuntimeError('private path and token must stay hidden')):
            response = self.upload(document)
        self.assertTrue(captured[0].stream.closed)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['data']['status'], 'ERROR')
        self.assertEqual(response.json['data']['error']['code'], 'PDF_DIAGNOSTIC_FAILED')
        self.assertNotIn('private path', response.get_data(as_text=True))
        self.assertEqual(response.json['data']['stages'][1]['status'], 'FAILED')
        self.assertEqual(response.json['data']['stages'][-1]['status'], 'NOT_EXECUTED')

    def test_compensation_te_tusd_is_one_physical_volume(self):
        items = (*ITEMS, *(
            (f'ENERGIA INJ. OUC MPT {kind} 08/2026 GDII-II', 'kWh', '-1000',
             '0,234567', '-234,56', '0,00', '0,00', '0,123456')
            for kind in ('TE', 'TUSD')
        ))
        response = self.upload(make_pdf(items=items, changes={'reference': '08/2026'}))
        self.assertEqual(response.status_code, 200)
        data = response.json['data']
        self.assertEqual(data['normalized']['billing_energy_input']['status'], 'VALID')
        self.assertEqual(data['normalized']['billing_energy_input']['energia_compensada_cobravel_kwh'],
                         '1000')
        self.assertEqual(len(data['compensations']), 1)
        self.assertEqual(len(data['compensations'][0]['componentes']), 2)


if __name__ == '__main__':
    unittest.main()
