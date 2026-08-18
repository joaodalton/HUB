"""add empresas table and empresa_id to users (fundacao multi-tenant)

Revision ID: c9d2e6f1a3b5
Revises: b8c4e2f6a1d7
Create Date: 2026-08-17 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'c9d2e6f1a3b5'
down_revision = 'b8c4e2f6a1d7'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'empresas',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('nome', sa.String(length=150), nullable=False),
        sa.Column('slug', sa.String(length=60), nullable=False),
        sa.Column('ativa', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug')
    )

    # Empresa #1 -- os dados que ja existem no banco (Select Energia Solar)
    # viram essa empresa. Se o nome/slug real for outro, ajuste antes de
    # rodar em producao (so essa linha, o resto da migration nao muda).
    empresas_table = sa.table(
        'empresas',
        sa.column('id', sa.Integer),
        sa.column('nome', sa.String),
        sa.column('slug', sa.String),
        sa.column('ativa', sa.Boolean)
    )
    op.bulk_insert(empresas_table, [
        {'id': 1, 'nome': 'Select Energia Solar', 'slug': 'select', 'ativa': True}
    ])

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('empresa_id', sa.Integer(), nullable=True))

    op.execute('UPDATE users SET empresa_id = 1')

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column('empresa_id', existing_type=sa.Integer(), nullable=False)
        batch_op.create_foreign_key('fk_users_empresa_id', 'empresas', ['empresa_id'], ['id'])


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_constraint('fk_users_empresa_id', type_='foreignkey')
        batch_op.drop_column('empresa_id')

    op.drop_table('empresas')