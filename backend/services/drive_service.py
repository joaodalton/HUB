import io
import zipfile

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

from config import Config
from utils.files import safe_filename, unique_filename


class GoogleDriveService:
    def __init__(self) -> None:
        credentials = service_account.Credentials.from_service_account_file(
            Config.GOOGLE_SERVICE_ACCOUNT_FILE,
            scopes=Config.GOOGLE_DRIVE_SCOPES
        )
        self.client = build('drive', 'v3', credentials=credentials)

    def search_files(self, query_text: str) -> list[dict]:
        query = (
            f"name contains '{query_text}' "
            f"and (mimeType='application/pdf' or mimeType='application/vnd.google-apps.folder') "
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


drive_service = None

def get_drive_service():
    global drive_service

    if drive_service is None:
        drive_service = GoogleDriveService()

    return drive_service
