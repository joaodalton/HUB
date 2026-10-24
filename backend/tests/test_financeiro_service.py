"""criar_pendencia_pagar_concessionaria: cria pendencia idempotente quando
existe FaturaConcessionaria correspondente por (empresa_id, consumer_unit_id,
competencia); nao cria nada quando nao existe correspondencia.

calcular_repasse/verificar_e_criar_pendencia_repasse: calcula o valor devido
ao usineiro e cria pendencia idempotente quando todas as UCs conectadas a
usina ja pagaram na competencia."""
import os
import sys
import tempfile
import unittest
from datetime import date
from decimal import Decimal
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
from models.plant import Plant  # noqa: E402
from models.consumer_unit import PlantConnection  # noqa: E402
from services.financeiro_service import (  # noqa: E402
    ORIGEM_PAGAR_CONCESSIONARIA,
    ORIGEM_REPASSE_USINEIRO,
    calcular_repasse,
    criar_pendencia_pagar_concessionaria,
    obter_dashboard,
    verificar_e_criar_pendencia_repasse,
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
        for model in (Pendencia, Fatura, FaturaConcessionaria, PlantConnection, Plant, ConsumerUnit, Client, Document):
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

    def test_calcular_repasse_percentual(self):
        plant = Plant(empresa_id=1, nome='Usina 1', uc='UC-USINA', kw_pico=Decimal('100'),
                       repasse_tipo='percentual', repasse_valor=Decimal('10.00'))
        db.session.add(plant)
        db.session.flush()
        conexao = PlantConnection(empresa_id=1, consumer_unit_id=self.uc.id, plant_id=plant.id)
        db.session.add(conexao)
        db.session.commit()

        self.assertEqual(calcular_repasse(plant, '2026-01'), Decimal('10.00'))

    def test_calcular_repasse_sem_contrato_configurado_retorna_none(self):
        plant = Plant(empresa_id=1, nome='Usina 2', uc='UC-USINA-2', kw_pico=Decimal('100'))
        db.session.add(plant)
        db.session.commit()

        self.assertIsNone(calcular_repasse(plant, '2026-01'))

    def test_calcular_repasse_tipo_setado_sem_valor_retorna_none_sem_estourar(self):
        plant = Plant(empresa_id=1, nome='Usina 2b', uc='UC-USINA-2B', kw_pico=Decimal('100'),
                       repasse_tipo='percentual', repasse_valor=None)
        db.session.add(plant)
        db.session.commit()

        self.assertIsNone(calcular_repasse(plant, '2026-01'))

    def test_verificar_e_criar_pendencia_repasse_so_cria_quando_todas_ucs_pagaram(self):
        plant = Plant(empresa_id=1, nome='Usina 3', uc='UC-USINA-3', kw_pico=Decimal('100'),
                       repasse_tipo='valor_fixo', repasse_valor=Decimal('50.00'))
        db.session.add(plant)
        db.session.flush()
        uc2 = ConsumerUnit(empresa_id=1, client_id=self.cliente.id, codigo='UC-2')
        db.session.add(uc2)
        db.session.flush()
        db.session.add_all([
            PlantConnection(empresa_id=1, consumer_unit_id=self.uc.id, plant_id=plant.id),
            PlantConnection(empresa_id=1, consumer_unit_id=uc2.id, plant_id=plant.id),
        ])
        db.session.commit()

        verificar_e_criar_pendencia_repasse(plant.id, '2026-01')
        self.assertEqual(
            Pendencia.query.filter_by(plant_id=plant.id, origem=ORIGEM_REPASSE_USINEIRO).count(), 0)

        fatura2 = Fatura(
            empresa_id=1, client_id=self.cliente.id, consumer_unit_id=uc2.id,
            concessionaria='CEMIG', competencia='2026-01', valor=50,
            mes_vencimento=date(2026, 1, 10), asaas_status='received',
        )
        db.session.add(fatura2)
        db.session.commit()

        verificar_e_criar_pendencia_repasse(plant.id, '2026-01')
        pendencia = Pendencia.query.filter_by(plant_id=plant.id, origem=ORIGEM_REPASSE_USINEIRO).one()
        self.assertEqual(pendencia.competencia, '2026-01')
        self.assertIn('valor', pendencia.metadados)

    def test_verificar_e_criar_pendencia_repasse_arredonda_valor_para_centavos(self):
        plant = Plant(empresa_id=1, nome='Usina 3b', uc='UC-USINA-3B', kw_pico=Decimal('100'),
                       repasse_tipo='percentual', repasse_valor=Decimal('33.335'))
        db.session.add(plant)
        db.session.flush()
        db.session.add(PlantConnection(empresa_id=1, consumer_unit_id=self.uc.id, plant_id=plant.id))
        db.session.commit()

        verificar_e_criar_pendencia_repasse(plant.id, '2026-01')
        pendencia = Pendencia.query.filter_by(plant_id=plant.id, origem=ORIGEM_REPASSE_USINEIRO).one()
        # calcular_repasse retorna 33.335 (100 * 33.335 / 100); congelado deve arredondar para 33.34 (ROUND_HALF_UP).
        self.assertEqual(pendencia.metadados['valor'], '33.34')

    def test_verificar_e_criar_pendencia_repasse_idempotente(self):
        plant = Plant(empresa_id=1, nome='Usina 4', uc='UC-USINA-4', kw_pico=Decimal('100'),
                       repasse_tipo='valor_fixo', repasse_valor=Decimal('50.00'))
        db.session.add(plant)
        db.session.flush()
        db.session.add(PlantConnection(empresa_id=1, consumer_unit_id=self.uc.id, plant_id=plant.id))
        db.session.commit()

        verificar_e_criar_pendencia_repasse(plant.id, '2026-01')
        verificar_e_criar_pendencia_repasse(plant.id, '2026-01')
        self.assertEqual(
            Pendencia.query.filter_by(plant_id=plant.id, origem=ORIGEM_REPASSE_USINEIRO).count(), 1)

    def test_verificar_e_criar_pendencia_repasse_sem_conexoes_nao_cria_nada(self):
        plant_sem_conexao = Plant(empresa_id=1, nome='Usina 5', uc='UC-USINA-5', kw_pico=Decimal('100'),
                                   repasse_tipo='valor_fixo', repasse_valor=Decimal('50.00'))
        db.session.add(plant_sem_conexao)
        db.session.commit()

        verificar_e_criar_pendencia_repasse(plant_sem_conexao.id, '2026-01')
        self.assertEqual(Pendencia.query.filter_by(plant_id=plant_sem_conexao.id).count(), 0)

    def test_obter_dashboard_oculta_repasse_enquanto_nem_todas_ucs_pagaram(self):
        plant = Plant(empresa_id=1, nome='Usina 6', uc='UC-USINA-6', kw_pico=Decimal('100'),
                       repasse_tipo='valor_fixo', repasse_valor=Decimal('50.00'))
        db.session.add(plant)
        db.session.flush()
        uc2 = ConsumerUnit(empresa_id=1, client_id=self.cliente.id, codigo='UC-6b')
        db.session.add(uc2)
        db.session.flush()
        db.session.add_all([
            PlantConnection(empresa_id=1, consumer_unit_id=self.uc.id, plant_id=plant.id),
            PlantConnection(empresa_id=1, consumer_unit_id=uc2.id, plant_id=plant.id),
        ])
        db.session.commit()

        dashboard = obter_dashboard(1, '2026-01')
        usina = next(u for u in dashboard['porUsina'] if u['usinaId'] == plant.id)
        self.assertIsNone(usina['repasseCalculado'])
        self.assertTrue(usina.get('aguardandoPagamentos'))

    def test_obter_dashboard_mostra_repasse_quando_todas_ucs_pagaram(self):
        plant = Plant(empresa_id=1, nome='Usina 7', uc='UC-USINA-7', kw_pico=Decimal('100'),
                       repasse_tipo='valor_fixo', repasse_valor=Decimal('50.00'))
        db.session.add(plant)
        db.session.flush()
        db.session.add(PlantConnection(empresa_id=1, consumer_unit_id=self.uc.id, plant_id=plant.id))
        db.session.commit()

        dashboard = obter_dashboard(1, '2026-01')
        usina = next(u for u in dashboard['porUsina'] if u['usinaId'] == plant.id)
        self.assertEqual(usina['repasseCalculado'], '50.00')
        self.assertNotIn('aguardandoPagamentos', usina)

    def test_obter_dashboard_exclui_fatura_cancelada_de_pendente_e_recebido(self):
        fatura_cancelada = Fatura(
            empresa_id=1, client_id=self.cliente.id, consumer_unit_id=self.uc.id,
            concessionaria='CEMIG', competencia='2026-02', valor=80,
            mes_vencimento=date(2026, 2, 10), asaas_status='canceled',
        )
        db.session.add(fatura_cancelada)
        db.session.commit()

        dashboard = obter_dashboard(1, '2026-02')
        cliente = next(c for c in dashboard['porCliente'] if c['clienteId'] == self.cliente.id)
        self.assertEqual(cliente['recebido'], '0.00')
        self.assertEqual(cliente['pendente'], '0.00')


if __name__ == '__main__':
    unittest.main()
