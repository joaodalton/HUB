"""Automacao de pendencias: deduplicacao e auto-resolucao por chave de regra
(metadados.regra), com fallback para o titulo em pendencias legadas."""
import os
import sys
import tempfile
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

_DATABASE_FILE = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_DATABASE_FILE.close()
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flask import g  # noqa: E402

from app import create_app  # noqa: E402
from extensions import db  # noqa: E402
from models.client import Client  # noqa: E402
from models.consumer_unit import ConsumerUnit, PlantConnection  # noqa: E402
from models.empresa import Empresa  # noqa: E402
from models.fatura import Fatura  # noqa: E402
from models.pendencia import Pendencia  # noqa: E402
from models.plant import Plant  # noqa: E402
from services import automacao_service as auto  # noqa: E402
from services.financeiro_service import ORIGEM_REPASSE_USINEIRO  # noqa: E402
try:
    from .support import IsolatedTestRuntime  # noqa: E402
except ImportError:
    from support import IsolatedTestRuntime  # noqa: E402


class AutomacaoPendenciasTest(IsolatedTestRuntime, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prepare_test_runtime(
            f"sqlite:///{_DATABASE_FILE.name.replace(chr(92), '/')}",
            'automacao-test-secret',
        )
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        with cls.app.app_context():
            db.create_all()
            db.session.add(Empresa(nome='A', slug='automacao-a'))
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
        for model in (Pendencia, Fatura, PlantConnection, ConsumerUnit, Client, Plant):
            db.session.query(model).delete()
        db.session.commit()
        self.cliente = Client(empresa_id=1, nome='Cliente', cpf='12345678900', email='c@x.test')
        db.session.add(self.cliente)
        db.session.flush()
        self.uc = ConsumerUnit(empresa_id=1, client_id=self.cliente.id, codigo='UC-1')
        self.plant = Plant(empresa_id=1, nome='Usina', uc='UC-P', kw_pico=10)
        db.session.add_all([self.uc, self.plant])
        db.session.commit()

    def tearDown(self):
        db.session.rollback()
        self.ctx.pop()

    def _pendencia(self, titulo, metadados=None, uc_id=None):
        pendencia = Pendencia(
            empresa_id=1, tipo='pendencia', categoria='UCs', origem='Automacao', status='aberta',
            titulo=titulo, descricao='x', client_id=self.cliente.id, consumer_unit_id=uc_id, metadados=metadados,
        )
        db.session.add(pendencia)
        db.session.commit()
        return pendencia

    def test_regra_is_read_from_metadados_or_legacy_title(self):
        com_regra = self._pendencia('Qualquer texto', {'regra': auto.REGRA_UC_SEM_USINA})
        legado = self._pendencia('UC UC-1 sem usina vinculada há 10 dias')
        falta_doc = self._pendencia('Falta documento obrigatório do cliente X')
        falta_campo = self._pendencia('Falta telefone do cliente X')
        self.assertEqual(auto._regra_de(com_regra), auto.REGRA_UC_SEM_USINA)
        self.assertEqual(auto._regra_de(legado), auto.REGRA_UC_SEM_USINA)
        self.assertEqual(auto._regra_de(falta_doc), auto.REGRA_DOCUMENTOS_OBRIGATORIOS)
        self.assertEqual(auto._regra_de(falta_campo), auto.REGRA_CAMPOS_OBRIGATORIOS)
        self.assertIsNone(auto._regra_de(self._pendencia('Pendencia manual qualquer')))

    def test_dedup_uses_rule_not_title(self):
        self._pendencia('Titulo renomeado sem a palavra-chave', {'regra': auto.REGRA_CLIENTE_SEM_UC})
        self.assertTrue(auto._ja_existe_pendencia_ativa(cliente_id=self.cliente.id, regra=auto.REGRA_CLIENTE_SEM_UC))
        self.assertFalse(auto._ja_existe_pendencia_ativa(cliente_id=self.cliente.id, regra=auto.REGRA_CAMPOS_OBRIGATORIOS))

    def test_resolution_closes_only_when_condition_is_met_and_commits_once(self):
        sem_usina_nova = self._pendencia('Renomeada', {'regra': auto.REGRA_UC_SEM_USINA}, uc_id=self.uc.id)
        sem_usina_legada = self._pendencia('UC UC-1 sem usina vinculada', uc_id=self.uc.id)
        sem_uc = self._pendencia('Cliente X sem UC cadastrada', {'regra': auto.REGRA_CLIENTE_SEM_UC})

        # Sem conexao ainda: nada resolve
        self.assertEqual(auto.resolver_pendencias_resolvidas(), 0 + 1)  # cliente ja tem UC -> 'sem UC' resolve
        self.assertEqual(Pendencia.query.get(sem_uc.id).status, 'resolvida')
        self.assertEqual(Pendencia.query.get(sem_usina_nova.id).status, 'aberta')

        db.session.add(PlantConnection(empresa_id=1, plant_id=self.plant.id, consumer_unit_id=self.uc.id, percentual=10))
        db.session.commit()
        self.assertEqual(auto.resolver_pendencias_resolvidas(), 2)
        self.assertEqual(Pendencia.query.get(sem_usina_nova.id).status, 'resolvida')
        self.assertEqual(Pendencia.query.get(sem_usina_legada.id).status, 'resolvida')
        self.assertIsNotNone(Pendencia.query.get(sem_usina_legada.id).resolved_at)

    def _fixed_utcnow(self):
        from datetime import datetime as real_datetime
        return real_datetime(2026, 1, 10)

    def test_verificar_fatura_geracao_usina_cria_pendencia_apos_dia_emissao(self):
        self.plant.dia_emissao_usina = 5
        db.session.commit()
        with patch('services.automacao_service.datetime') as mock_datetime:
            mock_datetime.utcnow.side_effect = self._fixed_utcnow
            resultado = auto.verificar_e_criar_pendencias()
        self.assertEqual(resultado['fatura_geracao_usina'], 1)
        pendencia = Pendencia.query.filter_by(
            plant_id=self.plant.id, origem=auto.REGRA_FATURA_GERACAO_USINA
        ).one()
        self.assertEqual(pendencia.categoria, 'Usinas')
        self.assertEqual(pendencia.competencia, '2026-01')

    def test_verificar_fatura_geracao_usina_nao_duplica_na_mesma_competencia(self):
        self.plant.dia_emissao_usina = 5
        db.session.commit()
        with patch('services.automacao_service.datetime') as mock_datetime:
            mock_datetime.utcnow.side_effect = self._fixed_utcnow
            auto.verificar_e_criar_pendencias()
            resultado = auto.verificar_e_criar_pendencias()
        self.assertEqual(resultado['fatura_geracao_usina'], 0)
        self.assertEqual(
            Pendencia.query.filter_by(plant_id=self.plant.id, origem=auto.REGRA_FATURA_GERACAO_USINA).count(), 1
        )

    def test_verificar_fatura_geracao_usina_sem_dia_emissao_configurado_nao_cria(self):
        self.plant.dia_emissao_usina = None
        db.session.commit()
        with patch('services.automacao_service.datetime') as mock_datetime:
            mock_datetime.utcnow.side_effect = self._fixed_utcnow
            resultado = auto.verificar_e_criar_pendencias()
        self.assertEqual(resultado['fatura_geracao_usina'], 0)

    def test_verificar_fatura_geracao_usina_antes_do_dia_emissao_nao_cria(self):
        self.plant.dia_emissao_usina = 20
        db.session.commit()
        with patch('services.automacao_service.datetime') as mock_datetime:
            mock_datetime.utcnow.side_effect = self._fixed_utcnow
            resultado = auto.verificar_e_criar_pendencias()
        self.assertEqual(resultado['fatura_geracao_usina'], 0)

    def test_verificar_repasses_pendentes_cria_pendencia_perdida_na_corrida(self):
        self.plant.repasse_tipo = 'valor_fixo'
        self.plant.repasse_valor = Decimal('50.00')
        db.session.add(PlantConnection(empresa_id=1, plant_id=self.plant.id, consumer_unit_id=self.uc.id))
        db.session.add(Fatura(
            empresa_id=1, client_id=self.cliente.id, consumer_unit_id=self.uc.id,
            concessionaria='CEMIG', competencia='2026-01', valor=100,
            mes_vencimento=date(2026, 1, 10), asaas_status='received',
        ))
        db.session.commit()

        with patch('services.automacao_service.datetime') as mock_datetime:
            mock_datetime.utcnow.side_effect = self._fixed_utcnow
            resultado = auto.verificar_e_criar_pendencias()

        self.assertEqual(resultado['repasses_pendentes'], 1)
        self.assertEqual(
            Pendencia.query.filter_by(plant_id=self.plant.id, origem=ORIGEM_REPASSE_USINEIRO).count(), 1
        )

    def test_verificar_repasses_pendentes_nao_duplica_ao_rodar_duas_vezes(self):
        self.plant.repasse_tipo = 'valor_fixo'
        self.plant.repasse_valor = Decimal('50.00')
        db.session.add(PlantConnection(empresa_id=1, plant_id=self.plant.id, consumer_unit_id=self.uc.id))
        db.session.add(Fatura(
            empresa_id=1, client_id=self.cliente.id, consumer_unit_id=self.uc.id,
            concessionaria='CEMIG', competencia='2026-01', valor=100,
            mes_vencimento=date(2026, 1, 10), asaas_status='received',
        ))
        db.session.commit()

        with patch('services.automacao_service.datetime') as mock_datetime:
            mock_datetime.utcnow.side_effect = self._fixed_utcnow
            auto.verificar_e_criar_pendencias()
            resultado = auto.verificar_e_criar_pendencias()

        self.assertEqual(resultado['repasses_pendentes'], 0)
        self.assertEqual(
            Pendencia.query.filter_by(plant_id=self.plant.id, origem=ORIGEM_REPASSE_USINEIRO).count(), 1
        )


if __name__ == '__main__':
    unittest.main()
