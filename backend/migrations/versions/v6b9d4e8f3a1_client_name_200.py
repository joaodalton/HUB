"""Allow client names up to 200 characters.

Revision ID: v6b9d4e8f3a1
Revises: u5a8c3d7e2f9
"""
from alembic import op
import sqlalchemy as sa

revision = 'v6b9d4e8f3a1'
down_revision = 'u5a8c3d7e2f9'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('clients') as batch:
        batch.alter_column('nome', existing_type=sa.String(150), type_=sa.String(200), existing_nullable=False)


def downgrade():
    if op.get_bind().execute(sa.text('SELECT id FROM clients WHERE length(nome) > 150 LIMIT 1')).first():
        raise RuntimeError('Client names exceed 150 characters; downgrade would truncate data.')
    with op.batch_alter_table('clients') as batch:
        batch.alter_column('nome', existing_type=sa.String(200), type_=sa.String(150), existing_nullable=False)
