"""C4.1: commercial tariff configuration, without calculation or data defaults."""
from alembic import op
import sqlalchemy as sa

revision = 'o9c4e8f1a3b5'
down_revision = 'n8b3d7e0f2a4'
branch_labels = None
depends_on = None

OLD_METHODS = "'energia_compensada', 'economia_gerada', 'valor_total_fatura', 'tarifa_fixa'"
NEW_METHODS = "'tarifa_fixa_com_desconto', 'tarifa_especifica', 'energia_recebida'"
COLUMNS = (
    ('tariff_hfp', sa.Numeric(18, 6)), ('tariff_hp', sa.Numeric(18, 6)),
    ('exclude_pis_cofins', sa.Boolean()), ('icms_policy', sa.String(20)),
    ('exclude_tariff_flag', sa.Boolean()), ('grace_enabled', sa.Boolean()),
    ('grace_without_discount', sa.Boolean()), ('grace_start', sa.Date()),
    ('grace_end', sa.Date()), ('recurring_additional_cost', sa.Numeric(18, 6)),
)
CHECKS = {
    'icms': "icms_policy IS NULL OR icms_policy = 'exclude'",
    'grace_dates': '(grace_start IS NULL AND grace_end IS NULL) OR '
                   '(grace_start IS NOT NULL AND grace_end IS NOT NULL AND grace_start <= grace_end)',
    'grace_enabled': 'grace_enabled IS TRUE OR '
                     '(grace_without_discount IS NULL AND grace_start IS NULL AND grace_end IS NULL)',
    'company_tariff': "calculation_method NOT IN ('tarifa_especifica', 'tarifa_fixa_com_desconto') "
                      'OR manual_tariff IS NOT NULL',
    'fixed_discount': "calculation_method <> 'tarifa_fixa_com_desconto' OR "
                      "(discount_type = 'percentage' AND discount_value IS NOT NULL)",
}


def upgrade():
    with op.batch_alter_table('grupos_regra_cobranca') as batch:
        for name, column_type in COLUMNS:
            batch.add_column(sa.Column(name, column_type, nullable=True))
        batch.drop_constraint('ck_grupo_regra_calculation_method', type_='check')
        batch.create_check_constraint('ck_grupo_regra_calculation_method',
                                      f'calculation_method IN ({OLD_METHODS}, {NEW_METHODS})')
        batch.drop_constraint('ck_grupo_regra_manual_tariff', type_='check')
        batch.create_check_constraint('ck_grupo_regra_manual_tariff',
                                      "tariff_source <> 'manual' OR manual_tariff IS NOT NULL")
        for name, expression in CHECKS.items():
            batch.create_check_constraint(f'ck_grupo_regra_{name}', expression)


def downgrade():
    configured = ' OR '.join(f'{name} IS NOT NULL' for name, _ in COLUMNS)
    if op.get_bind().execute(sa.text(
        f'SELECT id FROM grupos_regra_cobranca WHERE {configured} '
        f'OR calculation_method IN ({NEW_METHODS}) '
        "OR (tariff_source <> 'manual' AND manual_tariff IS NOT NULL) LIMIT 1"
    )).first():
        raise RuntimeError('Downgrade bloqueado: preservar configuracoes comerciais C4.1.')
    with op.batch_alter_table('grupos_regra_cobranca') as batch:
        for name in CHECKS:
            batch.drop_constraint(f'ck_grupo_regra_{name}', type_='check')
        for name, _ in COLUMNS:
            batch.drop_column(name)
        batch.drop_constraint('ck_grupo_regra_calculation_method', type_='check')
        batch.create_check_constraint('ck_grupo_regra_calculation_method',
                                      f'calculation_method IN ({OLD_METHODS})')
        batch.drop_constraint('ck_grupo_regra_manual_tariff', type_='check')
        batch.create_check_constraint('ck_grupo_regra_manual_tariff',
                                      "(tariff_source = 'manual' AND manual_tariff IS NOT NULL) OR "
                                      "(tariff_source <> 'manual' AND manual_tariff IS NULL)")
