# HUB — Deploy e Infraestrutura

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
| `ASAAS_API_BASE_URL` | `https://api-sandbox.asaas.com/v3` no Sandbox | Produção usa a URL v3 do ASAAS de produção |
| `PLATFORM_ASAAS_API_BASE_URL` | URL v3 da conta ASAAS da plataforma | Independente do ambiente tenant; HTTPS ASAAS obrigatório. |
| `PLATFORM_ASAAS_API_KEY` | Vazio | Segredo global da plataforma em env; não cadastrar como `ApiCredential` de empresa. |
| `PLATFORM_ASAAS_WEBHOOK_TOKEN` | Vazio | Token global exclusivo de `/api/v1/webhooks/asaas/platform`; vazio rejeita o webhook. |
| `STORAGE_PROVIDER` | `s3` em produção | Obrigatório para novos PDFs de fatura; `local` só é aceito em desenvolvimento/testes. Configuração ausente falha explicitamente no upload. |
| `OBJECT_STORAGE_ENDPOINT` | `https://<ACCOUNT_ID>.r2.cloudflarestorage.com` | Endpoint S3 do R2; produção exige HTTPS e domínio R2. |
| `OBJECT_STORAGE_BUCKET` | Nome do bucket privado | Confirmar no Cloudflare que `r2.dev` e domínio público estão desabilitados. |
| `OBJECT_STORAGE_ACCESS_KEY_ID` / `OBJECT_STORAGE_SECRET_ACCESS_KEY` | Credenciais R2 restritas ao bucket | Segredos só no Render; não expor no frontend ou banco. |
| `OBJECT_STORAGE_REGION` | `auto` | Valor usado pelo cliente S3 do R2. |
| Credenciais Asaas por empresa | Configurações → APIs e Integrações no HUB | Cadastre separadamente a chave de API e o token de autenticação do webhook no ambiente correto. O token é validado no header `asaas-access-token`; nunca use a chave de API como token. `ASAAS_WEBHOOK_TOKEN` global é legado e não autentica o webhook atual. |
| `META_APP_SECRET` | App Secret da aplicação Meta do HUB | Valida `X-Hub-Signature-256` no webhook WhatsApp; nunca vai ao frontend ou banco por empresa |
| `META_WEBHOOK_VERIFY_TOKEN` | Valor secreto escolhido ao configurar o callback Meta | Usado apenas no desafio `GET /api/v1/webhooks/whatsapp` |
| `META_GRAPH_API_BASE_URL` / `META_GRAPH_API_VERSION` | Endpoint e versão Graph API em uso | Atualizar a versão de forma controlada conforme ciclo da Meta |

`OAUTH_ALLOW_INSECURE_TRANSPORT` não deve ser configurada no Render. Ela só serve para OAuth local via HTTP e só tem efeito junto de `FLASK_DEBUG=true`, `GOOGLE_OAUTH_REDIRECT_URI` e `FRONTEND_URL` em `localhost`/loopback; produção falha fechada se callback ou frontend não forem URLs HTTPS absolutas, sem credenciais ou fragmentos. Para rodar localmente, use os valores de `backend/.env.example` e cadastre `http://localhost:8000/api/v1/oauth/google/callback` como URI de redirecionamento autorizada no cliente OAuth do Google Cloud. Reinicie o backend após alterar o `.env`.

### Ativação do R2 para PDFs de faturas (STORAGE-1A)

