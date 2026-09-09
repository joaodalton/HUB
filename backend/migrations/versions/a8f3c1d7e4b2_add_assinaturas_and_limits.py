"""add platform subscriptions and contracted limits

Revision ID: a8f3c1d7e4b2
Revises: f7b2c9d4e1a6
"""
from datetime import datetime

from alembic import op
import sqlalchemy as sa


revision = 'a8f3c1d7e4b2'
down_revision = 'f7b2c9d4e1a6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'assinaturas',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('empresa_id', sa.Integer(), nullable=False),
        sa.Column('plano_chave', sa.String(length=50), nullable=False),
        sa.Column('tipo', sa.String(length=20), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('trial_expira_em', sa.DateTime(), nullable=True),
        sa.Column('inicio_periodo_atual', sa.DateTime(), nullable=True),
        sa.Column('fim_periodo_atual', sa.DateTime(), nullable=True),
        sa.Column('proxima_cobranca', sa.DateTime(), nullable=True),
        sa.Column('asaas_subscription_id', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['empresa_id'], ['empresas.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('empresa_id'),
    )
    op.create_index('ix_assinaturas_empresa_id', 'assinaturas', ['empresa_id'])
    op.create_table(
        'limites_contratados',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('empresa_id', sa.Integer(), nullable=False),
        sa.Column('recurso', sa.String(length=20), nullable=False),
        sa.Column('quantidade_contratada', sa.Integer(), nullable=False),
        sa.Column('preco_unitario_vigente', sa.Numeric(10, 2), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['empresa_id'], ['empresas.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('empresa_id', 'recurso', name='uq_limites_contratados_empresa_recurso'),
    )
    op.create_index('ix_limites_contratados_empresa_id', 'limites_contratados', ['empresa_id'])

    empresas = op.get_bind().execute(sa.text('SELECT id FROM empresas ORDER BY id')).scalars().all()
    assinaturas = sa.table(
        'assinaturas',
        sa.column('empresa_id', sa.Integer), sa.column('plano_chave', sa.String),
        sa.column('tipo', sa.String), sa.column('status', sa.String),
        sa.column('created_at', sa.DateTime), sa.column('updated_at', sa.DateTime),
    )
    agora = datetime.utcnow()
    linhas = [
        {
            'empresa_id': empresa_id,
            'plano_chave': 'starter',
            'tipo': 'vitalicio' if empresa_id == 1 else 'trial',
            'status': 'ativa' if empresa_id == 1 else 'trial',
            'created_at': agora,
            'updated_at': agora,
        }
        for empresa_id in empresas
    ]
    if linhas:
        op.bulk_insert(assinaturas, linhas)


def downgrade():
    op.drop_index('ix_limites_contratados_empresa_id', table_name='limites_contratados')
    op.drop_table('limites_contratados')
    op.drop_index('ix_assinaturas_empresa_id', table_name='assinaturas')
    op.drop_table('assinaturas')
