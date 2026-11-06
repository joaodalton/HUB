"""flask expirar-planos-teste: suspende assinaturas do plano teste com trial vencido."""
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app  # noqa: E402
from extensions import db  # noqa: E402
from models.assinatura import Assinatura  # noqa: E402
from models.empresa import Empresa  # noqa: E402
try:
    from .support import IsolatedTestRuntime  # noqa: E402
except ImportError:
    from support import IsolatedTestRuntime  # noqa: E402


class ExpirarPlanosTesteCommandTest(IsolatedTestRuntime, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prepare_test_runtime('sqlite://', 'expirar-planos-teste-command-test')
        cls.app = create_app()

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()
        cls.restore_test_runtime()

    def setUp(self):
        self.context = self.app.app_context()
        self.context.push()
        self.addCleanup(self.context.pop)
        db.create_all()
        self.addCleanup(db.drop_all)

    def _criar_assinatura(self, nome, plano_chave, trial_expira_em, status='trial'):
        empresa = Empresa(nome=nome, slug=nome.lower(), status='ativa')
        db.session.add(empresa)
        db.session.flush()
        assinatura = Assinatura(
            empresa_id=empresa.id, plano_chave=plano_chave, tipo='trial', status=status,
            trial_expira_em=trial_expira_em,
        )
        db.session.add(assinatura)
        db.session.commit()
        return assinatura

    def test_suspende_apenas_teste_vencido(self):
        vencida = self._criar_assinatura('Vencida', 'teste', datetime.utcnow() - timedelta(days=1))
        nao_vencida = self._criar_assinatura('NaoVencida', 'teste', datetime.utcnow() + timedelta(days=1))
        outro_plano = self._criar_assinatura('OutroPlano', 'starter', datetime.utcnow() - timedelta(days=1))

        result = self.app.test_cli_runner().invoke(args=['expirar-planos-teste'])
        self.assertEqual(result.exit_code, 0)

        db.session.refresh(vencida)
        db.session.refresh(nao_vencida)
        db.session.refresh(outro_plano)
        self.assertEqual(vencida.status, 'suspensa')
        self.assertEqual(nao_vencida.status, 'trial')
        self.assertEqual(outro_plano.status, 'trial')


if __name__ == '__main__':
    unittest.main()
