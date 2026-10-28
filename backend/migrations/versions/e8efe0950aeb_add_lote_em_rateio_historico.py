"""add lote em rateio_historico

Revision ID: e8efe0950aeb
Revises: d4e8f2a6c1b7
Create Date: 2026-10-26 13:53:25.300244

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e8efe0950aeb'
down_revision = 'd4e8f2a6c1b7'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('rateio_historico', schema=None) as batch_op:
        batch_op.add_column(sa.Column('lote', sa.String(length=36), nullable=True))
        batch_op.create_index(batch_op.f('ix_rateio_historico_lote'), ['lote'], unique=False)


def downgrade():
    with op.batch_alter_table('rateio_historico', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_rateio_historico_lote'))
        batch_op.drop_column('lote')
