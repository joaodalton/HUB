"""add import previews and tenant-scoped client cpf

Revision ID: d5e7f9a1b2c3
Revises: c2d4e6f8a0b1
"""
from alembic import op
import sqlalchemy as sa

revision = 'd5e7f9a1b2c3'
down_revision = 'c2d4e6f8a0b1'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('import_previews',
        sa.Column('id', sa.Integer(), primary_key=True), sa.Column('empresa_id', sa.Integer(), nullable=False),
        sa.Column('created_by_id', sa.Integer(), nullable=False), sa.Column('arquivo_hash', sa.String(64), nullable=False),
        sa.Column('plano', sa.JSON(), nullable=False), sa.Column('status', sa.String(20), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False), sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['empresa_id'], ['empresas.id']), sa.ForeignKeyConstraint(['created_by_id'], ['users.id']))
    op.create_index('ix_import_previews_empresa_id', 'import_previews', ['empresa_id'])
    op.create_index('ix_import_previews_expires_at', 'import_previews', ['expires_at'])
    if op.get_bind().dialect.name == 'postgresql':
        op.execute('ALTER TABLE clients DROP CONSTRAINT IF EXISTS clients_cpf_key')
        op.create_unique_constraint('uq_clients_empresa_cpf', 'clients', ['empresa_id', 'cpf'])
    else:
        with op.batch_alter_table('clients', schema=None, naming_convention={'uq': 'uq_%(table_name)s_%(column_0_name)s'}) as batch:
            batch.drop_constraint('uq_clients_cpf', type_='unique')
            batch.create_unique_constraint('uq_clients_empresa_cpf', ['empresa_id', 'cpf'])

def downgrade():
    # Restoring the old global CPF constraint would silently lose the ability to
    # keep the same CPF in two tenants. Fail before any DDL/rebuild instead.
    duplicate_cpf = op.get_bind().execute(sa.text(
        'SELECT cpf FROM clients GROUP BY cpf HAVING COUNT(*) > 1 LIMIT 1'
    )).scalar()
    if duplicate_cpf is not None:
        raise ValueError('Não é possível reverter clients: existem CPFs repetidos entre empresas.')
    if op.get_bind().dialect.name == 'postgresql':
        op.drop_constraint('uq_clients_empresa_cpf', 'clients', type_='unique'); op.create_unique_constraint('clients_cpf_key', 'clients', ['cpf'])
    else:
        with op.batch_alter_table('clients', schema=None) as batch:
            batch.drop_constraint('uq_clients_empresa_cpf', type_='unique'); batch.create_unique_constraint('uq_clients_cpf', ['cpf'])
    op.drop_index('ix_import_previews_expires_at', table_name='import_previews')
    op.drop_index('ix_import_previews_empresa_id', table_name='import_previews'); op.drop_table('import_previews')
