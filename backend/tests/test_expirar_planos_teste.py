"""Script agendado: suspende assinaturas do plano teste com trial vencido."""
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path


_DATABASE_FILE = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_DATABASE_FILE.close()
_BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_BACKEND))
sys.path.insert(0, str(_BACKEND / 'scripts'))

from app import create_app  # noqa: E402
from extensions import db  # noqa: E402
from models.assinatura import Assinatura  # noqa: E402
from models.empresa import Empresa  # noqa: E402
import expirar_planos_teste  # noqa: E402
try:
    from .support import IsolatedTestRuntime  # noqa: E402
except ImportError:
    from support import IsolatedTestRuntime  # noqa: E402


class ExpirarPlanosTesteTest(IsolatedTestRuntime, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prepare_test_runtime(
            f"sqlite:///{_DATABASE_FILE.name.replace(chr(92), '/')}",
            'expirar-planos-teste-secret',
        )
        cls.app = create_app()
        cls.app.config['TESTING'] = True

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
            db.create_all()
            agora = datetime.utcnow()
            vencida = Empresa(nome='Vencida', slug='teste-vencida', status='ativa')
            no_prazo = Empresa(nome='No prazo', slug='teste-no-prazo', status='ativa')
            db.session.add_all([vencida, no_prazo])
            db.session.flush()
            db.session.add_all([
                Assinatura(empresa_id=vencida.id, plano_chave='teste', tipo='trial', status='trial',
                           trial_expira_em=agora - timedelta(days=1)),
                Assinatura(empresa_id=no_prazo.id, plano_chave='teste', tipo='trial', status='trial',
                           trial_expira_em=agora + timedelta(days=5)),
            ])
            db.session.commit()
            self.vencida_id = Assinatura.query.filter_by(empresa_id=vencida.id).one().id
            self.no_prazo_id = Assinatura.query.filter_by(empresa_id=no_prazo.id).one().id

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def _status(self, assinatura_id):
        with self.app.app_context():
            return db.session.get(Assinatura, assinatura_id).status

    def _rodar(self):
        with self.app.app_context():
            expirar_planos_teste.main()

    def test_suspende_assinatura_teste_vencida(self):
        self._rodar()
        self.assertEqual(self._status(self.vencida_id), 'suspensa')

    def test_nao_toca_teste_ainda_dentro_do_prazo(self):
        self._rodar()
        self.assertEqual(self._status(self.no_prazo_id), 'trial')

    def test_idempotente(self):
        self._rodar()
        self._rodar()
        self.assertEqual(self._status(self.vencida_id), 'suspensa')
        self.assertEqual(self._status(self.no_prazo_id), 'trial')


if __name__ == '__main__':
    unittest.main()
