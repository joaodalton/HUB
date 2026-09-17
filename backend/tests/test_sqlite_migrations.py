"""O histórico Alembic deve subir inteiro em SQLite vazio, como no CI/local."""
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import importlib.util
from contextlib import closing
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]


def _load_migration(filename: str):
    path = BACKEND_DIR / 'migrations' / 'versions' / filename
    spec = importlib.util.spec_from_file_location(filename[:-3], path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


class SQLiteMigrationsTest(unittest.TestCase):
    def test_c42_grace_policy_upgrade_preserves_legacy_dates_and_guards_downgrade(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'grace-policy.db'
            result = self._flask(path, 'upgrade', 'o9c4e8f1a3b5')
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            with closing(sqlite3.connect(path)) as connection, connection:
                connection.execute("INSERT INTO grupos_regra_cobranca "
                    "(id,empresa_id,nome,ativo,padrao,calculation_method,tariff_source,manual_tariff,"
                    "discount_type,tariff_basis,billing_mode,due_date_basis,due_date_offset_days,revision,created_at,updated_at,"
                    "grace_enabled,grace_without_discount,grace_start,grace_end) "
                    "VALUES (100,1,'Legado carencia',1,1,'energia_compensada','manual',0.123456,'none','consumed',"
                    "'auto','invoice_due_date',0,7,'2026-09-16','2026-09-16',1,1,'2026-09-01','2026-09-30')")
                legacy = connection.execute('SELECT * FROM grupos_regra_cobranca').fetchone()
            for command, target in (('upgrade', 'head'), ('downgrade', 'o9c4e8f1a3b5'), ('upgrade', 'head')):
                result = self._flask(path, command, target)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                with closing(sqlite3.connect(path)) as connection:
                    actual = connection.execute('SELECT * FROM grupos_regra_cobranca').fetchone()
                    self.assertEqual(actual[:len(legacy)], legacy)
                    self.assertTrue(all(value is None for value in actual[len(legacy):]))
            with closing(sqlite3.connect(path)) as connection, connection:
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute('UPDATE grupos_regra_cobranca SET grace_duration_months=0')
                connection.execute('UPDATE grupos_regra_cobranca SET grace_duration_months=3')
            result = self._flask(path, 'downgrade', 'o9c4e8f1a3b5')
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('preservar duracao de carencia C4.2', result.stdout + result.stderr)
            with closing(sqlite3.connect(path)) as connection:
                self.assertEqual(connection.execute('SELECT grace_duration_months,grace_start,revision FROM grupos_regra_cobranca').fetchone(),
                                 (3, '2026-09-01', 7))
                self.assertEqual(connection.execute('SELECT version_num FROM alembic_version').fetchone()[0], 'p0d5f9a2b4c6')

    def test_c42_postgresql_upgrade_sql(self):
        from io import StringIO
        from alembic.migration import MigrationContext
        from alembic.operations import Operations
        migration = _load_migration('p0d5f9a2b4c6_grace_policy_duration.py')
        output = StringIO()
        context = MigrationContext.configure(dialect_name='postgresql', opts={'as_sql': True, 'output_buffer': output})
        with Operations.context(context):
            migration.upgrade()
        sql = output.getvalue()
        self.assertIn('ADD COLUMN grace_duration_months INTEGER', sql)
        self.assertIn('ck_grupo_regra_grace_duration', sql)
        self.assertNotIn('UPDATE ', sql)
        self.assertNotIn('DROP COLUMN', sql)

    def test_c41_postgresql_upgrade_sql(self):
        from io import StringIO
        from alembic.migration import MigrationContext
        from alembic.operations import Operations
        migration = _load_migration('o9c4e8f1a3b5_billing_tariff_configuration.py')
        output = StringIO()
        context = MigrationContext.configure(dialect_name='postgresql',
            opts={'as_sql': True, 'output_buffer': output})
        with Operations.context(context):
            migration.upgrade()
        sql = output.getvalue()
        self.assertIn('ADD COLUMN tariff_hp NUMERIC(18, 6)', sql)
        self.assertIn('ADD COLUMN grace_start DATE', sql)
        self.assertIn("icms_policy = 'exclude'", sql)
        self.assertIn('ck_grupo_regra_fixed_discount', sql)
        self.assertNotIn('UPDATE ', sql)

    def test_c41_legacy_upgrade_roundtrip_constraints_and_lossless_downgrade_guard(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'commercial.db'
            result = self._flask(path, 'upgrade', 'n8b3d7e0f2a4')
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            with closing(sqlite3.connect(path)) as connection, connection:
                connection.execute("INSERT INTO grupos_regra_cobranca "
                    "(id,empresa_id,nome,ativo,padrao,calculation_method,tariff_source,manual_tariff,"
                    "discount_type,tariff_basis,billing_mode,due_date_basis,due_date_offset_days,revision,created_at,updated_at) "
                    "VALUES (100,1,'Legado',1,1,'energia_compensada','manual',0.123456,'none','consumed',"
                    "'auto','invoice_due_date',0,7,'2026-09-16','2026-09-16')")
                connection.execute("INSERT INTO regra_cobranca_assignments "
                    "(empresa_id,grupo_regra_cobranca_id,scope_type,ativo,created_at,updated_at) "
                    "VALUES (1,100,'company',1,'2026-09-16','2026-09-16')")
                legacy = connection.execute('SELECT * FROM grupos_regra_cobranca').fetchone()
                assignments = connection.execute('SELECT * FROM regra_cobranca_assignments').fetchall()
            for command, target in (('upgrade', 'head'), ('downgrade', 'n8b3d7e0f2a4'), ('upgrade', 'head')):
                result = self._flask(path, command, target)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                with closing(sqlite3.connect(path)) as connection:
                    row = connection.execute('SELECT * FROM grupos_regra_cobranca').fetchone()
                    self.assertEqual(row[:len(legacy)], legacy)
                    self.assertTrue(all(value is None for value in row[len(legacy):]))
                    self.assertEqual(connection.execute('SELECT * FROM regra_cobranca_assignments').fetchall(), assignments)
                    self.assertEqual(connection.execute('PRAGMA foreign_key_check').fetchall(), [])
            with closing(sqlite3.connect(path)) as connection, connection:
                for update in ("icms_policy='include'", "grace_start='2026-09-01'",
                               "grace_without_discount=1", "calculation_method='tarifa_fixa_com_desconto'"):
                    with self.subTest(update=update), self.assertRaises(sqlite3.IntegrityError):
                        connection.execute('UPDATE grupos_regra_cobranca SET ' + update)
                connection.execute("UPDATE grupos_regra_cobranca SET icms_policy='exclude',tariff_hfp=0.734821")
            result = self._flask(path, 'downgrade', 'n8b3d7e0f2a4')
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('preservar configuracoes comerciais C4.1', result.stdout + result.stderr)
            with closing(sqlite3.connect(path)) as connection:
                self.assertEqual(connection.execute('SELECT version_num FROM alembic_version').fetchone()[0], 'o9c4e8f1a3b5')
                self.assertEqual(connection.execute('SELECT icms_policy,tariff_hp FROM grupos_regra_cobranca').fetchone(), ('exclude', None))

    def test_b2_upgrade_preserves_faturas_and_downgrade_preserves_event_ledger(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'webhook.db'
            result = self._flask(path, 'upgrade', 'j4d9e3f8a6b0')
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            with closing(sqlite3.connect(path)) as connection, connection:
                connection.execute("INSERT INTO clients (id,nome,cpf,email,concessionaria,status,empresa_id) VALUES (100,'A','12345678901','a@test.local','Copel','ativo',1)")
                connection.execute("INSERT INTO consumer_units (id,client_id,codigo,empresa_id,base_tarifaria,tipo_ligacao) VALUES (100,100,'UC',1,'B1','Monofasico')")
                connection.execute("INSERT INTO faturas (id,empresa_id,client_id,consumer_unit_id,concessionaria,competencia,valor,mes_vencimento,asaas_id,asaas_status,created_at,updated_at) VALUES (100,1,100,100,'Copel','2026-09',10.25,'2026-10-05','pay_legacy','received','2026-09-01','2026-09-01')")
                original = connection.execute('SELECT * FROM faturas').fetchall()
            for command, target in (('upgrade', 'head'), ('downgrade', 'j4d9e3f8a6b0'), ('upgrade', 'head')):
                result = self._flask(path, command, target)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                with closing(sqlite3.connect(path)) as connection:
                    self.assertEqual(connection.execute('SELECT * FROM faturas').fetchall(), original)
            with closing(sqlite3.connect(path)) as connection, connection:
                indexes = {r[1] for r in connection.execute('PRAGMA index_list(payment_webhook_events)')}
                self.assertTrue({'ix_payment_webhook_events_empresa_id', 'ix_payment_webhook_events_fatura_id'} <= indexes)
                statement = "INSERT INTO payment_webhook_events (empresa_id,fatura_id,provider,event_id,event_type,external_payment_id,payload_hash,processed_at,created_at) VALUES (1,100,'asaas','evt_unique','PAYMENT_RECEIVED','pay_legacy','hash','2026-09-14','2026-09-14')"
                connection.execute(statement)
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(statement)
            result = self._flask(path, 'downgrade', 'j4d9e3f8a6b0')
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('preservar ledger de webhook', result.stdout + result.stderr)
            with closing(sqlite3.connect(path)) as connection:
                self.assertEqual(connection.execute('SELECT COUNT(*) FROM payment_webhook_events').fetchone()[0], 1)
                self.assertEqual(connection.execute('SELECT * FROM faturas').fetchall(), original)
                self.assertEqual(connection.execute('SELECT version_num FROM alembic_version').fetchone()[0], 'k5e0f4a9b7c1')

    def _environment(self, database_path: Path) -> dict:
        environment = os.environ.copy()
        environment.update({
            'DATABASE_URL': f"sqlite:///{database_path.as_posix()}",
            'SECRET_KEY': 'sqlite-migration-test-secret',
            'FLASK_DEBUG': 'true',
        })
        return environment

    def _flask(self, database_path: Path, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, '-m', 'flask', '--app', 'app', 'db', *args],
            cwd=BACKEND_DIR,
            env=self._environment(database_path),
            text=True,
            capture_output=True,
            check=False,
        )

    def test_legacy_numeric_normalizers_accept_valid_and_reject_malformed_data(self):
        migration = _load_migration('e5f9a3b2c7d4_consumo_percentual_numeric.py')
        self.assertEqual(migration._sqlite_normalizar_consumo('450 kWh'), '450.00')
        self.assertEqual(migration._sqlite_normalizar_consumo('1,25'), '1.25')
        self.assertEqual(migration._sqlite_normalizar_consumo('1.234'), '1.23')
        self.assertIsNone(migration._sqlite_normalizar_consumo('sem consumo'))
        self.assertEqual(migration._sqlite_normalizar_percentual('12.50'), '12.50')
        self.assertEqual(migration._sqlite_normalizar_percentual('1.234'), '1.23')
        with self.assertRaises(ValueError):
            migration._sqlite_normalizar_consumo('1.2.3')
        with self.assertRaises(ValueError):
            migration._sqlite_normalizar_percentual('12,50')
        with self.assertRaises(ValueError):
            migration._sqlite_normalizar_consumo('100000000')
        with self.assertRaises(ValueError):
            migration._sqlite_normalizar_percentual('1000')

    def test_empty_sqlite_upgrades_to_current_head(self):
        handle = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        handle.close()
        database_path = Path(handle.name)
        try:
            result = self._flask(database_path, 'upgrade')
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            connection = sqlite3.connect(database_path)
            try:
                revision = connection.execute('SELECT version_num FROM alembic_version').fetchone()[0]
                columns = {row[1] for row in connection.execute('PRAGMA table_info(api_credentials)')}
                uc_columns = {row[1] for row in connection.execute('PRAGMA table_info(consumer_units)')}
                client_columns = {row[1] for row in connection.execute('PRAGMA table_info(clients)')}
                fatura_columns = {row[1] for row in connection.execute('PRAGMA table_info(faturas)')}
                assinatura_columns = {row[1] for row in connection.execute('PRAGMA table_info(assinaturas)')}
                whatsapp_integration_columns = {row[1] for row in connection.execute('PRAGMA table_info(whatsapp_integrations)')}
                whatsapp_message_columns = {row[1] for row in connection.execute('PRAGMA table_info(whatsapp_messages)')}
                agenda_event_columns = {row[1] for row in connection.execute('PRAGMA table_info(agenda_events)')}
                fatura_concessionaria_columns = {row[1] for row in connection.execute('PRAGMA table_info(faturas_concessionarias)')}
                fatura_concessionaria_indexes = {row[1] for row in connection.execute("PRAGMA index_list('faturas_concessionarias')")}
                fatura_concessionaria_fks = {row[2] for row in connection.execute("PRAGMA foreign_key_list('faturas_concessionarias')")}
                billing_rule_columns = {row[1] for row in connection.execute("PRAGMA table_info('grupos_regra_cobranca')")}
                billing_rule_indexes = {row[1]: row for row in connection.execute("PRAGMA index_list('grupos_regra_cobranca')")}
                billing_rule_fks = {row[2] for row in connection.execute("PRAGMA foreign_key_list('grupos_regra_cobranca')")}
                billing_rule_sql = connection.execute(
                    "SELECT sql FROM sqlite_master WHERE type='table' AND name='grupos_regra_cobranca'"
                ).fetchone()[0]
                assignment_columns = {row[1] for row in connection.execute(
                    "PRAGMA table_info('regra_cobranca_assignments')"
                )}
                assignment_indexes = {row[1]: row for row in connection.execute(
                    "PRAGMA index_list('regra_cobranca_assignments')"
                )}
                assignment_fks = {row[2] for row in connection.execute(
                    "PRAGMA foreign_key_list('regra_cobranca_assignments')"
                )}
                preview_indexes = {row[1] for row in connection.execute("PRAGMA index_list('import_previews')")}
            finally:
                connection.close()
            self.assertEqual(revision, 'p0d5f9a2b4c6')
            self.assertTrue({'empresa_id', 'provider', 'nome', 'segredo_encrypted', 'interna'}.issubset(columns))
            self.assertTrue({'sem_usina_desde', 'concessionaria_credential_id'}.issubset(uc_columns))
            self.assertIn('asaas_customer_id', client_columns)
            self.assertTrue({'empresa_id', 'client_id', 'consumer_unit_id', 'asaas_id', 'asaas_status'}.issubset(fatura_columns))
            self.assertTrue({'empresa_id', 'plano_chave', 'tipo', 'status'}.issubset(assinatura_columns))
            self.assertTrue({'empresa_id', 'api_credential_id', 'phone_number_id', 'business_account_id'}.issubset(whatsapp_integration_columns))
            self.assertTrue({'empresa_id', 'conversation_id', 'direction', 'status'}.issubset(whatsapp_message_columns))
            self.assertTrue({'empresa_id', 'titulo', 'inicio', 'status'}.issubset(agenda_event_columns))
            self.assertTrue({
                'empresa_id', 'client_id', 'consumer_unit_id', 'document_id',
                'arquivo_hash', 'dados_brutos_extraidos', 'dados_normalizados',
                'status_extracao', 'status_validacao',
            }.issubset(fatura_concessionaria_columns))
            self.assertTrue({
                'ix_faturas_concessionarias_empresa_id',
                'ix_faturas_concessionarias_empresa_chave',
                'sqlite_autoindex_faturas_concessionarias_1',
            }.issubset(fatura_concessionaria_indexes))
            self.assertEqual(
                fatura_concessionaria_fks,
                {'empresas', 'clients', 'consumer_units', 'documents'},
            )
            self.assertTrue({
                'empresa_id', 'nome', 'ativo', 'padrao', 'calculation_method',
                'tariff_source', 'manual_tariff', 'discount_type', 'discount_value',
                'tariff_basis', 'energy_component_index', 'billing_mode',
                'due_date_basis', 'due_date_offset_days', 'monthly_interest',
                'fine_percentage', 'revision',
            }.issubset(billing_rule_columns))
            self.assertEqual(billing_rule_fks, {'empresas'})
            self.assertTrue({
                'ix_grupos_regra_cobranca_empresa_id',
                'uq_grupos_regra_cobranca_default_ativo',
            }.issubset(billing_rule_indexes))
            self.assertEqual(billing_rule_indexes['uq_grupos_regra_cobranca_default_ativo'][4], 1)
            self.assertGreaterEqual(billing_rule_sql.upper().count('NUMERIC(18, 6)'), 4)
            self.assertIn('ix_import_previews_expires_at', preview_indexes)
            self.assertTrue({
                'empresa_id', 'grupo_regra_cobranca_id', 'scope_type',
                'client_id', 'consumer_unit_id', 'ativo',
            }.issubset(assignment_columns))
            self.assertEqual(
                assignment_fks,
                {'empresas', 'grupos_regra_cobranca', 'clients', 'consumer_units'},
            )
            self.assertTrue({
                'uq_regra_assignment_company_ativo',
                'uq_regra_assignment_client_ativo',
                'uq_regra_assignment_uc_ativo',
                'ix_regra_assignment_empresa_scope',
            }.issubset(assignment_indexes))
            for name in (
                'uq_regra_assignment_company_ativo',
                'uq_regra_assignment_client_ativo',
                'uq_regra_assignment_uc_ativo',
            ):
                self.assertEqual(assignment_indexes[name][2], 1)
                self.assertEqual(assignment_indexes[name][4], 1)
        finally:
            database_path.unlink(missing_ok=True)

    def test_subscription_backfill_marks_only_empresa_one_as_vitalicia(self):
        handle = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        handle.close()
        database_path = Path(handle.name)
        try:
            upgraded = self._flask(database_path, 'upgrade', 'f7b2c9d4e1a6')
            self.assertEqual(upgraded.returncode, 0, upgraded.stdout + upgraded.stderr)
            connection = sqlite3.connect(database_path)
            try:
                connection.execute("INSERT INTO empresas (nome, slug, status) VALUES ('Empresa 2', 'empresa-2', 'ativa')")
                connection.commit()
            finally:
                connection.close()

            upgraded = self._flask(database_path, 'upgrade')
            self.assertEqual(upgraded.returncode, 0, upgraded.stdout + upgraded.stderr)
            connection = sqlite3.connect(database_path)
            try:
                assinaturas = connection.execute(
                    'SELECT empresa_id, tipo, status FROM assinaturas ORDER BY empresa_id'
                ).fetchall()
            finally:
                connection.close()
            self.assertEqual(assinaturas, [(1, 'vitalicio', 'ativa'), (2, 'trial', 'trial')])
        finally:
            database_path.unlink(missing_ok=True)

    def test_fatura_concessionaria_downgrade_preserves_source_records(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'fatura-concessionaria.db'
            result = self._flask(path, 'upgrade')
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result = self._flask(path, 'downgrade', 'k5e0f4a9b7c1')
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            with closing(sqlite3.connect(path)) as connection:
                tables = {row[0] for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )}
                self.assertNotIn('faturas_concessionarias', tables)

            self.assertEqual(self._flask(path, 'upgrade').returncode, 0)
            with closing(sqlite3.connect(path)) as connection, connection:
                connection.execute("INSERT INTO clients (id,nome,cpf,email,concessionaria,status,empresa_id) VALUES (100,'A','12345678901','a@test.local','Copel','ativo',1)")
                connection.execute("INSERT INTO consumer_units (id,client_id,codigo,empresa_id,base_tarifaria,tipo_ligacao) VALUES (100,100,'UC',1,'B1','Monofasico')")
                connection.execute("INSERT INTO documents (id,nome,storage_provider,empresa_id,client_id,consumer_unit_id) VALUES (100,'fatura.pdf','google_drive',1,100,100)")
                connection.execute("INSERT INTO faturas_concessionarias (empresa_id,client_id,consumer_unit_id,document_id,arquivo_hash,status_extracao,status_validacao,created_at,updated_at) VALUES (1,100,100,100,'hash','recebida','pendente','2026-09-15','2026-09-15')")
            result = self._flask(path, 'downgrade', 'k5e0f4a9b7c1')
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('preservar faturas originais', result.stdout + result.stderr)
            with closing(sqlite3.connect(path)) as connection:
                self.assertEqual(connection.execute('SELECT COUNT(*) FROM faturas_concessionarias').fetchone()[0], 1)
                self.assertEqual(connection.execute('SELECT version_num FROM alembic_version').fetchone()[0], 'l6f1a5b8c2d4')

    def test_billing_rule_upgrade_constraints_and_downgrade_guard(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'billing-rule.db'
            result = self._flask(path, 'upgrade')
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result = self._flask(path, 'downgrade', 'l6f1a5b8c2d4')
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(self._flask(path, 'upgrade').returncode, 0)

            statement = (
                "INSERT INTO grupos_regra_cobranca "
                "(empresa_id,nome,ativo,padrao,calculation_method,tariff_source,manual_tariff,"
                "discount_type,discount_value,tariff_basis,billing_mode,due_date_basis,"
                "due_date_offset_days,revision,created_at,updated_at) VALUES "
                "(1,?,1,1,'energia_compensada','manual',0.123456,'none',NULL,'compensated',"
                "'auto','invoice_due_date',-2,1,'2026-09-15','2026-09-15')"
            )
            with closing(sqlite3.connect(path)) as connection, connection:
                connection.execute(statement, ('Default',))
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(statement, ('Segundo default',))
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        statement.replace("'manual',0.123456", "'manual',NULL"),
                        ('Manual sem tarifa',),
                    )

            result = self._flask(path, 'downgrade', 'l6f1a5b8c2d4')
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('preservar perfis de regra de cobranca', result.stdout + result.stderr)
            with closing(sqlite3.connect(path)) as connection:
                self.assertEqual(connection.execute('SELECT COUNT(*) FROM grupos_regra_cobranca').fetchone()[0], 1)
                self.assertEqual(connection.execute('SELECT version_num FROM alembic_version').fetchone()[0], 'm7a2c6d9e1f3')

    def test_assignment_upgrade_constraints_uniqueness_and_downgrade_guard(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'billing-rule-assignment.db'
            self.assertEqual(self._flask(path, 'upgrade').returncode, 0)
            self.assertEqual(self._flask(path, 'downgrade', 'm7a2c6d9e1f3').returncode, 0)
            self.assertEqual(self._flask(path, 'upgrade').returncode, 0)

            rule = (
                "INSERT INTO grupos_regra_cobranca "
                "(id,empresa_id,nome,ativo,padrao,calculation_method,tariff_source,manual_tariff,"
                "discount_type,discount_value,tariff_basis,billing_mode,due_date_basis,"
                "due_date_offset_days,revision,created_at,updated_at) VALUES "
                "(100,1,'Regra',1,0,'energia_compensada','manual',0.123456,'none',NULL,"
                "'compensated','auto','invoice_due_date',0,1,'2026-09-15','2026-09-15')"
            )
            company = (
                "INSERT INTO regra_cobranca_assignments "
                "(empresa_id,grupo_regra_cobranca_id,scope_type,client_id,consumer_unit_id,ativo,created_at,updated_at) "
                "VALUES (1,100,'company',NULL,NULL,1,'2026-09-15','2026-09-15')"
            )
            with closing(sqlite3.connect(path)) as connection, connection:
                connection.execute(rule)
                connection.execute(company)
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(company)
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(company.replace("'company',NULL,NULL", "'client',NULL,NULL"))

            result = self._flask(path, 'downgrade', 'm7a2c6d9e1f3')
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('preservar historico de assignments', result.stdout + result.stderr)
            with closing(sqlite3.connect(path)) as connection:
                self.assertEqual(connection.execute(
                    'SELECT COUNT(*) FROM regra_cobranca_assignments'
                ).fetchone()[0], 1)
                self.assertEqual(
                    connection.execute('SELECT version_num FROM alembic_version').fetchone()[0],
                    'n8b3d7e0f2a4',
                )

    def test_fatura_b1_upgrade_legacy_roundtrip_and_downgrade_guard(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'faturas.db'
            result = self._flask(path, 'upgrade', 'i3c8d2e7f5a9')
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            with closing(sqlite3.connect(path)) as connection, connection:
                connection.execute("INSERT INTO clients (id,nome,cpf,email,concessionaria,status,empresa_id) VALUES (100,'A','12345678901','a@test.local','Copel','ativo',1)")
                connection.execute("INSERT INTO consumer_units (id,client_id,codigo,empresa_id,base_tarifaria,tipo_ligacao) VALUES (100,100,'UC',1,'B1','Monofasico')")
                connection.execute("INSERT INTO faturas (id,empresa_id,client_id,consumer_unit_id,concessionaria,competencia,valor,mes_vencimento,asaas_id,asaas_status,created_at,updated_at) VALUES (100,1,100,100,'Copel','2026-09',10.25,'2026-10-05','pay_legacy','received','2026-09-01','2026-09-01')")
                original = connection.execute('SELECT * FROM faturas').fetchone()
            result = self._flask(path, 'upgrade')
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            with closing(sqlite3.connect(path)) as connection, connection:
                row = connection.execute('SELECT * FROM faturas').fetchone()
                self.assertEqual(row[:len(original)], original)
                self.assertTrue(all(value is None for value in row[len(original):]))
                columns = {r[1]: r for r in connection.execute('PRAGMA table_info(faturas)')}
                self.assertEqual(columns['asaas_id'][3], 0)
                self.assertNotIn('cobrancas', {r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")})
            result = self._flask(path, 'downgrade', 'i3c8d2e7f5a9')
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            with closing(sqlite3.connect(path)) as connection, connection:
                self.assertEqual(connection.execute('SELECT * FROM faturas').fetchone(), original)
            self.assertEqual(self._flask(path, 'upgrade').returncode, 0)
            with closing(sqlite3.connect(path)) as connection, connection:
                connection.execute("UPDATE faturas SET external_reference='hub-test', emission_key='key', payment_provider='asaas', status_interno='aguardando_emissao', asaas_id=NULL WHERE id=100")
            result = self._flask(path, 'downgrade', 'i3c8d2e7f5a9')
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('preservar diario de emissao', result.stdout + result.stderr)
            with closing(sqlite3.connect(path)) as connection, connection:
                self.assertEqual(connection.execute('SELECT external_reference,asaas_id FROM faturas').fetchone(), ('hub-test', None))
                self.assertEqual(connection.execute('SELECT version_num FROM alembic_version').fetchone()[0], 'j4d9e3f8a6b0')

    def test_google_account_downgrade_rejects_duplicate_email_before_rebuild(self):
        handle = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        handle.close()
        database_path = Path(handle.name)
        try:
            upgraded = self._flask(database_path, 'upgrade', 'd1e5f8a2b4c7')
            self.assertEqual(upgraded.returncode, 0, upgraded.stdout + upgraded.stderr)
            connection = sqlite3.connect(database_path)
            try:
                connection.execute("INSERT INTO empresas (id, nome, slug, ativa) VALUES (2, 'Empresa 2', 'empresa-2', 1)")
                connection.execute("INSERT INTO google_accounts (nome, email, is_active, empresa_id) VALUES ('A', 'duplicado@example.test', 0, 1)")
                connection.execute("INSERT INTO google_accounts (nome, email, is_active, empresa_id) VALUES ('B', 'duplicado@example.test', 0, 2)")
                connection.commit()
            finally:
                connection.close()
            downgraded = self._flask(database_path, 'downgrade', 'c9d2e6f1a3b5')
            self.assertNotEqual(downgraded.returncode, 0)
            self.assertIn('emails repetidos entre empresas', downgraded.stdout + downgraded.stderr)
            connection = sqlite3.connect(database_path)
            try:
                self.assertEqual(connection.execute('SELECT COUNT(*) FROM google_accounts').fetchone()[0], 2)
            finally:
                connection.close()
        finally:
            database_path.unlink(missing_ok=True)

    def test_client_cpf_downgrade_rejects_cross_tenant_duplicates_before_ddl(self):
        handle = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        handle.close()
        database_path = Path(handle.name)
        try:
            upgraded = self._flask(database_path, 'upgrade', 'd5e7f9a1b2c3')
            self.assertEqual(upgraded.returncode, 0, upgraded.stdout + upgraded.stderr)
            connection = sqlite3.connect(database_path)
            try:
                connection.execute("INSERT INTO empresas (id, nome, slug, status) VALUES (2, 'Empresa 2', 'empresa-2', 'ativa')")
                connection.execute("INSERT INTO clients (nome, cpf, email, concessionaria, status, empresa_id) VALUES ('A', '12345678901', 'a@example.test', 'Copel', 'ativo', 1)")
                connection.execute("INSERT INTO clients (nome, cpf, email, concessionaria, status, empresa_id) VALUES ('B', '12345678901', 'b@example.test', 'Copel', 'ativo', 2)")
                connection.commit()
            finally:
                connection.close()
            downgraded = self._flask(database_path, 'downgrade', 'c2d4e6f8a0b1')
            self.assertNotEqual(downgraded.returncode, 0)
            self.assertIn('CPFs repetidos entre empresas', downgraded.stdout + downgraded.stderr)
            connection = sqlite3.connect(database_path)
            try:
                self.assertEqual(connection.execute('SELECT COUNT(*) FROM clients').fetchone()[0], 2)
                constraints = {row[1] for row in connection.execute("PRAGMA index_list('clients')")}
                self.assertIn('sqlite_autoindex_clients_1', constraints)
            finally:
                connection.close()
        finally:
            database_path.unlink(missing_ok=True)

    def test_message_template_backfill_and_downgrade_guard(self):
        handle = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        handle.close(); database_path = Path(handle.name)
        try:
            self.assertEqual(self._flask(database_path, 'upgrade', 'd5e7f9a1b2c3').returncode, 0)
            connection = sqlite3.connect(database_path)
            try:
                connection.execute("INSERT INTO empresas (id,nome,slug,status) VALUES (2,'Empresa 2','template-2','ativa')")
                connection.execute("INSERT INTO email_templates (chave,nome,assunto,corpo,variaveis_disponiveis) VALUES ('convite','Convite','Oi','Corpo','nome')")
                connection.commit()
            finally: connection.close()
            self.assertEqual(self._flask(database_path, 'upgrade', 'e6a8c0d2f4b6').returncode, 0)
            connection = sqlite3.connect(database_path)
            try:
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM message_templates WHERE canal='email' AND chave='convite'").fetchone()[0], 2)
                connection.execute("UPDATE message_templates SET corpo='Alterado' WHERE empresa_id=2 AND chave='convite'"); connection.commit()
            finally: connection.close()
            result = self._flask(database_path, 'downgrade', 'd5e7f9a1b2c3')
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('templates por empresa alterados ou criados', result.stdout + result.stderr)
        finally: database_path.unlink(missing_ok=True)


if __name__ == '__main__':
    unittest.main()
