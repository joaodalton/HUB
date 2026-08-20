# APP HUB — Deploy e Infraestrutura

> Registro de como o HUB foi tirado do "só roda no meu PC" pra "roda na nuvem, 24h". Leia isso antes de mexer em qualquer coisa relacionada a banco, deploy ou variável de ambiente — economiza reconstruir o raciocínio do zero.
> **Documentos relacionados:** [[ARCHITECTURE]] · [[VISAO]] · [[PROGRESS]]
> Complementa `VISAO.md` (norte do produto) e `PROGRESS.md` (histórico de tarefas). Este arquivo é especificamente sobre **infraestrutura**.

---

## 1. Visão geral da arquitetura em produção

```text
Usuário
  │
  ▼
Frontend (Render Static Site)
  │  VITE_API_BASE_URL aponta pro backend
  ▼
Backend (Render Web Service, Gunicorn)
  │
  ├──► Postgres de produção (Neon, projeto separado do de dev)
  └──► Google Drive (upload de documento + busca legada)
```

Existem **dois ambientes completamente separados**, cada um com seu próprio banco:

| | Dev (seu PC) | Produção (nuvem) |
|---|---|---|
| Backend | `python hub.py iniciar` | Render Web Service (Gunicorn) |
| Frontend | `localhost:5173` (Vite dev server) | Render Static Site |
| Banco | Neon "dev" | Neon "produção" (projeto separado) |
| `.env` | `backend\.env` local | Variáveis de ambiente no painel do Render |

**Nunca misturar os dois.** Rodar migration ou script contra o banco errado por engano já aconteceu nessa história (ver seção 5) — sempre confirma qual `DATABASE_URL` você tá usando antes de rodar qualquer coisa.

---

## 2. Variáveis de ambiente — de onde vem cada uma

### Backend (Render Web Service → Environment)

| Variável | De onde vem | Observação |
|---|---|---|
| `DATABASE_URL` | Connection string do projeto **Neon de produção** | Painel do Neon, projeto separado do de dev |
| `SECRET_KEY` | Gerada com `python -c "import secrets; print(secrets.token_hex(32))"` | **Diferente** da de dev, gerada especificamente pra produção |
| `SECRET_ENCRYPTION_KEY` | Gerada com `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` | Criptografa o refresh token do Google (`GoogleAccount`). Trocar essa chave invalida qualquer conta Google já conectada — reconectar é esperado, não é bug |
| `FLASK_DEBUG` | `false`, sempre | Nunca `true` em produção — expõe o debugger interativo do Werkzeug |
| `GOOGLE_OAUTH_CLIENT_ID` / `GOOGLE_OAUTH_CLIENT_SECRET` | Google Cloud Console → Credentials → OAuth 2.0 Client ID | **Cuidado ao colar no Render: sem aspas, sem espaço.** O Render não interpreta aspas como o `python-dotenv` faz local — vira parte literal do valor e o Google recusa com `invalid_client` |
| `GOOGLE_OAUTH_REDIRECT_URI` | `https://<domínio-do-backend>.onrender.com/api/v1/oauth/google/callback` | Precisa estar cadastrado como redirect URI autorizado no Google Cloud Console também, senão dá `redirect_uri_mismatch` |
| `GOOGLE_DRIVE_SCOPES` | `https://www.googleapis.com/auth/drive` (acesso completo) | **Não usar `drive.readonly`** — upload de documento (desde a troca pra Drive) precisa de escrita; a busca legada precisa listar arquivo que já existia antes do HUB, o que o escopo restrito `drive.file` não permite |
| `GOOGLE_DRIVE_ROOT_FOLDER_ID` | ID da pasta no Drive (pega da URL) | Opcional — vazio, os documentos vão pra raiz da conta conectada (funciona, só fica bagunçado) |
| `FRONTEND_URL` | URL do frontend publicado no Render | Alimenta CORS (Etapa 4) e o redirect pós-OAuth |

### Frontend (Render Static Site → Environment)

| Variável | Valor |
|---|---|
| `VITE_API_BASE_URL` | URL do backend publicado (ex.: `https://hub-backend-xxxx.onrender.com`) |

🚨 **Só tem efeito no momento do build**, não em runtime — o Vite "queima" o valor dentro do JS compilado. Trocar essa variável exige rodar um build novo (Manual Deploy no Render), reiniciar o serviço sozinho não é suficiente.

---

## 3. Como atualizar o schema do banco (rotina, não é evento único)

Toda vez que um model novo for criado ou alterado:

