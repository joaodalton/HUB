"""document category optional

Revision ID: 8f2a1c9d0eab
Revises: c4b5632aaedd
Create Date: 2026-07-30 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '8f2a1c9d0eab'
down_revision = 'c4b5632aaedd'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('documents', schema=None) as batch_op:
        batch_op.alter_column('category_id', existing_type=sa.Integer(), nullable=True)


def downgrade():
    with op.batch_alter_table('documents', schema=None) as batch_op:
        batch_op.alter_column('category_id', existing_type=sa.Integer(), nullable=False)