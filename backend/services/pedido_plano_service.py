"""criar_pedido: abre checkout de assinatura de plano (pedido pendente + ASAAS)."""
import secrets

from extensions import db
from models.pedido_plano import PedidoPlano
from planos.catalogo import PLANOS, get_plano
from services.asaas_client import PlatformAsaasService
from services.log_service import LogService


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

    cliente = None
    try:
        transport = _asaas_transport()
        cliente = transport.criar_cliente(dados_pagamento)
        assinatura = transport.criar_assinatura({
            'customer': cliente['id'],
            'value': float(plano['preco']),
            'cycle': 'MONTHLY',
            'externalReference': external_reference,
        })
    except Exception as exc:
        db.session.rollback()
        if cliente is not None:
            # Cliente ja foi criado na Asaas mas a assinatura falhou: fica orfao la,
            # sem PedidoPlano aqui para linkar -- precisa reconciliacao manual.
            LogService.error(
                acao='asaas_cliente_orfao',
                mensagem=f'Assinatura Asaas falhou apos criar cliente {cliente["id"]}; cliente ficou orfao na Asaas.',
                entidade='PedidoPlano',
                metadados={'asaasCustomerId': cliente['id'], 'externalReference': external_reference, 'erro': str(exc)},
            )
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
