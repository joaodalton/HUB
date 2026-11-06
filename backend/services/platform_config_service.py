"""Leitura de configuracao global da plataforma com fallback pra env var.

A tabela platform_configuracoes (editavel via /platform/configuracao, admin
only) tem prioridade; quando um campo esta vazio/None, cai pro Config.* lido
do .env -- preserva deploys existentes que nunca usaram a UI.
"""
from config import Config
from models.platform_configuracao import PlatformConfiguracao


def get_platform_asaas_credentials() -> dict:
    config = PlatformConfiguracao.get_or_create()
    return {
        'base_url': config.asaas_api_base_url or Config.PLATFORM_ASAAS_API_BASE_URL,
        'api_key': config.get_asaas_api_key() or Config.PLATFORM_ASAAS_API_KEY,
        'webhook_token': config.get_asaas_webhook_token() or Config.PLATFORM_ASAAS_WEBHOOK_TOKEN,
    }


def get_signup_config() -> dict:
    config = PlatformConfiguracao.get_or_create()
    return {
        'code': config.get_signup_code() or Config.SIGNUP_CODE,
        'empresa_id': config.signup_empresa_id if config.signup_empresa_id is not None else Config.SIGNUP_EMPRESA_ID,
    }
