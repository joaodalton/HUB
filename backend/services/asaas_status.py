# backend/services/asaas_status.py
"""Mapa unico status ASAAS -> status interno da fatura.

Antes existiam dois mapas divergentes (fatura_service.STATUS_MAP sem
RECEIVED_IN_CASH; asaas_webhook_service.STATUS sem CANCELLED/DELETED): a mesma
cobranca podia receber status diferente conforme viesse da sincronizacao ou do
webhook. Qualquer status novo da ASAAS entra aqui, e so aqui.
"""
ASAAS_STATUS_MAP = {
    'PENDING': 'pending',
    'RECEIVED': 'received',
    'CONFIRMED': 'received',
    'RECEIVED_IN_CASH': 'received',
    'OVERDUE': 'overdue',
    'CANCELLED': 'canceled',
    'DELETED': 'canceled',
    'REFUNDED': 'refunded',
}
