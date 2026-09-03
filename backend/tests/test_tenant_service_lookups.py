import os
import sys
import tempfile
import unittest
from pathlib import Path

_DB = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_DB.close()
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flask import g
from app import create_app
from config import Config
from extensions import db
from models.client import Client
from models.consumer_unit import ConsumerUnit, PlantConnection
from models.document import Document
from models.empresa import Empresa
from models.plant import Plant
from services.client_service import create_client, delete_client, update_client
from services.document_service import delete_document
from services.pendencia_service import criar_pendencia_manual
from services.plant_service import delete_plant, update_plant
from services.rateio_formulario_service import montar_tabela_formulario
from services.rateio_service import confirmar_selecao, preview_rateio
from services.settings_service import get_all_settings, update_settings
from services.uc_service import delete_uc, sync_connections, update_uc
try:
    from .support import IsolatedTestRuntime
except ImportError:
    from support import IsolatedTestRuntime


class TenantServiceLookupsTest(IsolatedTestRuntime, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prepare_test_runtime(
            f"sqlite:///{_DB.name.replace(chr(92), '/')}",
            'tenant-lookup-test',
        )
        cls.app = create_app()
        with cls.app.app_context():
            db.create_all()
            db.session.add_all([Empresa(nome='A', slug='lookup-a'), Empresa(nome='B', slug='lookup-b')])
            db.session.flush()
            client_a = Client(empresa_id=1, nome='A', cpf='12345678900', email='a@x.test')
            client_b = Client(empresa_id=2, nome='B', cpf='12345678901', email='b@x.test')
            plant_a = Plant(empresa_id=1, nome='A', uc='UC-A', kw_pico=1)
            plant_b = Plant(empresa_id=2, nome='B', uc='UC-B', kw_pico=1)
            db.session.add_all([client_a, client_b, plant_a, plant_b])
            db.session.flush()
            uc_a = ConsumerUnit(empresa_id=1, client_id=client_a.id, codigo='UC-A')
            uc_b = ConsumerUnit(empresa_id=2, client_id=client_b.id, codigo='UC-B')
            document_b = Document(empresa_id=2, nome='D', storage_provider='local', storage_ref='x')
            db.session.add_all([uc_a, uc_b, document_b])
            db.session.commit()
            cls.client_a, cls.client_b = client_a.id, client_b.id
            cls.plant_a, cls.plant_b = plant_a.id, plant_b.id
            cls.uc_a, cls.uc_b, cls.document_b = uc_a.id, uc_b.id, document_b.id

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()
        os.unlink(_DB.name)
        cls.restore_test_runtime()

    def test_foreign_ids_cannot_update_delete_or_be_referenced(self):
        with self.app.test_request_context('/'):
            g.current_empresa_id = 1
            self.assertIsNone(update_plant(self.plant_b, {'nome': 'Ataque'}))
            self.assertFalse(delete_plant(self.plant_b))
            self.assertIsNone(update_client(self.client_b, {'nome': 'Ataque'}))
            self.assertFalse(delete_client(self.client_b))
            self.assertIsNone(update_uc(self.uc_b, {'codigo': 'Ataque'}))
            self.assertFalse(delete_uc(self.uc_b))
            self.assertFalse(delete_document(self.document_b))
            sync_connections(
                ConsumerUnit.query.filter_by(id=self.uc_a).first(),
                [{'plantId': self.plant_b}],
            )
            self.assertEqual(PlantConnection.query.count(), 0)
            with self.assertRaisesRegex(ValueError, 'Cliente pertence a outra empresa'):
                criar_pendencia_manual({'categoria': 'Sistema', 'titulo': 'Teste', 'clienteId': self.client_b})
        with self.app.app_context():
            self.assertEqual(Plant.query.filter_by(id=self.plant_b).first().nome, 'B')

    def test_nested_client_uc_sets_current_empresa(self):
        with self.app.test_request_context('/'):
            g.current_empresa_id = 1
            created = create_client({
                'nome': 'Novo', 'cpf': '12345678902', 'email': 'novo@x.test',
                'ucs': [{'codigo': 'UC-N', 'conexoes': []}],
            })
            uc_id = created['ucs'][0]['id']
            self.assertEqual(ConsumerUnit.query.filter_by(id=uc_id).first().empresa_id, 1)
            updated = update_client(created['id'], {
                'nome': 'Novo',
                'ucs': [{'id': uc_id, 'codigo': 'UC-N2', 'conexoes': []}],
            })
            self.assertEqual(updated['ucs'][0]['id'], uc_id)
            self.assertEqual(ConsumerUnit.query.filter_by(id=uc_id).first().empresa_id, 1)

    def test_drive_root_setting_is_tenant_scoped(self):
        with self.app.test_request_context('/'):
            g.current_empresa_id = 1
            update_settings({'google_drive_root_folder_id': 'pasta-empresa-a'})
            self.assertEqual(get_all_settings()['google_drive_root_folder_id'], 'pasta-empresa-a')

        with self.app.test_request_context('/'):
            g.current_empresa_id = 2
            self.assertNotIn('google_drive_root_folder_id', get_all_settings())

    def test_rateio_foreign_ids_are_rejected_even_when_identity_mapped(self):
        with self.app.test_request_context('/'):
            g.current_empresa_id = 2
            Plant.query.filter_by(id=self.plant_b).first()
            ConsumerUnit.query.filter_by(id=self.uc_b).first()

            g.current_empresa_id = 1
            self.assertEqual(preview_rateio(self.plant_b), [])
            with self.assertRaisesRegex(ValueError, 'Usina nao encontrada'):
                montar_tabela_formulario(self.plant_b)
            with self.assertRaisesRegex(ValueError, f'UC id={self.uc_b} nao encontrada'):
                confirmar_selecao(
                    self.plant_a, '2026-09', [{'ucId': self.uc_b, 'percentual': 10}]
                )
            self.assertEqual(PlantConnection.query.filter_by(plant_id=self.plant_a).count(), 0)


if __name__ == '__main__':
    unittest.main()
