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


def _is_sqlite() -> bool:
    return op.get_bind().dialect.name == 'sqlite'


def _sqlite_normalizar_consumo(valor):
    """Equivalente local do regexp_replace usado no PostgreSQL.

    A migration original aceita dígitos, ponto e vírgula e transforma o resto
    em vazio/NULL. Preparamos valores textuais antes do batch_alter, pois
    SQLite não suporta ALTER COLUMN ... USING nem regexp_replace.
    """
    if valor is None:
        return None
    limpo = ''.join(char for char in str(valor).replace(',', '.') if char.isdigit() or char == '.')
    return limpo or None


def _upgrade_sqlite():
    bind = op.get_bind()
    for row in bind.execute(sa.text('SELECT id, consumo FROM consumer_units')).mappings():
        bind.execute(
            sa.text('UPDATE consumer_units SET consumo = :consumo WHERE id = :id'),
            {'id': row['id'], 'consumo': _sqlite_normalizar_consumo(row['consumo'])},
        )

    # percentual não aceita NULL no schema histórico. A migration PostgreSQL
    # também falharia se uma string vazia existisse por causa desse NOT NULL;
    # manter o valor limpo permite o mesmo cast para os dados válidos.
    for row in bind.execute(sa.text('SELECT id, percentual FROM plant_connections')).mappings():
        percentual = row['percentual']
        if percentual is None or str(percentual).strip() == '':
            raise ValueError('plant_connections.percentual vazio nao pode ser convertido para numerico.')
        bind.execute(
            sa.text('UPDATE plant_connections SET percentual = :percentual WHERE id = :id'),
            {'id': row['id'], 'percentual': str(percentual).strip()},
        )

    with op.batch_alter_table('consumer_units', schema=None) as batch_op:
        batch_op.alter_column(
            'consumo', existing_type=sa.String(length=30), type_=sa.Numeric(10, 2),
            existing_nullable=True, server_default=None,
        )
    with op.batch_alter_table('plant_connections', schema=None) as batch_op:
        batch_op.alter_column(
            'percentual', existing_type=sa.String(length=10), type_=sa.Numeric(5, 2),
            existing_nullable=False, server_default=sa.text('0'),
        )
        # true = usuário sobrescreveu manualmente (lápis) -- o motor NUNCA
        # sobrescreve essa conexão de novo até isso ser desmarcado.
        batch_op.add_column(sa.Column('percentual_manual', sa.Boolean(), nullable=False, server_default=sa.false()))


def upgrade():
    if _is_sqlite():
        _upgrade_sqlite()
        return

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
    if _is_sqlite():
        with op.batch_alter_table('plant_connections', schema=None) as batch_op:
            batch_op.drop_column('percentual_manual')
            batch_op.alter_column(
                'percentual', existing_type=sa.Numeric(5, 2), type_=sa.String(length=10),
                existing_nullable=False, server_default=None,
            )
        with op.batch_alter_table('consumer_units', schema=None) as batch_op:
            batch_op.alter_column(
                'consumo', existing_type=sa.Numeric(10, 2), type_=sa.String(length=30),
                existing_nullable=True, server_default=None,
            )
        return

    with op.batch_alter_table('plant_connections', schema=None) as batch_op:
        batch_op.drop_column('percentual_manual')

    op.execute("ALTER TABLE plant_connections ALTER COLUMN percentual TYPE VARCHAR(10) USING percentual::text")
    op.execute("ALTER TABLE consumer_units ALTER COLUMN consumo TYPE VARCHAR(30) USING consumo::text")
