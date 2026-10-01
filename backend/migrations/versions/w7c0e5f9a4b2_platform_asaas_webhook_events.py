"""Separate platform ASAAS receipt ledger; no tenant billing schema changes."""
from alembic import op
import sqlalchemy as sa

revision = 'w7c0e5f9a4b2'
down_revision = 'v6b9d4e8f3a1'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('platform_asaas_webhook_events',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('event_id', sa.String(255), nullable=False),
        sa.Column('event_type', sa.String(100), nullable=False),
        sa.Column('external_payment_id', sa.String(100), nullable=False),
        sa.Column('external_reference', sa.String(255), nullable=True),
        sa.Column('payload_hash', sa.String(64), nullable=False),
        sa.Column('received_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('event_id', name='uq_platform_asaas_webhook_event_id'),
    )


def downgrade():
    if op.get_bind().execute(sa.text('SELECT id FROM platform_asaas_webhook_events LIMIT 1')).first():
        raise RuntimeError('Downgrade bloqueado: preservar eventos ASAAS da plataforma.')
    op.drop_table('platform_asaas_webhook_events')
