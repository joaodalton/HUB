from flask import Flask, request, jsonify
from flask_cors import CORS
from google.oauth2 import service_account
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


# ---- Rota inicial (teste) ----
@app.route('/')
def home():
    return {"status": "Servidor rodando com sucesso!"}


if __name__ == '__main__':
    app.run(port=8000, debug=True)