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
from extensions import db
from models.empresa import Empresa
from models.pendencia import Pendencia
from models.user import User
from services.pendencia_service import criar_pendencia_manual, update_pendencia
try:
    from .support import IsolatedTestRuntime
except ImportError:
    from support import IsolatedTestRuntime


class PendenciaResponsavelTest(IsolatedTestRuntime, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prepare_test_runtime(
            f"sqlite:///{_DB.name.replace(chr(92), '/')}",
            'pendencia-responsavel-test',
        )
        cls.app = create_app()
        with cls.app.app_context():
            db.create_all()
            db.session.add(Empresa(nome='A', slug='pendencia-resp-a'))
            db.session.flush()
            user_a = User(empresa_id=1, nome='U', email='u@x.test', password_hash='x', role='operator')
            db.session.add(user_a)
            db.session.commit()
            cls.user_a = user_a.id

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()
        os.unlink(_DB.name)
        cls.restore_test_runtime()

    def test_criar_com_responsavel_usuario_mantem_comportamento_atual(self):
        with self.app.test_request_context('/'):
            g.current_empresa_id = 1
            pendencia = criar_pendencia_manual({
                'categoria': 'Sistema', 'titulo': 'Teste', 'responsavelId': self.user_a,
            })
            self.assertEqual(pendencia['responsavelId'], self.user_a)
            self.assertEqual(pendencia['responsavelTipo'], 'usuario')
            self.assertIsNone(pendencia['responsavelCargo'])

    def test_criar_com_responsavel_cargo(self):
        with self.app.test_request_context('/'):
            g.current_empresa_id = 1
            pendencia = criar_pendencia_manual({
                'categoria': 'Sistema', 'titulo': 'Teste cargo',
                'responsavelTipo': 'cargo', 'responsavelCargo': 'financial',
            })
            self.assertEqual(pendencia['responsavelTipo'], 'cargo')
            self.assertEqual(pendencia['responsavelCargo'], 'financial')
            self.assertIsNone(pendencia['responsavelId'])

    def test_criar_com_cargo_invalido_levanta_erro(self):
        with self.app.test_request_context('/'):
            g.current_empresa_id = 1
            with self.assertRaisesRegex(ValueError, 'responsavelCargo invalido'):
                criar_pendencia_manual({
                    'categoria': 'Sistema', 'titulo': 'Teste',
                    'responsavelTipo': 'cargo', 'responsavelCargo': 'inexistente',
                })

    def test_criar_com_tipo_invalido_levanta_erro(self):
        with self.app.test_request_context('/'):
            g.current_empresa_id = 1
            with self.assertRaisesRegex(ValueError, 'responsavelTipo invalido'):
                criar_pendencia_manual({
                    'categoria': 'Sistema', 'titulo': 'Teste', 'responsavelTipo': 'grupo',
                })

    def test_criar_com_cargo_ignora_responsavel_id_enviado_junto(self):
        with self.app.test_request_context('/'):
            g.current_empresa_id = 1
            pendencia = criar_pendencia_manual({
                'categoria': 'Sistema', 'titulo': 'Teste',
                'responsavelId': self.user_a, 'responsavelTipo': 'cargo', 'responsavelCargo': 'admin',
            })
            self.assertIsNone(pendencia['responsavelId'])
            registro = Pendencia.query.filter_by(id=pendencia['id']).one()
            self.assertIsNone(registro.responsavel_id)
            self.assertEqual(registro.responsavel_cargo, 'admin')

    def test_update_de_usuario_para_cargo_zera_responsavel_id(self):
        with self.app.test_request_context('/'):
            g.current_empresa_id = 1
            criada = criar_pendencia_manual({
                'categoria': 'Sistema', 'titulo': 'Teste', 'responsavelId': self.user_a,
            })
            atualizada = update_pendencia(criada['id'], {
                'responsavelTipo': 'cargo', 'responsavelCargo': 'viewer',
            })
            self.assertIsNone(atualizada['responsavelId'])
            self.assertEqual(atualizada['responsavelTipo'], 'cargo')
            self.assertEqual(atualizada['responsavelCargo'], 'viewer')

    def test_update_de_cargo_para_usuario_zera_responsavel_cargo(self):
        with self.app.test_request_context('/'):
            g.current_empresa_id = 1
            criada = criar_pendencia_manual({
                'categoria': 'Sistema', 'titulo': 'Teste',
                'responsavelTipo': 'cargo', 'responsavelCargo': 'owner',
            })
            atualizada = update_pendencia(criada['id'], {
                'responsavelTipo': 'usuario', 'responsavelId': self.user_a,
            })
            self.assertEqual(atualizada['responsavelId'], self.user_a)
            self.assertIsNone(atualizada['responsavelCargo'])


if __name__ == '__main__':
    unittest.main()
