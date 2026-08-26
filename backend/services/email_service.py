# backend/services/email_service.py
"""
Decide O QUE mandar e QUANDO -- a chamada de fato pro provedor vive em
integrations/resend_client.py. Sem RESEND_API_KEY configurada, send_email()
vira no-op (só loga warning) -- mesmo espírito do sentry_sdk.init sem DSN e
do drive_service sem credentials.json: nunca derruba a rota por falta de
configuração.

Uso:
    from services.email_service import send_email
    send_email(to='cliente@exemplo.com', subject='...', html='...', text='...')
"""
from integrations import resend_client
from services.log_service import LogService


def send_email(to: str, subject: str, html: str, text: str | None = None) -> bool:
    """Retorna True se a tentativa de envio foi feita, False se RESEND_API_KEY
    não está configurada (no-op silencioso pro chamador, só loga warning)."""
    if not resend_client.is_configured():
        LogService.warning(
            acao='email_not_configured',
            mensagem=f'RESEND_API_KEY nao configurada -- e-mail para {to} ("{subject}") nao foi enviado.',
            entidade='Email'
        )
        return False

    try:
        resend_client.send(to=to, subject=subject, html=html, text=text)
        LogService.info(acao='email_sent', mensagem=f'E-mail "{subject}" enviado para {to}', entidade='Email')
        return True
    except Exception as exc:
        LogService.error(
            acao='email_failed',
            mensagem=f'Falha ao enviar e-mail "{subject}" para {to}: {exc}',
            entidade='Email'
        )
        return False
