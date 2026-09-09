from datetime import datetime

from extensions import db

RECURSOS_VALIDOS = ('usuarios', 'clientes', 'ucs', 'usinas')


class LimiteContratado(db.Model):
    """Volume total contratado por empresa e recurso."""
    __tablename__ = 'limites_contratados'
    __table_args__ = (
        db.UniqueConstraint('empresa_id', 'recurso', name='uq_limites_contratados_empresa_recurso'),
    )

    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey('empresas.id'), nullable=False, index=True)
    recurso = db.Column(db.String(20), nullable=False)
    quantidade_contratada = db.Column(db.Integer, nullable=False)
    preco_unitario_vigente = db.Column(db.Numeric(10, 2), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            'recurso': self.recurso,
            'quantidadeContratada': self.quantidade_contratada,
            'precoUnitarioVigente': float(self.preco_unitario_vigente) if self.preco_unitario_vigente is not None else None,
        }
