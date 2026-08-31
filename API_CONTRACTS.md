# HUB — Contratos de API


> **Documentos relacionados:** [[ARCHITECTURE]] · [[VISAO]] · [[RATEIO]]
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


### `POST /auth/esqueci-senha` — pública
Body: `{ "email": string }`. Sempre retorna a mesma mensagem, mesmo se o e-mail não existir (não revela quem tem conta). Rate limit 5/min.

### `POST /auth/redefinir-senha` — pública
Body: `{ "token": string, "senha": string (min. 6) }`. Token vem do link do e-mail, TTL 1h, uso único. Rate limit 5/min.

## Templates de e-mail (`/email-templates`)

Restrito a `owner`/`admin` (`settings.read`/`settings.update`).

### `GET /email-templates` — `data` = array de `{ chave, nome, assunto, corpo, variaveisDisponiveis }`
### `GET /email-templates/<chave>` — `data` = um template. 404 se não existir.
### `PUT /email-templates/<chave>` — Body: `{ assunto, corpo }`. Atualiza o template.
### `POST /email-templates/<chave>/restaurar` — sem body. Volta ao texto padrão.
### `POST /email-templates/<chave>/testar` — sem body. Manda um e-mail de teste (dados de exemplo) pro e-mail do usuário logado. 503 se `RESEND_API_KEY` não estiver configurada.

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

## Pendências (`/pendencias`)

Fila única com `tipo` discriminando `pendencia` (tarefa manual), `alerta` (aviso automático) e `erro` (falha técnica) — decisão registrada no `PROGRESS.md`: começa numa tabela só, mas o código já é organizado por tipo (`CATEGORIAS_POR_TIPO`, `criar_pendencia_manual`/`criar_alerta`/`criar_erro` separados) pra facilitar separar em 3 tabelas no futuro, se precisar.

**Categorias válidas** (mesma lista pros 3 tipos hoje): `Financeiro`, `Documentos`, `UCs`, `Usinas`, `Sistema`, `Mensagens`.
**Prioridades**: `baixa`, `media`, `alta`, `critica`. **Status**: `aberta`, `resolvida`, `cancelada`.

### `GET /pendencias?tipo=&categoria=&origem=&status=&prioridade=&responsavelId=&clienteId=`
Todos os filtros opcionais e combináveis. `data` = array de `Pendencia`:
```json
{
  "id": 1, "tipo": "pendencia", "categoria": "Financeiro", "origem": "Manual",
  "titulo": "", "descricao": null,
  "clienteId": null, "clienteNome": null,
  "ucId": null, "ucCodigo": null,
  "usinaId": null, "usinaNome": null,
  "documentoId": null, "documentoNome": null,
  "prazo": null, "prioridade": "media",
  "responsavelId": 1, "responsavelNome": "admin@hub.com",
  "status": "aberta", "metadados": null,
  "criadoEm": "...", "atualizadoEm": "...", "resolvidoEm": null,
  "comentarios": [{ "id": 1, "pendenciaId": 1, "autorId": 1, "autorNome": "admin@hub.com", "texto": "", "criadoEm": "..." }]
}
```
`responsavelNome`/`autorNome` usam o **email** do usuário — `User` não tem campo "nome" hoje.

### `GET /pendencias/resumo`
`data` = `{ "pendencias": 5, "alertas": 2, "erros": 1 }` — contagem por tipo, **só status `aberta`**. Alimenta os cards do topo da tela.

### `GET /pendencias/<id>` — `data` = `Pendencia`. 404 se não existir.

### `POST /pendencias`
Body obrigatório: `titulo`, `categoria` (precisa estar em `CATEGORIAS_POR_TIPO['pendencia']`). Opcionais: `descricao`, `clienteId`, `ucId`, `usinaId`, `documentoId`, `prazo` (ISO ou `YYYY-MM-DD`), `prioridade` (default `media`), `responsavelId` (default: usuário logado).
**Sempre cria tipo `pendencia`** — não existe jeito de criar `alerta`/`erro` por essa rota (são gerados só pelo sistema, via `POST /pendencias/verificar` ou regras automáticas internas).
Sucesso (201): `data` = `Pendencia`. Erros: 400 (`titulo`/`categoria` faltando ou inválidos).

### `PUT /pendencias/<id>` — mesmo formato, todos os campos opcionais. 404 se não existir.

### `DELETE /pendencias/<id>` — sem body. 404 se não existir.

### `POST /pendencias/<id>/resolver` — sem body. Seta `status='resolvida'` e `resolvidoEm`. `data` = `Pendencia`.

### `POST /pendencias/<id>/cancelar` — sem body. Seta `status='cancelada'`. `data` = `Pendencia`.

### `POST /pendencias/<id>/reabrir` — sem body. Volta `status='aberta'`, limpa `resolvidoEm`. `data` = `Pendencia`.

