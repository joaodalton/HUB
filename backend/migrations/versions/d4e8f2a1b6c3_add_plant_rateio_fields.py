"""add plant rateio fields

Revision ID: d4e8f2a1b6c3
Revises: b7c3e5a1d9f4
Create Date: 2026-08-12 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'd4e8f2a1b6c3'
down_revision = 'b7c3e5a1d9f4'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('plants', schema=None) as batch_op:
        # Dados de localização/equipamento -- ainda não usados no cálculo,
        # servem pra quando a estimativa via CRESESB/API de inversor existir.
        batch_op.add_column(sa.Column('cep', sa.String(length=10), nullable=True))
        batch_op.add_column(sa.Column('latitude', sa.Numeric(9, 6), nullable=True))
        batch_op.add_column(sa.Column('longitude', sa.Numeric(9, 6), nullable=True))
        batch_op.add_column(sa.Column('num_modulos', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('potencia_modulo_w', sa.Numeric(8, 2), nullable=True))

        # Produção mensal manual (kWh) -- usada de verdade pelo motor de rateio.
        for mes in ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez']:
            batch_op.add_column(sa.Column(f'producao_{mes}', sa.Numeric(10, 2), nullable=False, server_default='0'))

        # Reserva estratégica -- desligada por padrão (0), cada usina escolhe a dela.
        batch_op.add_column(sa.Column('reserva_percentual', sa.Numeric(5, 2), nullable=False, server_default='0'))

        # Dia do mês em que a CONCESSIONÁRIA lê a usina (comparado com o dia de
        # emissão da UC pra sugerir elegibilidade -- ver rateio_service.py).
        batch_op.add_column(sa.Column('dia_emissao_usina', sa.Integer(), nullable=True))

        # Flag simples -- não entra na conta do motor ainda, só marca a usina.
        batch_op.add_column(sa.Column('is_coringa', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    with op.batch_alter_table('plants', schema=None) as batch_op:
        batch_op.drop_column('is_coringa')
        batch_op.drop_column('dia_emissao_usina')
        batch_op.drop_column('reserva_percentual')
        for mes in ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez']:
            batch_op.drop_column(f'producao_{mes}')
        batch_op.drop_column('potencia_modulo_w')
        batch_op.drop_column('num_modulos')
        batch_op.drop_column('longitude')
        batch_op.drop_column('latitude')
        batch_op.drop_column('cep')