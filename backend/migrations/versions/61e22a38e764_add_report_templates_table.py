"""add report_templates table

Revision ID: 61e22a38e764
Revises: e8efe0950aeb
Create Date: 2026-10-26 18:40:07.066038

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '61e22a38e764'
down_revision = 'e8efe0950aeb'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('report_templates',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('nome', sa.String(length=60), nullable=False),
    sa.Column('accent_hex', sa.String(length=6), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.Column('empresa_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['empresa_id'], ['empresas.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('report_templates', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_report_templates_empresa_id'), ['empresa_id'], unique=False)


def downgrade():
    with op.batch_alter_table('report_templates', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_report_templates_empresa_id'))

    op.drop_table('report_templates')
