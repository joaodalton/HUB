# backend/integrations/resend_client.py
"""
Cliente cru do Resend -- só sabe "conversar com a API do Resend": autenticar,
formatar o request, tratar erro específico do provedor. NÃO decide o que
mandar nem quando (isso é papel de services/email_service.py). Trocar de
provedor de e-mail um dia = trocar este arquivo, sem tocar em nenhum service.
"""
import resend

from config import Config

_configured = False


def is_configured() -> bool:
    return bool(Config.RESEND_API_KEY)


def _ensure_configured() -> None:
    global _configured

    if not _configured:
        resend.api_key = Config.RESEND_API_KEY
        _configured = True


def send(to: str, subject: str, html: str, text: str | None = None) -> None:
    """Lança exceção em caso de falha -- quem chama (email_service.py) decide
    como tratar/logar. Não verifica is_configured() aqui, isso é
    responsabilidade de quem chama (mesmo padrão de find_drive_service())."""
    _ensure_configured()

    params: dict = {
        'from': Config.EMAIL_FROM,
        'to': [to],
        'subject': subject,
        'html': html
    }
    if text:
        params['text'] = text

    resend.Emails.send(params)
