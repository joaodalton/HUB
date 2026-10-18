"""B1: durable issuance intent; legacy financial values remain untouched."""
from alembic import op
import sqlalchemy as sa

revision = 'j4d9e3f8a6b0'
down_revision = 'i3c8d2e7f5a9'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('faturas') as batch:
        batch.alter_column('asaas_id', existing_type=sa.String(100), nullable=True)
        for name, size in [('status_interno', 30), ('payment_provider', 40),
                           ('external_reference', 64), ('emission_key', 64),
                           ('payment_customer_id', 100)]:
            batch.add_column(sa.Column(name, sa.String(size), nullable=True))
        batch.add_column(sa.Column('emissao_iniciada_em', sa.DateTime(), nullable=True))
        batch.create_unique_constraint('uq_faturas_empresa_emission_key', ['empresa_id', 'emission_key'])
        batch.create_unique_constraint('uq_faturas_external_reference', ['external_reference'])
        batch.create_check_constraint('ck_faturas_status_interno',
            "status_interno IN ('aguardando_emissao', 'emitida', 'erro_emissao', 'cancelada')")


def downgrade():
    # Downgrade cannot discard an issuance journal or restore NOT NULL on pending intents.
    pending = op.get_bind().execute(sa.text(
        'SELECT id FROM faturas WHERE external_reference IS NOT NULL OR asaas_id IS NULL LIMIT 1'
    )).first()
    if pending:
        raise RuntimeError('Downgrade bloqueado: existem intencoes B1; preservar diario de emissao.')
    with op.batch_alter_table('faturas') as batch:
        batch.drop_constraint('ck_faturas_status_interno', type_='check')
        batch.drop_constraint('uq_faturas_external_reference', type_='unique')
        batch.drop_constraint('uq_faturas_empresa_emission_key', type_='unique')
        for name in ['status_interno', 'payment_provider', 'external_reference',
                     'emission_key', 'payment_customer_id', 'emissao_iniciada_em']:
            batch.drop_column(name)
        batch.alter_column('asaas_id', existing_type=sa.String(100), nullable=False)
