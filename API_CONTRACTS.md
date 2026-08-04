# HUB — Contratos de API

> Gerado a partir do código em `backend/routes/` e `backend/services/` em 2026-07-27.
> Se um endpoint mudar, atualize este arquivo no mesmo commit — é a regra combinada em `PROGRESS.md`.

## Convenções gerais

**Base URL:** `http://localhost:8000` (dev). Configurável no frontend via `services/config.ts`.

**Autenticação:** header `Authorization: Bearer <token>` em toda rota, exceto as marcadas como **pública** abaixo. Token vem de `POST /auth/login`, expira em 7 dias. Requisição sem token ou com token inválido/expirado recebe `401`.

**Envelope de resposta — sucesso** (`utils/api_response.py::success_response`):
```json
{ "success": true, "message": "texto", "data": {} }
```

**Envelope de resposta — erro** (`error_response`):
```json
{ "error": "texto", "details": {} }
```
`details` só aparece quando o backend manda explicitamente; a maioria dos erros só tem `error`.

---

## Auth (`/auth`)

### `POST /auth/bootstrap` — pública
Cria o admin único. Só funciona **uma vez** — depois que existir 1 usuário no banco, sempre retorna 403.

Body: `{ "email": string, "senha": string (min. 6 caracteres) }`

Sucesso (201): `data` = objeto `User` (`id, email, papel, ativo`).
Erros: 400 (faltando campo/senha curta), 403 (bootstrap já usado).

### `POST /auth/login` — pública
Body: `{ "email": string, "senha": string }`

Sucesso (200): `data` = `{ "token": string, "user": User }`.
Erro: 401 (email/senha inválidos).

---

## Clientes (`/clients`)

Todas exigem token.

### `GET /clients`
`data` = array de `Client`:
```json
{
  "id": 1, "nome": "", "cpf": "", "email": "", "telefone": "",
  "concessionaria": "", "status": "",
  "uc": "codigo da primeira UC ou ''",
  "usina": "nome da usina da 1a conexao da 1a UC, ou 'A definir'",
  "consumo": "consumo da primeira UC ou ''",
  "ucs": [ConsumerUnit, ...],
  "documentos": []
}
```
`uc`/`usina`/`consumo` são derivados da **primeira** UC do cliente — não confundir com a lista completa em `ucs`. `documentos` aqui sempre vem vazio (documentos de verdade são via `/documents`, filtrando por `clienteId`).

`status` é calculado no backend a cada save (`_resolve_status`), não é um campo livre:
- `"Esperando rateio"` se alguma UC tiver mais de 1 conexão de usina
- `"Concluido"` se alguma UC tiver pelo menos 1 conexão
- `"Esperando usina"` caso contrário

### `GET /clients/<id>`
`data` = `Client`. 404 se não existir.

### `POST /clients`
Body obrigatório: `nome`, `cpf`, `email` (não-vazios). Opcional: `telefone`, `concessionaria`, `ucs: [ConsumerUnitInput]`.

`ConsumerUnitInput` aninhada (mesmos campos do payload de `POST /ucs`, ver abaixo, **sem** `clienteId`) — `id` ausente ou não-numérico (ex.: UUID gerado no front) = UC nova; `id` numérico = UC existente que deve ser atualizada. UCs existentes que não vierem na lista são **excluídas**.

Sucesso (201): `data` = `Client`.
Erros: 400 (campo obrigatório faltando), 409 (CPF já cadastrado).

### `PUT /clients/<id>`
Mesmo body/validação de `POST`. 404 se cliente não existir. Sucesso: `data` = `Client`.

### `DELETE /clients/<id>`
Sem body. Apaga cliente e cascade de UCs/documentos vinculados. 404 se não existir.

---

## UCs (`/ucs`)

CRUD avulso — a mesma lógica de campos e conexões (`apply_uc_fields`/`sync_connections` em `services/uc_service.py`) é reaproveitada quando a UC vem aninhada dentro de `/clients`.

### `GET /ucs`
`data` = array de `ConsumerUnit`:
```json
{
  "id": 1, "clienteId": 1, "clienteNome": "",
  "codigo": "", "codigoAneel": null, "apelido": "", "documento": null,
  "endereco": null, "cep": null, "concessionaria": null,
  "geracaoPropria": false, "diaEmissaoFatura": null,
  "consumo": "", "baseTarifaria": "B1", "desconto": "",
  "tipoLigacao": "Monofasico", "inicioContrato": null, "terminoContrato": null,
  "carenciaMeses": null, "percentualDescontoCarencia": null,
  "conexoes": [{ "id": 1, "plantId": 1, "usina": "", "percentual": "" }]
}
```
`tipoLigacao` é sempre um de `Monofasico | Bifasico | Trifasico`. Datas de contrato em `YYYY-MM-DD`.

