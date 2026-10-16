"""Checagem de scope OAuth e obtencao de credencial pra geracao de relatorios
Google (Docs/Sheets/Slides). Nunca chama a API do Google se o scope concedido
pela conta ativa nao cobrir os 4 scopes de escrita exigidos."""
from models.google_account import GoogleAccount
from services.drive_service import _build_oauth_credentials

REQUIRED_REPORT_SCOPES = [
    'https://www.googleapis.com/auth/drive.file',
    'https://www.googleapis.com/auth/documents',
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/presentations',
]


class ReportAccountMissingError(Exception):
    pass


class ReportScopeError(Exception):
    def __init__(self, missing_scopes: list[str]):
        super().__init__('Conta Google ativa nao tem permissao de escrita suficiente para gerar relatorios.')
        self.missing_scopes = missing_scopes


def get_report_credentials(empresa_id: int):
    account = GoogleAccount.query.filter_by(empresa_id=empresa_id, is_active=True).first()
    if not account:
        raise ReportAccountMissingError('Nenhuma conta Google ativa para esta empresa.')

    granted = set((account.scopes or '').split(','))
    missing = [scope for scope in REQUIRED_REPORT_SCOPES if scope not in granted]
    if missing:
        raise ReportScopeError(missing)

    credentials = _build_oauth_credentials()
    if credentials is None:
        raise ReportAccountMissingError('Token da conta Google ativa nao pode ser renovado.')
    return credentials
