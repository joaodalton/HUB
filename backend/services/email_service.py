# backend/services/email_service.py
"""
Envio de e-mails transacionais via Resend. Sem RESEND_API_KEY configurada,
send_email() vira no-op (so loga warning) -- mesmo espirito do sentry_sdk.init
sem DSN e do drive_service sem credentials.json: nunca derruba a rota por
falta de configuracao.

Uso:
    from services.email_service import send_email
    send_email(to='cliente@exemplo.com', subject='...', html='...', text='...')
"""
import resend

from config import Config
from services.log_service import LogService

_configured = False


def _ensure_configured() -> bool:
    global _configured

    if not Config.RESEND_API_KEY:
        return False

    if not _configured:
        resend.api_key = Config.RESEND_API_KEY
        _configured = True

    return True


def _mensagem_amigavel_envio(exc: Exception) -> str:
    """Traduz falha do provedor de e-mail pra algo que a empresa entenda e
    possa agir sobre, sem citar nome/URL de configuracao de fornecedor --
    isso e detalhe de infraestrutura da plataforma, nao da empresa-tenant.
    O detalhe tecnico bruto continua disponivel em metadados pra debug."""
    texto = str(exc).lower()
    if 'rate limit' in texto or '429' in texto:
        return 'muitos e-mails enviados em um curto periodo -- tente novamente em alguns minutos'
    if 'domain' in texto or ('from' in texto and 'address' in texto) or 'api key' in texto or 'unauthorized' in texto:
        return 'o servico de envio de e-mail nao esta configurado corretamente -- contate o suporte'
    return 'entre em contato com o suporte caso o problema persista'


def send_email(to: str, subject: str, html: str, text: str | None = None) -> bool:
    """Retorna True se a tentativa de envio foi feita, False se RESEND_API_KEY
    nao esta configurada (no-op silencioso pro chamador, so loga warning)."""
    if not _ensure_configured():
        LogService.warning(
            acao='email_not_configured',
            mensagem=f'O servico de envio de e-mail nao esta configurado -- e-mail para {to} ("{subject}") nao foi enviado.',
            entidade='Email',
            metadados={'motivo': 'RESEND_API_KEY ausente'}
        )
        return False

    params: dict = {
        'from': Config.EMAIL_FROM,
        'to': [to],
        'subject': subject,
        'html': html
    }
    if text:
        params['text'] = text

    try:
        resend.Emails.send(params)
        LogService.info(acao='email_sent', mensagem=f'E-mail "{subject}" enviado para {to}', entidade='Email')
        return True
    except Exception as exc:
        LogService.error(
            acao='email_failed',
            mensagem=f'Falha ao enviar e-mail "{subject}" para {to}: {_mensagem_amigavel_envio(exc)}.',
            entidade='Email',
            metadados={'erro': str(exc)}
        )
        return False