### `POST /pendencias/<id>/comentarios`
Body: `{ "texto": string }`. Autor é sempre o usuário logado (`g.current_user`). Sucesso (201): `data` = `Pendencia` (já com o comentário novo em `comentarios`).

### `POST /pendencias/verificar`
Executa todas as regras automáticas de pendências. Body: nenhum. Retorna:
```json
{
  "data": {
    "verificacoes": {
      "ucs_sem_usina": 0,
      "clientes_sem_uc": 0,
      "campos_faltando": 0,
      "documentos_faltando": 0
    },
    "resolvidas": 0,
    "total_criadas": 0
  }
}
```

### `GET /pendencias/regras`
Lista as regras automáticas disponíveis. Retorna array de regras com `id`, `nome`, `descricao`, `categoria` e `ativa`.

---

## Dashboard (`/dashboard`)

### `GET /dashboard/resumo`
Requer `pendencias.read`. Retorna o resumo operacional calculado em tempo real, sempre no escopo da empresa ativa (ou da empresa selecionada por platform admin). Não cria nem persiste registros de dashboard.

`data`:
```json
{
  "geradoEm": "2026-08-31T12:00:00",
  "pendencias": {
    "abertas": 5,
    "vencidas": 1,
    "vencendoEm7Dias": 2,
    "resolvidasNoMes": 3,
    "fila": ["Pendencia"]
  },
  "clientes": { "disponivel": true, "total": 12, "porStatus": { "Ativo": 10, "Esperando usina": 2 } },
  "ucs": { "disponivel": true, "total": 14 },
  "usinas": { "disponivel": true, "total": 4, "porStatus": { "Ativa": 3, "Implantacao": 1 } },
  "documentos": { "disponivel": true, "total": 25, "porCategoria": { "1": 18, "semCategoria": 7 } }
}
```

`fila` contém no máximo 10 pendências abertas, ordenadas por prioridade e prazo, no formato `Pendencia`. `vencendoEm7Dias` cobre prazos entre o instante da consulta e os próximos sete dias; vencidas ficam apenas em `vencidas`. Em recursos sem permissão de leitura para o papel autenticado, `disponivel` é `false` e as métricas desse recurso retornam `null`, evitando exposição indireta de dados.

---

## Agenda (`/agenda`)

### `GET /agenda?inicio=YYYY-MM-DD&fim=YYYY-MM-DD&visao=dia|semana|mes`

Requer `pendencias.read`. Agenda nao possui tabela nem CRUD proprio: nesta fase cada item e uma visao em tempo real de uma `Pendencia` **aberta** que tem `prazo`. Assim, editar prazo ou reabrir a pendencia de origem aparece na proxima consulta; resolver ou cancelar a remove imediatamente, sem sincronizacao manual ou duplicacao de estado.

`inicio` e `fim` sao opcionais, mas devem ser enviados juntos e cobrir no maximo 93 dias-calendario (diferença máxima de 92 dias). Sem intervalo explicito, `visao` define o periodo atual (`mes` e o default; `dia` e hoje; `semana` vai de domingo a sabado). Datas usam `YYYY-MM-DD` e os limites sao inclusivos. O resultado e ordenado por prazo e limitado a 500 itens.

```json
{
  "data": {
    "visao": "mes", "inicio": "2026-08-01", "fim": "2026-08-31",
    "itens": [{
      "fonte": "pendencia", "pendenciaId": 1,
      "id": 1, "titulo": "Enviar fatura", "tipo": "pendencia",
      "prioridade": "alta", "prazo": "2026-08-31T14:00:00",
      "status": "aberta", "clienteId": 2,
      "ucId": null, "usinaId": null, "documentoId": null
    }]
  }
}
```

O item e uma projeção mínima para calendário/lista: não inclui descrição, comentários, responsável/e-mail, metadados ou timestamps. Nesta versao nao ha eventos manuais, financeiro ou rateio; novas fontes deverao ser adicionadas como consultas derivadas, nunca por uma tabela de eventos duplicada.

---

## Logs (`/logs`)

### `GET /rateio/formulario?plantId=`
Monta a tabela de revisão do Formulário Copel (Associações) a partir das `PlantConnection` já confirmadas dessa usina — não recalcula nada. `data`:
```json
{
  "plantId": 1, "plantNome": "", "empresaNome": "", "empresaCnpj": "",
  "somaPercentual": 100.0,
  "linhas": [
    { "ordem": 1, "tipo": "geradora", "nome": "", "documento": "", "ucIdentificacao": "", "percentual": 0.0, "termoAdesaoOk": null, "clienteId": null, "ucId": null },
    { "ordem": 2, "tipo": "beneficiaria", "nome": "", "documento": "", "ucIdentificacao": "", "percentual": 33.33, "termoAdesaoOk": true, "clienteId": 1, "ucId": 1 }
  ]
}
```
Linha 1 é sempre a usina/associação (0%, `termoAdesaoOk: null`). Linhas seguintes vêm ordenadas alfabeticamente pelo nome do cliente titular. Erro 404 se a usina não existir.

