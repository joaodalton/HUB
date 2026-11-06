"""add is_platform_worker flag to users

Revision ID: x1b4f8c2d9e7
Revises: w7c0e5f9a4b2
Create Date: 2026-10-18 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'x1b4f8c2d9e7'
down_revision = 'w7c0e5f9a4b2'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('is_platform_worker', sa.Boolean(), nullable=False, server_default=sa.false())
        )


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('is_platform_worker')
