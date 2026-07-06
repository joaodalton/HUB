import io
import re
import zipfile

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from google.oauth2 import service_account
from googleapiclient.http import MediaIoBaseDownload
from googleapiclient.discovery import build

app = Flask(__name__)
CORS(app)  # permite o frontend acessar o backend sem bloqueio

# ---- Configuração do Google Drive ----
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
SERVICE_ACCOUNT_FILE = 'credentials.json'

credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES
)
drive_service = build('drive', 'v3', credentials=credentials)


def safe_filename(name):
    name = re.sub(r'[<>:"/\\|?*]', '_', name)
    return name.strip() or 'arquivo'


def unique_filename(name, used_names):
    if name not in used_names:
        used_names.add(name)
        return name

    base, dot, ext = name.rpartition('.')
    if not dot:
        base = name
        ext = ''

    counter = 2
    while True:
        candidate = f"{base} ({counter})"
        if ext:
            candidate = f"{candidate}.{ext}"

        if candidate not in used_names:
            used_names.add(candidate)
            return candidate

        counter += 1


# ---- Rota de busca ----
@app.route('/search')
def search():
    query_text = request.args.get('q', '')

    q = (
        f"name contains '{query_text}' "
        f"and (mimeType='application/pdf' or mimeType='application/vnd.google-apps.folder') "
        f"and trashed=false"
    )

    results = drive_service.files().list(
        q=q,
        fields="files(id, name, mimeType, webViewLink, iconLink, modifiedTime)",
        pageSize=50
    ).execute()

    return jsonify(results.get('files', []))


# ---- Baixa varios arquivos reservados em um ZIP ----
@app.route('/download-zip', methods=['POST'])
def download_zip():
    data = request.get_json(silent=True) or {}
    file_ids = data.get('ids', [])

    if not file_ids:
        return jsonify({"error": "Nenhum arquivo informado."}), 400

    zip_buffer = io.BytesIO()
    used_names = set()
    skipped = []

    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for file_id in file_ids:
            metadata = drive_service.files().get(
                fileId=file_id,
                fields="id, name, mimeType"
            ).execute()

            if metadata.get('mimeType') == 'application/vnd.google-apps.folder':
                skipped.append(metadata.get('name', file_id))
                continue

            file_buffer = io.BytesIO()
            request_media = drive_service.files().get_media(fileId=file_id)
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

    return send_file(
        zip_buffer,
        mimetype='application/zip',
        as_attachment=True,
        download_name='hub-reservados.zip'
    )


# ---- Rota inicial (teste) ----
@app.route('/')
def home():
    return {"status": "Servidor rodando com sucesso!"}


if __name__ == '__main__':
    app.run(port=8000, debug=True)
