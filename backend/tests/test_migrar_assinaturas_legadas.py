"""Migracao de legado: isenta assinaturas starter antigas e trava franquia antiga."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

_DATABASE_FILE = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_DATABASE_FILE.close()
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app  # noqa: E402
from extensions import db  # noqa: E402
from models.assinatura import Assinatura  # noqa: E402
from models.empresa import Empresa  # noqa: E402
from models.limite_contratado import LimiteContratado  # noqa: E402
from scripts import migrar_assinaturas_legadas  # noqa: E402
try:
    from .support import IsolatedTestRuntime  # noqa: E402
except ImportError:
    from support import IsolatedTestRuntime  # noqa: E402


class MigrarAssinaturasLegadasTest(IsolatedTestRuntime, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prepare_test_runtime(
            f"sqlite:///{_DATABASE_FILE.name.replace(chr(92), '/')}",
            'migrar-legado-test-secret',
        )
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        with cls.app.app_context():
            db.create_all()

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()
        os.unlink(_DATABASE_FILE.name)
        cls.restore_test_runtime()

    def setUp(self):
        with self.app.app_context():
            empresa = Empresa(nome='Legado', slug='legado-starter')
            db.session.add(empresa)
            db.session.flush()
            db.session.add(Assinatura(empresa_id=empresa.id, plano_chave='starter', tipo='vitalicio', status='ativa'))
            db.session.commit()
            self.empresa_id = empresa.id

    def tearDown(self):
        with self.app.app_context():
            LimiteContratado.query.filter_by(empresa_id=self.empresa_id).delete()
            Assinatura.query.filter_by(empresa_id=self.empresa_id).delete()
            Empresa.query.filter_by(id=self.empresa_id).delete()
            db.session.commit()

    def test_marca_isento_e_trava_franquia_antiga(self):
        with self.app.app_context():
            migrar_assinaturas_legadas.main()
            assinatura = Assinatura.query.filter_by(empresa_id=self.empresa_id).first()
            self.assertTrue(assinatura.isento_cobranca)
            limite_usinas = LimiteContratado.query.filter_by(empresa_id=self.empresa_id, recurso='usinas').first()
            self.assertEqual(limite_usinas.quantidade_contratada, 10)  # franquia antiga do starter, nao a nova (5)

    def test_idempotente_nao_duplica_limite_contratado(self):
        with self.app.app_context():
            migrar_assinaturas_legadas.main()
            migrar_assinaturas_legadas.main()
            self.assertEqual(
                LimiteContratado.query.filter_by(empresa_id=self.empresa_id, recurso='usinas').count(), 1
            )

    def test_nao_toca_starter_pago_com_asaas_subscription_id(self):
        # Starter novo pago (concluir_cadastro sempre grava asaas_subscription_id)
        # nao deve ser confundido com legado -- re-rodar o script depois desta
        # feature nao pode isentar cobranca nem travar franquia antiga nele.
        with self.app.app_context():
            empresa = Empresa(nome='Starter pago novo', slug='starter-pago-novo')
            db.session.add(empresa)
            db.session.flush()
            db.session.add(Assinatura(
                empresa_id=empresa.id, plano_chave='starter', tipo='pago', status='ativa',
                asaas_subscription_id='sub_real_123',
            ))
            db.session.commit()
            empresa_id = empresa.id

            migrar_assinaturas_legadas.main()

            assinatura = Assinatura.query.filter_by(empresa_id=empresa_id).first()
            self.assertFalse(assinatura.isento_cobranca)
            self.assertIsNone(
                LimiteContratado.query.filter_by(empresa_id=empresa_id, recurso='usinas').first()
            )

            LimiteContratado.query.filter_by(empresa_id=empresa_id).delete()
            Assinatura.query.filter_by(empresa_id=empresa_id).delete()
            Empresa.query.filter_by(id=empresa_id).delete()
            db.session.commit()


if __name__ == '__main__':
    unittest.main()
