"""Cliente mínimo do ASAAS; cada instância usa a chave cifrada de uma empresa."""
from decimal import Decimal

import requests

from config import Config
from models.api_credential import ApiCredential


class AsaasError(RuntimeError):
    pass


class AsaasClient:
    def __init__(self, empresa_id: int):
        credential = ApiCredential.query.filter_by(empresa_id=empresa_id, provider='asaas').order_by(ApiCredential.id).first()
        if not credential:
            raise AsaasError('Credencial ASAAS não configurada para esta empresa.')
        self._headers = {'access_token': credential.get_segredo(), 'Content-Type': 'application/json'}

    def criar_cliente(self, data: dict) -> dict:
        return self._request('POST', '/customers', data)

    def criar_cobranca(self, data: dict) -> dict:
        return self._request('POST', '/payments', data)

    def consultar_cobranca(self, asaas_id: str) -> dict:
        return self._request('GET', f'/payments/{asaas_id}')

    def cancelar_cobranca(self, asaas_id: str) -> dict:
        return self._request('DELETE', f'/payments/{asaas_id}')

    def _request(self, method: str, path: str, payload: dict | None = None) -> dict:
        try:
            response = requests.request(method, f'{Config.ASAAS_API_BASE_URL.rstrip("/")}{path}', headers=self._headers, json=payload, timeout=20)
        except requests.RequestException as exc:
            raise AsaasError('Não foi possível comunicar com o ASAAS.') from exc
        if not response.ok:
            try:
                message = response.json().get('errors', [{}])[0].get('description')
            except ValueError:
                message = None
            raise AsaasError(message or 'ASAAS recusou a operação.')
        return response.json()


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
