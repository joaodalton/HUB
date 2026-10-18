from datetime import date, timedelta
import hashlib
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from sqlalchemy.orm.attributes import flag_modified

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from flask import g
from app import create_app
from extensions import db
from models.client import Client
from models.consumer_unit import ConsumerUnit, PlantConnection
from models.document import Document
from models.empresa import Empresa
from models.fatura_concessionaria import FaturaConcessionaria
from models.pendencia import Pendencia
from models.plant import Plant
from services.fatura_processing_service import FaturaProcessingService
from services.invoice_parsers.registry import ParserRegistry
try:
    from .support import IsolatedTestRuntime
except ImportError:
    from support import IsolatedTestRuntime


class InvoicePersistenceTest(IsolatedTestRuntime, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prepare_test_runtime('sqlite://', 'f7-persistence-test')
        cls.app = create_app()
        cls.document = (Path(__file__).parent / 'fixtures/invoices/copel/core_anon.pdf').read_bytes()

    @classmethod
    def tearDownClass(cls):
        cls.restore_test_runtime()

    def setUp(self):
        self.context = self.app.test_request_context('/')
        self.context.push()
        db.create_all()
        for tenant in (1, 2):
            db.session.add(Empresa(id=tenant, nome='Test', slug=f'f7-{tenant}'))
            db.session.add(Client(id=tenant, empresa_id=tenant, nome='Test', cpf=str(tenant), email=f'{tenant}@test.local'))
            db.session.add(Document(id=tenant, empresa_id=tenant, client_id=tenant, nome='test.pdf',
                                    storage_provider='google_drive', storage_ref=f'f7-{tenant}'))
            db.session.add(FaturaConcessionaria(id=tenant, empresa_id=tenant, client_id=tenant, document_id=tenant,
                                               arquivo_hash=hashlib.sha256(self.document).hexdigest()))
            db.session.add(ConsumerUnit(id=tenant, empresa_id=tenant, client_id=tenant,
                                       codigo='000000000000001'))
        db.session.add(Client(id=3, empresa_id=1, nome='Other', cpf='3', email='3@test.local'))
        db.session.commit()
        g.current_empresa_id = 1
        self.network = patch('socket.socket.connect', side_effect=AssertionError('External network'))
        self.network.start()

    def tearDown(self):
        self.network.stop()
        db.session.rollback()
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        self.context.pop()

    def process(self, **options):
        return FaturaProcessingService().process(1, document=self.document, **options)

    def invoice(self):
        return FaturaConcessionaria.query.filter_by(id=1, empresa_id=1).one()

    def uc(self):
        return ConsumerUnit.query.filter_by(id=1, empresa_id=1).one()

    def test_full_pipeline_matches_canonical_uc_and_persists_exact_snapshots(self):
        result = self.process()
        self.assertEqual(result.status, 'parsed')
        self.assertEqual(result.validation.status, 'valida')
        invoice = self.invoice()
        self.assertEqual((invoice.status_extracao, invoice.status_validacao), ('extraida', 'valida'))
        self.assertEqual(invoice.consumer_unit_id, 1)
        self.assertEqual(result.normalized.campos['uc_numero'].value, '000000000000001')
        self.assertEqual((invoice.parser_name, invoice.parser_version, invoice.layout_version), ('copel', '1.3.0', 'DANF3EA4B-V1.06'))
        self.assertEqual(invoice.competencia, '2030-08')
        self.assertEqual(invoice.dados_normalizados['invoice']['campos']['valor_total_concessionaria']['value'], '1234.567890')
        self.assertEqual(invoice.dados_brutos_extraidos['resumo']['valor_total_concessionaria']['value'], '1234.567890')
        self.assertIsNone(invoice.valor_total_concessionaria)  # sem arredondar coluna Numeric(18,2)
        self.assertIsNone(invoice.injecao_gd1_kwh)
        energy = invoice.dados_normalizados['invoice']['billing_energy_input']
        self.assertEqual(energy['status'], 'UNSUPPORTED')
        self.assertIsNone(energy['energia_compensada_cobravel_kwh'])
        self.assertEqual(energy['fatura_concessionaria_id'], invoice.id)
        self.assertEqual(energy['competencia'], invoice.competencia)

    def test_operational_processing_creates_one_gd_pending_only_when_expectation_is_proven(self):
        plant = Plant(empresa_id=1, nome='Ativa', uc='P-1', kw_pico=1, status='Ativa', data_ativacao=date(2030, 1, 1))
        db.session.add(plant); db.session.flush()
        db.session.add(PlantConnection(empresa_id=1, consumer_unit_id=1, plant_id=plant.id, percentual=100))
        db.session.commit()
        self.process()
        pending = Pendencia.query.filter_by(empresa_id=1, origem='GD_COMPENSATION_UNVERIFIED').one()
        self.assertEqual((pending.consumer_unit_id, pending.plant_id, pending.fatura_concessionaria_id), (1, plant.id, 1))
        self.assertEqual(pending.metadados['energyStatus'], 'UNSUPPORTED')

    def test_legacy_aneel_alias_does_not_match(self):
        uc = self.uc()
        uc.codigo, uc.codigo_aneel = '570778003105', '000000000000001'
        db.session.commit()
        result = self.process()
        self.assertEqual(result.validation.status, 'uc_nao_encontrada')
        self.assertIsNone(self.invoice().consumer_unit_id)

    def test_same_code_other_tenant_does_not_match_or_leak_identity_map(self):
        g.current_empresa_id = 2
        foreign = ConsumerUnit.query.filter_by(id=2, empresa_id=2).one()
        g.current_empresa_id = 1
        self.uc().codigo = 'different'
        db.session.commit()
        result = self.process()
        self.assertEqual(result.validation.status, 'uc_nao_encontrada')
        self.assertIsNone(self.invoice().consumer_unit_id)
        self.assertNotEqual(result.validation.consumer_unit_id, foreign.id)
        self.assertEqual(self.invoice().status_extracao, 'extraida')

    def test_other_client_conflict_never_moves_entities(self):
        self.uc().client_id = 3
        db.session.commit()
        uc_before = self.uc().to_dict()
        client_before = Client.query.filter_by(id=1, empresa_id=1).one().to_dict()
        result = self.process()
        self.assertEqual(result.validation.status, 'uc_pertence_outro_cliente')
        self.assertIsNone(self.invoice().consumer_unit_id)
        self.assertEqual(self.invoice().client_id, 1)
        self.assertEqual(self.uc().to_dict(), uc_before)
        self.assertEqual(Client.query.filter_by(id=1, empresa_id=1).one().to_dict(), client_before)

    def test_duplicate_candidates_are_review_not_first(self):
        db.session.add(ConsumerUnit(empresa_id=1, client_id=1, codigo='000000000000001'))
        db.session.commit()
        result = self.process()
        self.assertEqual(result.validation.status, 'revisao_necessaria')
        self.assertIsNone(result.validation.consumer_unit_id)

    def test_same_key_different_hash_review_not_deduplication(self):
        db.session.add(FaturaConcessionaria(id=3, empresa_id=1, client_id=1, document_id=1,
            arquivo_hash='a' * 64, chave_acesso='0' * 43 + '1'))
        db.session.commit()
        result = self.process()
        self.assertEqual(result.validation.status, 'revisao_necessaria')
        self.assertEqual(self.invoice().status_extracao, 'extraida')
        self.assertTrue(any(i.code == 'FISCAL_KEY_DIFFERENT_HASH' for i in result.validation.issues))
        self.assertEqual(FaturaConcessionaria.query.filter_by(empresa_id=1).count(), 2)

    def test_fiscal_key_other_tenant_not_conflict(self):
        g.current_empresa_id = 2
        other = FaturaConcessionaria.query.filter_by(id=2, empresa_id=2).one()
        other.chave_acesso, other.arquivo_hash = '0' * 43 + '1', 'a' * 64
        db.session.commit()
        g.current_empresa_id = 1
        self.assertEqual(self.process().validation.status, 'valida')

    def test_reprocess_blocked_before_parser_and_no_overwrite(self):
        self.process()
        before = self.invoice().to_dict()
        with patch('services.fatura_processing_service.MinimalExtractor.extract') as extract:
            result = self.process()
        self.assertEqual(result.issues[0].code, 'REPROCESSING_BLOCKED')
        extract.assert_not_called()
        self.assertEqual(self.invoice().to_dict(), before)

    def test_legacy_snapshot_without_identity_also_blocked(self):
        self.invoice().dados_brutos_extraidos = {}
        db.session.commit()
        self.assertEqual(self.process().issues[0].code, 'REPROCESSING_BLOCKED')

    def test_json_null_is_unprocessed_but_empty_snapshot_is_not(self):
        invoice = self.invoice()
        invoice.dados_brutos_extraidos = None
        invoice.dados_normalizados = None
        flag_modified(invoice, 'dados_brutos_extraidos')
        flag_modified(invoice, 'dados_normalizados')
        db.session.commit()
        self.assertEqual(self.process().validation.status, 'valida')

    def test_legacy_structural_data_without_identity_is_not_overwritten(self):
        self.invoice().numero_nota_fiscal = 'legacy'
        db.session.commit()
        self.assertEqual(self.process().issues[0].code, 'REPROCESSING_BLOCKED')
        self.assertEqual(self.invoice().numero_nota_fiscal, 'legacy')

    def test_unknown_layout_persists_status_only_and_allows_retry(self):
        result = FaturaProcessingService(ParserRegistry()).process(1, document=self.document)
        self.assertEqual(result.status, 'layout_nao_reconhecido')
        self.assertEqual(self.invoice().status_extracao, 'layout_nao_reconhecido')
        self.assertEqual(self.invoice().status_validacao, 'pendente')
        self.assertIsNone(self.invoice().dados_brutos_extraidos)
        self.assertEqual(self.process().validation.status, 'valida')

    def test_hash_mismatch_never_changes_state(self):
        before = self.invoice().to_dict()
        result = FaturaProcessingService().process(1, document=self.document + b'changed')
        self.assertEqual(result.issues[0].code, 'DOCUMENT_HASH_MISMATCH')
        self.assertEqual(self.invoice().to_dict(), before)

    def test_failures_rollback_all_snapshot_status_and_association(self):
        before = self.invoice().to_dict()
        for target in ('services.fatura_processing_service.InvoiceNormalizer.normalize',
                       'services.fatura_processing_service.InvoiceValidator.validate',
                       'services.fatura_processing_service.json_safe'):
            with patch(target, side_effect=RuntimeError('PRIVATE CONTENT')):
                result = self.process()
            self.assertEqual(result.status, 'erro')
            self.assertNotIn('PRIVATE', repr(result))
            self.assertEqual(self.invoice().to_dict(), before)
        with patch.object(db.session, 'commit', side_effect=RuntimeError('commit failed')):
            result = self.process()
        self.assertEqual(result.status, 'erro')
        self.assertEqual(self.invoice().to_dict(), before)

    def test_compare_and_swap_refuses_stale_snapshot(self):
        invoice = self.invoice()
        stale = (invoice.id, 1, invoice.updated_at - timedelta(seconds=1), invoice.arquivo_hash)
        with self.assertRaises(RuntimeError):
            FaturaProcessingService._save(stale, {'status_extracao': 'extraida'})
        db.session.rollback()
        self.assertEqual(self.invoice().status_extracao, 'recebida')

    def test_pending_changes_not_committed_by_processing(self):
        self.uc().apelido = 'pending edit'
        self.assertEqual(self.process().issues[0].code, 'CLEAN_SESSION_REQUIRED')
        db.session.rollback()
        self.assertNotEqual(self.uc().apelido, 'pending edit')

    def test_foreign_invoice_hidden(self):
        result = FaturaProcessingService().process(2, document=self.document)
        self.assertEqual(result.issues[0].code, 'INVOICE_NOT_FOUND')

    def test_success_does_not_mutate_uc_or_client(self):
        before = self.uc().to_dict()
        self.process()
        self.assertEqual(self.uc().to_dict(), before)

    def test_readonly_mode_does_not_persist_or_commit(self):
        before = self.invoice().to_dict()
        with patch.object(db.session, 'commit', side_effect=AssertionError('No commit')):
            result = self.process(persist=False)
        self.assertEqual(result.validation.status, 'valida')
        self.assertEqual(self.invoice().to_dict(), before)


if __name__ == '__main__':
    unittest.main()
