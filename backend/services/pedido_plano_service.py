"""criar_pedido: abre checkout de assinatura de plano (pedido pendente + ASAAS)."""
import hashlib
import secrets
from datetime import datetime, timedelta

from config import Config
from extensions import db
from models.pedido_plano import PedidoPlano
from planos.catalogo import PLANOS, get_plano
from services.asaas_client import PlatformAsaasService
from services.email_service import send_email
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


def _gerar_token() -> tuple[str, str]:
    token_cru = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token_cru.encode()).hexdigest()
    return token_cru, token_hash


def confirmar_pagamento(external_reference: str) -> None:
    """Chamado pelo webhook da Asaas quando PAYMENT_CONFIRMED. Idempotente:
    replay do mesmo evento (ou qualquer chamada apos o pedido ja ter saido
    de 'pendente') e no-op -- nao gera segundo token nem reenvia e-mail."""
    pedido = PedidoPlano.query.filter_by(external_reference=external_reference).first()
    if not pedido or pedido.status != 'pendente':
        return

    token_cru, token_hash = _gerar_token()
    enviado = _enviar_email_pagamento_confirmado(pedido, token_cru)
    if not enviado:
        # send_email ja logou o erro (email_failed); nao persiste pago/token_hash
        # aqui -- pedido fica 'pendente' pra um proximo webhook (redelivery da Asaas)
        # tentar de novo, em vez de ficar travado pelo guard de idempotencia pra sempre.
        db.session.rollback()
        return

    pedido.token_hash = token_hash
    pedido.status = 'pago'
    pedido.expires_at = datetime.utcnow() + timedelta(days=7)
    db.session.commit()


def _enviar_email_pagamento_confirmado(pedido: PedidoPlano, token_cru: str) -> bool:
    """Sem Empresa criada ainda nesse ponto do fluxo (e o proprio objetivo do
    cadastro), entao nao ha empresa_id pra usar email_template_service --
    e-mail direto com assunto/corpo fixos, igual send_email() ja suporta."""
    link = f'{Config.FRONTEND_URL}/cadastro-empresa?token={token_cru}'
    html = (
        f'<p>Seu pagamento foi confirmado!</p>'
        f'<p>Finalize o cadastro da sua empresa clicando no link abaixo:</p>'
        f'<p><a href="{link}">{link}</a></p>'
        f'<p>Este link expira em 7 dias.</p>'
    )
    text = (
        'Seu pagamento foi confirmado!\n\n'
        f'Finalize o cadastro da sua empresa acessando: {link}\n\n'
        'Este link expira em 7 dias.'
    )
    return send_email(to=pedido.email, subject='Pagamento confirmado -- finalize seu cadastro', html=html, text=text)
