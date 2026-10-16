"""Contrato HTTP Task 8: RBAC e mapeamento de erro em /api/v1/reports."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app
from extensions import db
from models.empresa import Empresa
from models.user import User
from utils.auth import generate_token

try:
    from .support import IsolatedTestRuntime
except ImportError:
    from support import IsolatedTestRuntime


class ReportRoutesTest(IsolatedTestRuntime, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.prepare_test_runtime('sqlite:///' + (Path(cls.temp.name) / 'reports.db').as_posix(),
                                 'report-routes-test', limiter_enabled=False)
        cls.app = create_app()

    @classmethod
    def tearDownClass(cls):
        cls.restore_test_runtime()
        cls.temp.cleanup()

    def setUp(self):
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        db.session.add(Empresa(id=1, nome='Empresa 1', slug='reports-1'))
        for user_id, role in ((1, 'owner'), (2, 'operator')):
            db.session.add(User(id=user_id, empresa_id=1, nome=role,
                                 email=f'user-{user_id}@example.test', password_hash='x', role=role))
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

    def _login_como(self, role):
        user_id = {'owner': 1, 'operator': 2}[role]
        return self.headers(user_id)

    def test_tipos_nao_exige_banco_e_retorna_lista_fixa(self):
        response = self.client.get('/api/v1/reports/tipos', headers=self.headers(1))
        self.assertEqual(response.status_code, 200)
        tipos = {item['tipo'] for item in response.get_json()['data']}
        self.assertEqual(tipos, {'cadastro', 'financeiro', 'rateio'})

    @patch('routes.report_routes.gerar_relatorio')
    def test_gerar_sem_permissao_retorna_403(self, mock_gerar):
        response = self.client.post('/api/v1/reports/gerar', json={'tipo': 'cadastro', 'formato': 'sheet'},
                                     headers=self._login_como('operator'))
        self.assertEqual(response.status_code, 403)
        mock_gerar.assert_not_called()

    @patch('routes.report_routes.gerar_relatorio')
    def test_gerar_scope_error_retorna_409(self, mock_gerar):
        from services.google_reports_auth import ReportScopeError
        mock_gerar.side_effect = ReportScopeError(['x'])
        response = self.client.post('/api/v1/reports/gerar', json={'tipo': 'cadastro', 'formato': 'sheet'},
                                     headers=self._login_como('owner'))
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()['code'], 'GOOGLE_SCOPE_MISSING')

    @patch('routes.report_routes.gerar_relatorio')
    def test_gerar_sucesso_retorna_201(self, mock_gerar):
        mock_gerar.return_value = {'driveFileId': 'abc', 'webViewLink': 'https://x'}
        response = self.client.post('/api/v1/reports/gerar', json={'tipo': 'cadastro', 'formato': 'sheet'},
                                     headers=self._login_como('owner'))
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json()['data'], {'driveFileId': 'abc', 'webViewLink': 'https://x'})


if __name__ == '__main__':
    unittest.main()
