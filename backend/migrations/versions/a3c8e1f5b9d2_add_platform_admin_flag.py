"""add is_platform_admin flag to users

Revision ID: a3c8e1f5b9d2
Revises: multi_tenant_v1
Create Date: 2026-08-18 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'a3c8e1f5b9d2'
down_revision = 'multi_tenant_v1'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('is_platform_admin', sa.Boolean(), nullable=False, server_default=sa.false())
        )


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('is_platform_admin')
