"""Block ordinary SQL rewrites of C5.5 financial snapshots and audit attempts.

Revision ID: s3c8d1e6f9a2
Revises: r2f7b5c0d3e8
"""
from alembic import op


revision = 's3c8d1e6f9a2'
down_revision = 'r2f7b5c0d3e8'
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().dialect.name != 'postgresql':
        return
    op.execute("""
        CREATE FUNCTION billing_calculation_immutable_guard()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'Registro financeiro imutável; use procedimento administrativo auditado.'
                USING ERRCODE = '55000';
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER billing_snapshots_immutable
        BEFORE UPDATE OR DELETE ON billing_calculation_snapshots
        FOR EACH ROW EXECUTE FUNCTION billing_calculation_immutable_guard()
    """)
    op.execute('ALTER TABLE billing_calculation_snapshots ENABLE ALWAYS TRIGGER billing_snapshots_immutable')
    op.execute("""
        CREATE TRIGGER billing_executions_immutable
        BEFORE UPDATE OR DELETE ON billing_calculation_executions
        FOR EACH ROW EXECUTE FUNCTION billing_calculation_immutable_guard()
    """)
    op.execute('ALTER TABLE billing_calculation_executions ENABLE ALWAYS TRIGGER billing_executions_immutable')


def downgrade():
    if op.get_bind().dialect.name != 'postgresql':
        return
    op.execute('DROP TRIGGER billing_executions_immutable ON billing_calculation_executions')
    op.execute('DROP TRIGGER billing_snapshots_immutable ON billing_calculation_snapshots')
    op.execute('DROP FUNCTION billing_calculation_immutable_guard()')
