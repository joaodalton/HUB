"""empresa e user: campos de RBAC (nome, role, status, email_verified, must_change_password)

Revision ID: e2f6a9c3d5b8
Revises: d1e5f8a2b4c7
Create Date: 2026-08-17 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'e2f6a9c3d5b8'
down_revision = 'd1e5f8a2b4c7'
branch_labels = None
depends_on = None


def upgrade():
    # ---------- empresas ----------
    with op.batch_alter_table('empresas', schema=None) as batch_op:
        batch_op.add_column(sa.Column('razao_social', sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column('cnpj', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('email', sa.String(length=150), nullable=True))
        batch_op.add_column(sa.Column('telefone', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('status', sa.String(length=20), nullable=True))

    op.execute("UPDATE empresas SET status = CASE WHEN ativa THEN 'ativa' ELSE 'inativa' END")

    with op.batch_alter_table('empresas', schema=None) as batch_op:
        batch_op.alter_column('status', existing_type=sa.String(length=20), nullable=False)
        batch_op.drop_column('ativa')

    # ---------- users ----------
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('nome', sa.String(length=150), nullable=True))
        batch_op.add_column(sa.Column('role', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('status', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('email_verified', sa.Boolean(), nullable=False, server_default=sa.true()))
        batch_op.add_column(sa.Column('must_change_password', sa.Boolean(), nullable=False, server_default=sa.false()))

    # Admin existente vira owner (toda empresa precisa de 1) -- os demais
    # (so existia 'viewer' alem de 'admin' ate aqui) viram viewer.
    op.execute("UPDATE users SET role = CASE WHEN papel = 'admin' THEN 'owner' ELSE 'viewer' END")
    op.execute("UPDATE users SET status = CASE WHEN ativo THEN 'ativo' ELSE 'inativo' END")

    # nome nao da pra derivar direito via SQL puro entre SQLite/Postgres --
    # usa o prefixo do email como ponto de partida (sem tela de "editar
    # perfil" ainda pra ajustar depois, fica pro backlog).
    connection = op.get_bind()
    users_table = sa.table('users', sa.column('id', sa.Integer), sa.column('email', sa.String), sa.column('nome', sa.String))
    for row in connection.execute(sa.select(users_table.c.id, users_table.c.email)):
        prefixo = row.email.split('@')[0] if row.email else 'Usuario'
        connection.execute(users_table.update().where(users_table.c.id == row.id).values(nome=prefixo))

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column('role', existing_type=sa.String(length=20), nullable=False)
        batch_op.alter_column('status', existing_type=sa.String(length=20), nullable=False)
        batch_op.alter_column('nome', existing_type=sa.String(length=150), nullable=False)
        batch_op.drop_column('papel')
        batch_op.drop_column('ativo')


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('papel', sa.String(length=30), nullable=True))
        batch_op.add_column(sa.Column('ativo', sa.Boolean(), nullable=True))

    op.execute("UPDATE users SET papel = CASE WHEN role IN ('owner','admin') THEN 'admin' ELSE 'viewer' END")
    op.execute("UPDATE users SET ativo = CASE WHEN status = 'ativo' THEN true ELSE false END")

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column('papel', existing_type=sa.String(length=30), nullable=False)
        batch_op.alter_column('ativo', existing_type=sa.Boolean(), nullable=False)
        batch_op.drop_column('must_change_password')
        batch_op.drop_column('email_verified')
        batch_op.drop_column('status')
        batch_op.drop_column('role')
        batch_op.drop_column('nome')

    with op.batch_alter_table('empresas', schema=None) as batch_op:
        batch_op.add_column(sa.Column('ativa', sa.Boolean(), nullable=True))

    op.execute("UPDATE empresas SET ativa = CASE WHEN status = 'ativa' THEN true ELSE false END")

    with op.batch_alter_table('empresas', schema=None) as batch_op:
        batch_op.alter_column('ativa', existing_type=sa.Boolean(), nullable=False)
        batch_op.drop_column('status')
        batch_op.drop_column('telefone')
        batch_op.drop_column('email')
        batch_op.drop_column('cnpj')
        batch_op.drop_column('razao_social')