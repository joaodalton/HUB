"""track when a consumer unit became disconnected from every plant

Revision ID: i3c8d2e7f5a9
Revises: h2b7c1d9e4f6
Create Date: 2026-09-11 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'i3c8d2e7f5a9'
down_revision = 'h2b7c1d9e4f6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('api_credentials', schema=None) as batch_op:
        batch_op.add_column(sa.Column('interna', sa.Boolean(), nullable=False, server_default=sa.false()))
    with op.batch_alter_table('consumer_units', schema=None) as batch_op:
        batch_op.add_column(sa.Column('sem_usina_desde', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('concessionaria_credential_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            'fk_consumer_units_concessionaria_credential', 'api_credentials',
            ['concessionaria_credential_id'], ['id']
        )


def downgrade():
    with op.batch_alter_table('consumer_units', schema=None) as batch_op:
        batch_op.drop_constraint('fk_consumer_units_concessionaria_credential', type_='foreignkey')
        batch_op.drop_column('concessionaria_credential_id')
        batch_op.drop_column('sem_usina_desde')
    with op.batch_alter_table('api_credentials', schema=None) as batch_op:
        batch_op.drop_column('interna')
