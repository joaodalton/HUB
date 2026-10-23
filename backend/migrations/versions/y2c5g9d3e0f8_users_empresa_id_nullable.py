"""make users.empresa_id nullable for platform-only accounts

Revision ID: y2c5g9d3e0f8
Revises: x1b4f8c2d9e7
Create Date: 2026-10-19 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'y2c5g9d3e0f8'
down_revision = 'x1b4f8c2d9e7'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column('empresa_id', existing_type=sa.Integer(), nullable=True)
    conn = op.get_bind()
    conn.execute(sa.text("""
        UPDATE users SET empresa_id = NULL
        WHERE (is_platform_worker = true OR is_platform_admin = true)
        AND empresa_id IN (SELECT id FROM empresas WHERE slug = 'plataforma-interna')
    """))


def downgrade():
    # Linhas com empresa_id NULL so podem voltar pra NOT NULL se a empresa
    # 'plataforma-interna' ainda existir; caso contrario o downgrade falha.
    conn = op.get_bind()
    conn.execute(sa.text("""
        UPDATE users SET empresa_id = (SELECT id FROM empresas WHERE slug = 'plataforma-interna')
        WHERE empresa_id IS NULL
        AND EXISTS (SELECT 1 FROM empresas WHERE slug = 'plataforma-interna')
    """))
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column('empresa_id', existing_type=sa.Integer(), nullable=False)
