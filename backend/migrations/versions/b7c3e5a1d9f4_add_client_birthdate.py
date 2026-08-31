"""add client birthdate

Revision ID: b7c3e5a1d9f4
Revises: f3d7b1c9a4e2
Create Date: 2026-08-09 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'b7c3e5a1d9f4'
down_revision = 'f3d7b1c9a4e2'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('clients', schema=None) as batch_op:
        batch_op.add_column(sa.Column('data_nascimento', sa.Date(), nullable=True))


def downgrade():
    with op.batch_alter_table('clients', schema=None) as batch_op:
        batch_op.drop_column('data_nascimento')