"""Criar uma nova empresa muda o resultado do guard de get_drive_service()
(empresa unica vs. 2+), entao o cache por empresa_id precisa ser invalidado
inteiro -- senao uma empresa ja cacheada com root_folder_id='' (permitido
so enquanto era a UNICA empresa) continua vazando cross-tenant depois que
uma segunda empresa e criada, pelo resto da vida do processo."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

_DB = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_DB.close()
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app
from extensions import db
from models.empresa import Empresa
import services.drive_service as drive_service
from services.empresa_service import criar_empresa_com_owner
try:
    from .support import IsolatedTestRuntime
except ImportError:
    from support import IsolatedTestRuntime


class EmpresaServiceDriveCacheTest(IsolatedTestRuntime, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prepare_test_runtime(f"sqlite:///{_DB.name.replace(chr(92), '/')}", 'empresa-drive-cache-test')
        cls.app = create_app()
        with cls.app.app_context():
            db.create_all()
            db.session.add(Empresa(nome='Unica', slug='empresa-drive-cache-unica'))
            db.session.commit()

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()
        os.unlink(_DB.name)
        cls.restore_test_runtime()

    def tearDown(self):
        drive_service.invalidate_drive_cache()

    def test_criar_empresa_invalidates_cached_drive_service(self):
        # Simula o cache populado enquanto so havia 1 empresa (root_folder_id
        # vazio e permitido pelo guard de get_drive_service() nesse caso).
        drive_service._drive_service_cache[1] = Mock(root_folder_id='')
        self.assertIn(1, drive_service._drive_service_cache)

        with self.app.app_context():
            criar_empresa_com_owner({
                'empresa': {'nome': 'Segunda Empresa'},
                'owner': {
                    'nome': 'Owner Segunda',
                    'email': 'owner-segunda@example.test',
                    'senha': 'senha123'
                }
            })

        self.assertEqual(drive_service._drive_service_cache, {})


if __name__ == '__main__':
    unittest.main()
