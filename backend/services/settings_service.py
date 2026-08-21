# backend/services/settings_service.py
from extensions import db
from models.setting import Setting

# Whitelist explícita de chaves de configuração permitidas.
# Qualquer chave não listada aqui é REJEITADA na atualização (PUT /api/v1/settings).
#
# Motivo de segurança: evitar que um cliente envie chaves arbitrárias que
# possam ser lidas por outras partes do sistema ou que poluam a tabela de
# settings com dados não documentados.
#
# Quando uma nova chave for adicionada ao sistema, ela deve ser incluída aqui
# explicitamente — não basta adicionar ao modelo ou à rota.
SETTINGS_KEYS_WHITELIST = frozenset({
    # === GERAL (configuração da empresa) ===
    'site_name',
    'company_name',
    'company_cnpj',
    'company_email',
    'company_telefone',
    'company_endereco',
    'company_cep',
    'company_cidade',
    'company_state',
    'company_logo_url',
    'company_favicon_url',
    'company_description',

    # === APARÊNCIA (UI/branding) ===
    'primary_color',
    'secondary_color',
    'background_color',
    'text_color',
    'font_family',
    'logo_position',
    'show_company_name',
    'custom_css',

    # === EMAIL ===
    'resend_api_key',
    'email_from',
    'email_reply_to',
    'email_signature',

    # === TAXAS & FINANCEIRO ===
    'taxa_juros',
    'taxa_processamento',
    'moeda',
    'periodicidade_fatura',
    'dia_emissao_fatura',
    'limite_credito_padrao',
    'dias_protesto',

    # === NOTIFICAÇÕES ===
    'notificacoes_ativas',
    'email_notificacoes',
    'sms_notificacoes',

    # === SEGURANÇA ===
    'require_mfa',
    'session_timeout_min',
    'max_login_attempts',
    'password_min_length',
    'allowed_roles',
})


def get_all_settings() -> dict:
    settings = Setting.query.all()
    return {setting.chave: setting.valor for setting in settings}


def _is_key_allowed(chave: str) -> bool:
    """Verifica se a chave está na whitelist de configurações permitidas."""
    return chave in SETTINGS_KEYS_WHITELIST


def update_settings(data: dict) -> dict:
    """
    Atualiza ou cria settings com validação de whitelist.

    Args:
        data: dict de {chave: valor} a serem atualizados

    Returns:
        dict com todos os settings após atualização

    Raises:
        ValueError: se alguma chave não estiver na whitelist
    """
    # Valida todas as chaves antes de fazer qualquer alteração
    invalid_keys = []
    for chave in data.keys():
        if not _is_key_allowed(chave):
            invalid_keys.append(chave)

    if invalid_keys:
        raise ValueError(
            f'Chaves não permitidas: {", ".join(sorted(invalid_keys))}. '
            f'Lista de chaves válidas: {sorted(SETTINGS_KEYS_WHITELIST)}'
        )

    # Todas as chaves são válidas — procede com a atualização
    for chave, valor in data.items():
        setting = Setting.query.filter_by(chave=chave).first()

        if setting:
            setting.valor = valor
        else:
            setting = Setting(chave=chave, valor=valor)
            db.session.add(setting)

    db.session.commit()
    return get_all_settings()
