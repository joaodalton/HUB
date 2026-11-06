"""E2E via HTTP real: upload de fatura da concessionaria -> calculo -> boleto (Asaas mockado).

Cobre a lacuna citada em PROGRESS.md ("CI sem e2e... dado o historico de hotfixes de
upload, Hotfix F6.2"). Reaproveita as fixtures Copel anonimizadas e os padroes de
mock ja usados em test_fatura_concessionaria_upload.py, test_billing_calculation_service.py
e test_billing_calculation_routes.py -- nenhuma regra de negocio e alterada aqui.
"""
import hashlib
import io
import json
import sys
import tempfile
import unittest
from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app
from extensions import db
from models.client import Client
from models.consumer_unit import ConsumerUnit
from models.document import Document
from models.empresa import Empresa
from models.fatura_concessionaria import FaturaConcessionaria
from models.grupo_regra_cobranca import GrupoRegraCobranca
from models.regra_cobranca_assignment import RegraCobrancaAssignment
from models.user import User
from services import fatura_service
from services import fatura_concessionaria_upload_service as upload_service
from services.invoice_normalization_service import InvoiceNormalizer, json_safe
from services.invoice_parsers.copel import CopelDANF3EParser
from services.invoice_parsers.schemas import ExtractedField
from utils.auth import generate_token

try:
    from .support import IsolatedTestRuntime
except ImportError:
    from support import IsolatedTestRuntime


FIXTURES = Path(__file__).parent / 'fixtures/invoices/copel'


class FakeObjectStore:
    provider = 's3'

    def __init__(self):
        self.files = {}

    def put(self, key, data, content_type):
        self.files[key] = data

    def read(self, key, max_bytes):
        return self.files[key][:max_bytes + 1]

    def delete(self, key):
        self.files.pop(key, None)


