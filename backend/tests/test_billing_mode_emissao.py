"""Task 5: modo unificada/separada aplicado na emissao, link de pagamento e debito automatico da UC.

Usa o calculo real (fixture Copel anonimizada, como no e2e) e um cliente ASAAS simulado.
"""
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
from flask import g
from app import create_app
from extensions import db
from models.calculo_cobranca import BillingCalculationExecution
from models.client import Client
from models.consumer_unit import ConsumerUnit
from models.document import Document
from models.empresa import Empresa
from models.fatura import Fatura
from models.fatura_concessionaria import FaturaConcessionaria
from models.grupo_regra_cobranca import GrupoRegraCobranca
from models.regra_cobranca_assignment import RegraCobrancaAssignment
from models.user import User
from services import fatura_service
from services.asaas_client import AsaasError
from services.fatura_service import resolve_billing_mode
from services.invoice_normalization_service import InvoiceNormalizer, json_safe
from services.invoice_parsers.copel import CopelDANF3EParser
from services.invoice_parsers.schemas import ExtractedField
from utils.auth import generate_token

try:
    from .support import IsolatedTestRuntime
except ImportError:
    from support import IsolatedTestRuntime


FIXTURES = Path(__file__).parent / 'fixtures/invoices/copel'
COPEL = Decimal('71.05')


