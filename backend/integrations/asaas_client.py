# backend/integrations/asaas_client.py
"""
Cliente cru do ASAAS (asaas.com) -- só sabe "conversar com a API do ASAAS":
autenticar (header access_token), formatar o request, tratar erro específico
do provedor. NÃO decide quando cobrar, de quem, nem guarda nada no banco do
HUB (isso é papel de um service de domínio, ainda a ser desenhado -- ver
Issue "Modelo de cobrança ASAAS").

Documentação oficial: https://docs.asaas.com/reference

Ambientes:
  sandbox    -> https://sandbox.asaas.com/api/v3 (dados fictícios, sem cobrança real)
  production -> https://api.asaas.com/v3
"""
import requests

from config import Config

_BASE_URLS = {
    'sandbox': 'https://sandbox.asaas.com/api/v3',
    'production': 'https://api.asaas.com/v3'
}


class AsaasError(Exception):
    """Erro retornado pela API do ASAAS (4xx/5xx) -- guarda o payload de erro
    original pra quem chamar decider como tratar/exibir."""

    def __init__(self, status_code: int, payload: dict | None = None, message: str | None = None):
        self.status_code = status_code
        self.payload = payload or {}
        mensagens = [
            erro.get('description', str(erro))
            for erro in self.payload.get('errors', [])
        ] or [message or str(self.payload)]
        super().__init__(f'ASAAS [{status_code}]: {"; ".join(mensagens)}')


def is_configured() -> bool:
    return bool(Config.ASAAS_API_KEY)


def _base_url() -> str:
    return _BASE_URLS.get(Config.ASAAS_ENV, _BASE_URLS['sandbox'])


def _headers() -> dict:
    return {
        'access_token': Config.ASAAS_API_KEY,
        'Content-Type': 'application/json'
    }


def _request(method: str, path: str, **kwargs) -> dict:
    try:
        response = requests.request(
            method, f'{_base_url()}{path}',
            headers=_headers(), timeout=15, **kwargs
        )
    except requests.exceptions.RequestException as exc:
        raise AsaasError(0, {}, f'Erro de conexão com ASAAS: {exc}')

    if not response.ok:
        try:
            payload = response.json() if response.content else {}
        except Exception:
            payload = {}
        raise AsaasError(response.status_code, payload)

    return response.json() if response.content else {}


# ---------- Clientes (pessoa física/jurídica cobrada) ----------

def create_customer(
    name: str,
    cpf_cnpj: str,
    email: str | None = None,
    phone: str | None = None,
    external_reference: str | None = None
) -> dict:
    """external_reference -- id do Client/UC no HUB, pra rastrear de volta
    qual registro nosso corresponde a esse cliente no ASAAS."""
    payload: dict = {'name': name, 'cpfCnpj': cpf_cnpj}
    if email:
        payload['email'] = email
    if phone:
        payload['phone'] = phone
    if external_reference:
        payload['externalReference'] = str(external_reference)

    return _request('POST', '/customers', json=payload)


def find_customer_by_reference(external_reference: str) -> dict | None:
    result = _request('GET', '/customers', params={'externalReference': external_reference})
    items = result.get('data', [])
    return items[0] if items else None


# ---------- Cobranças (boleto/pix/cartão) ----------

def create_charge(
    customer_id: str,
    value: float,
    due_date: str,
    description: str | None = None,
    billing_type: str = 'BOLETO',
    external_reference: str | None = None
) -> dict:
    """due_date no formato YYYY-MM-DD. billing_type: BOLETO, PIX, CREDIT_CARD, UNDEFINED
    (UNDEFINED deixa o pagador escolher na página de cobrança do ASAAS)."""
    payload: dict = {
        'customer': customer_id,
        'billingType': billing_type,
        'value': value,
        'dueDate': due_date
    }
    if description:
        payload['description'] = description
    if external_reference:
        payload['externalReference'] = str(external_reference)

    return _request('POST', '/payments', json=payload)


def get_charge(charge_id: str) -> dict:
    return _request('GET', f'/payments/{charge_id}')


def cancel_charge(charge_id: str) -> dict:
    return _request('DELETE', f'/payments/{charge_id}')


def list_charges_by_customer(customer_id: str) -> list[dict]:
    result = _request('GET', '/payments', params={'customer': customer_id})
    return result.get('data', [])
