"""Garante que a DATABASE_URL do Postgres use psycopg2 explicitamente.

Regressao: o SQLAlchemy 2.1 trocou o driver padrao de "postgresql://" para
psycopg (v3), que o HUB nao instala. O boot em producao falhava com
"No module named 'psycopg'".
"""
import sys
import unittest
from pathlib import Path

import sqlalchemy as sa


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import normalize_database_url  # noqa: E402


class DatabaseUrlDriverTest(unittest.TestCase):
    def test_postgresql_without_driver_uses_psycopg2(self):
        self.assertEqual(
            normalize_database_url('postgresql://u:p@host:5432/db?sslmode=require'),
            'postgresql+psycopg2://u:p@host:5432/db?sslmode=require',
        )

    def test_legacy_postgres_scheme_uses_psycopg2(self):
        self.assertEqual(
            normalize_database_url('postgres://u:p@host/db'),
            'postgresql+psycopg2://u:p@host/db',
        )

    def test_explicit_driver_is_preserved(self):
        for url in (
            'postgresql+psycopg2://u:p@host/db',
            'postgresql+psycopg://u:p@host/db',
        ):
            self.assertEqual(normalize_database_url(url), url)

    def test_sqlite_is_untouched(self):
        url = 'sqlite:////tmp/hub.db'
        self.assertEqual(normalize_database_url(url), url)

    def test_normalized_url_selects_psycopg2_dialect(self):
        url = sa.engine.make_url(normalize_database_url('postgresql://u:p@host/db'))
        self.assertEqual(url.get_dialect().driver, 'psycopg2')


if __name__ == '__main__':
    unittest.main()
