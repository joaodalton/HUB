"""F1: immutable utility invoice source records."""
from alembic import op
import sqlalchemy as sa


revision = 'l6f1a5b8c2d4'
down_revision = 'k5e0f4a9b7c1'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'faturas_concessionarias',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('empresa_id', sa.Integer(), sa.ForeignKey('empresas.id'), nullable=False),
        sa.Column('client_id', sa.Integer(), sa.ForeignKey('clients.id'), nullable=False),
        sa.Column('consumer_unit_id', sa.Integer(), sa.ForeignKey('consumer_units.id'), nullable=True),
        sa.Column('document_id', sa.Integer(), sa.ForeignKey('documents.id'), nullable=False),
        sa.Column('concessionaria', sa.String(50), nullable=True),
        sa.Column('codigo_uc_extraido', sa.String(100), nullable=True),
        sa.Column('competencia', sa.String(7), nullable=True),
        sa.Column('numero_nota_fiscal', sa.String(100), nullable=True),
        sa.Column('serie_nota_fiscal', sa.String(50), nullable=True),
        sa.Column('chave_acesso', sa.String(64), nullable=True),
        sa.Column('arquivo_hash', sa.String(64), nullable=False),
        sa.Column('data_emissao', sa.Date(), nullable=True),
        sa.Column('data_leitura_anterior', sa.Date(), nullable=True),
        sa.Column('data_leitura_atual', sa.Date(), nullable=True),
        sa.Column('data_proxima_leitura', sa.Date(), nullable=True),
        sa.Column('data_vencimento', sa.Date(), nullable=True),
        sa.Column('consumo_kwh', sa.Numeric(18, 6), nullable=True),
        sa.Column('energia_compensada_kwh', sa.Numeric(18, 6), nullable=True),
        sa.Column('injecao_gd1_kwh', sa.Numeric(18, 6), nullable=True),
        sa.Column('injecao_gd2_kwh', sa.Numeric(18, 6), nullable=True),
        sa.Column('saldo_creditos_kwh', sa.Numeric(18, 6), nullable=True),
        sa.Column('valor_total_concessionaria', sa.Numeric(18, 2), nullable=True),
        sa.Column('parser_name', sa.String(100), nullable=True),
        sa.Column('parser_version', sa.String(50), nullable=True),
        sa.Column('layout_name', sa.String(100), nullable=True),
        sa.Column('layout_version', sa.String(50), nullable=True),
        sa.Column('status_extracao', sa.String(30), nullable=False, server_default='recebida'),
        sa.Column('status_validacao', sa.String(30), nullable=False, server_default='pendente'),
        sa.Column('dados_brutos_extraidos', sa.JSON(), nullable=True),
        sa.Column('dados_normalizados', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "status_extracao IN ('recebida', 'processando', 'extraida', "
            "'layout_nao_reconhecido', 'erro')",
            name='ck_faturas_concessionarias_status_extracao',
        ),
        sa.CheckConstraint(
            "status_validacao IN ('pendente', 'valida', 'revisao_necessaria', "
            "'uc_nao_encontrada', 'uc_pertence_outro_cliente')",
            name='ck_faturas_concessionarias_status_validacao',
        ),
        sa.UniqueConstraint(
            'empresa_id', 'arquivo_hash',
            name='uq_faturas_concessionarias_empresa_hash',
        ),
    )
    op.create_index(
        'ix_faturas_concessionarias_empresa_id',
        'faturas_concessionarias', ['empresa_id'],
    )
    op.create_index(
        'ix_faturas_concessionarias_empresa_chave',
        'faturas_concessionarias', ['empresa_id', 'chave_acesso'],
    )


def downgrade():
    if op.get_bind().execute(sa.text(
        'SELECT id FROM faturas_concessionarias LIMIT 1'
    )).first():
        raise RuntimeError(
            'Downgrade bloqueado: preservar faturas originais da concessionaria.'
        )
    op.drop_table('faturas_concessionarias')