### `POST /rateio/formulario/verificar-documentos`
Body: `{ "plantId": number }`. Confere Termo de Adesão de cada UC beneficiária (por nome/categoria do `Document`). Se faltar algum, cria uma `Pendencia` (categoria `Documentos`, prioridade `critica`) e retorna `ok: false`.
`data`: `{ "ok": boolean, "faltando": [{ "clienteId": number, "ucId": number, "nome": string }] }`.

### `POST /rateio/formulario/gerar-pdf`
Body: `{ "plantId": number, "responsavelNome": string, "responsavelCpf": string }`. Gera o Formulário Copel (Associações) preenchido por overlay em cima do template oficial (`backend/assets/formulario_copel_associacao.pdf`). **Resposta binária** (`application/pdf`, `Content-Disposition: attachment`), não passa pelo envelope `success_response`.
Bloqueia com 400 se: faltar Termo de Adesão de alguma UC beneficiária, ou a usina tiver mais de 24 UCs beneficiárias (limite do formulário oficial).

### `POST /rateio/formulario/gerar-termos`
Body: `{ "plantId": number }`. Baixa do Google Drive o Termo de Adesão de cada UC beneficiária (mesma ordem alfabética da tabela) e mescla num PDF único. **Resposta binária** (`application/pdf`). Bloqueia com 400 nas mesmas condições da rota acima.

CNPJ e Estatuto **não têm rota própria** — são `Document` normais (ver `GET /empresas/documentos` e `GET /documents/<id>/download`), cadastrados uma vez em Configurações.

---

## Logs (`/logs`)

### `GET /logs?limit=50&nivel=&entidade=&entidadeId=`
Todos os filtros opcionais. `limit` tem teto de 200. `entidade`/`entidadeId` combinados servem pra timeline de um registro específico (ex.: histórico de uma Pendência: `entidade=Pendencia&entidadeId=3`).
`data` = array de `LogEntry`, mais recente primeiro:
```json
{ "id": 1, "nivel": "info", "acao": "create", "entidade": "Pendencia", "entidadeId": 3, "mensagem": "", "metadados": null, "criadoEm": "..." }
```

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

O callback registrado e `FRONTEND_URL` devem usar HTTPS absoluto sem credenciais ou fragmento em produção. HTTP só é permitido para `localhost`/loopback quando `FLASK_DEBUG=true` **e** `OAUTH_ALLOW_INSECURE_TRANSPORT=true` forem configurados explicitamente; a aplicação remove a exceção de transporte inseguro do OAuthlib em qualquer outro ambiente. A validação padrão de escopos do OAuthlib permanece ativa.

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

## Empresa — documentos fixos (`/empresas/documentos`)

Cartão CNPJ e Estatuto da associação, usados na geração do formulário Copel de rateio. Reaproveita o storage de `Document` — cada upload substitui o anterior daquele tipo (o antigo é excluído).

### `GET /empresas/documentos`
Requer permissão `settings.read`. `data` = `{ "cnpj": Document | null, "estatuto": Document | null }` (formato `Document`, ver seção Documentos).

### `POST /empresas/documentos/<tipo>` — **multipart/form-data**
`tipo` = `cnpj` ou `estatuto`. Campo do form: `arquivo` (obrigatório). Requer permissão `settings.update`.
Sucesso: `data` = mesmo formato do GET acima, já atualizado.
Erros: 400 (sem arquivo / tipo inválido), 503 (Google Drive indisponível).

---

## Google Drive — busca legada (`/drive`)

Usa a conta OAuth ativa se houver uma; cai pro `credentials.json` de service account se não. Prefixo real: `/api/v1/drive` (`drive_routes.py`, `url_prefix='/api/v1/drive'`).

### `GET /drive/search?q=texto`
Retorna array cru do Google (não passa pelo envelope `success_response`): `[{ id, name, mimeType, webViewLink, iconLink, modifiedTime }, ...]`. Busca só PDFs e pastas.
Erro (503): `{ "error": "Google Drive nao configurado: ..." }` se não houver credencial válida (nem OAuth nem service account).

### `POST /download-zip`
Body: `{ "ids": string[] }` (IDs de arquivo do Drive). Retorna o **binário do ZIP** direto (`application/zip`, `hub-reservados.zip`), não JSON. Pastas na lista são ignoradas e listadas num `pastas-nao-baixadas.txt` dentro do ZIP. Erro 400 se `ids` vazio, 503 se Drive não configurado.

---

## Health (`/`)

### `GET /` — pública
`{ "status": "Servidor rodando com sucesso!" }`. Sem envelope `success_response`.
