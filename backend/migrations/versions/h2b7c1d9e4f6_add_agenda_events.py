"""add tenant agenda events

Revision ID: h2b7c1d9e4f6
Revises: g1a9d2e6f4c8
"""
from alembic import op
import sqlalchemy as sa

revision = 'h2b7c1d9e4f6'
down_revision = 'g1a9d2e6f4c8'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'agenda_events',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('empresa_id', sa.Integer(), nullable=False),
        sa.Column('titulo', sa.String(200), nullable=False),
        sa.Column('descricao', sa.Text(), nullable=True),
        sa.Column('inicio', sa.DateTime(), nullable=False),
        sa.Column('fim', sa.DateTime(), nullable=True),
        sa.Column('categoria', sa.String(50), nullable=False, server_default='Operacional'),
        sa.Column('status', sa.String(20), nullable=False, server_default='aberto'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['empresa_id'], ['empresas.id']),
        sa.CheckConstraint("status IN ('aberto', 'cancelado')", name='ck_agenda_events_status'),
    )
    op.create_index('ix_agenda_events_empresa_id', 'agenda_events', ['empresa_id'])
    op.create_index('ix_agenda_events_inicio', 'agenda_events', ['inicio'])


def downgrade():
    op.drop_index('ix_agenda_events_inicio', table_name='agenda_events')
    op.drop_index('ix_agenda_events_empresa_id', table_name='agenda_events')
    op.drop_table('agenda_events')
