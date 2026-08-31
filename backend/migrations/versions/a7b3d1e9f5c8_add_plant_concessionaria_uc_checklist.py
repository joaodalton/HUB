"""add plant concessionaria and uc elegibilidade checklist

Revision ID: a7b3d1e9f5c8
Revises: f6a1c4d8e9b5
Create Date: 2026-08-13 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'a7b3d1e9f5c8'
down_revision = 'f6a1c4d8e9b5'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('plants', schema=None) as batch_op:
        batch_op.add_column(sa.Column('concessionaria', sa.String(length=50), nullable=True))

    with op.batch_alter_table('consumer_units', schema=None) as batch_op:
        # Checklist MANUAL de elegibilidade (marcado por vocês, não calculado
        # sozinho -- não existe automação de documento/financeiro no HUB ainda).
        batch_op.add_column(sa.Column('documentacao_completa', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column('sem_pendencia_financeira', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column('cliente_estrategico', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    with op.batch_alter_table('consumer_units', schema=None) as batch_op:
        batch_op.drop_column('cliente_estrategico')
        batch_op.drop_column('sem_pendencia_financeira')
        batch_op.drop_column('documentacao_completa')

    with op.batch_alter_table('plants', schema=None) as batch_op:
        batch_op.drop_column('concessionaria')