"""multi_tenant: adiciona empresa_id em todos os modelos de dominio

Revision ID: multi_tenant_v1
Revises: e2f6a9c3d5b8, f4a7b2c6d9e1
Create Date: 2026-08-17 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'multi_tenant_v1'
down_revision = ('e2f6a9c3d5b8', 'f4a7b2c6d9e1')
branch_labels = None
depends_on = None


def upgrade():
    # ---------- clients ----------
    with op.batch_alter_table('clients', schema=None) as batch_op:
        batch_op.add_column(sa.Column('empresa_id', sa.Integer(), nullable=True))

    # Todos os clientes existentes vao pra empresa 1 (Select Energia Solar)
    op.execute("UPDATE clients SET empresa_id = 1 WHERE empresa_id IS NULL")

    with op.batch_alter_table('clients', schema=None) as batch_op:
        batch_op.alter_column('empresa_id', existing_type=sa.Integer(), nullable=False)
        batch_op.create_foreign_key('fk_clients_empresa', 'empresas', ['empresa_id'], ['id'])
        batch_op.create_index('ix_clients_empresa_id', ['empresa_id'])

    # ---------- plants ----------
    with op.batch_alter_table('plants', schema=None) as batch_op:
        batch_op.add_column(sa.Column('empresa_id', sa.Integer(), nullable=True))

    op.execute("UPDATE plants SET empresa_id = 1 WHERE empresa_id IS NULL")

    with op.batch_alter_table('plants', schema=None) as batch_op:
        batch_op.alter_column('empresa_id', existing_type=sa.Integer(), nullable=False)
        batch_op.create_foreign_key('fk_plants_empresa', 'empresas', ['empresa_id'], ['id'])
        batch_op.create_index('ix_plants_empresa_id', ['empresa_id'])

    # ---------- consumer_units ----------
    with op.batch_alter_table('consumer_units', schema=None) as batch_op:
        batch_op.add_column(sa.Column('empresa_id', sa.Integer(), nullable=True))

    # UC herda empresa_id do cliente
    op.execute("""
        UPDATE consumer_units
        SET empresa_id = (
            SELECT empresa_id FROM clients WHERE clients.id = consumer_units.client_id
        )
        WHERE empresa_id IS NULL
    """)

    with op.batch_alter_table('consumer_units', schema=None) as batch_op:
        batch_op.alter_column('empresa_id', existing_type=sa.Integer(), nullable=False)
        batch_op.create_foreign_key('fk_consumer_units_empresa', 'empresas', ['empresa_id'], ['id'])
        batch_op.create_index('ix_consumer_units_empresa_id', ['empresa_id'])

    # ---------- plant_connections ----------
    with op.batch_alter_table('plant_connections', schema=None) as batch_op:
        batch_op.add_column(sa.Column('empresa_id', sa.Integer(), nullable=True))

    # PlantConnection herda empresa_id da UC
    op.execute("""
        UPDATE plant_connections
        SET empresa_id = (
            SELECT empresa_id FROM consumer_units WHERE consumer_units.id = plant_connections.consumer_unit_id
        )
        WHERE empresa_id IS NULL
    """)

    with op.batch_alter_table('plant_connections', schema=None) as batch_op:
        batch_op.alter_column('empresa_id', existing_type=sa.Integer(), nullable=False)
        batch_op.create_foreign_key('fk_plant_connections_empresa', 'empresas', ['empresa_id'], ['id'])
        batch_op.create_index('ix_plant_connections_empresa_id', ['empresa_id'])

    # ---------- documents ----------
    with op.batch_alter_table('documents', schema=None) as batch_op:
        batch_op.add_column(sa.Column('empresa_id', sa.Integer(), nullable=True))

    # Documento herda empresa_id do cliente (prioridade) ou da UC
    op.execute("""
        UPDATE documents
        SET empresa_id = COALESCE(
            (SELECT empresa_id FROM clients WHERE clients.id = documents.client_id),
            (SELECT empresa_id FROM consumer_units WHERE consumer_units.id = documents.consumer_unit_id),
            1
        )
        WHERE empresa_id IS NULL
    """)

    with op.batch_alter_table('documents', schema=None) as batch_op:
        batch_op.alter_column('empresa_id', existing_type=sa.Integer(), nullable=False)
        batch_op.create_foreign_key('fk_documents_empresa', 'empresas', ['empresa_id'], ['id'])
        batch_op.create_index('ix_documents_empresa_id', ['empresa_id'])

    # ---------- pendencias ----------
    with op.batch_alter_table('pendencias', schema=None) as batch_op:
        batch_op.add_column(sa.Column('empresa_id', sa.Integer(), nullable=True))

    # Pendencia herda empresa_id da UC (prioridade), Cliente ou Planta
    op.execute("""
        UPDATE pendencias
        SET empresa_id = COALESCE(
            (SELECT empresa_id FROM consumer_units WHERE consumer_units.id = pendencias.consumer_unit_id),
            (SELECT empresa_id FROM clients WHERE clients.id = pendencias.client_id),
            (SELECT empresa_id FROM plants WHERE plants.id = pendencias.plant_id),
            1
        )
        WHERE empresa_id IS NULL
    """)

    with op.batch_alter_table('pendencias', schema=None) as batch_op:
        batch_op.alter_column('empresa_id', existing_type=sa.Integer(), nullable=False)
        batch_op.create_foreign_key('fk_pendencias_empresa', 'empresas', ['empresa_id'], ['id'])
        batch_op.create_index('ix_pendencias_empresa_id', ['empresa_id'])

    # ---------- pendencia_comentarios ----------
    with op.batch_alter_table('pendencia_comentarios', schema=None) as batch_op:
        batch_op.add_column(sa.Column('empresa_id', sa.Integer(), nullable=True))

    # Comentario herda empresa_id da pendencia
    op.execute("""
        UPDATE pendencia_comentarios
        SET empresa_id = (
            SELECT empresa_id FROM pendencias WHERE pendencias.id = pendencia_comentarios.pendencia_id
        )
        WHERE empresa_id IS NULL
    """)

    with op.batch_alter_table('pendencia_comentarios', schema=None) as batch_op:
        batch_op.alter_column('empresa_id', existing_type=sa.Integer(), nullable=False)
        batch_op.create_foreign_key('fk_pendencia_comentarios_empresa', 'empresas', ['empresa_id'], ['id'])
        batch_op.create_index('ix_pendencia_comentarios_empresa_id', ['empresa_id'])


def downgrade():
    with op.batch_alter_table('pendencia_comentarios', schema=None) as batch_op:
        batch_op.drop_constraint('fk_pendencia_comentarios_empresa', type_='foreignkey')
        batch_op.drop_index('ix_pendencia_comentarios_empresa_id')
        batch_op.drop_column('empresa_id')

    with op.batch_alter_table('pendencias', schema=None) as batch_op:
        batch_op.drop_constraint('fk_pendencias_empresa', type_='foreignkey')
        batch_op.drop_index('ix_pendencias_empresa_id')
        batch_op.drop_column('empresa_id')

    with op.batch_alter_table('documents', schema=None) as batch_op:
        batch_op.drop_constraint('fk_documents_empresa', type_='foreignkey')
        batch_op.drop_index('ix_documents_empresa_id')
        batch_op.drop_column('empresa_id')

    with op.batch_alter_table('plant_connections', schema=None) as batch_op:
        batch_op.drop_constraint('fk_plant_connections_empresa', type_='foreignkey')
        batch_op.drop_index('ix_plant_connections_empresa_id')
        batch_op.drop_column('empresa_id')

    with op.batch_alter_table('consumer_units', schema=None) as batch_op:
        batch_op.drop_constraint('fk_consumer_units_empresa', type_='foreignkey')
        batch_op.drop_index('ix_consumer_units_empresa_id')
        batch_op.drop_column('empresa_id')

    with op.batch_alter_table('plants', schema=None) as batch_op:
        batch_op.drop_constraint('fk_plants_empresa', type_='foreignkey')
        batch_op.drop_index('ix_plants_empresa_id')
        batch_op.drop_column('empresa_id')

    with op.batch_alter_table('clients', schema=None) as batch_op:
        batch_op.drop_constraint('fk_clients_empresa', type_='foreignkey')
        batch_op.drop_index('ix_clients_empresa_id')
        batch_op.drop_column('empresa_id')
