"""Add faturas.billing_mode/invoice_url and consumer_units.debito_automatico.

Revision ID: d2e3f4a5b6c7
Revises: c1d2e3f4a5b6
"""
from alembic import op
import sqlalchemy as sa


revision = 'd2e3f4a5b6c7'
down_revision = 'c1d2e3f4a5b6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('faturas') as batch:
        batch.add_column(sa.Column('billing_mode', sa.String(20), nullable=True))
        batch.add_column(sa.Column('invoice_url', sa.String(2048), nullable=True))
    with op.batch_alter_table('consumer_units') as batch:
        batch.add_column(sa.Column('debito_automatico', sa.Boolean(), nullable=False,
                                   server_default=sa.false()))


def downgrade():
    with op.batch_alter_table('consumer_units') as batch:
        batch.drop_column('debito_automatico')
    with op.batch_alter_table('faturas') as batch:
        batch.drop_column('invoice_url')
        batch.drop_column('billing_mode')
