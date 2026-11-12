"""add crm_leads table

Revision ID: ba20021705c0
Revises: c5d7e9f1a3b5
"""
from alembic import op
import sqlalchemy as sa


revision = 'ba20021705c0'
down_revision = 'c5d7e9f1a3b5'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'crm_leads',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('empresa_id', sa.Integer(), nullable=False),
        sa.Column('provider', sa.String(length=40), nullable=False),
        sa.Column('external_id', sa.String(length=60), nullable=False),
        sa.Column('titulo', sa.String(length=255), nullable=True),
        sa.Column('status', sa.Integer(), nullable=True),
        sa.Column('valor', sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column('pipeline_nome', sa.String(length=150), nullable=True),
        sa.Column('etapa_nome', sa.String(length=150), nullable=True),
        sa.Column('dados_brutos', sa.JSON(), nullable=True),
        sa.Column('criado_em_origem', sa.DateTime(), nullable=True),
        sa.Column('atualizado_em_origem', sa.DateTime(), nullable=True),
        sa.Column('importado_em', sa.DateTime(), nullable=False),
        sa.Column('atualizado_em', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['empresa_id'], ['empresas.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('empresa_id', 'provider', 'external_id', name='uq_crm_leads_empresa_provider_external_id'),
    )
    op.create_index('ix_crm_leads_empresa_id', 'crm_leads', ['empresa_id'])


def downgrade():
    op.drop_index('ix_crm_leads_empresa_id', table_name='crm_leads')
    op.drop_table('crm_leads')
