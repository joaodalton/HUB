"""C2: tenant billing rule assignments by explicit scope."""
from alembic import op
import sqlalchemy as sa


revision = 'n8b3d7e0f2a4'
down_revision = 'm7a2c6d9e1f3'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'regra_cobranca_assignments',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('empresa_id', sa.Integer(), sa.ForeignKey('empresas.id'), nullable=False),
        sa.Column(
            'grupo_regra_cobranca_id', sa.Integer(),
            sa.ForeignKey('grupos_regra_cobranca.id'), nullable=False,
        ),
        sa.Column('scope_type', sa.String(20), nullable=False),
        sa.Column('client_id', sa.Integer(), sa.ForeignKey('clients.id'), nullable=True),
        sa.Column(
            'consumer_unit_id', sa.Integer(), sa.ForeignKey('consumer_units.id'), nullable=True,
        ),
        sa.Column('ativo', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "scope_type IN ('company', 'client', 'consumer_unit')",
            name='ck_regra_assignment_scope_type',
        ),
        sa.CheckConstraint(
            "(scope_type = 'company' AND client_id IS NULL AND consumer_unit_id IS NULL) OR "
            "(scope_type = 'client' AND client_id IS NOT NULL AND consumer_unit_id IS NULL) OR "
            "(scope_type = 'consumer_unit' AND client_id IS NULL AND consumer_unit_id IS NOT NULL)",
            name='ck_regra_assignment_target',
        ),
    )
    op.create_index(
        'ix_regra_cobranca_assignments_empresa_id',
        'regra_cobranca_assignments', ['empresa_id'],
    )
    op.create_index(
        'ix_regra_cobranca_assignments_grupo_regra_cobranca_id',
        'regra_cobranca_assignments', ['grupo_regra_cobranca_id'],
    )
    op.create_index(
        'ix_regra_cobranca_assignments_client_id',
        'regra_cobranca_assignments', ['client_id'],
    )
    op.create_index(
        'ix_regra_cobranca_assignments_consumer_unit_id',
        'regra_cobranca_assignments', ['consumer_unit_id'],
    )
    op.create_index(
        'ix_regra_assignment_empresa_scope',
        'regra_cobranca_assignments', ['empresa_id', 'scope_type'],
    )
    op.create_index(
        'uq_regra_assignment_company_ativo',
        'regra_cobranca_assignments', ['empresa_id'], unique=True,
        postgresql_where=sa.text("ativo IS TRUE AND scope_type = 'company'"),
        sqlite_where=sa.text("ativo = 1 AND scope_type = 'company'"),
    )
    op.create_index(
        'uq_regra_assignment_client_ativo',
        'regra_cobranca_assignments', ['empresa_id', 'client_id'], unique=True,
        postgresql_where=sa.text("ativo IS TRUE AND scope_type = 'client'"),
        sqlite_where=sa.text("ativo = 1 AND scope_type = 'client'"),
    )
    op.create_index(
        'uq_regra_assignment_uc_ativo',
        'regra_cobranca_assignments', ['empresa_id', 'consumer_unit_id'], unique=True,
        postgresql_where=sa.text("ativo IS TRUE AND scope_type = 'consumer_unit'"),
        sqlite_where=sa.text("ativo = 1 AND scope_type = 'consumer_unit'"),
    )


def downgrade():
    if op.get_bind().execute(sa.text(
        'SELECT id FROM regra_cobranca_assignments LIMIT 1'
    )).first():
        raise RuntimeError(
            'Downgrade bloqueado: preservar historico de assignments de regra de cobranca.'
        )
    op.drop_table('regra_cobranca_assignments')