```powershell
cd backend
# 1. Gera a migration comparando os models atuais com o schema do banco de DEV
venv\Scripts\flask db migrate -m "descricao curta da mudanca"

# 2. ABRE o arquivo gerado em backend\migrations\versions\ antes de rodar.
#    Confere principalmente: coluna nova NOT NULL numa tabela que ja tem dado
#    precisa de server_default, senao quebra. Ja aconteceu nesse projeto.

# 3. Aplica no banco de DEV e testa a funcionalidade local
venv\Scripts\flask db upgrade

# 4. Commit + push (migration e codigo, faz parte do repo)
git add backend/migrations/versions/
git commit -m "..."
git push
```

Depois que o backend em produção fizer redeploy com o código novo, aplica a mesma migration no banco de **produção** — sem editar o `.env` local (evita esquecer de voltar pro banco de dev depois, como já rolou uma vez):

```powershell
cd backend
$env:DATABASE_URL = "postgresql://...string do Neon de PRODUCAO..."
venv\Scripts\flask db upgrade
Remove-Item Env:\DATABASE_URL
```

Isso seta a variável só naquela janela do PowerShell — fechar o terminal (ou rodar o `Remove-Item`) já volta tudo ao normal.

> **Alternativa melhor, se algum dia fizer upgrade de plano no Render:** campo "Pre-Deploy Command" nas configurações do serviço, com `flask db upgrade` — roda sozinho antes de cada deploy, contra a `DATABASE_URL` que já tá nas env vars de produção. É recurso pago no plano atual, por isso ainda fazemos manual.

---

## 4. Como migrar dados do zero (SQLite antigo → Postgres)

Script em `backend/scripts/migrate_sqlite_to_postgres.py` — pontual, só pra quando existir um `hub.db` novo pra trazer (não é rotina, diferente da seção 3).

```powershell
venv\Scripts\python scripts\migrate_sqlite_to_postgres.py                                    # dry-run
venv\Scripts\python scripts\migrate_sqlite_to_postgres.py --apply                             # aplica
venv\Scripts\python scripts\migrate_sqlite_to_postgres.py --apply --include-users              # inclui usuarios
venv\Scripts\python scripts\migrate_sqlite_to_postgres.py --apply --force --only users          # so re-roda 1 tabela
```
Detalhes de cada flag no docstring do próprio arquivo.

---

## 5. Se algo quebrar: rollback

**Backend ou frontend no Render:** dashboard do serviço → aba **Events** → escolhe um deploy anterior que funcionava → **Rollback**. O Render mantém builds anteriores prontos, é praticamente instantâneo.

**Banco de dados:** Neon mantém histórico de pontos no tempo (Point-in-Time Restore) mesmo no plano free, por um período limitado — dá pra restaurar pelo próprio painel do Neon em caso de dado corrompido/apagado por engano. Não depende de backup manual nosso pra esse caso.

**Migration aplicada errada:** `flask db downgrade -1` reverte a última migration (testamos isso funcionar de ponta a ponta, incluindo com `batch_alter_table`, na Etapa 2).

---

## 6. Reconectar Google Drive — quando e por quê

Precisa reconectar a conta Google (Configurações → desconectar → conectar de novo) sempre que:
- `SECRET_ENCRYPTION_KEY` mudar (o refresh token salvo fica ilegível com a chave nova)
- `GOOGLE_DRIVE_SCOPES` mudar pra um escopo mais amplo (o token antigo foi autorizado só com o escopo de antes — Google não amplia sozinho)

Sintoma de token quebrado: erro 503 "Google Drive não configurado ou indisponível" ao tentar buscar ou subir documento.

---

## 7. Domínio e SSL

Render provisiona SSL automático (Let's Encrypt) tanto pro domínio `.onrender.com` padrão quanto pra domínio próprio, se um dia configurarmos um (`hub.selectenergiasolar.com.br`, por exemplo). Não precisa fazer nada manual pra isso funcionar — só confirmar o cadeado no navegador depois de qualquer mudança de domínio.

---

## 8. Coisas aprendidas no caminho (não repetir)

- **Render não lê arquivo `_redirects` (isso é do Netlify).** Rewrite de SPA é configurado direto no dashboard: Settings → Redirects/Rewrites → `/*` → `/index.html` → Rewrite (não Redirect).
- **Neon free "dorme" com inatividade** — tanto ele quanto o backend do Render (também free) podem demorar uns 30-50s na primeira requisição depois de um tempo parado. Normal do plano grátis, não é bug.
- **`pool_pre_ping` no SQLAlchemy é obrigatório com Neon** — sem isso, a primeira query depois do banco "dormir" quebra com `SSL connection has been closed unexpectedly`.
- **Variável de ambiente no Render não interpreta aspas** — colar um valor entre aspas vira parte literal da string (causou o erro `invalid_client` do Google).
- **Blueprint novo esquece o prefixo `/api/v1` fácil** — já aconteceu duas vezes (`pendencia_routes.py`, `log_routes.py`) numa sessão que não seguiu o padrão. Sempre conferir com `grep -rn "url_prefix" backend/routes/` depois de criar rota nova.