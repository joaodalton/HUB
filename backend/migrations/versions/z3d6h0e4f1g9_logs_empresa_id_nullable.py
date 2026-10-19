"""make logs.empresa_id nullable to allow logging after empresa deletion

Revision ID: z3d6h0e4f1g9
Revises: y2c5g9d3e0f8
Create Date: 2026-10-19 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'z3d6h0e4f1g9'
down_revision = 'y2c5g9d3e0f8'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('logs', schema=None) as batch_op:
        batch_op.alter_column('empresa_id', existing_type=sa.Integer(), nullable=True)


def downgrade():
    # Linhas com empresa_id NULL (logs de empresas ja excluidas) impedem o
    # downgrade; precisariam ser removidas ou realocadas manualmente antes.
    with op.batch_alter_table('logs', schema=None) as batch_op:
        batch_op.alter_column('empresa_id', existing_type=sa.Integer(), nullable=False)
