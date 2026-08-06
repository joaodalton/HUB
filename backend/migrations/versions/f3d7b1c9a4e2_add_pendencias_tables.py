"""add pendencias tables

Revision ID: f3d7b1c9a4e2
Revises: a1f9c2e6d8b3
Create Date: 2026-08-04 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'f3d7b1c9a4e2'
down_revision = 'a1f9c2e6d8b3'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'pendencias',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tipo', sa.String(length=20), nullable=False),
        sa.Column('categoria', sa.String(length=50), nullable=False),
        sa.Column('origem', sa.String(length=50), nullable=False),
        sa.Column('titulo', sa.String(length=200), nullable=False),
        sa.Column('descricao', sa.Text(), nullable=True),
        sa.Column('client_id', sa.Integer(), nullable=True),
        sa.Column('consumer_unit_id', sa.Integer(), nullable=True),
        sa.Column('plant_id', sa.Integer(), nullable=True),
        sa.Column('document_id', sa.Integer(), nullable=True),
        sa.Column('prazo', sa.DateTime(), nullable=True),
        sa.Column('prioridade', sa.String(length=20), nullable=False),
        sa.Column('responsavel_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('metadados', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id']),
        sa.ForeignKeyConstraint(['consumer_unit_id'], ['consumer_units.id']),
        sa.ForeignKeyConstraint(['plant_id'], ['plants.id']),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id']),
        sa.ForeignKeyConstraint(['responsavel_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table(
        'pendencia_comentarios',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('pendencia_id', sa.Integer(), nullable=False),
        sa.Column('autor_id', sa.Integer(), nullable=True),
        sa.Column('texto', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['pendencia_id'], ['pendencias.id']),
        sa.ForeignKeyConstraint(['autor_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('pendencia_comentarios')
    op.drop_table('pendencias')