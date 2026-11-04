"""criar_pedido: abre checkout de assinatura de plano (pedido pendente + ASAAS)."""
import secrets

from extensions import db
from models.pedido_plano import PedidoPlano
from planos.catalogo import PLANOS, get_plano
from services.asaas_client import PlatformAsaasService


def _asaas_transport():
    return PlatformAsaasService()


def criar_pedido(email: str, plano_chave: str, dados_pagamento: dict) -> dict:
    if plano_chave not in PLANOS or not PLANOS[plano_chave]['comprável']:
        raise ValueError('Plano inexistente ou nao comercializavel.')
    plano = get_plano(plano_chave)

    external_reference = 'hub-platform-pedido-' + secrets.token_urlsafe(16)
    pedido = PedidoPlano(email=email, plano_chave=plano_chave, external_reference=external_reference)
    db.session.add(pedido)
    db.session.flush()

    transport = _asaas_transport()
    try:
        cliente = transport.criar_cliente(dados_pagamento)
        assinatura = transport.criar_assinatura({
            'customer': cliente['id'],
            'value': float(plano['preco']),
            'cycle': 'MONTHLY',
            'externalReference': external_reference,
        })
    except Exception:
        db.session.rollback()
        raise

    pedido.asaas_customer_id = cliente['id']
    pedido.asaas_subscription_id = assinatura['id']
    db.session.commit()

    return {
        'id': pedido.id,
        'email': pedido.email,
        'planoChave': pedido.plano_chave,
        'externalReference': pedido.external_reference,
        'asaasCustomerId': pedido.asaas_customer_id,
        'asaasSubscriptionId': pedido.asaas_subscription_id,
        'status': pedido.status,
    }
