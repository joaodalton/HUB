"""add empresa_id to google_accounts

Revision ID: d1e5f8a2b4c7
Revises: c9d2e6f1a3b5
Create Date: 2026-08-17 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'd1e5f8a2b4c7'
down_revision = 'c9d2e6f1a3b5'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('google_accounts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('empresa_id', sa.Integer(), nullable=True))

    op.execute('UPDATE google_accounts SET empresa_id = 1')

    with op.batch_alter_table('google_accounts', schema=None) as batch_op:
        batch_op.alter_column('empresa_id', existing_type=sa.Integer(), nullable=False)
        batch_op.create_foreign_key('fk_google_accounts_empresa_id', 'empresas', ['empresa_id'], ['id'])
        batch_op.drop_constraint('google_accounts_email_key', type_='unique')
        batch_op.create_unique_constraint('uq_google_accounts_empresa_email', ['empresa_id', 'email'])


def downgrade():
    with op.batch_alter_table('google_accounts', schema=None) as batch_op:
        batch_op.drop_constraint('uq_google_accounts_empresa_email', type_='unique')
        batch_op.create_unique_constraint('google_accounts_email_key', ['email'])
        batch_op.drop_constraint('fk_google_accounts_empresa_id', type_='foreignkey')
        batch_op.drop_column('empresa_id')