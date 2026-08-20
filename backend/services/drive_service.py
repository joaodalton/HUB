import io
import zipfile

from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials as OAuthCredentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

from config import Config
from utils.files import safe_filename, unique_filename


class GoogleDriveService:
    def __init__(self, credentials) -> None:
        self.client = build('drive', 'v3', credentials=credentials)

    # Lista fechada de proposito -- ainda e um whitelist, so mais largo que so PDF/pasta,
    # pra alimentar o filtro dinamico de "Tipo de arquivo" no frontend com algo real.
    _SEARCHABLE_MIME_TYPES = [
        'application/pdf',
        'application/vnd.google-apps.folder',
        'image/jpeg',
        'image/png',
        'application/vnd.google-apps.document',
        'application/vnd.google-apps.spreadsheet'
    ]

    def search_files(self, query_text: str) -> list[dict]:
        # Mesmo escape ja usado em find_duplicate() deste arquivo -- sem isso,
        # buscar por termo com apostrofo (ex.: "O'Brien") quebra a sintaxe da
        # query do Drive (erro 400 da API do Google, sem tratamento especifico
        # em drive_routes.py -- vira 500 cru pro usuario).
        escaped_query_text = query_text.replace("'", "\\'")
        mime_filter = ' or '.join(f"mimeType='{mime}'" for mime in self._SEARCHABLE_MIME_TYPES)
        query = (
            f"name contains '{escaped_query_text}' "
            f"and ({mime_filter}) "
            f"and trashed=false"
        )

        results = self.client.files().list(
            q=query,
            fields="files(id, name, mimeType, webViewLink, iconLink, modifiedTime)",
            pageSize=50
        ).execute()

        return results.get('files', [])

    def create_reserved_zip(self, file_ids: list[str]) -> io.BytesIO:
        zip_buffer = io.BytesIO()
        used_names: set[str] = set()
        skipped: list[str] = []

        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for file_id in file_ids:
                metadata = self.client.files().get(
                    fileId=file_id,
                    fields="id, name, mimeType"
                ).execute()

                if metadata.get('mimeType') == 'application/vnd.google-apps.folder':
                    skipped.append(metadata.get('name', file_id))
                    continue

                file_buffer = io.BytesIO()
                request_media = self.client.files().get_media(fileId=file_id)
                downloader = MediaIoBaseDownload(file_buffer, request_media)

                done = False
                while not done:
                    _, done = downloader.next_chunk()

                filename = unique_filename(safe_filename(metadata.get('name', file_id)), used_names)
                zip_file.writestr(filename, file_buffer.getvalue())

            if skipped:
                zip_file.writestr(
                    'pastas-nao-baixadas.txt',
                    'Estas pastas foram reservadas, mas nao entram no ZIP automaticamente:\n'
                    + '\n'.join(skipped)
                )

        zip_buffer.seek(0)
        return zip_buffer

    def find_duplicate(self, name: str, md5: str, parent_folder_id: str | None) -> str | None:
        """Procura, dentro da pasta configurada, um arquivo com o MESMO nome E o
        MESMO conteudo (md5Checksum) do que esta prestes a ser enviado. So o nome
        bater nao e suficiente pra considerar duplicata -- dois arquivos diferentes
        podem ter o mesmo nome por coincidencia; o md5 e quem garante que e
        realmente o mesmo arquivo. Retorna o fileId existente, ou None se nao achar."""
        escaped_name = name.replace("'", "\\'")
        query = f"name = '{escaped_name}' and trashed=false"
        if parent_folder_id:
            query += f" and '{parent_folder_id}' in parents"

        results = self.client.files().list(
            q=query,
            fields="files(id, name, md5Checksum)",
            pageSize=10
        ).execute()

        for candidate in results.get('files', []):
            if candidate.get('md5Checksum') == md5:
                return candidate['id']

        return None

    def upload_file(self, file_bytes: bytes, name: str, mime_type: str | None, parent_folder_id: str | None) -> str:
        """Envia o arquivo de verdade pro Drive (nao e link, e copia real). Usada
        pelo upload de Documento -- substitui o disco local, que some a cada
        deploy no Render (filesystem efemero)."""
        metadata: dict = {'name': name}
        if parent_folder_id:
            metadata['parents'] = [parent_folder_id]

        media = MediaIoBaseUpload(
            io.BytesIO(file_bytes),
            mimetype=mime_type or 'application/octet-stream',
            resumable=False
        )

        created = self.client.files().create(
            body=metadata,
            media_body=media,
            fields='id'
        ).execute()

        return created['id']


_drive_service_cache: GoogleDriveService | None = None


def _build_oauth_credentials():
    """Credenciais da conta Google conectada via OAuth (a marcada is_active=True).
    Retorna None se nao houver conta conectada ou se o token nao puder ser renovado
    -- nesses casos get_drive_service() cai pro credentials.json de service account,
    em vez de derrubar a rota."""
    from models.google_account import GoogleAccount  # import tardio: evita ciclo no app factory
    from services.log_service import LogService

    account = GoogleAccount.query.filter_by(is_active=True).first()
    if not account:
        return None

    refresh_token = account.get_refresh_token()
    if not refresh_token:
        return None

    credentials = OAuthCredentials(
        token=None,
        refresh_token=refresh_token,
        token_uri='https://oauth2.googleapis.com/token',
        client_id=Config.GOOGLE_OAUTH_CLIENT_ID,
        client_secret=Config.GOOGLE_OAUTH_CLIENT_SECRET,
        scopes=Config.GOOGLE_DRIVE_SCOPES
    )

    try:
        credentials.refresh(GoogleAuthRequest())
    except Exception as exc:  # RefreshError (token revogado/expirado) ou falha de rede -- nunca derruba a rota
        LogService.warning(
            acao='oauth_refresh_failed',
            mensagem=f'Token da conta {account.email} nao renovou (revogacao/expiracao ou rede fora do ar). Reconecte em Configuracoes se persistir.',
            entidade='GoogleAccount',
            metadados={'id': account.id, 'erro': str(exc)}
        )
        return None

    return credentials


def _build_service_account_credentials():
    # Le o caminho do credentials.json direto do .env a cada chamada (nao de Config, que so foi lido uma vez quando o processo subiu) -- assim uma credencial trocada pela tela de Configuracoes vale na hora, sem reiniciar.
    from services.database_config_service import resolve_google_credentials_path  # import tardio: evita ciclo

    return service_account.Credentials.from_service_account_file(
        str(resolve_google_credentials_path()),
        scopes=Config.GOOGLE_DRIVE_SCOPES
    )


def get_drive_service() -> GoogleDriveService:
    """Prefere a conta OAuth ativa (multi-conta, sem precisar compartilhar pasta
    manualmente); cai pro credentials.json de service account se nao houver
    conta conectada ou o token dela estiver morto."""
    global _drive_service_cache

    if _drive_service_cache is not None:
        return _drive_service_cache

    credentials = _build_oauth_credentials()

    if credentials is None:
        credentials = _build_service_account_credentials()

    _drive_service_cache = GoogleDriveService(credentials)
    return _drive_service_cache


def invalidate_drive_cache() -> None:
    """Chamado pelo oauth_service ao conectar/ativar/desconectar uma conta, pra
    forcar o proximo get_drive_service() a reconstruir com a credencial certa."""
    global _drive_service_cache
    _drive_service_cache = None