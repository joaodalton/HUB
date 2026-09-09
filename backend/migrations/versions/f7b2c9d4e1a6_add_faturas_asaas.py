"""add faturas and ASAAS customer reference

Revision ID: f7b2c9d4e1a6
Revises: e6a8c0d2f4b6
"""
from alembic import op
import sqlalchemy as sa


revision = 'f7b2c9d4e1a6'
down_revision = 'e6a8c0d2f4b6'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('clients', sa.Column('asaas_customer_id', sa.String(length=100), nullable=True))
    op.create_index('ix_clients_asaas_customer_id', 'clients', ['asaas_customer_id'])
    op.create_table(
        'faturas',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('empresa_id', sa.Integer(), nullable=False),
        sa.Column('client_id', sa.Integer(), nullable=False),
        sa.Column('consumer_unit_id', sa.Integer(), nullable=False),
        sa.Column('concessionaria', sa.String(length=50), nullable=False),
        sa.Column('competencia', sa.String(length=7), nullable=False),
        sa.Column('valor', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('mes_vencimento', sa.Date(), nullable=False),
        sa.Column('origem', sa.String(length=20), nullable=False, server_default='manual'),
        sa.Column('asaas_id', sa.String(length=100), nullable=False),
        sa.Column('asaas_status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('boleto_url', sa.String(length=2048), nullable=True),
        sa.Column('linha_digitavel', sa.String(length=100), nullable=True),
        sa.Column('codigo_barras', sa.String(length=100), nullable=True),
        sa.Column('criado_por_id', sa.Integer(), nullable=True),
        sa.Column('enviado_em', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['empresa_id'], ['empresas.id']),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id']),
        sa.ForeignKeyConstraint(['consumer_unit_id'], ['consumer_units.id']),
        sa.ForeignKeyConstraint(['criado_por_id'], ['users.id']),
        sa.CheckConstraint("origem IN ('manual', 'automatica')", name='ck_faturas_origem'),
        sa.CheckConstraint("asaas_status IN ('pending', 'received', 'overdue', 'canceled', 'refunded')", name='ck_faturas_asaas_status'),
        sa.UniqueConstraint('empresa_id', 'asaas_id', name='uq_faturas_empresa_asaas_id'),
    )
    op.create_index('ix_faturas_empresa_id', 'faturas', ['empresa_id'])
    op.create_index('ix_faturas_asaas_id', 'faturas', ['asaas_id'])


def downgrade():
    op.drop_index('ix_faturas_asaas_id', table_name='faturas')
    op.drop_index('ix_faturas_empresa_id', table_name='faturas')
    op.drop_table('faturas')
    op.drop_index('ix_clients_asaas_customer_id', table_name='clients')
    op.drop_column('clients', 'asaas_customer_id')
