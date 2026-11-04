"""POST /api/v1/platform/pedidos-plano -- rota publica de checkout (sem autenticacao)."""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app  # noqa: E402
from config import Config  # noqa: E402
from extensions import db  # noqa: E402
from datetime import datetime, timedelta  # noqa: E402

from models.pedido_plano import PedidoPlano  # noqa: E402
from services.asaas_client import AsaasError  # noqa: E402
from services.pedido_plano_service import _gerar_token  # noqa: E402
try:
    from .support import IsolatedTestRuntime  # noqa: E402
except ImportError:
    from support import IsolatedTestRuntime  # noqa: E402


class CriarPedidoRouteTest(IsolatedTestRuntime, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prepare_test_runtime('sqlite://', 'pedido-plano-route-test', limiter_enabled=False)
        Config.FRONTEND_URL = 'https://hub.test'
        cls.app = create_app()
        cls.app.config['TESTING'] = True

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
        self.client = self.app.test_client()

    def _post(self, body):
        return self.client.post('/api/v1/platform/pedidos-plano', json=body)

    def test_cria_pedido_com_sucesso(self):
        with mock.patch('services.pedido_plano_service._asaas_transport') as mocked:
            mocked.return_value.criar_cliente.return_value = {'id': 'cus_1'}
            mocked.return_value.criar_assinatura.return_value = {'id': 'sub_1'}
            response = self._post({
                'email': 'cliente@teste.com',
                'planoChave': 'starter',
                'dadosPagamento': {'cpfCnpj': '12345678900', 'nome': 'Fulano', 'billingType': 'PIX'},
            })

        self.assertEqual(response.status_code, 201)
        data = response.get_json()['data']
        self.assertEqual(data['planoChave'], 'starter')
        self.assertEqual(data['status'], 'pendente')
        pedido = PedidoPlano.query.filter_by(email='cliente@teste.com').first()
        self.assertIsNotNone(pedido)

    def test_plano_nao_compravel_retorna_400(self):
        response = self._post({'email': 'a@b.com', 'planoChave': 'teste', 'dadosPagamento': {}})
        self.assertEqual(response.status_code, 400)
        self.assertIsNone(PedidoPlano.query.filter_by(email='a@b.com').first())

    def test_email_ausente_retorna_400(self):
        response = self._post({'planoChave': 'starter', 'dadosPagamento': {}})
        self.assertEqual(response.status_code, 400)

    def test_dados_pagamento_nao_dict_retorna_400_em_vez_de_500(self):
        response = self._post({'email': 'a@b.com', 'planoChave': 'starter', 'dadosPagamento': 'nao-e-objeto'})
        self.assertEqual(response.status_code, 400)
        self.assertIsNone(PedidoPlano.query.filter_by(email='a@b.com').first())

    def test_plano_chave_nao_string_retorna_400_em_vez_de_500(self):
        response = self._post({'email': 'a@b.com', 'planoChave': 123, 'dadosPagamento': {}})
        self.assertEqual(response.status_code, 400)

    def test_falha_asaas_retorna_502_nao_500(self):
        with mock.patch('services.pedido_plano_service._asaas_transport') as mocked:
            mocked.return_value.criar_cliente.side_effect = AsaasError('ASAAS recusou a operacao.')
            response = self._post({
                'email': 'falhaasaas@teste.com',
                'planoChave': 'starter',
                'dadosPagamento': {'cpfCnpj': '12345678900', 'billingType': 'BOLETO'},
            })
        self.assertEqual(response.status_code, 502)
        self.assertIsNone(PedidoPlano.query.filter_by(email='falhaasaas@teste.com').first())

    def test_billing_type_ausente_retorna_400(self):
        response = self._post({
            'email': 'semtipo@teste.com', 'planoChave': 'starter', 'dadosPagamento': {'cpfCnpj': '12345678900'},
        })
        self.assertEqual(response.status_code, 400)
        self.assertIsNone(PedidoPlano.query.filter_by(email='semtipo@teste.com').first())

    def test_corpo_nao_dict_retorna_400_em_vez_de_500(self):
        response = self.client.post('/api/v1/platform/pedidos-plano', json=[1, 2, 3])
        self.assertEqual(response.status_code, 400)

    def test_email_muito_longo_retorna_400(self):
        response = self._post({
            'email': ('a' * 145) + '@b.com', 'planoChave': 'starter',
            'dadosPagamento': {'cpfCnpj': '12345678900', 'billingType': 'PIX'},
        })
        self.assertEqual(response.status_code, 400)


class ConcluirCadastroRouteAuthTest(IsolatedTestRuntime, unittest.TestCase):
    """A rota /pedidos-plano/concluir e publica (sem token) -- ela so foi
    adicionada ao whitelist de auth (app.py public_paths) nesta correcao;
    sem isso, o middleware global de autenticacao rejeitava com 401 antes
    mesmo do service rodar, deixando a rota inalcancavel em producao."""

    @classmethod
    def setUpClass(cls):
        cls.prepare_test_runtime('sqlite://', 'pedido-plano-concluir-route-test', limiter_enabled=False)
        Config.FRONTEND_URL = 'https://hub.test'
        cls.app = create_app()
        cls.app.config['TESTING'] = True

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
        self.client = self.app.test_client()

    def test_rota_concluir_e_acessivel_sem_token_de_autenticacao(self):
        token_cru, token_hash = _gerar_token()
        db.session.add(PedidoPlano(
            email='rota@teste.com', plano_chave='starter', external_reference='hub-platform-ref-rota',
            token_hash=token_hash, status='pago', expires_at=datetime.utcnow() + timedelta(days=7),
        ))
        db.session.commit()

        response = self.client.post('/api/v1/platform/pedidos-plano/concluir', json={
            'token': token_cru, 'nomeEmpresa': 'Empresa Rota', 'slug': 'empresa-rota', 'senha': 'senha123',
        })
        self.assertEqual(response.status_code, 201)

    def test_rota_concluir_rejeita_slug_invalido_com_400_nao_500(self):
        token_cru, token_hash = _gerar_token()
        db.session.add(PedidoPlano(
            email='slugbad@teste.com', plano_chave='starter', external_reference='hub-platform-ref-slugbad',
            token_hash=token_hash, status='pago', expires_at=datetime.utcnow() + timedelta(days=7),
        ))
        db.session.commit()

        response = self.client.post('/api/v1/platform/pedidos-plano/concluir', json={
            'token': token_cru, 'nomeEmpresa': 'Empresa', 'slug': 'Slug Invalido!', 'senha': 'senha123',
        })
        self.assertEqual(response.status_code, 400)

    def test_rota_concluir_corpo_nao_dict_retorna_400_em_vez_de_500(self):
        response = self.client.post('/api/v1/platform/pedidos-plano/concluir', json='nao-e-objeto')
        self.assertEqual(response.status_code, 400)


if __name__ == '__main__':
    unittest.main()