### `GET /ucs/<id>`
`data` = `ConsumerUnit`. 404 se não existir.

### `POST /ucs`
Body obrigatório: `clienteId` (precisa existir), `codigo` (não-vazio). Todos os outros campos do objeto acima são opcionais/aceitos. `conexoes: [{ plantId, percentual }]` — omitir a chave = nenhuma conexão criada.

Sucesso (201): `data` = `ConsumerUnit`.
Erros: 400 (cliente/código faltando), 409 (`ValueError` do service — cliente informado não existe).

### `PUT /ucs/<id>`
Mesmo formato de body, todos os campos opcionais (só atualiza o que vier). Se enviar `clienteId` diferente do atual, move a UC pro outro cliente (404 se o novo cliente não existir → vira erro 409 na prática, ver código). Se a chave `conexoes` **não** vier no body, as conexões existentes são mantidas; se vier (mesmo vazia `[]`), substitui tudo.

Sucesso: `data` = `ConsumerUnit`. 404 se a UC não existir.

### `DELETE /ucs/<id>`
Sem body. Cascade nas conexões. 404 se não existir.

---

## Usinas (`/plants`)

### `GET /plants`
`data` = array de `Plant`:
```json
{
  "id": 1, "nome": "", "uc": "", "kwPico": 0.0,
  "mediaGeracao": "0 kWp", "status": "Implantacao",
  "percentualDisponivel": 0, "marcaInversor": null,
  "telefoneProprietario": null, "emailProprietario": null,
  "cidade": null, "uf": null, "endereco": null,
  "dataAtivacao": null, "responsavel": null
}
```
`dataAtivacao` em `YYYY-MM-DD`. `uf` é sigla (2 caracteres), sem validação contra lista de UFs por enquanto.
`percentualDisponivel` é **manual** — não é recalculado a partir das conexões existentes (decisão registrada em `PROGRESS.md`, revisar só quando o rateio automático da V3.0 existir).

### `GET /plants/<id>` — `data` = `Plant`. 404 se não existir.

### `POST /plants`
Body obrigatório: `nome`. Aceita todos os campos do objeto acima (`uc`, `kwPico`, `status`, `percentualDisponivel`, `marcaInversor`, `telefoneProprietario`, `emailProprietario`, `cidade`, `uf`, `endereco`, `dataAtivacao`, `responsavel`).

### `PUT /plants/<id>` — mesmo body, todos opcionais. 404 se não existir.

### `DELETE /plants/<id>` — cascade nas conexões dessa usina. 404 se não existir.

---

## Categorias (`/categories`)

Usadas para classificar Documentos.

### `GET /categories`
`data` = array de `{ id, nome, tipo, descricao }`, ordenado por nome.

### `POST /categories`
Body: `{ nome (obrigatório), tipo?, descricao? }`. Nome é único (case-insensitive).
Sucesso (201): `data` = `Category`. Erro: 400 (nome faltando), 409 (nome já existe).

> Não existe `PUT`/`DELETE /categories` ainda.

---

## Documentos (`/documents`)

### `GET /documents?clienteId=&ucId=`
Ambos filtros opcionais e combináveis. `data` = array de `Document`:
```json
{
  "id": 1, "nome": "", "clienteId": 1, "ucId": null,
  "categoriaId": 1, "categoria": "nome da categoria",
  "storageProvider": "local", "storageRef": "1/uuid_arquivo.pdf",
  "mimeType": "application/pdf"
}
```

### `GET /documents/<id>` — `data` = `Document`. 404 se não existir.

### `POST /documents` — **multipart/form-data**, não JSON.
Campos do form: `arquivo` (file, obrigatório), `nome` (opcional — usa o nome do arquivo se vazio), `clienteId` (opcional), `ucId` (opcional), `categoriaId` (**obrigatório**).

Arquivo salvo em `backend/uploads/<clienteId ou 'sem-cliente'>/<uuid>_<nome-original>` (fora do git). Sucesso (201): `data` = `Document`.
Erros: 400 (sem arquivo / sem categoria), 409 (cliente, UC ou categoria informados não existem).

### `PUT /documents/<id>` — Body: `{ "nome": string }`. Só renomeia, não troca o arquivo. 404 se não existir.

### `DELETE /documents/<id>` — apaga registro **e** arquivo físico do disco. 404 se não existir.

