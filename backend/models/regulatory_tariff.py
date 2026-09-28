"""Base tarifária ANEEL global, separada dos dados comerciais por empresa."""
from datetime import datetime

from extensions import db


class DecimalText(db.TypeDecorator):
    """SQLite também preserva a tarifa financeira sem convertê-la em float."""
    impl = db.String(40)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return None if value is None else str(value)

    def process_result_value(self, value, dialect):
        from decimal import Decimal
        return None if value is None else Decimal(value)


class RegulatoryTariffImport(db.Model):
    __tablename__ = 'regulatory_tariff_imports'
    id = db.Column(db.Integer, primary_key=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    file_name = db.Column(db.String(255), nullable=False)
    file_hash = db.Column(db.String(64), nullable=False, index=True)
    source_url = db.Column(db.String(1000), nullable=False)
    source_version = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='completed')
    summary = db.Column(db.JSON, nullable=False, default=dict)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)


class RegulatoryTariffPreview(db.Model):
    __tablename__ = 'regulatory_tariff_previews'
    id = db.Column(db.Integer, primary_key=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    file_name = db.Column(db.String(255), nullable=False)
    file_hash = db.Column(db.String(64), nullable=False)
    source_url = db.Column(db.String(1000), nullable=False)
    source_version = db.Column(db.String(255), nullable=False)
    plan = db.Column(db.JSON, nullable=False)
    summary = db.Column(db.JSON, nullable=False)
    status = db.Column(db.String(20), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    consumed_at = db.Column(db.DateTime, nullable=True)


class RegulatoryTariff(db.Model):
    __tablename__ = 'regulatory_tariffs'
    id = db.Column(db.Integer, primary_key=True)
    import_id = db.Column(db.Integer, db.ForeignKey('regulatory_tariff_imports.id'), nullable=False, index=True)
    official_distributor = db.Column(db.String(100), nullable=False)
    distributor = db.Column(db.String(100), nullable=False)
    component = db.Column(db.String(50), nullable=False)
    base_tariff = db.Column(db.String(100), nullable=False)
    subgroup = db.Column(db.String(50), nullable=False)
    modality = db.Column(db.String(100), nullable=False)
    tariff_class = db.Column(db.String(100), nullable=False, default='')
    tariff_subclass = db.Column(db.String(100), nullable=False, default='')
    tariff_detail = db.Column(db.String(100), nullable=False)
    tariff_period = db.Column(db.String(100), nullable=False, default='')
    source_value = db.Column(DecimalText(), nullable=False)
    source_unit = db.Column(db.String(20), nullable=False)
    value_kwh = db.Column(DecimalText(), nullable=False)
    valid_from = db.Column(db.Date, nullable=False, index=True)
    valid_until = db.Column(db.Date, nullable=False, index=True)
    source_reference = db.Column(db.String(500), nullable=False)
    source_url = db.Column(db.String(1000), nullable=False)
    source_version = db.Column(db.String(255), nullable=False)
    file_hash = db.Column(db.String(64), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint(
        'official_distributor', 'component', 'base_tariff', 'subgroup', 'modality',
        'tariff_class', 'tariff_subclass', 'tariff_detail', 'tariff_period',
        'valid_from', 'valid_until', name='uq_regulatory_tariff_natural_key'),)
