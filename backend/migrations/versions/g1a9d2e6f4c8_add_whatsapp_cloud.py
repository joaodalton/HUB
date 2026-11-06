"""add Meta WhatsApp Cloud integration, conversations and approval metadata

Revision ID: g1a9d2e6f4c8
Revises: a8f3c1d7e4b2
"""
from alembic import op
import sqlalchemy as sa

revision = 'g1a9d2e6f4c8'
down_revision = 'a8f3c1d7e4b2'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('message_templates', sa.Column('meta_status', sa.String(20), nullable=False, server_default='draft'))
    op.add_column('message_templates', sa.Column('meta_category', sa.String(20), nullable=True))
    op.add_column('message_templates', sa.Column('meta_template_id', sa.String(100), nullable=True))
    op.add_column('message_templates', sa.Column('meta_rejection_reason', sa.String(500), nullable=True))
    op.add_column('message_templates', sa.Column('meta_submitted_at', sa.DateTime(), nullable=True))
    op.create_table(
        'whatsapp_integrations',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('empresa_id', sa.Integer(), nullable=False),
        sa.Column('api_credential_id', sa.Integer(), nullable=False),
        sa.Column('phone_number_id', sa.String(100), nullable=False),
        sa.Column('business_account_id', sa.String(100), nullable=False),
        sa.Column('display_phone_number', sa.String(40), nullable=True),
        sa.Column('verified_name', sa.String(150), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['empresa_id'], ['empresas.id']),
        sa.ForeignKeyConstraint(['api_credential_id'], ['api_credentials.id']),
        sa.UniqueConstraint('empresa_id', name='uq_whatsapp_integrations_empresa'),
        sa.UniqueConstraint('phone_number_id', name='uq_whatsapp_integrations_phone_number'),
        sa.UniqueConstraint('api_credential_id'),
    )
    op.create_index('ix_whatsapp_integrations_empresa_id', 'whatsapp_integrations', ['empresa_id'])
    op.create_table(
        'whatsapp_conversations',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('empresa_id', sa.Integer(), nullable=False),
        sa.Column('client_id', sa.Integer(), nullable=True),
        sa.Column('consumer_unit_id', sa.Integer(), nullable=True),
        sa.Column('phone_number', sa.String(30), nullable=False),
        sa.Column('contact_name', sa.String(150), nullable=True),
        sa.Column('last_message_at', sa.DateTime(), nullable=True),
        sa.Column('unread_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['empresa_id'], ['empresas.id']),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id']),
        sa.ForeignKeyConstraint(['consumer_unit_id'], ['consumer_units.id']),
        sa.UniqueConstraint('empresa_id', 'phone_number', name='uq_whatsapp_conversations_empresa_phone'),
    )
    op.create_index('ix_whatsapp_conversations_empresa_id', 'whatsapp_conversations', ['empresa_id'])
    op.create_index('ix_whatsapp_conversations_last_message_at', 'whatsapp_conversations', ['last_message_at'])
    op.create_table(
        'whatsapp_messages',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('empresa_id', sa.Integer(), nullable=False),
        sa.Column('conversation_id', sa.Integer(), nullable=False),
        sa.Column('message_template_id', sa.Integer(), nullable=True),
        sa.Column('direction', sa.String(10), nullable=False),
        sa.Column('message_type', sa.String(20), nullable=False, server_default='text'),
        sa.Column('body', sa.Text(), nullable=False, server_default=''),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('meta_message_id', sa.String(150), nullable=True),
        sa.Column('provider_error', sa.String(500), nullable=True),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.Column('delivered_at', sa.DateTime(), nullable=True),
        sa.Column('read_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['empresa_id'], ['empresas.id']),
        sa.ForeignKeyConstraint(['conversation_id'], ['whatsapp_conversations.id']),
        sa.ForeignKeyConstraint(['message_template_id'], ['message_templates.id']),
        sa.UniqueConstraint('meta_message_id', name='uq_whatsapp_messages_meta_message'),
        sa.CheckConstraint("direction IN ('inbound', 'outbound')", name='ck_whatsapp_messages_direction'),
        sa.CheckConstraint("status IN ('queued', 'sent', 'delivered', 'read', 'failed', 'received')", name='ck_whatsapp_messages_status'),
    )
    op.create_index('ix_whatsapp_messages_empresa_id', 'whatsapp_messages', ['empresa_id'])
    op.create_index('ix_whatsapp_messages_conversation_id', 'whatsapp_messages', ['conversation_id'])


def downgrade():
    op.drop_index('ix_whatsapp_messages_conversation_id', table_name='whatsapp_messages')
    op.drop_index('ix_whatsapp_messages_empresa_id', table_name='whatsapp_messages')
    op.drop_table('whatsapp_messages')
    op.drop_index('ix_whatsapp_conversations_last_message_at', table_name='whatsapp_conversations')
    op.drop_index('ix_whatsapp_conversations_empresa_id', table_name='whatsapp_conversations')
    op.drop_table('whatsapp_conversations')
    op.drop_index('ix_whatsapp_integrations_empresa_id', table_name='whatsapp_integrations')
    op.drop_table('whatsapp_integrations')
    op.drop_column('message_templates', 'meta_submitted_at')
    op.drop_column('message_templates', 'meta_rejection_reason')
    op.drop_column('message_templates', 'meta_template_id')
    op.drop_column('message_templates', 'meta_category')
    op.drop_column('message_templates', 'meta_status')
