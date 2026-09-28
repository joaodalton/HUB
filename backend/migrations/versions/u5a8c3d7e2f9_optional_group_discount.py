"""Permit a fixed-with-discount profile without discount stored on the group.

Revision ID: u5a8c3d7e2f9
Revises: t4d9e2a7c1b5
"""
from alembic import op
import sqlalchemy as sa


revision = 'u5a8c3d7e2f9'
down_revision = 't4d9e2a7c1b5'
branch_labels = None
depends_on = None


OLD_CHECK = (
    "calculation_method <> 'tarifa_fixa_com_desconto' OR "
    "(discount_type = 'percentage' AND discount_value IS NOT NULL)"
)
NEW_CHECK = (
    OLD_CHECK + " OR (discount_type = 'none' AND discount_value IS NULL)"
)


def upgrade():
    with op.batch_alter_table('grupos_regra_cobranca') as batch:
        batch.drop_constraint('ck_grupo_regra_fixed_discount', type_='check')
        batch.create_check_constraint('ck_grupo_regra_fixed_discount', NEW_CHECK)


def downgrade():
    if op.get_bind().execute(sa.text(
        "SELECT id FROM grupos_regra_cobranca "
        "WHERE calculation_method = 'tarifa_fixa_com_desconto' "
        "AND discount_type = 'none' LIMIT 1"
    )).first():
        raise RuntimeError('Downgrade bloqueado: preservar regras sem desconto no grupo.')
    with op.batch_alter_table('grupos_regra_cobranca') as batch:
        batch.drop_constraint('ck_grupo_regra_fixed_discount', type_='check')
        batch.create_check_constraint('ck_grupo_regra_fixed_discount', OLD_CHECK)
