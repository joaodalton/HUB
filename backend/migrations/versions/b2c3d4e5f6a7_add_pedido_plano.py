"""add pedidos_plano table

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-11-04 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'pedidos_plano',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=150), nullable=False),
        sa.Column('plano_chave', sa.String(length=30), nullable=False),
        sa.Column('external_reference', sa.String(length=120), nullable=False),
        sa.Column('asaas_customer_id', sa.String(length=64), nullable=True),
        sa.Column('asaas_subscription_id', sa.String(length=64), nullable=True),
        sa.Column('token_hash', sa.String(length=64), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('external_reference'),
        sa.UniqueConstraint('token_hash'),
    )


def downgrade():
    op.drop_table('pedidos_plano')
