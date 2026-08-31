# backend/models/pendencia.py
from datetime import datetime

from extensions import db, TenantMixin

TIPOS = ('pendencia', 'alerta', 'erro')
PRIORIDADES = ('baixa', 'media', 'alta', 'critica')
STATUSES = ('aberta', 'resolvida', 'cancelada')

# Categorias fixas por tipo. Hoje os 3 tipos apontam pra mesma lista de
# proposito -- decisao registrada com o Joao (2026-08): comeca igual pros 3,
# fica facil separar depois (e so trocar o valor de uma chave aqui, sem
# mexer em model/service/rota). Nao trocar por uma lista unica global --
# perderia esse ponto de extensao.
CATEGORIAS_PADRAO = ('Financeiro', 'Documentos', 'UCs', 'Usinas', 'Sistema', 'Mensagens')
CATEGORIAS_POR_TIPO = {
    'pendencia': CATEGORIAS_PADRAO,
    'alerta': CATEGORIAS_PADRAO,
    'erro': CATEGORIAS_PADRAO
}


class Pendencia(TenantMixin, db.Model):
    __tablename__ = 'pendencias'

    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(20), nullable=False, default='pendencia')
    categoria = db.Column(db.String(50), nullable=False)
    origem = db.Column(db.String(50), nullable=False, default='Manual')
    titulo = db.Column(db.String(200), nullable=False)
    descricao = db.Column(db.Text, nullable=True)

    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)
    consumer_unit_id = db.Column(db.Integer, db.ForeignKey('consumer_units.id'), nullable=True)
    plant_id = db.Column(db.Integer, db.ForeignKey('plants.id'), nullable=True)
    document_id = db.Column(db.Integer, db.ForeignKey('documents.id'), nullable=True)

    prazo = db.Column(db.DateTime, nullable=True)
    prioridade = db.Column(db.String(20), nullable=False, default='media')
    responsavel_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    status = db.Column(db.String(20), nullable=False, default='aberta')

    metadados = db.Column(db.JSON, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    resolved_at = db.Column(db.DateTime, nullable=True)

    client = db.relationship('Client')
    consumer_unit = db.relationship('ConsumerUnit')
    plant = db.relationship('Plant')
    document = db.relationship('Document')
    responsavel = db.relationship('User')
    comentarios = db.relationship(
        'PendenciaComentario',
        back_populates='pendencia',
        cascade='all, delete-orphan',
        order_by='PendenciaComentario.created_at'
    )

    def to_dict(self) -> dict:
        # A FK histórica pode ter sido gravada antes da validação de tenant no
        # service. Nunca exponha email/ID de responsável de outra empresa.
        responsavel_compativel = (
            self.responsavel
            if self.responsavel and self.responsavel.empresa_id == self.empresa_id
            else None
        )
        return {
            'id': self.id,
            'tipo': self.tipo,
            'categoria': self.categoria,
            'origem': self.origem,
            'titulo': self.titulo,
            'descricao': self.descricao,
            'clienteId': self.client_id,
            'clienteNome': self.client.nome if self.client else None,
            'ucId': self.consumer_unit_id,
            'ucCodigo': self.consumer_unit.codigo if self.consumer_unit else None,
            'usinaId': self.plant_id,
            'usinaNome': self.plant.nome if self.plant else None,
            'documentoId': self.document_id,
            'documentoNome': self.document.nome if self.document else None,
            'prazo': self.prazo.isoformat() if self.prazo else None,
            'prioridade': self.prioridade,
            'responsavelId': responsavel_compativel.id if responsavel_compativel else None,
            'responsavelNome': responsavel_compativel.email if responsavel_compativel else None,
            'status': self.status,
            'metadados': self.metadados,
            'criadoEm': self.created_at.isoformat() if self.created_at else None,
            'atualizadoEm': self.updated_at.isoformat() if self.updated_at else None,
            'resolvidoEm': self.resolved_at.isoformat() if self.resolved_at else None,
            'comentarios': [comentario.to_dict() for comentario in self.comentarios]
        }


class PendenciaComentario(TenantMixin, db.Model):
    __tablename__ = 'pendencia_comentarios'

    id = db.Column(db.Integer, primary_key=True)
    pendencia_id = db.Column(db.Integer, db.ForeignKey('pendencias.id'), nullable=False)
    autor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    texto = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    pendencia = db.relationship('Pendencia', back_populates='comentarios')
    autor = db.relationship('User')

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'pendenciaId': self.pendencia_id,
            'autorId': self.autor_id,
            'autorNome': self.autor.email if self.autor else None,
            'texto': self.texto,
            'criadoEm': self.created_at.isoformat() if self.created_at else None
        }
