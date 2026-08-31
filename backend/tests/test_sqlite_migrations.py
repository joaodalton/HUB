"""O histórico Alembic deve subir inteiro em SQLite vazio, como no CI/local."""
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]


class SQLiteMigrationsTest(unittest.TestCase):
    def test_empty_sqlite_upgrades_to_current_head(self):
        handle = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        handle.close()
        database_path = Path(handle.name)
        try:
            environment = os.environ.copy()
            environment.update({
                'DATABASE_URL': f"sqlite:///{database_path.as_posix()}",
                'SECRET_KEY': 'sqlite-migration-test-secret',
                'FLASK_DEBUG': 'true',
            })
            result = subprocess.run(
                [sys.executable, '-m', 'flask', '--app', 'app', 'db', 'upgrade'],
                cwd=BACKEND_DIR,
                env=environment,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            connection = sqlite3.connect(database_path)
            try:
                revision = connection.execute('SELECT version_num FROM alembic_version').fetchone()[0]
                columns = {row[1] for row in connection.execute('PRAGMA table_info(api_credentials)')}
            finally:
                connection.close()
            self.assertEqual(revision, 'c2d4e6f8a0b1')
            self.assertTrue({'empresa_id', 'provider', 'nome', 'segredo_encrypted'}.issubset(columns))
        finally:
            database_path.unlink(missing_ok=True)


if __name__ == '__main__':
    unittest.main()
