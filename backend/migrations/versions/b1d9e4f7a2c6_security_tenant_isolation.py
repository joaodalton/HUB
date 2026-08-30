"""Isola settings, logs e historico por empresa e adiciona versao de sessao.

Revision ID: b1d9e4f7a2c6
Revises: a2c8f4e1b9d6
"""
from alembic import op
import sqlalchemy as sa


revision = 'b1d9e4f7a2c6'
down_revision = 'a2c8f4e1b9d6'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    empresas = [row[0] for row in bind.execute(sa.text('SELECT id FROM empresas ORDER BY id'))]
    if not empresas:
        raise RuntimeError('A migracao de seguranca exige ao menos uma empresa cadastrada.')

    with op.batch_alter_table('users') as batch_op:
        batch_op.add_column(sa.Column('session_version', sa.Integer(), nullable=False, server_default='1'))

    existing_settings = list(bind.execute(sa.text(
        'SELECT chave, valor, created_at, updated_at FROM settings'
    )).mappings())
    first_empresa_id = empresas[0]
    op.create_table(
        '_settings_tenant',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('empresa_id', sa.Integer(), sa.ForeignKey('empresas.id'), nullable=False),
        sa.Column('chave', sa.String(length=100), nullable=False),
        sa.Column('valor', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.UniqueConstraint('empresa_id', 'chave', name='uq_settings_empresa_chave'),
    )
    for empresa_id in empresas:
        for setting in existing_settings:
            bind.execute(sa.text(
                'INSERT INTO _settings_tenant (empresa_id, chave, valor, created_at, updated_at) '
                'VALUES (:empresa_id, :chave, :valor, :created_at, :updated_at)'
            ), {'empresa_id': empresa_id, **dict(setting)})
    op.drop_table('settings')
    op.rename_table('_settings_tenant', 'settings')
    op.create_index('ix_settings_empresa_id', 'settings', ['empresa_id'])

    with op.batch_alter_table('logs') as batch_op:
        batch_op.add_column(sa.Column('empresa_id', sa.Integer(), nullable=True))
    bind.execute(sa.text('UPDATE logs SET empresa_id = :empresa_id'), {'empresa_id': first_empresa_id})
    with op.batch_alter_table('logs') as batch_op:
        batch_op.alter_column('empresa_id', existing_type=sa.Integer(), nullable=False)
        batch_op.create_foreign_key('fk_logs_empresa', 'empresas', ['empresa_id'], ['id'])
        batch_op.create_index('ix_logs_empresa_id', ['empresa_id'])

    with op.batch_alter_table('rateio_historico') as batch_op:
        batch_op.add_column(sa.Column('empresa_id', sa.Integer(), nullable=True))
    bind.execute(sa.text(
        'UPDATE rateio_historico SET empresa_id = '
        '(SELECT empresa_id FROM plants WHERE plants.id = rateio_historico.plant_id)'
    ))
    with op.batch_alter_table('rateio_historico') as batch_op:
        batch_op.alter_column('empresa_id', existing_type=sa.Integer(), nullable=False)
        batch_op.create_foreign_key('fk_rateio_historico_empresa', 'empresas', ['empresa_id'], ['id'])
        batch_op.create_index('ix_rateio_historico_empresa_id', ['empresa_id'])


def downgrade():
    with op.batch_alter_table('rateio_historico') as batch_op:
        batch_op.drop_index('ix_rateio_historico_empresa_id')
        batch_op.drop_constraint('fk_rateio_historico_empresa', type_='foreignkey')
        batch_op.drop_column('empresa_id')

    with op.batch_alter_table('logs') as batch_op:
        batch_op.drop_index('ix_logs_empresa_id')
        batch_op.drop_constraint('fk_logs_empresa', type_='foreignkey')
        batch_op.drop_column('empresa_id')

    bind = op.get_bind()
    first_empresa_id = bind.execute(sa.text('SELECT MIN(id) FROM empresas')).scalar()
    op.create_table(
        '_settings_global',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('chave', sa.String(length=100), nullable=False, unique=True),
        sa.Column('valor', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )
    if first_empresa_id is not None:
        bind.execute(sa.text(
            'INSERT INTO _settings_global (chave, valor, created_at, updated_at) '
            'SELECT chave, valor, created_at, updated_at FROM settings WHERE empresa_id = :empresa_id'
        ), {'empresa_id': first_empresa_id})
    op.drop_table('settings')
    op.rename_table('_settings_global', 'settings')

    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_column('session_version')
