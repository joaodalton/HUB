from datetime import datetime
from extensions import db, TenantMixin


class ImportPreview(TenantMixin, db.Model):
    __tablename__ = 'import_previews'
    id = db.Column(db.Integer, primary_key=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    arquivo_hash = db.Column(db.String(64), nullable=False)
    plano = db.Column(db.JSON, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='pronto')
    # This index supports both request-time cleanup and a periodic purge job.
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
