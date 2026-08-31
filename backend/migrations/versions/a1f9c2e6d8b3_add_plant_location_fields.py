"""add plant location fields

Revision ID: a1f9c2e6d8b3
Revises: 8f2a1c9d0eab
Create Date: 2026-08-03 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1f9c2e6d8b3'
down_revision = '8f2a1c9d0eab'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('plants', schema=None) as batch_op:
        batch_op.add_column(sa.Column('cidade', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('uf', sa.String(length=2), nullable=True))
        batch_op.add_column(sa.Column('endereco', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('data_ativacao', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('responsavel', sa.String(length=150), nullable=True))


def downgrade():
    with op.batch_alter_table('plants', schema=None) as batch_op:
        batch_op.drop_column('responsavel')
        batch_op.drop_column('data_ativacao')
        batch_op.drop_column('endereco')
        batch_op.drop_column('uf')
        batch_op.drop_column('cidade')