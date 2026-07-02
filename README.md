# Buscador de arquivos no Google Drive

## Como rodar

### 1. Backend
```bash
cd backend
python -m venv venv
venv\Scripts\activate   # Windows
pip install -r requirements.txt
python app.py
```

### 2. Frontend
Abra `frontend/index.html` no navegador (ou use Live Server no VS Code).

## Importante
Coloque seu `credentials.json` da Service Account dentro da pasta `backend/`.
Esse arquivo NÃO deve ser enviado ao GitHub.