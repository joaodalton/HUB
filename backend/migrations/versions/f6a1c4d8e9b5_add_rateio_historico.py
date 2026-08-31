"""add rateio historico

Revision ID: f6a1c4d8e9b5
Revises: e5f9a3b2c7d4
Create Date: 2026-08-12 00:00:02.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'f6a1c4d8e9b5'
down_revision = 'e5f9a3b2c7d4'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'rateio_historico',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('competencia', sa.String(length=7), nullable=False),  # 'YYYY-MM'
        sa.Column('plant_id', sa.Integer(), nullable=False),
        sa.Column('consumer_unit_id', sa.Integer(), nullable=False),
        sa.Column('percentual', sa.Numeric(5, 2), nullable=False),
        sa.Column('consumo_considerado', sa.Numeric(10, 2), nullable=True),
        sa.Column('producao_considerada', sa.Numeric(10, 2), nullable=True),
        sa.Column('manual', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['plant_id'], ['plants.id']),
        sa.ForeignKeyConstraint(['consumer_unit_id'], ['consumer_units.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_rateio_historico_competencia', 'rateio_historico', ['competencia'])


def downgrade():
    op.drop_index('ix_rateio_historico_competencia', table_name='rateio_historico')
    op.drop_table('rateio_historico')