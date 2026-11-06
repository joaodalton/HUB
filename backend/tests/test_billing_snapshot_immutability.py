"""Migration C5.5: mutações SQL diretas exigem procedimento administrativo explícito."""
import importlib.util
import os
import unittest
from io import StringIO
from pathlib import Path
from uuid import uuid4

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.engine import make_url


MIGRATION = Path(__file__).resolve().parents[1] / 'migrations' / 'versions' / \
    's3c8d1e6f9a2_billing_snapshot_immutability.py'


def load_migration():
    spec = importlib.util.spec_from_file_location('billing_snapshot_immutability', MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BillingSnapshotImmutabilityTest(unittest.TestCase):
    def test_postgres_upgrade_and_downgrade_are_reversible_without_data_mutation(self):
        migration = load_migration()
        output = StringIO()
        context = MigrationContext.configure(dialect_name='postgresql',
            opts={'as_sql': True, 'output_buffer': output})
        with Operations.context(context):
            migration.upgrade()
        sql = output.getvalue()
        self.assertIn('CREATE TRIGGER billing_snapshots_immutable', sql)
        self.assertIn('CREATE TRIGGER billing_executions_immutable', sql)
        self.assertNotIn('UPDATE billing_calculation_', sql)
        self.assertNotIn('DELETE FROM billing_calculation_', sql)
        output = StringIO()
        context = MigrationContext.configure(dialect_name='postgresql',
            opts={'as_sql': True, 'output_buffer': output})
        with Operations.context(context):
            migration.downgrade()
        self.assertIn('DROP TRIGGER', output.getvalue())

    @unittest.skipUnless(os.getenv('RUN_BILLING_IMMUTABILITY_PG') == '1',
                         'requer banco PostgreSQL de teste isolado')
    def test_postgres_blocks_direct_update_and_delete(self):
        url = os.getenv('TEST_POSTGRES_BILLING_URL', '')
        parsed = make_url(url)
        if not parsed.drivername.startswith('postgresql') or not (parsed.database or '').startswith('test_'):
            self.fail('TEST_POSTGRES_BILLING_URL deve apontar a banco PostgreSQL test_* isolado')
        engine = create_engine(url)
        with engine.connect() as conn:
            transaction = conn.begin()
            schema = f'billing_immutability_{uuid4().hex}'
            try:
                conn.execute(text(f'CREATE SCHEMA {schema}'))
                conn.execute(text(f'SET LOCAL search_path TO {schema}'))
                for name in ('snapshots', 'executions'):
                    conn.execute(text(f'CREATE TABLE billing_calculation_{name} (id integer PRIMARY KEY, value integer)'))
                    conn.execute(text(f'INSERT INTO billing_calculation_{name} (id, value) VALUES (1, 7)'))
                context = MigrationContext.configure(conn)
                with Operations.context(context):
                    load_migration().upgrade()
                for name in ('snapshots', 'executions'):
                    for mutation in ('UPDATE', 'DELETE'):
                        statement = (f'UPDATE billing_calculation_{name} SET value = 9 WHERE id = 1'
                                     if mutation == 'UPDATE' else
                                     f'DELETE FROM billing_calculation_{name} WHERE id = 1')
                        with self.assertRaises(DBAPIError):
                            with conn.begin_nested():
                                conn.execute(text(statement))
                    self.assertEqual(conn.scalar(text(
                        f'SELECT value FROM billing_calculation_{name} WHERE id = 1')), 7)
                with Operations.context(context):
                    load_migration().downgrade()
                conn.execute(text('UPDATE billing_calculation_snapshots SET value = 9 WHERE id = 1'))
                self.assertEqual(conn.scalar(text(
                    'SELECT value FROM billing_calculation_snapshots WHERE id = 1')), 9)
            finally:
                transaction.rollback()
        engine.dispose()


if __name__ == '__main__':
    unittest.main()
