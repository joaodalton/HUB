"""add responsavel_tipo e responsavel_cargo em pendencias

Revision ID: 918e7595f818
Revises: 61e22a38e764
Create Date: 2026-10-27 19:21:05.521673

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '918e7595f818'
down_revision = '61e22a38e764'
branch_labels = None
depends_on = None


def upgrade():
    # server_default garante que linhas existentes (NOT NULL) nao quebrem.
    with op.batch_alter_table('pendencias', schema=None) as batch_op:
        batch_op.add_column(sa.Column(
            'responsavel_tipo', sa.String(length=20), nullable=False, server_default='usuario'
        ))
        batch_op.add_column(sa.Column('responsavel_cargo', sa.String(length=20), nullable=True))


def downgrade():
    with op.batch_alter_table('pendencias', schema=None) as batch_op:
        batch_op.drop_column('responsavel_cargo')
        batch_op.drop_column('responsavel_tipo')
