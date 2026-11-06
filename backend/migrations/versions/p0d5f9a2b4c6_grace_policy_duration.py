"""C4.2: reusable grace policy; preserve legacy dates for explicit review."""
from alembic import op
import sqlalchemy as sa

revision = 'p0d5f9a2b4c6'
down_revision = 'o9c4e8f1a3b5'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('grupos_regra_cobranca') as batch:
        batch.add_column(sa.Column('grace_duration_months', sa.Integer(), nullable=True))
        batch.create_check_constraint('ck_grupo_regra_grace_duration',
            'grace_duration_months IS NULL OR (grace_duration_months > 0 AND grace_enabled IS TRUE)')


def downgrade():
    if op.get_bind().execute(sa.text(
        'SELECT id FROM grupos_regra_cobranca WHERE grace_duration_months IS NOT NULL LIMIT 1'
    )).first():
        raise RuntimeError('Downgrade bloqueado: preservar duracao de carencia C4.2.')
    with op.batch_alter_table('grupos_regra_cobranca') as batch:
        batch.drop_constraint('ck_grupo_regra_grace_duration', type_='check')
        batch.drop_column('grace_duration_months')
