"""Importação ANEEL global: preview privado, publicação atômica e idempotência."""
import io
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch
from pathlib import Path

_DB = tempfile.NamedTemporaryFile(suffix='.db', delete=False); _DB.close()
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app
from extensions import db
from models.empresa import Empresa
from models.log_entry import LogEntry
from models.regulatory_tariff import RegulatoryTariff, RegulatoryTariffImport
from models.user import User
from utils.auth import generate_token
from sqlalchemy.exc import OperationalError
from config import Config
from services import regulatory_tariff_import_service
from services.aneel_ckan_client import AneelCkanClient, AneelCkanInvalidResponse, AneelCkanUnavailable, REQUIRED_COLUMNS
try:
    from .support import IsolatedTestRuntime
except ImportError:
    from support import IsolatedTestRuntime


class RepeatingStream:
    def __init__(self, size): self.remaining = size

    def read(self, size=-1):
        if not self.remaining: return b''
        count = self.remaining if size < 0 else min(size, self.remaining)
        self.remaining -= count
        return b'x' * count


HEADER = ('SigNomeAgente;DscComponenteTarifario;DscBaseTarifaria;DscSubGrupoTarifario;'
          'DscModalidadeTarifaria;DscClasseConsumidor;DscSubClasseConsumidor;'
          'DscDetalheConsumidor;DscPostoTarifario;VlrComponenteTarifario;DscUnidade;'
          'DatInicioVigencia;DatFimVigencia;DscResolucaoHomologatoria\n')
ROW = ('COPEL-DIS;TUSD_FioB;Tarifa de Aplicação;B1;Convencional;Residencial;Residencial;'
       'SCEE;Não se aplica;214.53560037400001;R$/MWh;2026-06-24;2027-06-23;'
       'RESOLUÇÃO HOMOLOGATÓRIA Nº 3.592, DE 23 DE JUNHO DE 2026\n')


