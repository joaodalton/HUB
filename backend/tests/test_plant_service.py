"""update_plant: aceita contrato de repasse ao usineiro (repasseTipo/repasseValor),
validando repasseTipo contra os valores aceitos pela CheckConstraint do banco
antes de persistir."""
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
from models.empresa import Empresa  # noqa: E402
from models.plant import Plant  # noqa: E402
from models.user import User  # noqa: E402
from services.plant_service import update_plant  # noqa: E402
from utils.auth import generate_token  # noqa: E402
try:
    from .support import IsolatedTestRuntime  # noqa: E402
except ImportError:
    from support import IsolatedTestRuntime  # noqa: E402


class PlantServiceTest(IsolatedTestRuntime, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prepare_test_runtime(
            f"sqlite:///{_DATABASE_FILE.name.replace(chr(92), '/')}",
            'plant-service-test-secret',
        )
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        with cls.app.app_context():
            db.create_all()
            empresa = Empresa(nome='A', slug='plant-service-a')
            db.session.add(empresa)
            db.session.flush()
            owner = User(empresa_id=empresa.id, nome='Owner', email='owner@plant-service.test',
                          password_hash='x', role='owner')
            db.session.add(owner)
            db.session.commit()
            cls.owner_id = owner.id

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
        db.session.query(Plant).delete()
        db.session.commit()
        self.plant = Plant(empresa_id=1, nome='Usina', uc='UC-1', kw_pico=100)
        db.session.add(self.plant)
        db.session.commit()

    def tearDown(self):
        db.session.rollback()
        self.ctx.pop()

    def test_update_plant_aceita_repasse_tipo_e_valor(self):
        resultado = update_plant(self.plant.id, {'repasseTipo': 'percentual', 'repasseValor': '15.00'})
        self.assertEqual(resultado['repasseTipo'], 'percentual')
        self.assertEqual(resultado['repasseValor'], 15.00)

    def test_update_plant_aceita_repasse_valor_fixo(self):
        resultado = update_plant(self.plant.id, {'repasseTipo': 'valor_fixo', 'repasseValor': '200.50'})
        self.assertEqual(resultado['repasseTipo'], 'valor_fixo')
        self.assertEqual(resultado['repasseValor'], 200.50)

    def test_update_plant_rejeita_repasse_tipo_invalido(self):
        with self.assertRaises(ValueError):
            update_plant(self.plant.id, {'repasseTipo': 'outra_coisa'})

    def test_update_plant_rejeita_repasse_valor_invalido(self):
        with self.assertRaises(ValueError):
            update_plant(self.plant.id, {'repasseValor': 'nao-e-numero'})

    def test_update_plant_aceita_repasse_tipo_e_valor_nulos(self):
        update_plant(self.plant.id, {'repasseTipo': 'percentual', 'repasseValor': '10.00'})
        resultado = update_plant(self.plant.id, {'repasseTipo': None, 'repasseValor': None})
        self.assertIsNone(resultado['repasseTipo'])
        self.assertIsNone(resultado['repasseValor'])

    def test_put_route_retorna_400_quando_repasse_tipo_invalido(self):
        token = generate_token(self.owner_id)
        resposta = self.app.test_client().put(
            f'/api/v1/plants/{self.plant.id}',
            headers={'Authorization': f'Bearer {token}'},
            json={'repasseTipo': 'outra_coisa'},
        )
        self.assertEqual(resposta.status_code, 400)
        self.assertIn('error', resposta.get_json())


if __name__ == '__main__':
    unittest.main()
