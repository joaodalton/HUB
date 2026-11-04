# backend/models/pedido_plano.py
from datetime import datetime

from extensions import db

STATUSES = ('pendente', 'pago', 'usado', 'expirado')


class PedidoPlano(db.Model):
    __tablename__ = 'pedidos_plano'

    # SEM TenantMixin -- o checkout de assinatura de plano e publico e roda
    # antes de existir empresa/usuario autenticado, entao g.current_empresa_id
    # nao existe nesse ponto. Mesma linha do Invitation.
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), nullable=False)
    plano_chave = db.Column(db.String(30), nullable=False)
    external_reference = db.Column(db.String(120), nullable=False, unique=True)
    asaas_customer_id = db.Column(db.String(64), nullable=True)
    asaas_subscription_id = db.Column(db.String(64), nullable=True)
    token_hash = db.Column(db.String(64), nullable=True, unique=True)
    expires_at = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), nullable=False, default='pendente')

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
