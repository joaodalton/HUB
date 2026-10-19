"""Add plant repasse fields, document plant link and pendencia competencia.

Revision ID: x8d1f60ab5c3
Revises: w7c0e5f9a4b2
"""
from alembic import op
import sqlalchemy as sa


revision = 'x8d1f60ab5c3'
down_revision = 'w7c0e5f9a4b2'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('plants') as batch:
        batch.add_column(sa.Column('repasse_tipo', sa.String(20), nullable=True))
        batch.add_column(sa.Column('repasse_valor', sa.Numeric(10, 2), nullable=True))
        batch.create_check_constraint(
            'ck_plants_repasse_tipo',
            "repasse_tipo IS NULL OR repasse_tipo IN ('percentual', 'valor_fixo')"
        )

    with op.batch_alter_table('documents') as batch:
        batch.add_column(sa.Column('plant_id', sa.Integer(), nullable=True))
        batch.create_foreign_key('fk_documents_plant', 'plants', ['plant_id'], ['id'])

    with op.batch_alter_table('pendencias') as batch:
        batch.add_column(sa.Column('competencia', sa.String(7), nullable=True))
        batch.create_unique_constraint(
            'uq_pendencias_plant_origem_competencia',
            ['empresa_id', 'plant_id', 'origem', 'competencia']
        )


def downgrade():
    with op.batch_alter_table('pendencias') as batch:
        batch.drop_constraint('uq_pendencias_plant_origem_competencia', type_='unique')
        batch.drop_column('competencia')

    with op.batch_alter_table('documents') as batch:
        batch.drop_constraint('fk_documents_plant', type_='foreignkey')
        batch.drop_column('plant_id')

    with op.batch_alter_table('plants') as batch:
        batch.drop_constraint('ck_plants_repasse_tipo', type_='check')
        batch.drop_column('repasse_valor')
        batch.drop_column('repasse_tipo')
