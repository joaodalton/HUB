"""add encrypted API credentials per company

Revision ID: c2d4e6f8a0b1
Revises: b1d9e4f7a2c6
"""
from alembic import op
import sqlalchemy as sa


revision = 'c2d4e6f8a0b1'
down_revision = 'b1d9e4f7a2c6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'api_credentials',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('empresa_id', sa.Integer(), nullable=False),
        sa.Column('provider', sa.String(length=40), nullable=False),
        sa.Column('nome', sa.String(length=100), nullable=False),
        sa.Column('segredo_encrypted', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['empresa_id'], ['empresas.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('empresa_id', 'provider', 'nome', name='uq_api_credentials_empresa_provider_nome'),
    )
    op.create_index('ix_api_credentials_empresa_id', 'api_credentials', ['empresa_id'])


def downgrade():
    op.drop_index('ix_api_credentials_empresa_id', table_name='api_credentials')
    op.drop_table('api_credentials')
