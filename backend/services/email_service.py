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


def send_email(to: str, subject: str, html: str, text: str | None = None) -> bool:
    """Retorna True se a tentativa de envio foi feita, False se RESEND_API_KEY
    nao esta configurada (no-op silencioso pro chamador, so loga warning)."""
    if not _ensure_configured():
        LogService.warning(
            acao='email_not_configured',
            mensagem=f'RESEND_API_KEY nao configurada -- e-mail para {to} ("{subject}") nao foi enviado.',
            entidade='Email'
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
            mensagem=f'Falha ao enviar e-mail "{subject}" para {to}: {exc}',
            entidade='Email'
        )
        return False