"""add tenant message templates

Revision ID: e6a8c0d2f4b6
Revises: d5e7f9a1b2c3
"""
from alembic import op
import sqlalchemy as sa

revision = 'e6a8c0d2f4b6'
down_revision = 'd5e7f9a1b2c3'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('message_templates',
        sa.Column('id', sa.Integer(), primary_key=True), sa.Column('empresa_id', sa.Integer(), nullable=False),
        sa.Column('canal', sa.String(20), nullable=False), sa.Column('chave', sa.String(50), nullable=False),
        sa.Column('nome', sa.String(150), nullable=False), sa.Column('assunto', sa.String(255), nullable=False, server_default=''),
        sa.Column('corpo', sa.Text(), nullable=False), sa.Column('variaveis_permitidas', sa.String(255), nullable=False, server_default=''),
        sa.Column('padrao', sa.Boolean(), nullable=False, server_default=sa.false()), sa.Column('origem_chave', sa.String(50)),
        sa.Column('created_at', sa.DateTime()), sa.Column('updated_at', sa.DateTime()),
        sa.ForeignKeyConstraint(['empresa_id'], ['empresas.id']),
        sa.CheckConstraint("canal IN ('email', 'whatsapp')", name='ck_message_templates_canal'),
        sa.UniqueConstraint('empresa_id', 'canal', 'chave', name='uq_message_templates_empresa_canal_chave'))
    op.create_index('ix_message_templates_empresa_id', 'message_templates', ['empresa_id'])
    op.execute("""INSERT INTO message_templates (empresa_id, canal, chave, nome, assunto, corpo, variaveis_permitidas, padrao, origem_chave, created_at, updated_at)
        SELECT e.id, 'email', t.chave, t.nome, t.assunto, t.corpo, COALESCE(t.variaveis_disponiveis,''), 1, t.chave, t.created_at, t.updated_at FROM empresas e CROSS JOIN email_templates t""")

def downgrade():
    changed = op.get_bind().execute(sa.text("""SELECT 1 FROM message_templates m WHERE m.canal <> 'email' OR m.padrao = 0 OR m.origem_chave IS NULL OR NOT EXISTS
        (SELECT 1 FROM email_templates e WHERE e.chave=m.origem_chave AND e.nome=m.nome AND e.assunto=m.assunto AND e.corpo=m.corpo AND COALESCE(e.variaveis_disponiveis,'')=m.variaveis_permitidas) LIMIT 1""")).scalar()
    if changed is not None: raise ValueError('Não é possível reverter: existem templates por empresa alterados ou criados.')
    op.drop_index('ix_message_templates_empresa_id', table_name='message_templates')
    op.drop_table('message_templates')
