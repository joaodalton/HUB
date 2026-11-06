"""B2: tenant-owned event ledger, no changes to issuance or legacy invoices."""
from alembic import op
import sqlalchemy as sa

revision = 'k5e0f4a9b7c1'
down_revision = 'j4d9e3f8a6b0'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('payment_webhook_events',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('empresa_id', sa.Integer(), sa.ForeignKey('empresas.id'), nullable=False),
        sa.Column('fatura_id', sa.Integer(), sa.ForeignKey('faturas.id'), nullable=False),
        sa.Column('provider', sa.String(40), nullable=False),
        sa.Column('event_id', sa.String(255), nullable=False),
        sa.Column('event_type', sa.String(100), nullable=False),
        sa.Column('external_payment_id', sa.String(100), nullable=False),
        sa.Column('external_reference', sa.String(255), nullable=True),
        sa.Column('payload_hash', sa.String(64), nullable=False),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('provider', 'event_id', name='uq_payment_webhook_provider_event'),
    )
    op.create_index('ix_payment_webhook_events_empresa_id', 'payment_webhook_events', ['empresa_id'])
    op.create_index('ix_payment_webhook_events_fatura_id', 'payment_webhook_events', ['fatura_id'])


def downgrade():
    if op.get_bind().execute(sa.text('SELECT id FROM payment_webhook_events LIMIT 1')).first():
        raise RuntimeError('Downgrade bloqueado: preservar ledger de webhook financeiro.')
    op.drop_table('payment_webhook_events')
