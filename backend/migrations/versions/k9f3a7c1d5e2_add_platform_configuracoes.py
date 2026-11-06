"""add platform_configuracoes table

Revision ID: k9f3a7c1d5e2
Revises: 918e7595f818
Create Date: 2026-11-03 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'k9f3a7c1d5e2'
down_revision = '918e7595f818'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'platform_configuracoes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('asaas_api_base_url', sa.String(length=255), nullable=True),
        sa.Column('asaas_api_key_encrypted', sa.Text(), nullable=True),
        sa.Column('asaas_webhook_token_encrypted', sa.Text(), nullable=True),
        sa.Column('signup_code_encrypted', sa.Text(), nullable=True),
        sa.Column('signup_empresa_id', sa.Integer(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade():
    op.drop_table('platform_configuracoes')
