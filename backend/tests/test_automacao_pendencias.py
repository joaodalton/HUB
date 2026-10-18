"""Automacao de pendencias: deduplicacao e auto-resolucao por chave de regra
(metadados.regra), com fallback para o titulo em pendencias legadas."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

_DATABASE_FILE = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_DATABASE_FILE.close()
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flask import g  # noqa: E402

from app import create_app  # noqa: E402
from extensions import db  # noqa: E402
from models.client import Client  # noqa: E402
from models.consumer_unit import ConsumerUnit, PlantConnection  # noqa: E402
from models.empresa import Empresa  # noqa: E402
from models.pendencia import Pendencia  # noqa: E402
from models.plant import Plant  # noqa: E402
from services import automacao_service as auto  # noqa: E402
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
        for model in (Pendencia, PlantConnection, ConsumerUnit, Client, Plant):
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


if __name__ == '__main__':
    unittest.main()