class BillingModeEmissaoTest(IsolatedTestRuntime, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.prepare_test_runtime('sqlite:///' + (Path(cls.temp.name) / 'mode.db').as_posix(),
                                 'billing-mode-emissao', limiter_enabled=False)
        cls.app = create_app()

    @classmethod
    def tearDownClass(cls):
        cls.restore_test_runtime()
        cls.temp.cleanup()

    def setUp(self):
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        for tenant in (1, 2):
            db.session.add(Empresa(id=tenant, nome=f'Empresa {tenant}', slug=f'mode-{tenant}'))
            db.session.add(Client(id=tenant, empresa_id=tenant, nome='Cliente', cpf=f'{tenant:011d}',
                                  email=f'cliente{tenant}@mode.test', asaas_customer_id=f'cus_{tenant}'))
            db.session.add(ConsumerUnit(id=tenant, empresa_id=tenant, client_id=tenant,
                                        codigo=f'{tenant:015d}'))
            db.session.add(User(id=tenant, empresa_id=tenant, nome='Owner',
                                email=f'owner{tenant}@mode.test', password_hash='x', role='owner'))
        db.session.add(GrupoRegraCobranca(
            id=1, empresa_id=1, nome='Regra', ativo=True, padrao=False, revision=1,
            calculation_method='energia_compensada', tariff_source='invoice',
            manual_tariff=Decimal('0.70'), discount_type='none', tariff_basis='compensated',
            billing_mode='unified', due_date_basis='invoice_due_date', due_date_offset_days=0))
        db.session.add(RegraCobrancaAssignment(empresa_id=1, grupo_regra_cobranca_id=1,
                                                scope_type='company', ativo=True))
        db.session.add(Document(id=2, empresa_id=2, client_id=2, nome='b.pdf', storage_provider='google_drive'))
        db.session.add(FaturaConcessionaria(id=2, empresa_id=2, client_id=2, document_id=2,
                                            arquivo_hash='2' * 64))
        db.session.add(Document(id=1, empresa_id=1, client_id=1, nome='a.pdf', storage_provider='google_drive'))
        db.session.add(FaturaConcessionaria(id=1, empresa_id=1, client_id=1, document_id=1,
                                            arquivo_hash='1' * 64))
        db.session.commit()
        self.http = self.app.test_client()
        self.posts = 0
        self.remote = {}
        self.fail_post = False
        patcher = patch.object(fatura_service, 'AsaasClient')
        self.asaas = patcher.start().return_value
        self.addCleanup(patcher.stop)
        self.asaas.criar_cobranca.side_effect = self._post
        self.asaas.consultar_por_referencia.side_effect = lambda ref: self.remote.get(ref)

    def tearDown(self):
        db.session.rollback()
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        self.ctx.pop()

    def _post(self, payload):
        self.posts += 1
        if self.fail_post:
            raise AsaasError('timeout')
        payment = {**payload, 'id': f'pay_{self.posts}', 'status': 'PENDING',
                   'bankSlipUrl': 'https://example.test/boleto',
                   'invoiceUrl': 'https://example.test/fatura'}
        self.remote[payload['externalReference']] = payment
        return payment

    def headers(self, user_id=1):
        return {'Authorization': f'Bearer {generate_token(user_id)}'}

    def _prepare_invoice(self):
        """Fatura extraida e validada da UC 1, pronta para calculo (GD comprovada)."""
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
                                                   fatura_concessionaria_id=1)
        invoice = db.session.get(FaturaConcessionaria, 1)
        invoice.consumer_unit_id = 1
        invoice.status_extracao = 'extraida'
        invoice.status_validacao = 'valida'
        invoice.dados_normalizados = {
            'invoice': json_safe(replace(normalized, consumer_unit_id=1)),
            'validation': {'status': 'valida', 'consumer_unit_id': 1,
                           'uc_numero': f'{1:015d}', 'issues': []},
        }
        invoice.competencia = '2030-08'
        invoice.parser_name = normalized.identity.parser_name
        invoice.parser_version = normalized.identity.parser_version
        invoice.layout_name = normalized.identity.layout_name
        invoice.layout_version = normalized.identity.layout_version
        invoice.data_vencimento = date(2030, 9, 5)
        invoice.valor_total_concessionaria = COPEL
        db.session.commit()

    def _set_rule(self, mode, debito=False):
        db.session.get(GrupoRegraCobranca, 1).billing_mode = mode
        db.session.get(ConsumerUnit, 1).debito_automatico = debito
        db.session.commit()

    def _gerar(self, invoice_id=1, user_id=1):
        return self.http.post(f'/api/v1/billing-calculations/invoices/{invoice_id}/gerar-boleto',
                              headers=self.headers(user_id))

    def _hub_amount(self):
        execution = BillingCalculationExecution.query.filter_by(
            empresa_id=1, fatura_concessionaria_id=1).order_by(BillingCalculationExecution.id.desc()).first()
        self.assertEqual(execution.status, 'CALCULATED')
        return execution.snapshot.valor_final

    def test_resolve_billing_mode(self):
        self.assertEqual(resolve_billing_mode('unified', True), 'unified')
        self.assertEqual(resolve_billing_mode('separate', False), 'separate')
        self.assertEqual(resolve_billing_mode('auto', True), 'separate')
        self.assertEqual(resolve_billing_mode('auto', False), 'unified')
        with self.assertRaises(ValueError):
            resolve_billing_mode('bogus', False)

    def test_unified_charges_hub_plus_concessionaria_and_stores_links(self):
        self._prepare_invoice()
        response = self._gerar()
        self.assertEqual(response.status_code, 201, response.json)
        hub = self._hub_amount()
        fatura = Fatura.query.one()
        self.assertEqual((fatura.valor, fatura.billing_mode), (hub + COPEL, 'unified'))
        data = response.json['data']
        self.assertEqual((data['billingMode'], data['invoiceUrl'], data['boletoUrl'], data['faturaConcessionariaId']),
                         ('unified', 'https://example.test/fatura', 'https://example.test/boleto', 1))
        self.assertEqual((fatura.invoice_url, fatura.boleto_url),
                         ('https://example.test/fatura', 'https://example.test/boleto'))

    def test_separate_charges_only_hub_amount(self):
        self._prepare_invoice()
        self._set_rule('separate')
        self.assertEqual(self._gerar().status_code, 201)
        fatura = Fatura.query.one()
        self.assertEqual((fatura.valor, fatura.billing_mode), (self._hub_amount(), 'separate'))

    def test_auto_follows_uc_debito_automatico(self):
        self._prepare_invoice()
        self._set_rule('auto', debito=True)
        self.assertEqual(self._gerar().json['data']['billingMode'], 'separate')

    def test_auto_without_debito_is_unified(self):
        self._prepare_invoice()
        self._set_rule('auto', debito=False)
        self.assertEqual(self._gerar().json['data']['billingMode'], 'unified')

    def test_pending_emission_is_reemitted_with_stored_data_and_never_recalculated(self):
        self._prepare_invoice()
        self.fail_post = True
        first = self._gerar()
        self.assertEqual(first.status_code, 409, first.json)
        pending = Fatura.query.one()
        stored = (pending.valor, pending.billing_mode)
        self.assertEqual(stored[1], 'unified')
        # A regra muda e o POST do primeiro envio chega ao ASAAS tardiamente.
        self._set_rule('separate')
        self.fail_post = False
        self.remote[pending.external_reference] = {
            'id': 'pay_late', 'externalReference': pending.external_reference,
            'customer': 'cus_1', 'billingType': 'BOLETO', 'value': float(pending.valor),
            'dueDate': '2030-09-05', 'status': 'PENDING', 'bankSlipUrl': 'https://example.test/boleto'}
        second = self._gerar()
        self.assertEqual(second.status_code, 201, second.json)
        self.assertEqual(Fatura.query.count(), 1)
        fatura = Fatura.query.one()
        self.assertEqual(((fatura.valor, fatura.billing_mode), fatura.asaas_id), (stored, 'pay_late'))
        self.assertEqual(self.posts, 1)
        self.assertEqual(BillingCalculationExecution.query.count(), 1)

    def test_active_boleto_is_idempotent(self):
        self._prepare_invoice()
        first = self._gerar()
        second = self._gerar()
        self.assertEqual((first.status_code, second.status_code), (201, 201))
        self.assertEqual(first.json['data']['id'], second.json['data']['id'])
        self.assertEqual((self.posts, Fatura.query.count()), (1, 1))

    def test_blocked_calculation_returns_stage_and_blockers_without_posting(self):
        self._prepare_invoice()
        RegraCobrancaAssignment.query.update({'ativo': False})
        db.session.commit()
        response = self._gerar()
        self.assertEqual(response.status_code, 422, response.json)
        self.assertEqual(response.json['code'], 'BILLING_CALCULATION_REQUIRED')
        self.assertEqual(response.json['details']['stage'], 'RULE_RESOLUTION')
        self.assertIn('NO_RULE_CONFIGURED', response.json['details']['blockers'])
        self.assertEqual((self.posts, Fatura.query.count()), (0, 0))

    def test_client_without_email_is_rejected(self):
        self._prepare_invoice()
        db.session.get(Client, 1).email = ''
        db.session.commit()
        response = self._gerar()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json['error'], 'Cliente sem email cadastrado.')
        self.assertEqual(self.posts, 0)

    def test_other_tenant_invoice_answers_404(self):
        self.assertEqual(self._gerar(invoice_id=2, user_id=1).status_code, 404)
        self.assertEqual(self._gerar(invoice_id=1, user_id=2).status_code, 404)

    def test_manual_emission_without_billing_mode_keeps_null(self):
        with self.app.test_request_context('/'):
            g.current_empresa_id = 1
            fatura_service.emitir({'clienteId': 1, 'ucId': 1, 'valor': '10.00',
                                   'competencia': '2030-08', 'mesVencimento': '2030-09-05'}, 1, 1)
        self.assertIsNone(Fatura.query.one().billing_mode)

    def test_uc_debito_automatico_roundtrip_and_rejects_non_boolean(self):
        self.assertIs(self.http.get('/api/v1/ucs/1', headers=self.headers()).json['data']['debitoAutomatico'], False)
        ok = self.http.put('/api/v1/ucs/1', json={'debitoAutomatico': True}, headers=self.headers())
        self.assertEqual(ok.status_code, 200, ok.json)
        self.assertIs(ok.json['data']['debitoAutomatico'], True)
        self.assertIs(self.http.get('/api/v1/ucs/1', headers=self.headers()).json['data']['debitoAutomatico'], True)
        for bad in ('true', 1, None, []):
            response = self.http.put('/api/v1/ucs/1', json={'debitoAutomatico': bad}, headers=self.headers())
            self.assertEqual(response.status_code, 400, bad)
            self.assertEqual(response.json['code'], 'INVALID_DEBITO_AUTOMATICO')
        self.assertIs(db.session.get(ConsumerUnit, 1).debito_automatico, True)


if __name__ == '__main__':
    unittest.main()
