"""O histórico Alembic deve subir inteiro em SQLite vazio, como no CI/local."""
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import importlib.util
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
                preview_indexes = {row[1] for row in connection.execute("PRAGMA index_list('import_previews')")}
            finally:
                connection.close()
            self.assertEqual(revision, 'e6a8c0d2f4b6')
            self.assertTrue({'empresa_id', 'provider', 'nome', 'segredo_encrypted'}.issubset(columns))
            self.assertIn('ix_import_previews_expires_at', preview_indexes)
        finally:
            database_path.unlink(missing_ok=True)

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
