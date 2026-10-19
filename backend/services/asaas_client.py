"""ASAAS transport and isolated tenant/platform credential adapters."""
from decimal import Decimal
from urllib.parse import urlparse

import requests

from config import Config
from models.api_credential import ApiCredential


class AsaasError(RuntimeError):
    pass


def ambiente_asaas(base_url=None):
    parsed = urlparse(Config.ASAAS_API_BASE_URL if base_url is None else base_url)
    try:
        invalid_port = parsed.port is not None
    except ValueError:
        invalid_port = True
    if (parsed.scheme != 'https' or parsed.username or parsed.password or invalid_port
            or parsed.query or parsed.fragment or parsed.path.rstrip('/') != '/v3'):
        raise AsaasError('Ambiente ASAAS nao reconhecido.')
    host = parsed.hostname
    if host == 'api-sandbox.asaas.com':
        return 'sandbox'
    if host in ('api.asaas.com', 'www.asaas.com'):
        return 'producao'
    raise AsaasError('Ambiente ASAAS nao reconhecido.')


class AsaasTransport:
    """HTTP only; the caller supplies an endpoint and API key."""

    def __init__(self, base_url: str, api_key: str):
        ambiente_asaas(base_url)
        if not api_key:
            raise AsaasError('Credencial ASAAS nao configurada.')
        self._base_url = base_url.rstrip('/')
        self._headers = {'access_token': api_key, 'Content-Type': 'application/json', 'User-Agent': 'HUB/1.0'}

    def testar_conexao(self) -> None:
        self._request('GET', '/myAccount')

    def criar_cliente(self, data: dict) -> dict:
        return self._request('POST', '/customers', data)

    def criar_cobranca(self, data: dict) -> dict:
        return self._request('POST', '/payments', data)

    def consultar_cobranca(self, asaas_id: str) -> dict:
        return self._request('GET', f'/payments/{asaas_id}')

    def consultar_por_referencia(self, external_reference: str) -> dict | None:
        result = self._request('GET', '/payments', params={
            'externalReference': external_reference, 'limit': 2, 'offset': 0,
        })
        rows = result.get('data')
        if (not isinstance(rows, list) or result.get('hasMore') is not False
                or len(rows) > 1 or any(not isinstance(row, dict)
                or row.get('externalReference') != external_reference for row in rows)):
            raise AsaasError('Resposta de conciliacao ASAAS ambigua ou invalida.')
        return rows[0] if rows else None

    def cancelar_cobranca(self, asaas_id: str) -> dict:
        return self._request('DELETE', f'/payments/{asaas_id}')

    def _request(self, method: str, path: str, payload: dict | None = None, *, params=None) -> dict:
        try:
            options = {'params': params} if params is not None else {}
            response = requests.request(method, f'{self._base_url}{path}', headers=self._headers,
                json=payload, timeout=20, allow_redirects=False, **options)
        except requests.RequestException as exc:
            raise AsaasError('Nao foi possivel comunicar com o ASAAS.') from exc
        if not response.ok:
            # External payloads may contain secrets or personal data.
            raise AsaasError('ASAAS recusou a operacao.')
        try:
            result = response.json()
        except ValueError as exc:
            raise AsaasError('Resposta ASAAS invalida; resultado da operacao desconhecido.') from exc
        if not isinstance(result, dict):
            raise AsaasError('Resposta ASAAS invalida; resultado da operacao desconhecido.')
        return result


class AsaasClient(AsaasTransport):
    """Existing tenant interface used by B0-B3 billing consumers."""

    def __init__(self, empresa_id: int):
        credentials = ApiCredential.query.filter_by(empresa_id=empresa_id, provider='asaas', interna=False)
        credential = credentials.filter_by(nome=f'api_key_{ambiente_asaas()}').first()
        if not credential:
            # Preserve legacy free names without crossing environments or using webhook tokens.
            credential = credentials.filter(
                ~ApiCredential.nome.startswith('webhook_token', autoescape=True),
                ~ApiCredential.nome.startswith('api_key_', autoescape=True),
            ).order_by(ApiCredential.id).first()
        if not credential:
            raise AsaasError('Credencial ASAAS nao configurada para esta empresa.')
        super().__init__(Config.ASAAS_API_BASE_URL, credential.get_segredo())


class PlatformAsaasService(AsaasTransport):
    """Platform gateway; never resolves an ApiCredential from a tenant."""

    def __init__(self):
        super().__init__(Config.PLATFORM_ASAAS_API_BASE_URL, Config.PLATFORM_ASAAS_API_KEY)


def customer_payload(client) -> dict:
    payload = {'name': client.nome, 'cpfCnpj': client.cpf}
    if client.email:
        payload['email'] = client.email
    if client.telefone:
        payload['mobilePhone'] = client.telefone
    return payload


def payment_payload(customer_id: str, value: Decimal, due_date, external_reference: str) -> dict:
    return {
        'customer': customer_id,
        'billingType': 'BOLETO',
        'value': float(value),
        'dueDate': due_date.isoformat(),
        'externalReference': external_reference,
    }
