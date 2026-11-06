import os
import sys
import tempfile
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

from sqlalchemy.exc import IntegrityError


_DB = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_DB.close()
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flask import g
from app import create_app
from extensions import db
from models.client import Client
from models.consumer_unit import ConsumerUnit
from models.document import Document
from models.empresa import Empresa
from models.fatura_concessionaria import FaturaConcessionaria
try:
    from .support import IsolatedTestRuntime
except ImportError:
    from support import IsolatedTestRuntime


class FaturaConcessionariaTest(IsolatedTestRuntime, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prepare_test_runtime(
            f"sqlite:///{_DB.name.replace(chr(92), '/')}",
            'fatura-concessionaria-test',
        )
        cls.app = create_app()
        with cls.app.app_context():
            db.create_all()
            for tenant in (1, 2):
                db.session.add(Empresa(id=tenant, nome=f'Empresa {tenant}', slug=f'fatura-f1-{tenant}'))
                client = Client(
                    id=tenant, empresa_id=tenant, nome=f'Cliente {tenant}',
                    cpf=f'{tenant:011d}', email=f'cliente{tenant}@test.local',
                )
                uc = ConsumerUnit(
                    id=tenant, empresa_id=tenant, client_id=tenant,
                    codigo=f'UC-{tenant}',
                )
                document = Document(
                    id=tenant, empresa_id=tenant, client_id=tenant,
                    consumer_unit_id=tenant, nome=f'fatura-{tenant}.pdf',
                    storage_provider='google_drive', storage_ref=f'doc-{tenant}',
                    mime_type='application/pdf',
                )
                db.session.add_all([client, uc, document])
            db.session.commit()

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()
        os.unlink(_DB.name)
        cls.restore_test_runtime()

    def tearDown(self):
        with self.app.app_context():
            FaturaConcessionaria.query.delete()
            db.session.commit()

    def _fatura(self, tenant=1, **overrides):
        values = {
            'empresa_id': tenant,
            'client_id': tenant,
            'consumer_unit_id': tenant,
            'document_id': tenant,
            'concessionaria': 'Copel',
            'codigo_uc_extraido': f'UC-{tenant}',
            'competencia': '2026-09',
            'chave_acesso': 'chave-fiscal-compartilhada',
            'arquivo_hash': str(tenant) * 64,
        }
        values.update(overrides)
        return FaturaConcessionaria(**values)

    def test_valid_creation_relationships_decimal_json_and_defaults(self):
        with self.app.app_context():
            fatura = self._fatura(
                data_emissao=date(2026, 9, 10),
                consumo_kwh=Decimal('123.456789'),
                energia_compensada_kwh=Decimal('12.000001'),
                injecao_gd1_kwh=Decimal('1.123456'),
                injecao_gd2_kwh=Decimal('2.654321'),
                saldo_creditos_kwh=Decimal('99.999999'),
                valor_total_concessionaria=Decimal('321.09'),
                dados_brutos_extraidos={'origem': {'texto': '123,456789'}},
                dados_normalizados={'consumoKwh': '123.456789'},
            )
            db.session.add(fatura)
            db.session.commit()

            self.assertEqual((fatura.client.id, fatura.consumer_unit.id, fatura.document.id), (1, 1, 1))
            self.assertIsInstance(fatura.consumo_kwh, Decimal)
            self.assertEqual(fatura.consumo_kwh, Decimal('123.456789'))
            self.assertEqual(fatura.valor_total_concessionaria, Decimal('321.09'))
            data = fatura.to_dict()
            self.assertEqual(data['consumoKwh'], '123.456789')
            self.assertEqual(data['valorTotalConcessionaria'], '321.09')
            self.assertEqual(data['dadosBrutosExtraidos']['origem']['texto'], '123,456789')
            self.assertEqual(data['dadosNormalizados']['consumoKwh'], '123.456789')
            self.assertEqual((data['statusExtracao'], data['statusValidacao']), ('recebida', 'pendente'))

    def test_tenant_isolation_hides_other_company_record(self):
        with self.app.app_context():
            fatura = self._fatura(tenant=2)
            db.session.add(fatura)
            db.session.commit()
            fatura_id = fatura.id
        with self.app.test_request_context('/'):
            g.current_empresa_id = 1
            self.assertIsNone(FaturaConcessionaria.query.filter_by(id=fatura_id).first())
            g.current_empresa_id = 2
            self.assertEqual(FaturaConcessionaria.query.filter_by(id=fatura_id).one().empresa_id, 2)

    def test_hash_is_unique_per_tenant_but_fiscal_key_is_not(self):
        with self.app.app_context():
            db.session.add(self._fatura())
            db.session.commit()
            db.session.add(self._fatura(arquivo_hash='1' * 64))
            with self.assertRaises(IntegrityError):
                db.session.commit()
            db.session.rollback()

            db.session.add(self._fatura(arquivo_hash='a' * 64))
            db.session.add(self._fatura(tenant=2, arquivo_hash='1' * 64))
            db.session.commit()
            self.assertEqual(FaturaConcessionaria.query.count(), 3)


if __name__ == '__main__':
    unittest.main()
