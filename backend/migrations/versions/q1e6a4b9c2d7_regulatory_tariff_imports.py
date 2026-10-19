"""C5.4.1 global ANEEL tariff import base."""
from alembic import op
import sqlalchemy as sa

revision = 'q1e6a4b9c2d7'
down_revision = 'p0d5f9a2b4c6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('regulatory_tariff_imports',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('file_name', sa.String(255), nullable=False), sa.Column('file_hash', sa.String(64), nullable=False),
        sa.Column('source_url', sa.String(1000), nullable=False), sa.Column('source_version', sa.String(255), nullable=False),
        sa.Column('status', sa.String(20), nullable=False), sa.Column('summary', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False), sa.Column('completed_at', sa.DateTime()),
    )
    op.create_index('ix_regulatory_tariff_imports_created_by_id', 'regulatory_tariff_imports', ['created_by_id'])
    op.create_index('ix_regulatory_tariff_imports_file_hash', 'regulatory_tariff_imports', ['file_hash'])
    op.create_table('regulatory_tariff_previews',
        sa.Column('id', sa.Integer(), primary_key=True), sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('file_name', sa.String(255), nullable=False), sa.Column('file_hash', sa.String(64), nullable=False),
        sa.Column('source_url', sa.String(1000), nullable=False), sa.Column('source_version', sa.String(255), nullable=False),
        sa.Column('plan', sa.JSON(), nullable=False), sa.Column('summary', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False), sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False), sa.Column('consumed_at', sa.DateTime()),
    )
    op.create_index('ix_regulatory_tariff_previews_created_by_id', 'regulatory_tariff_previews', ['created_by_id'])
    op.create_index('ix_regulatory_tariff_previews_expires_at', 'regulatory_tariff_previews', ['expires_at'])
    op.create_table('regulatory_tariffs',
        sa.Column('id', sa.Integer(), primary_key=True), sa.Column('import_id', sa.Integer(), sa.ForeignKey('regulatory_tariff_imports.id'), nullable=False),
        sa.Column('official_distributor', sa.String(100), nullable=False), sa.Column('distributor', sa.String(100), nullable=False),
        sa.Column('component', sa.String(50), nullable=False), sa.Column('base_tariff', sa.String(100), nullable=False),
        sa.Column('subgroup', sa.String(50), nullable=False), sa.Column('modality', sa.String(100), nullable=False),
        sa.Column('tariff_class', sa.String(100), nullable=False, server_default=''), sa.Column('tariff_subclass', sa.String(100), nullable=False, server_default=''), sa.Column('tariff_detail', sa.String(100), nullable=False), sa.Column('tariff_period', sa.String(100), nullable=False, server_default=''),
        sa.Column('source_value', sa.String(40), nullable=False), sa.Column('source_unit', sa.String(20), nullable=False), sa.Column('value_kwh', sa.String(40), nullable=False),
        sa.Column('valid_from', sa.Date(), nullable=False), sa.Column('valid_until', sa.Date(), nullable=False),
        sa.Column('source_reference', sa.String(500), nullable=False), sa.Column('source_url', sa.String(1000), nullable=False),
        sa.Column('source_version', sa.String(255), nullable=False), sa.Column('file_hash', sa.String(64), nullable=False), sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('official_distributor', 'component', 'base_tariff', 'subgroup', 'modality', 'tariff_class', 'tariff_subclass', 'tariff_detail', 'tariff_period', 'valid_from', 'valid_until', name='uq_regulatory_tariff_natural_key'),
    )
    op.create_index('ix_regulatory_tariffs_import_id', 'regulatory_tariffs', ['import_id'])
    op.create_index('ix_regulatory_tariffs_valid_from', 'regulatory_tariffs', ['valid_from'])
    op.create_index('ix_regulatory_tariffs_valid_until', 'regulatory_tariffs', ['valid_until'])


def downgrade():
    op.drop_table('regulatory_tariffs')
    op.drop_table('regulatory_tariff_previews')
    op.drop_table('regulatory_tariff_imports')
