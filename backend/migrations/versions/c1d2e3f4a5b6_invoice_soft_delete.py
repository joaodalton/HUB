"""Add deleted_at to faturas_concessionarias (soft delete).

Revision ID: c1d2e3f4a5b6
Revises: ba20021705c0
"""
from alembic import op
import sqlalchemy as sa


revision = 'c1d2e3f4a5b6'
down_revision = 'ba20021705c0'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('faturas_concessionarias', sa.Column('deleted_at', sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table('faturas_concessionarias') as batch:
        batch.drop_column('deleted_at')
