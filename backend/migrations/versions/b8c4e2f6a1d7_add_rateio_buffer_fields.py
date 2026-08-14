"""add rateio buffer fields

Revision ID: b8c4e2f6a1d7
Revises: a7b3d1e9f5c8
Create Date: 2026-08-13 00:00:01.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'b8c4e2f6a1d7'
down_revision = 'a7b3d1e9f5c8'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('plants', schema=None) as batch_op:
        # Se preenchido, sobrepõe a média calculada dos 12 meses -- mesma
        # ideia do "🖊 manual" que já existe em percentual_disponivel.
        batch_op.add_column(sa.Column('producao_media_manual', sa.Numeric(10, 2), nullable=True))

    with op.batch_alter_table('consumer_units', schema=None) as batch_op:
        # Override do buffer de consumo POR cliente -- quando preenchido,
        # ganha do valor global de Configurações (ver rateio_service.py).
        batch_op.add_column(sa.Column('buffer_percentual', sa.Numeric(5, 2), nullable=True))


def downgrade():
    with op.batch_alter_table('consumer_units', schema=None) as batch_op:
        batch_op.drop_column('buffer_percentual')

    with op.batch_alter_table('plants', schema=None) as batch_op:
        batch_op.drop_column('producao_media_manual')