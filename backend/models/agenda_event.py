from datetime import datetime

from extensions import TenantMixin, db


class AgendaEvent(TenantMixin, db.Model):
    """Evento operacional próprio; pendências continuam no model Pendencia."""
    __tablename__ = 'agenda_events'
    __table_args__ = (
        db.CheckConstraint("status IN ('aberto', 'cancelado')", name='ck_agenda_events_status'),
    )

    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200), nullable=False)
    descricao = db.Column(db.Text, nullable=True)
    inicio = db.Column(db.DateTime, nullable=False, index=True)
    fim = db.Column(db.DateTime, nullable=True)
    categoria = db.Column(db.String(50), nullable=False, default='Operacional')
    status = db.Column(db.String(20), nullable=False, default='aberto')
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'titulo': self.titulo,
            'descricao': self.descricao,
            'inicio': self.inicio.isoformat(),
            'fim': self.fim.isoformat() if self.fim else None,
            'categoria': self.categoria,
            'status': self.status,
            'criadoEm': self.created_at.isoformat() if self.created_at else None,
            'atualizadoEm': self.updated_at.isoformat() if self.updated_at else None,
        }
