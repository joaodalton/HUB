"""add empresa_id to google_accounts

Revision ID: d1e5f8a2b4c7
Revises: c9d2e6f1a3b5
Create Date: 2026-08-17 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'd1e5f8a2b4c7'
down_revision = 'c9d2e6f1a3b5'
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().dialect.name == 'sqlite':
        # SQLite cria UNIQUE(email) sem um nome removível. Recriar a tabela
        # preserva os dados e troca a unicidade global pela unicidade tenant.
        op.create_table(
            'google_accounts_new',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('nome', sa.String(length=150), nullable=False),
            sa.Column('email', sa.String(length=150), nullable=False),
            sa.Column('refresh_token_encrypted', sa.Text(), nullable=True),
            sa.Column('scopes', sa.String(length=500), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.Column('empresa_id', sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(['empresa_id'], ['empresas.id'], name='fk_google_accounts_empresa_id'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('empresa_id', 'email', name='uq_google_accounts_empresa_email'),
        )
        op.execute("""
            INSERT INTO google_accounts_new
              (id, nome, email, refresh_token_encrypted, scopes, is_active, created_at, updated_at, empresa_id)
            SELECT id, nome, email, refresh_token_encrypted, scopes, is_active, created_at, updated_at, 1
            FROM google_accounts
        """)
        op.drop_table('google_accounts')
        op.rename_table('google_accounts_new', 'google_accounts')
        return

    with op.batch_alter_table('google_accounts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('empresa_id', sa.Integer(), nullable=True))

    op.execute('UPDATE google_accounts SET empresa_id = 1')

    with op.batch_alter_table('google_accounts', schema=None) as batch_op:
        batch_op.alter_column('empresa_id', existing_type=sa.Integer(), nullable=False)
        batch_op.create_foreign_key('fk_google_accounts_empresa_id', 'empresas', ['empresa_id'], ['id'])
        batch_op.drop_constraint('google_accounts_email_key', type_='unique')
        batch_op.create_unique_constraint('uq_google_accounts_empresa_email', ['empresa_id', 'email'])


def downgrade():
    if op.get_bind().dialect.name == 'sqlite':
        duplicates = op.get_bind().execute(sa.text("""
            SELECT email FROM google_accounts
            GROUP BY email HAVING COUNT(*) > 1
        """)).scalars().all()
        if duplicates:
            raise ValueError(
                'Nao e possivel reverter google_accounts: existem emails repetidos entre empresas.'
            )
        op.create_table(
            'google_accounts_old',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('nome', sa.String(length=150), nullable=False),
            sa.Column('email', sa.String(length=150), nullable=False),
            sa.Column('refresh_token_encrypted', sa.Text(), nullable=True),
            sa.Column('scopes', sa.String(length=500), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('email'),
        )
        op.execute("""
            INSERT INTO google_accounts_old
              (id, nome, email, refresh_token_encrypted, scopes, is_active, created_at, updated_at)
            SELECT id, nome, email, refresh_token_encrypted, scopes, is_active, created_at, updated_at
            FROM google_accounts
        """)
        op.drop_table('google_accounts')
        op.rename_table('google_accounts_old', 'google_accounts')
        return

    with op.batch_alter_table('google_accounts', schema=None) as batch_op:
        batch_op.drop_constraint('uq_google_accounts_empresa_email', type_='unique')
        batch_op.create_unique_constraint('google_accounts_email_key', ['email'])
        batch_op.drop_constraint('fk_google_accounts_empresa_id', type_='foreignkey')
        batch_op.drop_column('empresa_id')
