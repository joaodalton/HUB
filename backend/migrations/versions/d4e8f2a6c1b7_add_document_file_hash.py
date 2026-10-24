"""Add documents.file_hash for S3 upload dedup.

Revision ID: d4e8f2a6c1b7
Revises: x8d1f60ab5c3
"""
from alembic import op
import sqlalchemy as sa


revision = 'd4e8f2a6c1b7'
down_revision = 'x8d1f60ab5c3'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('documents') as batch:
        batch.add_column(sa.Column('file_hash', sa.String(64), nullable=True))


def downgrade():
    with op.batch_alter_table('documents') as batch:
        batch.drop_column('file_hash')
