"""C5.5: immutable tenant billing calculation attempts and snapshots."""
from alembic import op
import sqlalchemy as sa


revision = 'r2f7b5c0d3e8'
down_revision = 'q1e6a4b9c2d7'
branch_labels = None
depends_on = None


def upgrade():
    op.create_index('uq_faturas_concessionarias_id_empresa',
                    'faturas_concessionarias', ['id', 'empresa_id'], unique=True)
    op.create_table(
        'billing_calculation_snapshots',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('empresa_id', sa.Integer(), sa.ForeignKey('empresas.id'), nullable=False),
        sa.Column('fatura_concessionaria_id', sa.Integer(), nullable=False),
        sa.Column('fingerprint', sa.String(64), nullable=False),
        sa.Column('regra_snapshot', sa.JSON(), nullable=False),
        sa.Column('entrada_normalizada', sa.JSON(), nullable=False),
        sa.Column('resultado', sa.JSON(), nullable=False),
        sa.Column('valor_final', sa.Numeric(18, 2), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('empresa_id', 'fingerprint', name='uq_billing_snapshot_empresa_fingerprint'),
        sa.UniqueConstraint('id', 'empresa_id', name='uq_billing_snapshot_id_empresa'),
        sa.UniqueConstraint('id', 'empresa_id', 'fatura_concessionaria_id',
                            name='uq_billing_snapshot_id_empresa_invoice'),
        sa.ForeignKeyConstraint(
            ['fatura_concessionaria_id', 'empresa_id'],
            ['faturas_concessionarias.id', 'faturas_concessionarias.empresa_id'],
            name='fk_billing_snapshot_invoice_tenant',
        ),
        sa.CheckConstraint('length(fingerprint) = 64', name='ck_billing_snapshot_fingerprint'),
    )
    op.create_index('ix_billing_calculation_snapshots_empresa_id',
                    'billing_calculation_snapshots', ['empresa_id'])
    op.create_index('ix_billing_calculation_snapshots_fatura_concessionaria_id',
                    'billing_calculation_snapshots', ['fatura_concessionaria_id'])
    op.create_table(
        'billing_calculation_executions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('empresa_id', sa.Integer(), sa.ForeignKey('empresas.id'), nullable=False),
        sa.Column('fatura_concessionaria_id', sa.Integer(), nullable=False),
        sa.Column('snapshot_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('auditoria', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "status IN ('CALCULATED', 'REVIEW_REQUIRED', 'MISSING_DATA', 'UNSUPPORTED', 'ERROR')",
            name='ck_billing_execution_status',
        ),
        sa.CheckConstraint(
            "(status = 'CALCULATED' AND snapshot_id IS NOT NULL) OR "
            "(status <> 'CALCULATED' AND snapshot_id IS NULL)",
            name='ck_billing_execution_snapshot',
        ),
        sa.ForeignKeyConstraint(
            ['fatura_concessionaria_id', 'empresa_id'],
            ['faturas_concessionarias.id', 'faturas_concessionarias.empresa_id'],
            name='fk_billing_execution_invoice_tenant',
        ),
        sa.ForeignKeyConstraint(
            ['snapshot_id', 'empresa_id', 'fatura_concessionaria_id'],
            ['billing_calculation_snapshots.id', 'billing_calculation_snapshots.empresa_id',
             'billing_calculation_snapshots.fatura_concessionaria_id'],
            name='fk_billing_execution_snapshot_invoice_tenant',
        ),
    )
    op.create_index('ix_billing_calculation_executions_empresa_id',
                    'billing_calculation_executions', ['empresa_id'])
    op.create_index('ix_billing_calculation_executions_fatura_concessionaria_id',
                    'billing_calculation_executions', ['fatura_concessionaria_id'])
    op.create_index('ix_billing_calculation_executions_snapshot_id',
                    'billing_calculation_executions', ['snapshot_id'])


def downgrade():
    connection = op.get_bind()
    for table in ('billing_calculation_executions', 'billing_calculation_snapshots'):
        if connection.execute(sa.text(f'SELECT id FROM {table} LIMIT 1')).first():
            raise RuntimeError('Downgrade bloqueado: preservar auditoria de cálculo de cobrança.')
    op.drop_table('billing_calculation_executions')
    op.drop_table('billing_calculation_snapshots')
    op.drop_index('uq_faturas_concessionarias_id_empresa', table_name='faturas_concessionarias')