### `GET /documents/<id>/download` — retorna o arquivo (`send_file`, `as_attachment`). 404 se o documento ou o arquivo em disco não existir.

---

## Configurações — aparência (`/settings`)

Armazenamento livre chave/valor. Hoje só usado pela tela de Aparência (`themeColor`, `logoDataUrl`).

### `GET /settings` — `data` = `{ "chave1": "valor1", ... }` (objeto plano, não array).

### `PUT /settings` — Body: `{ "chave": "valor", ... }` (uma ou mais chaves). Cria ou atualiza cada uma. `data` = objeto completo atualizado, igual ao `GET`.

---

## Configurações — banco de dados (`/config`)

Controla qual provedor de dados o backend usa (Google Drive service-account, ou SQL — SQL ainda é só cadastro de credenciais, sem driver real conectado). Persistido direto no `.env` do backend via `dotenv`.

### `GET /config/database`
```json
{
  "provider": "google_drive",
  "googleDrive": {
    "configured": true, "credentialsFile": "credentials.json",
    "rootFolderId": "", "dataFile": "hub-data.json", "credentialsFound": true
  },
  "sql": {
    "configured": false, "driver": "", "host": "", "port": "",
    "database": "", "user": "", "passwordConfigured": false
  }
}
```

### `POST /config/database/provider` — Body: `{ "provider": "google_drive" | "sql" }`. Erro 400 se vier outro valor.

### `POST /config/database/google-drive` — Body: `{ credentialsFile?, rootFolderId?, dataFile? }`. Sempre também seta `provider=google_drive`.

### `POST /config/database/sql` — Body: `{ driver?, host?, port?, database?, user?, password? }`. Senha nunca volta em nenhum `GET` (só `passwordConfigured: true/false`). Sempre também seta `provider=sql`.

### `POST /config/database/test` — Body: `{ "provider": "google_drive" | "sql" }`. `data` = `{ "ok": boolean }`, `message` explica o motivo se `ok=false`. **Não testa conexão real** hoje — só confere se os campos obrigatórios estão preenchidos (SQL) ou se `credentials.json` + pasta raiz existem (Drive).

---

## OAuth Google (`/oauth/google`)

Fluxo de autorização de usuário real (PKCE), complementar ao `credentials.json` de service account usado pelo Drive legado. Contas ficam salvas em `GoogleAccount`, refresh token criptografado (nunca exposto em nenhum `to_dict`).

### `GET /oauth/google/authorize` — pública
Sem chamar via `fetch` — é link direto (`<a href>`). Redireciona pro consentimento do Google.

### `GET /oauth/google/callback` — pública
Chamada pelo próprio Google, nunca pelo frontend diretamente. Sempre redireciona de volta pro frontend: `{FRONTEND_URL}/configuracoes?google_oauth=sucesso` ou `...?google_oauth=erro&motivo=...`.

### `GET /oauth/google/accounts`
`data` = array de `GoogleAccount`: `{ id, nome, email, scopes: string[], ativa: boolean }`.

### `POST /oauth/google/accounts/<id>/activate`
Sem body. Marca essa conta como `ativa` (desativa todas as outras — só uma ativa por vez). `data` = `GoogleAccount`. 404 se não existir.

### `DELETE /oauth/google/accounts/<id>`
Sem body. Remove a conta do banco (**não revoga** o acesso do lado do Google — isso é manual em myaccount.google.com/permissions). 404 se não existir.

---

## Google Drive — busca legada (sem prefixo de rota)

Usa a conta OAuth ativa se houver uma; cai pro `credentials.json` de service account se não. Essas duas rotas **não têm `/drive` no path** — ficam na raiz mesmo, cuidado ao chamar.

### `GET /search?q=texto`
Retorna array cru do Google (não passa pelo envelope `success_response`): `[{ id, name, mimeType, webViewLink, iconLink, modifiedTime }, ...]`. Busca só PDFs e pastas.
Erro (503): `{ "error": "Google Drive nao configurado: ..." }` se não houver credencial válida (nem OAuth nem service account).

### `POST /download-zip`
Body: `{ "ids": string[] }` (IDs de arquivo do Drive). Retorna o **binário do ZIP** direto (`application/zip`, `hub-reservados.zip`), não JSON. Pastas na lista são ignoradas e listadas num `pastas-nao-baixadas.txt` dentro do ZIP. Erro 400 se `ids` vazio, 503 se Drive não configurado.

---

## Health (`/`)

### `GET /` — pública
`{ "status": "Servidor rodando com sucesso!" }`. Sem envelope `success_response`.