class E2EUploadCalculoCobrancaTest(IsolatedTestRuntime, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.prepare_test_runtime('sqlite:///' + (Path(cls.temp.name) / 'e2e.db').as_posix(),
                                  'e2e-upload-calculo-cobranca', limiter_enabled=False)
        cls.app = create_app()

    @classmethod
    def tearDownClass(cls):
        cls.restore_test_runtime()
        cls.temp.cleanup()

    def setUp(self):
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        db.session.add(Empresa(id=1, nome='Empresa E2E', slug='e2e-cobranca'))
        db.session.add(Client(id=1, empresa_id=1, nome='Cliente E2E', cpf='11111111111',
                               email='cliente@e2e.test'))
        db.session.add(ConsumerUnit(id=1, empresa_id=1, client_id=1, codigo='000000000000001'))
        db.session.add(User(id=1, empresa_id=1, nome='Owner', email='owner@e2e.test',
                             password_hash='x', role='owner'))
        db.session.add(GrupoRegraCobranca(
            id=1, empresa_id=1, nome='Regra', ativo=True, padrao=False, revision=1,
            calculation_method='energia_compensada', tariff_source='invoice',
            manual_tariff=Decimal('0.70'), discount_type='none', tariff_basis='compensated',
            billing_mode='auto', due_date_basis='invoice_due_date', due_date_offset_days=0,
        ))
        db.session.add(RegraCobrancaAssignment(empresa_id=1, grupo_regra_cobranca_id=1,
                                                scope_type='company', ativo=True))
        db.session.commit()
        self.client = self.app.test_client()
        self.store = FakeObjectStore()
        self.store_patch = patch.object(upload_service, 'get_object_storage', return_value=self.store)
        self.store_patch.start()

    def tearDown(self):
        self.store_patch.stop()
        db.session.rollback()
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        self.ctx.pop()

    def headers(self):
        return {'Authorization': f'Bearer {generate_token(1)}'}

    def _upload(self):
        body = (FIXTURES / 'core_anon.pdf').read_bytes()
        response = self.client.post(
            '/api/v1/clients/1/invoices/upload', headers=self.headers(),
            data={'arquivo': (io.BytesIO(body), 'fatura.pdf', 'application/pdf')},
            content_type='multipart/form-data',
        )
        return response, body

    def _confirm_gd_compensation(self, invoice_id):
        # shortcut: a comprovacao real de energia compensada GD chega por um fluxo
        # assincrono separado (gd_compensation_pending_service), fora do escopo deste
        # e2e; aqui replicamos o merge usado em test_billing_calculation_service.py
        # para simular sua conclusao antes de acionar o calculo real via HTTP.
        parser = CopelDANF3EParser()
        parsed = parser.parse((FIXTURES / 'core_anon.pdf').read_bytes())
        rows = json.loads((FIXTURES / 'gd_events_sanitized.json').read_text(encoding='utf-8')
                           )['ouc_gdi_gdii_2026_09'][:2]

        def field(value):
            return ExtractedField('found', value, Decimal('0.95'), 'sanitized:copel-real')

        items = tuple({
            'descricao_original': field(row['label']), 'unidade': field('kWh'),
            'quantidade': field(Decimal(row['quantity_kwh'])),
            'tarifa_unitaria': field(Decimal(row['tariff_unit'])),
            'preco_unitario_com_tributos': field(Decimal(row['taxed_unit_price'])),
        } for row in rows)
        components, _, _ = parser._energy(items, field(Decimal('0')))
        parsed = replace(parsed, itens=parsed.itens + items,
                          energy_components=parsed.energy_components + components,
                          compensation_supported=True)
        normalized = InvoiceNormalizer().normalize(parsed, empresa_id=1, client_id=1,
                                                    fatura_concessionaria_id=invoice_id)
        invoice = db.session.get(FaturaConcessionaria, invoice_id)
        invoice.dados_normalizados = {
            'invoice': json_safe(replace(normalized, consumer_unit_id=1)),
            'validation': {'status': 'valida', 'consumer_unit_id': 1,
                            'uc_numero': '000000000000001', 'issues': []},
        }
        invoice.competencia = '2030-08'
        invoice.parser_name = normalized.identity.parser_name
        invoice.parser_version = normalized.identity.parser_version
        invoice.layout_name = normalized.identity.layout_name
        invoice.layout_version = normalized.identity.layout_version
        db.session.commit()

    def test_upload_calculo_e_emissao_de_boleto_via_http_real(self):
        upload_response, body = self._upload()
        self.assertEqual(upload_response.status_code, 201, upload_response.json)
        invoice_id = upload_response.json['data']['invoiceId']
        invoice = db.session.get(FaturaConcessionaria, invoice_id)
        self.assertEqual(invoice.status_extracao, 'extraida')
        self.assertEqual(invoice.consumer_unit_id, 1)
        self.assertEqual(invoice.arquivo_hash, hashlib.sha256(body).hexdigest())

        self._confirm_gd_compensation(invoice_id)

        execute_response = self.client.post(
            f'/api/v1/billing-calculations/invoices/{invoice_id}/execute',
            headers=self.headers())
        self.assertEqual(execute_response.status_code, 201, execute_response.json)
        self.assertEqual(execute_response.json['data']['status'], 'CALCULATED')
        self.assertIsNotNone(execute_response.json['data']['snapshotId'])

        db.session.get(Client, 1).asaas_customer_id = 'cus_e2e'
        invoice = db.session.get(FaturaConcessionaria, invoice_id)
        invoice.data_vencimento = date(2030, 9, 5)
        # shortcut: valor_total_concessionaria do PDF real exigiria mais casas decimais
        # do que a coluna Numeric aceita (ver comentario em fatura_processing_service.py);
        # fora do escopo deste e2e, fixamos o valor liquido faturado pela concessionaria.
        invoice.valor_total_concessionaria = Decimal('50.00')
        db.session.commit()

        with patch.object(fatura_service, 'AsaasClient') as asaas_cls:
            asaas = asaas_cls.return_value
            asaas.criar_cobranca.side_effect = lambda payload: {
                'id': 'pay_e2e', 'externalReference': payload['externalReference'],
                'customer': payload['customer'], 'billingType': 'BOLETO',
                'value': payload['value'], 'dueDate': payload['dueDate'],
                'status': 'PENDING', 'bankSlipUrl': 'https://example.test/boleto-e2e',
            }
            boleto_response = self.client.post(
                f'/api/v1/billing-calculations/invoices/{invoice_id}/gerar-boleto',
                headers=self.headers())
        self.assertEqual(boleto_response.status_code, 201, boleto_response.json)
        self.assertEqual(boleto_response.json['data']['asaasId'], 'pay_e2e')
        asaas.criar_cobranca.assert_called_once()

    def test_upload_failure_returns_503_when_storage_is_unavailable(self):
        """Hotfix F6.2: falha de armazenamento apos a extracao vira 503 sem persistir nada."""
        with patch.object(self.store, 'put', side_effect=RuntimeError('indisponivel')):
            response, _ = self._upload()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json['code'], 'DOCUMENT_STORAGE_UNAVAILABLE')
        self.assertEqual((Document.query.count(), FaturaConcessionaria.query.count()), (0, 0))


if __name__ == '__main__':
    unittest.main()
