"""criar_pendencia_pagar_concessionaria: cria pendencia idempotente quando
existe FaturaConcessionaria correspondente por (empresa_id, consumer_unit_id,
competencia); nao cria nada quando nao existe correspondencia."""
import os
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

_DATABASE_FILE = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_DATABASE_FILE.close()
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flask import g  # noqa: E402

from app import create_app  # noqa: E402
from extensions import db  # noqa: E402
from models.client import Client  # noqa: E402
from models.consumer_unit import ConsumerUnit  # noqa: E402
from models.document import Document  # noqa: E402
from models.empresa import Empresa  # noqa: E402
from models.fatura import Fatura  # noqa: E402
from models.fatura_concessionaria import FaturaConcessionaria  # noqa: E402
from models.pendencia import Pendencia  # noqa: E402
from services.financeiro_service import (  # noqa: E402
    ORIGEM_PAGAR_CONCESSIONARIA,
    criar_pendencia_pagar_concessionaria,
)
try:
    from .support import IsolatedTestRuntime  # noqa: E402
except ImportError:
    from support import IsolatedTestRuntime  # noqa: E402


class FinanceiroServiceTest(IsolatedTestRuntime, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prepare_test_runtime(
            f"sqlite:///{_DATABASE_FILE.name.replace(chr(92), '/')}",
            'financeiro-test-secret',
        )
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        with cls.app.app_context():
            db.create_all()
            db.session.add(Empresa(nome='A', slug='financeiro-a'))
            db.session.commit()

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()
        os.unlink(_DATABASE_FILE.name)
        cls.restore_test_runtime()

    def setUp(self):
        self.ctx = self.app.app_context()
        self.ctx.push()
        g.current_empresa_id = 1
        for model in (Pendencia, Fatura, FaturaConcessionaria, ConsumerUnit, Client, Document):
            db.session.query(model).delete()
        db.session.commit()
        self.cliente = Client(empresa_id=1, nome='Cliente', cpf='12345678900', email='c@x.test')
        db.session.add(self.cliente)
        db.session.flush()
        self.uc = ConsumerUnit(empresa_id=1, client_id=self.cliente.id, codigo='UC-1')
        db.session.add(self.uc)
        db.session.flush()
        self.documento = Document(empresa_id=1, nome='fatura.pdf')
        db.session.add(self.documento)
        db.session.flush()
        self.fatura = Fatura(
            empresa_id=1, client_id=self.cliente.id, consumer_unit_id=self.uc.id,
            concessionaria='CEMIG', competencia='2026-01', valor=100,
            mes_vencimento=date(2026, 1, 10), asaas_status='received',
        )
        db.session.add(self.fatura)
        db.session.commit()

    def tearDown(self):
        db.session.rollback()
        self.ctx.pop()

    def test_criar_pendencia_pagar_concessionaria_cria_pendencia_idempotente(self):
        invoice = FaturaConcessionaria(
            empresa_id=1, client_id=self.cliente.id, consumer_unit_id=self.uc.id,
            document_id=self.documento.id, competencia='2026-01', arquivo_hash='hash-1',
        )
        db.session.add(invoice)
        db.session.commit()

        criar_pendencia_pagar_concessionaria(self.fatura)
        criar_pendencia_pagar_concessionaria(self.fatura)

        pendencias = Pendencia.query.filter_by(
            empresa_id=self.fatura.empresa_id, fatura_concessionaria_id=invoice.id,
            origem=ORIGEM_PAGAR_CONCESSIONARIA).all()
        self.assertEqual(len(pendencias), 1)
        self.assertEqual(pendencias[0].categoria, 'Financeiro')

    def test_criar_pendencia_pagar_concessionaria_sem_fatura_concessionaria_correspondente_nao_cria_nada(self):
        criar_pendencia_pagar_concessionaria(self.fatura)
        self.assertEqual(Pendencia.query.filter_by(empresa_id=self.fatura.empresa_id).count(), 0)


if __name__ == '__main__':
    unittest.main()
