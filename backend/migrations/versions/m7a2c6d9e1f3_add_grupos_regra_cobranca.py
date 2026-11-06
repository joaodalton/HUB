"""C1: reusable tenant billing rule profiles."""
from alembic import op
import sqlalchemy as sa


revision = 'm7a2c6d9e1f3'
down_revision = 'l6f1a5b8c2d4'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'grupos_regra_cobranca',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('empresa_id', sa.Integer(), sa.ForeignKey('empresas.id'), nullable=False),
        sa.Column('nome', sa.String(150), nullable=False),
        sa.Column('descricao', sa.Text(), nullable=True),
        sa.Column('ativo', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('padrao', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('calculation_method', sa.String(40), nullable=False),
        sa.Column('tariff_source', sa.String(20), nullable=False),
        sa.Column('manual_tariff', sa.Numeric(18, 6), nullable=True),
        sa.Column('discount_type', sa.String(20), nullable=False),
        sa.Column('discount_value', sa.Numeric(18, 6), nullable=True),
        sa.Column('tariff_basis', sa.String(40), nullable=False),
        sa.Column('energy_component_index', sa.Integer(), nullable=True),
        sa.Column('billing_mode', sa.String(20), nullable=False),
        sa.Column('due_date_basis', sa.String(40), nullable=False),
        sa.Column('due_date_offset_days', sa.Integer(), nullable=False),
        sa.Column('monthly_interest', sa.Numeric(18, 6), nullable=True),
        sa.Column('fine_percentage', sa.Numeric(18, 6), nullable=True),
        sa.Column('revision', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "calculation_method IN ('energia_compensada', 'economia_gerada', "
            "'valor_total_fatura', 'tarifa_fixa')",
            name='ck_grupo_regra_calculation_method',
        ),
        sa.CheckConstraint("tariff_source IN ('invoice', 'manual')", name='ck_grupo_regra_tariff_source'),
        sa.CheckConstraint(
            "discount_type IN ('percentage', 'fixed', 'none')",
            name='ck_grupo_regra_discount_type',
        ),
        sa.CheckConstraint(
            "tariff_basis IN ('consumed', 'compensated', 'gd1', 'gd2', 'documented_component')",
            name='ck_grupo_regra_tariff_basis',
        ),
        sa.CheckConstraint(
            "billing_mode IN ('auto', 'unified', 'separate')",
            name='ck_grupo_regra_billing_mode',
        ),
        sa.CheckConstraint(
            "due_date_basis IN ('invoice_due_date', 'invoice_issue_date', "
            "'reading_date', 'calculation_date')",
            name='ck_grupo_regra_due_date_basis',
        ),
        sa.CheckConstraint(
            "(tariff_source = 'manual' AND manual_tariff IS NOT NULL) OR "
            "(tariff_source <> 'manual' AND manual_tariff IS NULL)",
            name='ck_grupo_regra_manual_tariff',
        ),
        sa.CheckConstraint(
            "(discount_type = 'none' AND discount_value IS NULL) OR "
            "(discount_type <> 'none' AND discount_value IS NOT NULL)",
            name='ck_grupo_regra_discount_value',
        ),
        sa.CheckConstraint(
            "(tariff_basis = 'documented_component' AND energy_component_index IS NOT NULL "
            "AND energy_component_index >= 0) OR "
            "(tariff_basis <> 'documented_component' AND energy_component_index IS NULL)",
            name='ck_grupo_regra_energy_component',
        ),
        sa.CheckConstraint('revision >= 1', name='ck_grupo_regra_revision'),
    )
    op.create_index(
        'ix_grupos_regra_cobranca_empresa_id',
        'grupos_regra_cobranca', ['empresa_id'],
    )
    op.create_index(
        'uq_grupos_regra_cobranca_default_ativo',
        'grupos_regra_cobranca', ['empresa_id'], unique=True,
        postgresql_where=sa.text('ativo IS TRUE AND padrao IS TRUE'),
        sqlite_where=sa.text('ativo = 1 AND padrao = 1'),
    )


def downgrade():
    if op.get_bind().execute(sa.text(
        'SELECT id FROM grupos_regra_cobranca LIMIT 1'
    )).first():
        raise RuntimeError(
            'Downgrade bloqueado: preservar perfis de regra de cobranca.'
        )
    op.drop_table('grupos_regra_cobranca')
