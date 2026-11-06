"""add isento_cobranca to assinaturas

Revision ID: a1b2c3d4e5f6
Revises: k9f3a7c1d5e2
Create Date: 2026-11-04 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'a1b2c3d4e5f6'
down_revision = 'k9f3a7c1d5e2'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('assinaturas', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('isento_cobranca', sa.Boolean(), nullable=False, server_default=sa.false())
        )


def downgrade():
    with op.batch_alter_table('assinaturas', schema=None) as batch_op:
        batch_op.drop_column('isento_cobranca')
