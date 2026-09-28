"""Link operational GD compensation pendencies to their source invoice.

Revision ID: t4d9e2a7c1b5
Revises: s3c8d1e6f9a2
"""
from alembic import op
import sqlalchemy as sa


revision = 't4d9e2a7c1b5'
down_revision = 's3c8d1e6f9a2'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('pendencias') as batch:
        batch.add_column(sa.Column('fatura_concessionaria_id', sa.Integer(), nullable=True))
        batch.create_foreign_key('fk_pendencias_fatura_concessionaria', 'faturas_concessionarias',
                                 ['fatura_concessionaria_id'], ['id'])
        batch.create_unique_constraint('uq_pendencias_fatura_origem',
                                       ['empresa_id', 'fatura_concessionaria_id', 'origem'])


def downgrade():
    with op.batch_alter_table('pendencias') as batch:
        batch.drop_constraint('uq_pendencias_fatura_origem', type_='unique')
        batch.drop_constraint('fk_pendencias_fatura_concessionaria', type_='foreignkey')
        batch.drop_column('fatura_concessionaria_id')
