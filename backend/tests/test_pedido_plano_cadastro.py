"""concluir_cadastro: token pago -> cria Empresa + Assinatura + owner User."""
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app  # noqa: E402
from config import Config  # noqa: E402
from extensions import db  # noqa: E402
from models.assinatura import Assinatura  # noqa: E402
from models.empresa import Empresa  # noqa: E402
from models.pedido_plano import PedidoPlano  # noqa: E402
from models.user import User  # noqa: E402
from services.pedido_plano_service import _gerar_token, concluir_cadastro  # noqa: E402
try:
    from .support import IsolatedTestRuntime  # noqa: E402
except ImportError:
    from support import IsolatedTestRuntime  # noqa: E402


class ConcluirCadastroTest(IsolatedTestRuntime, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prepare_test_runtime('sqlite://', 'pedido-plano-cadastro-test')
        Config.FRONTEND_URL = 'https://hub.test'
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

    def _criar_pedido_pago(self, plano_chave='avancado', email='cliente@teste.com'):
        token_cru, token_hash = _gerar_token()
        pedido = PedidoPlano(
            email=email,
            plano_chave=plano_chave,
            external_reference='hub-platform-ref-' + token_hash[:8],
            asaas_subscription_id='sub_123',
            token_hash=token_hash,
            status='pago',
            expires_at=datetime.utcnow() + timedelta(days=7),
        )
        db.session.add(pedido)
        db.session.commit()
        return pedido, token_cru

    def test_concluir_cadastro_cria_empresa_assinatura_e_owner(self):
        pedido, token_cru = self._criar_pedido_pago(plano_chave='avancado')

        resultado = concluir_cadastro(token_cru, 'Minha Empresa', 'minha-empresa', 'senha123')

        empresa = Empresa.query.filter_by(slug='minha-empresa').first()
        self.assertIsNotNone(empresa)
        self.assertEqual(resultado['empresaId'], empresa.id)

        assinatura = Assinatura.query.filter_by(empresa_id=empresa.id).first()
        self.assertEqual(assinatura.plano_chave, 'avancado')
        self.assertEqual(assinatura.tipo, 'pago')
        self.assertEqual(assinatura.status, 'ativa')
        self.assertEqual(assinatura.asaas_subscription_id, 'sub_123')

        owner = User.query.filter_by(empresa_id=empresa.id, role='owner').first()
        self.assertIsNotNone(owner)
        self.assertEqual(owner.email, pedido.email)
        self.assertTrue(owner.email_verified)

        self.assertEqual(PedidoPlano.query.get(pedido.id).status, 'usado')

    def test_token_usado_nao_cria_segunda_empresa(self):
        pedido, token_cru = self._criar_pedido_pago(plano_chave='starter', email='reuso@teste.com')
        concluir_cadastro(token_cru, 'Primeira', 'primeira-empresa', 'senha123')

        # Chamada sequencial com o mesmo token: a segunda passa pelo guarded
        # update (pago->usado) e nao mais so pela checagem de status, ja que o
        # primeiro commit deixou o pedido como 'usado' no banco.
        with self.assertRaises(ValueError):
            concluir_cadastro(token_cru, 'Outra', 'outra-empresa', 'senha123')

        self.assertIsNone(Empresa.query.filter_by(slug='outra-empresa').first())

    def test_senha_curta_levanta_value_error_sem_criar_nada(self):
        pedido, token_cru = self._criar_pedido_pago(email='senhacurta@teste.com')

        with self.assertRaises(ValueError):
            concluir_cadastro(token_cru, 'Empresa Senha Curta', 'empresa-senha-curta', '123')

        self.assertIsNone(Empresa.query.filter_by(slug='empresa-senha-curta').first())
        self.assertEqual(PedidoPlano.query.get(pedido.id).status, 'pago')

    def test_nome_empresa_em_branco_levanta_value_error_sem_criar_nada(self):
        pedido, token_cru = self._criar_pedido_pago(email='nomevazio@teste.com')

        with self.assertRaises(ValueError):
            concluir_cadastro(token_cru, '   ', 'empresa-nome-vazio', 'senha123')

        self.assertIsNone(Empresa.query.filter_by(slug='empresa-nome-vazio').first())
        self.assertEqual(PedidoPlano.query.get(pedido.id).status, 'pago')

    def test_token_invalido_levanta_value_error(self):
        with self.assertRaises(ValueError):
            concluir_cadastro('token-que-nao-existe', 'Empresa', 'slug', 'senha123')

    def test_token_expirado_marca_expirado_e_levanta_value_error(self):
        token_cru, token_hash = _gerar_token()
        pedido = PedidoPlano(
            email='expirado@teste.com',
            plano_chave='starter',
            external_reference='hub-platform-ref-exp',
            token_hash=token_hash,
            status='pago',
            expires_at=datetime.utcnow() - timedelta(days=1),
        )
        db.session.add(pedido)
        db.session.commit()

        with self.assertRaises(ValueError):
            concluir_cadastro(token_cru, 'Empresa', 'slug-expirado', 'senha123')

        self.assertEqual(PedidoPlano.query.get(pedido.id).status, 'expirado')

    def test_slug_duplicado_levanta_value_error(self):
        db.session.add(Empresa(nome='Ja Existe', slug='ja-existe', status='ativa'))
        db.session.commit()

        pedido, token_cru = self._criar_pedido_pago(email='dup@teste.com')
        with self.assertRaises(ValueError):
            concluir_cadastro(token_cru, 'Nova', 'ja-existe', 'senha123')


if __name__ == '__main__':
    unittest.main()