O R2 deve estar habilitado na conta Cloudflare antes de criar bucket ou credenciais. Use um bucket privado exclusivo para cada ambiente. Confira no bucket que **Public Development URL (`r2.dev`) está desabilitada** e que não há domínio público ativo. Crie um token de API do R2 com permissão **Object Read & Write**, limitado ao bucket desse ambiente; o backend precisa de `PutObject`, `GetObject` e `DeleteObject`. Guarde o Access Key ID e o Secret Access Key somente no ambiente do backend. A [documentação de tokens R2](https://developers.cloudflare.com/r2/api/tokens/) e a [documentação de buckets públicos](https://developers.cloudflare.com/r2/buckets/public-buckets/) descrevem essas configurações.

Em desenvolvimento, coloque `STORAGE_PROVIDER=s3`, `OBJECT_STORAGE_ENDPOINT=https://<ACCOUNT_ID>.r2.cloudflarestorage.com`, `OBJECT_STORAGE_BUCKET`, `OBJECT_STORAGE_ACCESS_KEY_ID`, `OBJECT_STORAGE_SECRET_ACCESS_KEY` e `OBJECT_STORAGE_REGION=auto` em `backend/.env`, que é ignorado pelo Git. Use uma credencial própria de desenvolvimento/teste e um bucket separado de produção. Não copie segredos para logs, documentação, frontend ou comandos que imprimam o ambiente.

Antes de configurar o Render, valide no bucket de desenvolvimento: escrita, existência física, leitura e exclusão de um objeto descartável; upload de PDF de teste pela API do HUB; `Document.storage_provider=s3`, `storage_ref` opaca e hash da fatura; download autenticado com SHA-256, headers e nome; negação entre duas empresas; leitura de documento legado; e resposta controlada quando o provider falha. Só então configure as mesmas seis variáveis no **Web Service de backend** do Render, usando **outro bucket e outro token restrito** para produção. Confirme o serviço e workspace antes de alterar variáveis, pois a mudança pode iniciar um deploy. Faça o teste funcional de produção antes de registrar `R2_READY=true` e `STORAGE_1_DONE=true` no `PROGRESS.md`; esses dois nomes são marcadores documentais, não variáveis de ambiente do HUB.

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

## 4. Limpeza periódica de previews de importação

O preview de importação pode conter CPF/e-mail temporariamente. A aplicação o remove antes de cada preview/confirmação e também expõe uma limpeza global, segura para executar por agendador da plataforma, sem chamar serviços externos:

```powershell
cd backend
..\.venv\Scripts\flask purge-import-previews
```

O comando remove somente registros com `expires_at` já vencido, de todas as empresas, e mostra a quantidade removida. Agende-o diariamente no mecanismo operacional escolhido (por exemplo, um cron do provedor) depois de configurar o ambiente; esta alteração não configura nem executa deploy.

## 5. Como migrar dados do zero (SQLite antigo → Postgres)

Script em `backend/scripts/migrate_sqlite_to_postgres.py` — pontual, só pra quando existir um `hub.db` novo pra trazer (não é rotina, diferente da seção 3).

```powershell
venv\Scripts\python scripts\migrate_sqlite_to_postgres.py                                    # dry-run
venv\Scripts\python scripts\migrate_sqlite_to_postgres.py --apply                             # aplica
venv\Scripts\python scripts\migrate_sqlite_to_postgres.py --apply --include-users              # inclui usuarios
venv\Scripts\python scripts\migrate_sqlite_to_postgres.py --apply --force --only users          # so re-roda 1 tabela
```
Detalhes de cada flag no docstring do próprio arquivo.

---

## 6. Se algo quebrar: rollback

**Backend ou frontend no Render:** dashboard do serviço → aba **Events** → escolhe um deploy anterior que funcionava → **Rollback**. O Render mantém builds anteriores prontos, é praticamente instantâneo.

**Banco de dados:** Neon mantém histórico de pontos no tempo (Point-in-Time Restore) mesmo no plano free, por um período limitado — dá pra restaurar pelo próprio painel do Neon em caso de dado corrompido/apagado por engano. Não depende de backup manual nosso pra esse caso.

**Migration aplicada errada:** `flask db downgrade -1` reverte a última migration (testamos isso funcionar de ponta a ponta, incluindo com `batch_alter_table`, na Etapa 2).

---

## 7. Reconectar Google Drive — quando e por quê

Precisa reconectar a conta Google (Configurações → desconectar → conectar de novo) sempre que:
- `SECRET_ENCRYPTION_KEY` mudar (o refresh token salvo fica ilegível com a chave nova)
- `GOOGLE_DRIVE_SCOPES` mudar pra um escopo mais amplo (o token antigo foi autorizado só com o escopo de antes — Google não amplia sozinho)

Sintoma de token quebrado: erro 503 "Google Drive não configurado ou indisponível" ao tentar buscar ou subir documento.

---

## 8. Domínio e SSL

Render provisiona SSL automático (Let's Encrypt) tanto pro domínio `.onrender.com` padrão quanto pra domínio próprio, se um dia configurarmos um (`hub.selectenergiasolar.com.br`, por exemplo). Não precisa fazer nada manual pra isso funcionar — só confirmar o cadeado no navegador depois de qualquer mudança de domínio.

---

## 9. Coisas aprendidas no caminho (não repetir)

- **Render não lê arquivo `_redirects` (isso é do Netlify).** Rewrite de SPA é configurado direto no dashboard: Settings → Redirects/Rewrites → `/*` → `/index.html` → Rewrite (não Redirect).
- **Neon free "dorme" com inatividade** — tanto ele quanto o backend do Render (também free) podem demorar uns 30-50s na primeira requisição depois de um tempo parado. Normal do plano grátis, não é bug.
- **`pool_pre_ping` no SQLAlchemy é obrigatório com Neon** — sem isso, a primeira query depois do banco "dormir" quebra com `SSL connection has been closed unexpectedly`.
- **Variável de ambiente no Render não interpreta aspas** — colar um valor entre aspas vira parte literal da string (causou o erro `invalid_client` do Google).
- **Blueprint novo esquece o prefixo `/api/v1` fácil** — já aconteceu duas vezes (`pendencia_routes.py`, `log_routes.py`) numa sessão que não seguiu o padrão. Sempre conferir com `grep -rn "url_prefix" backend/routes/` depois de criar rota nova.
