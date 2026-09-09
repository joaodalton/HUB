"""Cotas por empresa: trial limitado, vitalicio e assinatura ausente."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

_DATABASE_FILE = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_DATABASE_FILE.close()
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app  # noqa: E402
from extensions import db  # noqa: E402
from models.assinatura import Assinatura  # noqa: E402
from models.empresa import Empresa  # noqa: E402
from models.limite_contratado import LimiteContratado  # noqa: E402
from models.user import User  # noqa: E402
from planos.catalogo import PLANOS  # noqa: E402
from services.quota_service import get_limite, verificar_cota  # noqa: E402
from utils.auth import generate_token  # noqa: E402
try:
    from .support import IsolatedTestRuntime  # noqa: E402
except ImportError:
    from support import IsolatedTestRuntime  # noqa: E402


class QuotaEnforcementTest(IsolatedTestRuntime, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prepare_test_runtime(
            f"sqlite:///{_DATABASE_FILE.name.replace(chr(92), '/')}",
            'quota-enforcement-test-secret',
        )
        cls._franquias_originais = PLANOS['starter']['franquia'].copy()
        PLANOS['starter']['franquia']['clientes'] = 2
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        with cls.app.app_context():
            db.create_all()
            vitalicia = Empresa(nome='Vitalicia', slug='quota-vitalicia')
            trial = Empresa(nome='Trial', slug='quota-trial')
            sem_assinatura = Empresa(nome='Sem assinatura', slug='quota-sem-assinatura')
            db.session.add_all([vitalicia, trial, sem_assinatura])
            db.session.flush()
            db.session.add_all([
                Assinatura(empresa_id=vitalicia.id, plano_chave='starter', tipo='vitalicio', status='ativa'),
                Assinatura(empresa_id=trial.id, plano_chave='starter', tipo='trial', status='trial'),
                LimiteContratado(empresa_id=trial.id, recurso='clientes', quantidade_contratada=2),
                User(empresa_id=vitalicia.id, nome='Owner vitalicio', email='vitalicio@quota.test', password_hash='x', role='owner'),
                User(empresa_id=trial.id, nome='Owner trial', email='trial@quota.test', password_hash='x', role='owner'),
            ])
            db.session.commit()
            cls.vitalicia_id = vitalicia.id
            cls.trial_id = trial.id
            cls.sem_assinatura_id = sem_assinatura.id
            cls.vitalicia_owner_id = User.query.filter_by(empresa_id=vitalicia.id).one().id
            cls.trial_owner_id = User.query.filter_by(empresa_id=trial.id).one().id

    @classmethod
    def tearDownClass(cls):
        PLANOS['starter']['franquia'].update(cls._franquias_originais)
        with cls.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()
        os.unlink(_DATABASE_FILE.name)
        cls.restore_test_runtime()

    def _token(self, user_id: int) -> str:
        with self.app.app_context():
            return generate_token(user_id)

    def _create_client(self, owner_id: int, number: int):
        return self.app.test_client().post(
            '/api/v1/clients',
            headers={'Authorization': f'Bearer {self._token(owner_id)}'},
            json={
                'nome': f'Cliente {number}',
                'cpf': f'{number:011d}',
                'email': f'cliente-{number}@quota.test',
            },
        )

    def test_trial_blocks_the_next_client_and_returns_quota_details(self):
        PLANOS['starter']['franquia']['clientes'] = 2
        self.assertEqual(self._create_client(self.trial_owner_id, 1).status_code, 201)
        self.assertEqual(self._create_client(self.trial_owner_id, 2).status_code, 201)

        blocked = self._create_client(self.trial_owner_id, 3)
        self.assertEqual(blocked.status_code, 403)
        self.assertEqual(blocked.get_json()['code'], 'QUOTA_EXCEEDED')
        self.assertEqual(blocked.get_json()['details'], {'recurso': 'clientes', 'uso': 2, 'limite': 2})

    def test_vitalicia_and_empresa_sem_assinatura_are_unlimited(self):
        for number in range(10, 14):
            self.assertEqual(self._create_client(self.vitalicia_owner_id, number).status_code, 201)

        with self.app.test_request_context('/'):
            from flask import g
            g.current_empresa_id = self.sem_assinatura_id
            self.assertIsNone(get_limite(self.sem_assinatura_id, 'clientes'))
            self.assertEqual(verificar_cota(self.sem_assinatura_id, 'clientes'), (True, 0, None))

    def test_all_creation_routes_enforce_their_resource_quota(self):
        with self.app.app_context():
            LimiteContratado.query.filter_by(empresa_id=self.trial_id, recurso='clientes').delete()
            db.session.commit()
        PLANOS['starter']['franquia'].update({'clientes': 0, 'ucs': 0, 'usinas': 0, 'usuarios': 0})
        try:
            headers = {'Authorization': f'Bearer {self._token(self.trial_owner_id)}'}
            requests = (
                ('/api/v1/clients', {'nome': 'Bloqueado', 'cpf': '99999999999', 'email': 'bloqueado@quota.test'}, 'clientes'),
                ('/api/v1/ucs', {'clienteId': 1, 'codigo': 'BLOQUEADA'}, 'ucs'),
                ('/api/v1/plants', {'nome': 'Bloqueada'}, 'usinas'),
                ('/api/v1/users', {'nome': 'Bloqueado', 'email': 'usuario@quota.test', 'senha': 'senha-segura'}, 'usuarios'),
            )
            client = self.app.test_client()
            for path, payload, recurso in requests:
                response = client.post(path, headers=headers, json=payload)
                self.assertEqual(response.status_code, 403)
                self.assertEqual(response.get_json()['code'], 'QUOTA_EXCEEDED')
                self.assertEqual(response.get_json()['details']['recurso'], recurso)
        finally:
            PLANOS['starter']['franquia'].update(self._franquias_originais)
            with self.app.app_context():
                db.session.add(LimiteContratado(empresa_id=self.trial_id, recurso='clientes', quantidade_contratada=2))
                db.session.commit()


if __name__ == '__main__':
    unittest.main()
