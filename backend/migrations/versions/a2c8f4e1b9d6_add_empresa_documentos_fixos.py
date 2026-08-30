"""add documento_cnpj_id e documento_estatuto_id em empresas

Revision ID: a2c8f4e1b9d6
Revises: multi_tenant_v1
Create Date: 2026-08-27 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'a2c8f4e1b9d6'
down_revision = 'c9190fb66b9f'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('empresas', schema=None) as batch_op:
        batch_op.add_column(sa.Column('documento_cnpj_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('documento_estatuto_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_empresas_documento_cnpj', 'documents', ['documento_cnpj_id'], ['id'])
        batch_op.create_foreign_key('fk_empresas_documento_estatuto', 'documents', ['documento_estatuto_id'], ['id'])


def downgrade():
    with op.batch_alter_table('empresas', schema=None) as batch_op:
        batch_op.drop_constraint('fk_empresas_documento_estatuto', type_='foreignkey')
        batch_op.drop_constraint('fk_empresas_documento_cnpj', type_='foreignkey')
        batch_op.drop_column('documento_estatuto_id')
        batch_op.drop_column('documento_cnpj_id')
