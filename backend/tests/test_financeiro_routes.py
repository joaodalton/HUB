"""Contrato HTTP do dashboard do financeiro: RBAC, isolamento por tenant."""
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app
from extensions import db
from models.client import Client
from models.consumer_unit import ConsumerUnit, PlantConnection
from models.empresa import Empresa
from models.fatura import Fatura
from models.plant import Plant
from models.user import User
from utils.auth import generate_token

try:
    from .support import IsolatedTestRuntime
except ImportError:
    from support import IsolatedTestRuntime


class FinanceiroRoutesTest(IsolatedTestRuntime, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.prepare_test_runtime('sqlite:///' + (Path(cls.temp.name) / 'financeiro.db').as_posix(),
                                 'financeiro-routes-test', limiter_enabled=False)
        cls.app = create_app()

    @classmethod
    def tearDownClass(cls):
        cls.restore_test_runtime()
        cls.temp.cleanup()

    def setUp(self):
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

        for tenant in (10, 20):
            db.session.add(Empresa(id=tenant, nome=f'Empresa {tenant}', slug=f'financeiro-{tenant}'))
            db.session.add(Client(id=tenant, empresa_id=tenant, nome=f'Cliente {tenant}',
                                  cpf=str(tenant), email=f'{tenant}@example.test'))
            db.session.add(ConsumerUnit(id=tenant, empresa_id=tenant, client_id=tenant, codigo=f'UC{tenant}'))
            db.session.add(Plant(id=tenant, empresa_id=tenant, nome=f'Usina {tenant}',
                                 uc=f'UC-USINA-{tenant}', kw_pico=100))
            db.session.add(PlantConnection(id=tenant, empresa_id=tenant, consumer_unit_id=tenant,
                                           plant_id=tenant, percentual=100))
            db.session.add(Fatura(id=tenant, empresa_id=tenant, client_id=tenant, consumer_unit_id=tenant,
                                  concessionaria='Copel', competencia='2026-10', valor=1000,
                                  mes_vencimento=date(2026, 10, 10), asaas_status='received'))

        # Usina sem nenhuma UC conectada (tenant 10).
        db.session.add(Plant(id=11, empresa_id=10, nome='Usina sem conexao', uc='UC-USINA-11', kw_pico=50))

        users = ((1, 10, 'owner', False), (2, 10, 'financial', False), (3, 10, 'operator', False),
                 (4, 20, 'owner', False))
        for user_id, tenant, role, platform in users:
            db.session.add(User(id=user_id, empresa_id=tenant, nome=role,
                                email=f'user-{user_id}@example.test', password_hash='x',
                                role=role, is_platform_admin=platform))
        db.session.commit()
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.rollback()
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        self.ctx.pop()

    def headers(self, user_id):
        return {'Authorization': f'Bearer {generate_token(user_id)}'}

    def test_dashboard_retorna_totais_por_cliente_e_por_usina(self):
        response = self.client.get('/api/v1/financeiro/dashboard?competencia=2026-10',
                                   headers=self.headers(1))
        self.assertEqual(response.status_code, 200)
        body = response.json['data']
        self.assertIn('porCliente', body)
        self.assertIn('porUsina', body)

        cliente = next(c for c in body['porCliente'] if c['clienteId'] == 10)
        self.assertEqual(cliente['recebido'], '1000.00')
        self.assertEqual(cliente['pendente'], '0.00')

        usina = next(u for u in body['porUsina'] if u['usinaId'] == 10)
        self.assertEqual(usina['recebido'], '1000.00')
        self.assertIsNone(usina['repasseCalculado'])  # sem contrato configurado
        self.assertTrue(usina['contratoPendente'])

        # Usina sem nenhuma UC conectada nao deve ser tratada como pendencia de contrato.
        usina_sem_conexao = next(u for u in body['porUsina'] if u['usinaId'] == 11)
        self.assertEqual(usina_sem_conexao['recebido'], '0.00')
        self.assertIsNone(usina_sem_conexao['repasseCalculado'])
        self.assertFalse(usina_sem_conexao['contratoPendente'])
        self.assertTrue(usina_sem_conexao['semClientesConectados'])

        # Isolamento por tenant: dados da empresa 20 nao aparecem aqui.
        self.assertFalse(any(c['clienteId'] == 20 for c in body['porCliente']))
        self.assertFalse(any(u['usinaId'] == 20 for u in body['porUsina']))

    def test_dashboard_rejeita_competencia_com_formato_invalido(self):
        response = self.client.get('/api/v1/financeiro/dashboard?competencia=2026-10-01',
                                   headers=self.headers(1))
        self.assertEqual(response.status_code, 400)

    def test_dashboard_aceita_competencia_bem_formada(self):
        response = self.client.get('/api/v1/financeiro/dashboard?competencia=2026-10',
                                   headers=self.headers(1))
        self.assertEqual(response.status_code, 200)

    def test_dashboard_requer_permissao_financeiro_read(self):
        url = '/api/v1/financeiro/dashboard?competencia=2026-10'
        self.assertEqual(self.client.get(url).status_code, 401)
        self.assertEqual(self.client.get(url, headers=self.headers(3)).status_code, 403)
        self.assertEqual(self.client.get(url, headers=self.headers(2)).status_code, 200)

    # ---- GET /financeiro/pendentes-boleto ----
    URL = '/api/v1/financeiro/pendentes-boleto'

    def make_invoice(self, n, *, tenant=10, plants=(), email='c@example.test', nome=None, mode='unified',
                     debito=False, valor='71.05', vencimento=date(2026, 11, 20), hub='168.75',
                     validacao='valida', stage=None, deleted=None, uc=True):
        """Cliente+UC+fatura da concessionaria com (opcionalmente) calculo. stage: etapa bloqueada."""
        from datetime import datetime
        from decimal import Decimal
        from models.document import Document
        from models.fatura_concessionaria import FaturaConcessionaria
        db.session.add(Client(id=n, empresa_id=tenant, nome=nome or f'Cli {n}', cpf=str(n), email=email))
        db.session.add(Document(id=n, empresa_id=tenant, client_id=n, nome='c.pdf', storage_provider='google_drive'))
        db.session.add(ConsumerUnit(id=n, empresa_id=tenant, client_id=n, codigo=f'UC{n}', debito_automatico=debito))
        for plant_id in plants:
            db.session.add(PlantConnection(empresa_id=tenant, consumer_unit_id=n, plant_id=plant_id, percentual=50))
        db.session.add(FaturaConcessionaria(
            id=n, empresa_id=tenant, client_id=n, consumer_unit_id=n if uc else None, document_id=n,
            arquivo_hash=str(n) * 32, competencia='2026-10', data_vencimento=vencimento,
            valor_total_concessionaria=None if valor is None else Decimal(valor),
            status_validacao=validacao, deleted_at=deleted and datetime.utcnow()))
        db.session.commit()
        if hub is not None:
            self.add_execution(n, tenant, hub=hub, mode=mode)
        elif stage:
            self.add_execution(n, tenant, stage=stage)

    def add_execution(self, n, tenant, *, hub=None, mode='unified', stage=None):
        from decimal import Decimal
        from models.calculo_cobranca import BillingCalculationExecution, BillingCalculationSnapshot
        snapshot_id = None
        if hub is not None:
            snapshot = BillingCalculationSnapshot(
                empresa_id=tenant, fatura_concessionaria_id=n, fingerprint=f'{n}{hub}{mode}'.ljust(64, 'f'),
                regra_snapshot={'billing_mode': mode}, entrada_normalizada={}, resultado={},
                valor_final=Decimal(hub))
            db.session.add(snapshot)
            db.session.flush()
            snapshot_id = snapshot.id
        stages = [{'stage': stage, 'status': 'MISSING_DATA', 'blockers': ['X_MISSING', 'Y_MISSING']}] if stage else []
        db.session.add(BillingCalculationExecution(
            empresa_id=tenant, fatura_concessionaria_id=n, snapshot_id=snapshot_id,
            status='CALCULATED' if hub is not None else 'MISSING_DATA', auditoria={'stages': stages}))
        db.session.commit()

    def pendentes(self, user_id=1):
        response = self.client.get(self.URL, headers=self.headers(user_id))
        self.assertEqual(response.status_code, 200)
        return response.json['data']

    def test_pendentes_agrupa_por_usina_e_sem_usina_por_ultimo(self):
        self.make_invoice(101, plants=(10, 11), nome='Zeca')
        self.make_invoice(102, nome='Ana')
        self.make_invoice(103, plants=(10,), nome='Ana B', debito=True, mode='auto')
        data = self.pendentes()
        self.assertEqual([(g['usinaId'], g['usinaNome']) for g in data],
                         [(10, 'Usina 10'), (11, 'Usina sem conexao'), (None, None)])
        self.assertEqual([i['clienteNome'] for i in data[0]['itens']], ['Ana B', 'Zeca'])
        self.assertEqual([i['invoiceId'] for i in data[1]['itens']], [101])
        zeca = data[0]['itens'][1]
        self.assertEqual(zeca, {
            'invoiceId': 101, 'clienteId': 101, 'clienteNome': 'Zeca', 'ucId': 101, 'ucCodigo': 'UC101',
            'competencia': '2026-10', 'dataVencimento': '2026-11-20', 'valorConcessionaria': '71.05',
            'valorHub': '168.75', 'valorCobrar': '239.80', 'billingMode': 'unified',
            'emissaoPendente': False, 'bloqueio': None})
        ana_b = data[0]['itens'][0]  # auto + debito automatico => separate => so valor Hub
        self.assertEqual((ana_b['billingMode'], ana_b['valorCobrar']), ('separate', '168.75'))

    def test_pendentes_filtra_boleto_ativo_validacao_e_exclusao(self):
        from datetime import datetime
        self.make_invoice(111, nome='Pago')
        self.make_invoice(112, nome='Cancelado')
        self.make_invoice(113, nome='Revisao', validacao='revisao_necessaria')
        self.make_invoice(114, nome='Excluida', deleted=True)
        self.make_invoice(115, nome='SemUc', uc=False)
        for fid, n, status in ((1111, 111, 'pending'), (1112, 112, 'canceled')):
            db.session.add(Fatura(id=fid, empresa_id=10, client_id=n, consumer_unit_id=n, concessionaria='Copel',
                                  competencia='2026-10', valor=10, mes_vencimento=date(2026, 11, 20),
                                  asaas_id=f'pay_{n}', asaas_status=status))
        db.session.commit()
        ids = [i['invoiceId'] for g in self.pendentes() for i in g['itens']]
        self.assertEqual(ids, [112])

    def test_pendentes_bloqueios_na_ordem_da_tabela(self):
        self.make_invoice(121, email='  ', nome='A')
        self.make_invoice(122, vencimento=None, valor=None, nome='B')
        self.make_invoice(123, hub=None, nome='C')
        self.make_invoice(124, hub=None, stage='RULE_RESOLUTION', nome='D')
        self.make_invoice(125, hub=None, stage='NORMALIZATION', nome='E')
        self.make_invoice(126, vencimento=None, valor='0.00', hub=None, email='', nome='F')
        itens = {i['invoiceId']: i for g in self.pendentes() for i in g['itens']}
        self.assertEqual(itens[121]['bloqueio'], {'code': 'CLIENT_EMAIL_MISSING', 'message': 'Cliente sem e-mail cadastrado.'})
        self.assertEqual(itens[122]['bloqueio'], {'code': 'INVOICE_DATA_INCOMPLETE',
                                                  'message': 'Faltou na fatura: dataVencimento, valor.'})
        self.assertEqual(itens[123]['bloqueio'], {'code': 'NOT_CALCULATED', 'message': 'Cobrança ainda não calculada.'})
        self.assertEqual((itens[123]['valorHub'], itens[123]['valorCobrar'], itens[123]['billingMode']),
                         (None, None, None))
        self.assertEqual(itens[124]['bloqueio'], {'code': 'RULE_MISSING', 'message': 'Cliente sem regra de cobrança.'})
        self.assertEqual(itens[125]['bloqueio'], {
            'code': 'CALCULATION_BLOCKED', 'message': 'Cálculo bloqueado em NORMALIZATION: X_MISSING, Y_MISSING.'})
        self.assertEqual(itens[126]['bloqueio']['code'], 'CLIENT_EMAIL_MISSING')
        self.assertIsNone(itens[122]['dataVencimento'])

    def test_pendentes_valor_zero_ou_negativo_e_dado_incompleto(self):
        self.make_invoice(161, valor='0.00', hub=None, nome='Zero')
        self.make_invoice(162, valor='-5.00', nome='Negativo')
        itens = {i['invoiceId']: i for g in self.pendentes() for i in g['itens']}
        for invoice_id in (161, 162):
            self.assertEqual(itens[invoice_id]['bloqueio'], {
                'code': 'INVOICE_DATA_INCOMPLETE', 'message': 'Faltou na fatura: valor.'})

    def test_pendentes_linhas_inconsistentes_nao_derrubam_a_listagem(self):
        from models.fatura_concessionaria import FaturaConcessionaria
        self.make_invoice(171, plants=(999,), nome='PlantaOrfa')  # conexao aponta para usina inexistente
        self.make_invoice(172, nome='UcOrfa')
        self.make_invoice(173, nome='ClienteOrfao')
        FaturaConcessionaria.query.filter_by(id=172).update({'consumer_unit_id': 9999})
        FaturaConcessionaria.query.filter_by(id=173).update({'client_id': 9999})
        db.session.commit()
        data = self.pendentes()
        self.assertEqual([(g['usinaId'], [i['invoiceId'] for i in g['itens']]) for g in data], [(None, [171])])

    def test_pendentes_usa_ultima_execucao_mesmo_sem_snapshot(self):
        self.make_invoice(131, nome='Velho')  # execucao 1 calculada
        self.add_execution(131, 10, stage='RULE_RESOLUTION')  # execucao 2 bloqueada, mais recente
        item = self.pendentes()[0]['itens'][0]
        self.assertEqual(item['bloqueio']['code'], 'RULE_MISSING')
        self.assertIsNone(item['valorHub'])

    def test_pendentes_emissao_pendente_reusa_valor_e_modo_gravados(self):
        self.make_invoice(141, nome='Retry')
        db.session.add(Fatura(id=1141, empresa_id=10, client_id=141, consumer_unit_id=141, concessionaria='Copel',
                              competencia='2026-10', valor=300, mes_vencimento=date(2026, 11, 20),
                              status_interno='erro_emissao', billing_mode='separate'))
        db.session.commit()
        item = self.pendentes()[0]['itens'][0]
        self.assertTrue(item['emissaoPendente'])
        self.assertEqual((item['valorCobrar'], item['billingMode'], item['valorHub']), ('300.00', 'separate', '168.75'))

    def test_pendentes_isolamento_e_permissao(self):
        self.make_invoice(151, tenant=20)
        self.assertEqual(self.pendentes(1), [])
        self.assertEqual(len(self.pendentes(4)), 1)
        self.assertEqual(self.client.get(self.URL).status_code, 401)
        self.assertEqual(self.client.get(self.URL, headers=self.headers(3)).status_code, 403)


if __name__ == '__main__':
    unittest.main()
