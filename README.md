# APP HUB - Central de documentos

Busca arquivos no Google Drive, permite reservar documentos e baixar os arquivos selecionados em ZIP.

## Como rodar

### 1. Backend Python

```bash
cd backend
venv\Scripts\python.exe app.py
```

Se ainda nao tiver criado o ambiente virtual:

```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

O backend roda em:

```text
http://localhost:8000
```

### 2. Frontend TypeScript

Instale o Node.js antes de rodar o frontend.

Na primeira vez:

```bash
cd frontend
npm install
npm run dev
```

Depois, no dia a dia:

```bash
cd frontend
npm run dev
```

O frontend roda em:

```text
http://127.0.0.1:5173
```

## Importante

Coloque seu `credentials.json` da Service Account dentro da pasta `backend/`.
Esse arquivo NAO deve ser enviado ao GitHub.