class RegulatoryTariffImportTest(IsolatedTestRuntime, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prepare_test_runtime(f"sqlite:///{_DB.name.replace(chr(92), '/')}", 'regulatory-import-test', limiter_enabled=False)
        cls.app = create_app(); cls.app.config.update(TESTING=True, RATELIMIT_ENABLED=False)
        with cls.app.app_context():
            db.create_all()
            first, second = Empresa(nome='A', slug='reg-a'), Empresa(nome='B', slug='reg-b')
            db.session.add_all((first, second)); db.session.flush()
            users = (
                User(empresa_id=first.id, nome='Plataforma A', email='platform-a@example.test', password_hash='x', role='owner', is_platform_admin=True),
                User(empresa_id=second.id, nome='Plataforma B', email='platform-b@example.test', password_hash='x', role='owner', is_platform_admin=True),
                User(empresa_id=first.id, nome='Empresa', email='company@example.test', password_hash='x', role='owner'),
            )
            db.session.add_all(users); db.session.commit()
            cls.platform_a, cls.platform_b, cls.company = (user.id for user in users)

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove(); db.drop_all(); db.engine.dispose()
        os.unlink(_DB.name); cls.restore_test_runtime()

    def setUp(self):
        with self.app.app_context():
            RegulatoryTariff.query.delete()
            RegulatoryTariffImport.query.delete()
            db.session.commit()

    def token(self, user_id):
        with self.app.app_context(): return generate_token(user_id)

    def upload(self, user_id, content=HEADER + ROW):
        return self.app.test_client().post('/api/v1/regulatory-tariffs/imports/preview',
            headers={'Authorization': 'Bearer ' + self.token(user_id)},
            data={'arquivo': (io.BytesIO(content.encode('utf-8')), 'componentes-tarifarias-2026.csv'),
                  'sourceUrl': 'https://dadosabertos.aneel.gov.br/dataset/componentes-tarifarias'},
            content_type='multipart/form-data')

    def confirm(self, user_id, preview_id):
        return self.app.test_client().post('/api/v1/regulatory-tariffs/imports/confirm',
            headers={'Authorization': 'Bearer ' + self.token(user_id)}, json={'previewId': preview_id})

    def test_preview_is_private_then_confirm_publishes_official_copel_tariff(self):
        response = self.upload(self.platform_a)
        self.assertEqual(response.status_code, 201); preview = response.json['data']
        self.assertEqual((preview['validos'], preview['conflitos'], preview['rejeitados']), (1, 0, 0))
        with self.app.app_context(): self.assertEqual(RegulatoryTariff.query.count(), 0)
        self.assertEqual(self.confirm(self.platform_b, preview['previewId']).status_code, 404)
        confirmed = self.confirm(self.platform_a, preview['previewId'])
        self.assertEqual(confirmed.status_code, 200)
        self.assertEqual(confirmed.json['data']['created'], 1)
        with self.app.app_context():
            tariff = RegulatoryTariff.query.one()
            self.assertEqual((tariff.official_distributor, str(tariff.value_kwh)), ('COPEL-DIS', '0.21453560037400001'))
            self.assertEqual((tariff.valid_from.isoformat(), tariff.valid_until.isoformat()), ('2026-06-24', '2027-06-23'))
            self.assertEqual(RegulatoryTariffImport.query.one().status, 'completed')
            from services.regulatory_tariff_repository import RegulatoryTariffRepository
            resolved = tuple(RegulatoryTariffRepository().fio_b_tariffs())
            self.assertEqual((resolved[0].unit_tariff, resolved[0].reference),
                             (tariff.value_kwh, tariff.source_reference))

    def test_status_of_empty_base_is_missing_and_schema_unavailable_is_503(self):
        empty = self.app.test_client().get('/api/v1/regulatory-tariffs/status',
            headers={'Authorization': 'Bearer ' + self.token(self.platform_a)})
        self.assertEqual(empty.status_code, 200)
        self.assertEqual(empty.json['data'], {
            'status': 'missing', 'records': 0,
            'coverage': {'from': None, 'until': None}, 'lastImport': None,
        })

        self.app.config['PROPAGATE_EXCEPTIONS'] = False
        try:
            with patch('routes.regulatory_tariff_routes.status',
                       side_effect=OperationalError('select', {}, Exception('unavailable'))):
                unavailable = self.app.test_client().get('/api/v1/regulatory-tariffs/status',
                    headers={'Authorization': 'Bearer ' + self.token(self.platform_a)})
        finally:
            self.app.config['PROPAGATE_EXCEPTIONS'] = True
        self.assertEqual(unavailable.status_code, 503)
        self.assertEqual(unavailable.json['error'], 'Base regulatória indisponível. Tente novamente mais tarde.')

    def test_same_file_is_noop_and_divergent_natural_key_blocks_publication(self):
        first = self.upload(self.platform_a).json['data']['previewId']
        self.assertEqual(self.confirm(self.platform_a, first).status_code, 200)
        repeat = self.upload(self.platform_a).json['data']['previewId']
        self.assertEqual(self.confirm(self.platform_a, repeat).json['data']['unchanged'], 1)
        conflict = self.upload(self.platform_a, (HEADER + ROW.replace('214.53560037400001', '300.00000000000000')))
        self.assertEqual(conflict.status_code, 201)
        self.assertEqual(conflict.json['data']['conflitos'], 1)
        self.assertEqual(self.confirm(self.platform_a, conflict.json['data']['previewId']).status_code, 409)
        overlap = self.upload(self.platform_a, HEADER + ROW.replace('2026-06-24', '2026-07-01'))
        self.assertEqual(overlap.json['data']['conflitos'], 1)
        with self.app.app_context(): self.assertEqual(RegulatoryTariff.query.count(), 1)

    def test_schema_component_and_platform_authorization_are_enforced(self):
        self.assertEqual(self.upload(self.company).status_code, 403)
        unsupported = self.upload(self.platform_a, HEADER + ROW.replace('TUSD_FioB', 'TUSD'))
        self.assertEqual(unsupported.status_code, 201)
        self.assertEqual(unsupported.json['data']['rejeitados'], 1)
        formula = self.upload(self.platform_a, HEADER + ROW.replace('COPEL-DIS', '=COPEL-DIS'))
        self.assertEqual(formula.status_code, 201)
        self.assertGreaterEqual(formula.json['data']['rejeitados'], 1)
        truncated = self.upload(self.platform_a, HEADER + 'COPEL-DIS;TUSD_FioB\n')
        self.assertIn(truncated.status_code, (201, 400))
        self.assertEqual(self.app.test_client().get('/api/v1/regulatory-tariffs/status',
            headers={'Authorization': 'Bearer ' + self.token(self.company)}).status_code, 403)

    def test_streamed_100_mib_limit_never_leaves_temporary_file(self):
        self.assertEqual(Config.REGULATORY_TARIFF_MAX_BYTES, 100 * 1024 * 1024)
        with tempfile.TemporaryDirectory() as folder:
            path, digest = regulatory_tariff_import_service._copy_to_temp(
                RepeatingStream(Config.REGULATORY_TARIFF_MAX_BYTES), folder)
            self.assertTrue(path.exists())
            self.assertEqual(path.stat().st_size, Config.REGULATORY_TARIFF_MAX_BYTES)
            self.assertEqual(len(digest), 64)
            regulatory_tariff_import_service._remove_temp(path)
            self.assertFalse(path.exists())
            with self.assertRaisesRegex(ValueError, '100 MiB'):
                regulatory_tariff_import_service._copy_to_temp(
                    RepeatingStream(Config.REGULATORY_TARIFF_MAX_BYTES + 1), folder)
            self.assertEqual(list(Path(folder).iterdir()), [])

    def test_orphan_cleanup_only_removes_expired_private_temp_files(self):
        with tempfile.TemporaryDirectory() as folder:
            stale = Path(folder) / 'regulatory-tariff-stale.csv'; active = Path(folder) / 'regulatory-tariff-active.csv'
            stale.write_bytes(b'x'); active.write_bytes(b'x')
            now = datetime.fromtimestamp(active.stat().st_mtime) + timedelta(minutes=1)
            old = (now - timedelta(minutes=30)).timestamp()
            os.utime(stale, (old, old))
            self.assertEqual(regulatory_tariff_import_service.purge_temporary_files(now=now, temp_dir=folder), 1)
            self.assertFalse(stale.exists()); self.assertTrue(active.exists())

    def test_ckan_preview_normalizes_official_decimal_and_reuses_confirmation(self):
        records = [{
            'SigNomeAgente': 'COPEL-DIS', 'DscComponenteTarifario': 'TUSD_FioB',
            'DscBaseTarifaria': 'Tarifa de Aplicação', 'DscSubGrupoTarifario': 'B1',
            'DscModalidadeTarifaria': 'Convencional', 'DscClasseConsumidor': 'Residencial',
            'DscSubClasseConsumidor': 'Residencial', 'DscDetalheConsumidor': 'SCEE',
            'DscPostoTarifario': 'Não se aplica', 'VlrComponenteTarifario': '214,53560037400001',
            'DscUnidade': 'R$/MWh', 'DatInicioVigencia': '2026-06-24',
            'DatFimVigencia': '2027-06-23', 'DscResolucaoHomologatoria': 'RH 3.592/2026',
        }]
        source = {'resource_id': 'e8717aa8-2521-453f-bf16-fbb9a16eea39', 'source_version': '2026-09-17'}
        with patch('services.regulatory_tariff_import_service.fetch_copel_fio_b', return_value=(records, source)):
            with self.app.test_request_context():
                from flask import g
                g.current_user = User.query.get(self.platform_a)
                preview = regulatory_tariff_import_service.create_ckan_preview('COPEL-DIS', 2026)
        self.assertEqual((preview['status'], preview['validos'], preview['sourceVersion']), ('ready', 1, '2026-09-17'))
        confirmed = self.confirm(self.platform_a, preview['previewId'])
        self.assertEqual((confirmed.status_code, confirmed.json['data']['created']), (200, 1))
        with self.app.app_context():
            tariff = RegulatoryTariff.query.one()
            self.assertEqual(str(tariff.source_value), '214.53560037400001')

    def test_ckan_preview_route_preserves_platform_admin_and_unavailable_status(self):
        self.assertEqual(self.app.test_client().post('/api/v1/regulatory-tariffs/imports/ckan/preview',
            headers={'Authorization': 'Bearer ' + self.token(self.company)}, json={'distributor': 'COPEL-DIS', 'year': 2026}).status_code, 403)
        self.app.config['PROPAGATE_EXCEPTIONS'] = False
        try:
            with patch('routes.regulatory_tariff_routes.create_ckan_preview',
                       side_effect=AneelCkanUnavailable('ANEEL indisponível. Tente novamente mais tarde.')):
                response = self.app.test_client().post('/api/v1/regulatory-tariffs/imports/ckan/preview',
                    headers={'Authorization': 'Bearer ' + self.token(self.platform_a)}, json={'distributor': 'COPEL-DIS', 'year': 2026})
        finally:
            self.app.config['PROPAGATE_EXCEPTIONS'] = True
        self.assertEqual((response.status_code, response.json['error']),
                         (503, 'ANEEL indisponível. Tente novamente mais tarde.'))
        with self.app.app_context():
            audit = LogEntry.query.filter_by(acao='regulatory_tariff_ckan_failed').order_by(LogEntry.id.desc()).first()
            self.assertEqual((audit.nivel, audit.metadados['createdById'], audit.metadados['distributor']),
                             ('warning', self.platform_a, 'COPEL-DIS'))
        malformed = self.app.test_client().post('/api/v1/regulatory-tariffs/imports/ckan/preview',
            headers={'Authorization': 'Bearer ' + self.token(self.platform_a)}, json=[])
        self.assertEqual(malformed.status_code, 400)


class AneelCkanClientTest(unittest.TestCase):
    def test_rejects_non_official_api_host(self):
        with self.assertRaisesRegex(ValueError, 'oficial'):
            AneelCkanClient(api_url='https://example.test/api/3/action')

    def test_unavailable_network_is_specific(self):
        client = AneelCkanClient(timeout_seconds=1)
        with patch('services.aneel_ckan_client.build_opener') as opener:
            opener.return_value.open.side_effect = OSError('offline')
            with self.assertRaises(AneelCkanUnavailable):
                client._request('datastore_search', {'resource_id': 'x'})

    def test_rejects_malformed_record_before_normalization(self):
        client = AneelCkanClient()
        with patch.object(client, '_request', return_value={'records': [{}], 'next_page': None}):
            with self.assertRaises(AneelCkanInvalidResponse):
                client._records('resource', {}, 10)

    def test_discovers_resource_and_paginates_with_exact_filters(self):
        client = AneelCkanClient()
        resource = {'id': 'resource-2026', 'name': 'componentes-tarifarias-2026.csv', 'datastore_active': True,
                    'url': 'https://dadosabertos.aneel.gov.br/download.csv', 'last_modified': '2026-09-17'}
        first, second = (dict.fromkeys(REQUIRED_COLUMNS, 'x'), dict.fromkeys(REQUIRED_COLUMNS, 'x'))
        first.update({'_id': 1, 'DatGeracaoConjuntoDados': '2026-09-17'}); second.update({'_id': 2})
        responses = [
            {'resources': [resource]},
            {'records': [first], 'next_page': {'_id': {'gt': 1}}},
            {'records': [second], 'next_page': None},
        ]
        with patch.object(client, '_request', side_effect=responses) as request:
            rows, source = client.copel_fio_b(2026, 10)
        self.assertEqual(([row['_id'] for row in rows], source['resource_id'], source['filters']['SigNomeAgente']),
                         ([1, 2], 'resource-2026', 'COPEL-DIS'))
        self.assertEqual(request.call_count, 3)


if __name__ == '__main__':
    unittest.main()
