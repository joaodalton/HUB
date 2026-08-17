"""consumo and percentual to numeric

Revision ID: e5f9a3b2c7d4
Revises: d4e8f2a1b6c3
Create Date: 2026-08-12 00:00:01.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'e5f9a3b2c7d4'
down_revision = 'd4e8f2a1b6c3'
branch_labels = None
depends_on = None


def upgrade():
    # consumo era texto livre ("450", "450 kWh", vazio...) -- limpa tudo que
    # não é dígito/vírgula/ponto, troca vírgula por ponto, e só então converte.
    # Valor vazio ou sem nenhum dígito vira NULL (não zero -- zero seria "UC
    # com consumo zero de verdade", que é diferente de "nunca preencheram").
    op.execute("""
        ALTER TABLE consumer_units
        ALTER COLUMN consumo TYPE NUMERIC(10, 2)
        USING NULLIF(
            regexp_replace(replace(consumo, ',', '.'), '[^0-9.]', '', 'g'),
            ''
        )::numeric
    """)
    op.execute("ALTER TABLE consumer_units ALTER COLUMN consumo DROP DEFAULT")

    # percentual já era só número digitado como texto -- conversão direta.
    op.execute("""
        ALTER TABLE plant_connections
        ALTER COLUMN percentual TYPE NUMERIC(5, 2)
        USING NULLIF(percentual, '')::numeric
    """)
    op.execute("ALTER TABLE plant_connections ALTER COLUMN percentual DROP DEFAULT")
    op.execute("ALTER TABLE plant_connections ALTER COLUMN percentual SET DEFAULT 0")

    with op.batch_alter_table('plant_connections', schema=None) as batch_op:
        # true = usuário sobrescreveu manualmente (lápis) -- o motor NUNCA
        # sobrescreve essa conexão de novo até isso ser desmarcado.
        batch_op.add_column(sa.Column('percentual_manual', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    with op.batch_alter_table('plant_connections', schema=None) as batch_op:
        batch_op.drop_column('percentual_manual')

    op.execute("ALTER TABLE plant_connections ALTER COLUMN percentual TYPE VARCHAR(10) USING percentual::text")
    op.execute("ALTER TABLE consumer_units ALTER COLUMN consumo TYPE VARCHAR(30) USING consumo::text")