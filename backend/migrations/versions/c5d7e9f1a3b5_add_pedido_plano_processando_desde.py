"""add pedidos_plano.processando_desde

Revision ID: c5d7e9f1a3b5
Revises: b2c3d4e5f6a7
Create Date: 2026-11-04 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'c5d7e9f1a3b5'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('pedidos_plano', sa.Column('processando_desde', sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column('pedidos_plano', 'processando_desde')
