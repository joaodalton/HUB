# HUB — Contratos de API

## Limite de plano

Os `POST /clients`, `POST /ucs`, `POST /plants` e `POST /users` retornam `403` com `code: "QUOTA_EXCEEDED"` quando a empresa autenticada atingiu a cota. `details` contém `recurso`, `uso` e `limite`.


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

## Saúde

### `GET /` — pública
Liveness do processo. Retorna `200` enquanto a aplicação estiver executando; não consulta serviços externos.

### `GET /ready` — pública
Readiness do banco. Executa uma consulta mínima e retorna `200` com `database: "ok"`; se o banco estiver indisponível, retorna `503` sem detalhes internos.

## Auth (`/auth`)

### `POST /auth/bootstrap` — pública
Cria o admin único. Só funciona **uma vez** — depois que existir 1 usuário no banco, sempre retorna 403.

Body: `{ "email": string, "senha": string (min. 6 caracteres) }`

Sucesso (201): `data` = objeto `User` (`id, email, papel, ativo`).
Erros: 400 (faltando campo/senha curta), 403 (bootstrap já usado).

### `POST /auth/login` — pública
Body: `{ "email": string, "senha": string }`

Sucesso (200): `data` = `User` (o token é enviado apenas em cookie HttpOnly). `mustChangePassword: true` sinaliza que a sessão fica limitada a identidade, logout e troca de senha até a conclusão.
Erro: 401 (email/senha inválidos).

### `POST /auth/alterar-senha` — autenticada

Body: `{ "senhaAtual": string, "novaSenha": string }`. Exige senha atual válida e nova senha com pelo menos 6 caracteres. Retorna o `User` sem campos de senha, limpa `mustChangePassword`, incrementa a versão de sessão e renova os cookies de autenticação; qualquer token anterior deixa de valer.


### `POST /auth/esqueci-senha` — pública
Body: `{ "email": string }`. Sempre retorna a mesma mensagem, mesmo se o e-mail não existir (não revela quem tem conta). Rate limit 5/min.

### `POST /auth/redefinir-senha` — pública
Body: `{ "token": string, "senha": string (min. 6) }`. Token vem do link do e-mail, TTL 1h, uso único. Rate limit 5/min.

## Usuários (`/users`)

### `PUT /users/<id>/ativo`

Exige `users.deactivate` ou `users.reactivate`; só alcança usuários da empresa autenticada. Body obrigatório: `{ "ativo": boolean }` — strings, números e ausência do campo retornam `400`. Não permite desativar o próprio usuário nem o `owner` da empresa. Cada transição entre `ativo` e `inativo` incrementa a versão de sessão, invalidando tokens emitidos antes da transição.

## Templates de e-mail (`/email-templates`)

Restrito a `owner`/`admin` (`settings.read`/`settings.update`).

### `GET /email-templates` — `data` = array de `{ chave, nome, assunto, corpo, variaveisDisponiveis }`
### `GET /email-templates/<chave>` — `data` = um template. 404 se não existir.
### Endpoints mutáveis/teste legados retornam `410`; use `/message-templates`.

## Templates de mensagem (`/message-templates`)

Templates por empresa com `canal` `email` ou `whatsapp`. Listagem/consulta exigem `settings.read`; criação, edição, exclusão, restauração e `POST /message-templates/<id>/preview` exigem `settings.update`. Preview só renderiza localmente, sem enviar mensagens. Variáveis aceitas: `nome`, `link`, `papel`, `empresa`; HTML livre, placeholders desconhecidos/malformados e links não HTTPS absolutos são rejeitados.

Templates WhatsApp também retornam `metaStatus` (`draft`, `pending`, `approved`, `rejected`), `metaCategory`, `metaTemplateId`, motivo de rejeição e data de submissão. Alterar corpo, chave ou categoria volta o item para `draft`: a edição local nunca altera silenciosamente um template já aprovado pela Meta.

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
CAD-1: `nome` é obrigatório, recebe trim e aceita de 1 a 200 caracteres. `cpf` aceita máscara, mas deve ter 11 dígitos e verificadores válidos; é persistido só com dígitos. `telefone` permanece opcional; quando informado, aceita máscara e prefixo `+55`, sendo salvo com 10 dígitos (fixo com DDD) ou 11 dígitos (celular com DDD e primeiro dígito 9). DDD deve ser válido. Entradas longas ou inválidas retornam 400 sem truncamento. As regras valem também para `PUT /clients` e para prévia/confirmação de importação. Dados legados não são regravados numa edição de outro campo.

Body obrigatório: `nome`, `cpf`, `email` (não-vazios). Opcional: `telefone`, `concessionaria`, `ucs: [ConsumerUnitInput]`.

`ConsumerUnitInput` aninhada (mesmos campos do payload de `POST /ucs`, ver abaixo, **sem** `clienteId`) — `id` ausente ou não-numérico (ex.: UUID gerado no front) = UC nova; `id` numérico = UC existente que deve ser atualizada. UCs existentes que não vierem na lista são **excluídas**.

Sucesso (201): `data` = `Client`.
Erros: 400 (campo obrigatório faltando), 409 (CPF já cadastrado).

### `PUT /clients/<id>`
Mesma validação dos campos enviados no `POST`. Omitir `ucs` preserva as UCs e o status existentes; enviar a lista reconcilia apenas UCs já pertencentes a esse cliente. Um ID de UC alheia retorna 404 sem alterar os vínculos. 404 também se o cliente não existir. Sucesso: `data` = `Client`.

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
  "codigo": "", "apelido": "", "documento": null,
  "endereco": null, "cep": null, "concessionaria": null,
  "geracaoPropria": false, "diaEmissaoFatura": null,
  "consumo": "", "baseTarifaria": "B1", "desconto": "",
  "tipoLigacao": "Monofasico", "inicioContrato": null, "terminoContrato": null,
  "carenciaMeses": null, "percentualDescontoCarencia": null,
  "conexoes": [{ "id": 1, "plantId": 1, "usina": "", "percentual": "" }]
}
```
`tipoLigacao` é sempre um de `Monofasico | Bifasico | Trifasico`. Datas de contrato em `YYYY-MM-DD`.
`desconto` é texto percentual de 0 a 100 (`20` e `20%` equivalem a 20%);
`null`/vazio significa sem desconto. Novos valores fora desse formato são
rejeitados no CRUD de UC/Cliente e no preview de importação. Valores legados
inválidos bloqueiam novas execuções financeiras para revisão.
`senhaConcessionariaConfigurada` indica se existe senha salva para a UC; a senha não aparece nas respostas comuns.

### `GET /ucs/<id>`
`data` = `ConsumerUnit`. 404 se não existir.

### `GET /ucs/<id>/senha-concessionaria`
Restrita a `owner`/`admin` (ou administrador da plataforma). Revela sob demanda `{ "senhaConcessionaria": string }` para a UC da empresa atual; não entra em listagens nem nos endpoints normais de Cliente/UC. Cada revelação é auditada sem registrar a senha. Retorna 404 se a UC ou a senha não existir.

### `POST /ucs`
Para Copel, `codigo` de 12 dígitos é salvo como string de 15 dígitos com `000` à esquerda; código de 15 dígitos é preservado. Outros comprimentos são rejeitados. A regra também vale na edição, no cadastro aninhado de Cliente e no upload/processamento/cálculo operacional. Outras concessionárias preservam o código informado sem normalização. `codigo_aneel` continua apenas como dado legado e não participa do vínculo da fatura. Códigos já persistidos não são migrados automaticamente; a busca documental reconhece temporariamente o legado Copel de 12 dígitos, restringe a concessionária e mantém erro de ambiguidade em caso de colisão. `documento`, quando informado ou alterado, aceita CPF/CNPJ numérico com máscara e verificadores válidos; documentos legados não são alterados em edições de outros campos. CNPJ alfanumérico não é aceito nesta versão; não foi criado CHECK numérico no banco.

Body obrigatório: `clienteId` (precisa existir), `codigo` (não-vazio). Todos os outros campos do objeto acima são opcionais/aceitos. `conexoes: [{ plantId, percentual }]` — omitir a chave = nenhuma conexão criada. `senhaConcessionaria` é opcional, exige `documento` e é salva por CPF/CNPJ: UCs com o mesmo documento compartilham a credencial cifrada; documentos diferentes usam credenciais separadas.

Sucesso (201): `data` = `ConsumerUnit`.
Erros: 400 (código/documento ausente ou inválido), 404 (cliente informado não existe).

### `PUT /ucs/<id>`
Mesmo formato de body, todos os campos opcionais (só atualiza o que vier). Se enviar `clienteId` diferente do atual, move a UC pro outro cliente (404 se o novo cliente não existir). Código/documento inválido retorna 400. Se a chave `conexoes` **não** vier no body, as conexões existentes são mantidas; se vier (mesmo vazia `[]`), substitui tudo. `senhaConcessionaria` segue a mesma regra de identificação por CPF/CNPJ do `POST`.

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

## Faturas originais da concessionária

### `POST /billing-calculations/invoices/upload` — **multipart/form-data**

Upload da página de Faturas sem seleção de cliente. Requer `faturas.create` e exatamente um campo `arquivo` (PDF); o tenant vem da autenticação. Após validar o PDF, o backend extrai o código documental da UC pelo parser suportado e procura correspondência exata em `ConsumerUnit.codigo` **dentro da empresa**. Apenas uma UC correspondente autoriza vincular o documento ao cliente proprietário dessa UC. Não recebe cliente, UC ou empresa do corpo da requisição. O vínculo persistido no upload é com o cliente; `consumerUnitId` só é preenchido pelo processamento/validação F7.

Para administrador da plataforma, a rota equivalente é `POST /platform/empresas/<empresaId>/billing-calculations/invoices/upload`, com empresa explícita e a mesma permissão. Erros antes do armazenamento: `INVOICE_LAYOUT_UNSUPPORTED` ou `UC_CODE_UNREADABLE` (422), `UC_NOT_FOUND` (422), `UC_MATCH_AMBIGUOUS` (409) e `CLIENT_NOT_FOUND` (404). Falha de vínculo não cria Documento nem fatura. Validação de arquivo, resposta e limites seguem o contrato abaixo. Uma duplicata por hash é conferida contra a UC atual: cliente divergente retorna `INVOICE_CLIENT_CONFLICT` (409), sem alterar a fonte histórica; cliente igual retorna a fonte imutável existente.

O campo legado `codigoAneel` permanece no banco para preservar valores anteriores, mas não participa da correspondência e não é exposto e, se enviado, é ignorado no CRUD de UC. Para o layout Copel suportado, `codigo` deve conter o mesmo identificador documental de 15 dígitos do PDF. Ausência de compensação GD não impede o upload; afeta a elegibilidade posterior para cobrança.

### `POST /clients/<clientId>/invoices/upload` — **multipart/form-data**

Requer `faturas.create` (`owner`, `admin` ou `financial`). Campo `arquivo` obrigatório; nesta versão aceita exatamente um PDF por chamada. O tenant vem da autenticação e o Cliente precisa pertencer a ele. Nenhum `empresaId` ou UC é aceito do request.

Valida extensão `.pdf`, MIME `application/pdf`, magic bytes `%PDF`, integridade, ausência de criptografia, tamanho e páginas antes de persistir. Limites: `FATURA_CONCESSIONARIA_MAX_BYTES` (default 10 MiB) e `FATURA_CONCESSIONARIA_MAX_PAGES` (default 10).

Sucesso novo (201) ou idempotente por `empresa_id + SHA-256` (200):

```json
{
  "success": true,
  "message": "Fatura recebida.",
  "data": {
    "duplicate": false,
    "invoiceId": 123,
    "invoice": { "id": 123, "statusExtracao": "recebida", "statusValidacao": "pendente" }
  }
}
```

Na duplicidade, `duplicate` é `true`, `invoiceId` aponta para o registro mais antigo e nenhum novo `Document` é criado. Erros controlados usam `error` e `code`: `INVALID_FILE_TYPE`, `INVALID_PDF`, `PDF_ENCRYPTED`, `FILE_TOO_LARGE`, `PDF_TOO_MANY_PAGES`, `CLIENT_NOT_FOUND` ou `DOCUMENT_STORAGE_UNAVAILABLE`.

Não há PUT para `FaturaConcessionaria`; o PDF e o registro-fonte são imutáveis.

Após processamento interno F7, o mesmo objeto `invoice` pode apresentar status
de extração/validação independentes, identidade do parser, vínculo UC validado
e snapshots. `dadosBrutosExtraidos` contém ParsedInvoice; `dadosNormalizados`
contém `{ "invoice": InvoiceNormalized, "validation": InvoiceValidationResult }`.
Nos snapshots, Decimal é string exata e datas são ISO; cada campo documental
mantém status/source/confidence/warnings. Colunas numéricas escalares podem
continuar null: F7 preserva precisão nos snapshots, sem arredondá-las para a
escala do model. Contrato detalhado em FATURAS_E_COBRANCAS.md, Sprint F7.
Desde C4.3, InvoiceNormalized inclui billing_energy_input: compensações canônicas,
energia_compensada_cobravel_kwh (Decimal textual ou null), status, issues,
identidade documental, competência e fatura_concessionaria_id. Somente VALID
autoriza consumo energético futuro. Copel atual retorna UNSUPPORTED; snapshots
anteriores não são reprocessados. Não há novo endpoint ou cobrança.
O upload não executa processamento; a duplicata continua
retornando o registro existente sem reprocessar ou sobrescrever snapshots.

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

Requer `pendencias.read`. A resposta combina projeções de `Pendencia` **aberta** com `prazo` e eventos manuais `AgendaEvent` abertos. Pendências não são copiadas: criar, editar prazo, reabrir, resolver ou cancelar em `/pendencias` aparece na próxima consulta da Agenda. Eventos são o único estado próprio da Agenda e são sempre filtrados pela empresa autenticada.

`inicio` e `fim` sao opcionais, mas devem ser enviados juntos e cobrir no maximo 93 dias-calendario (diferença máxima de 92 dias). Sem intervalo explicito, `visao` define o periodo atual (`mes` e o default; `dia` e hoje; `semana` vai de domingo a sabado). Datas usam `YYYY-MM-DD` e os limites sao inclusivos. O resultado e ordenado por prazo e limitado a 500 itens.

```json
{
  "data": {
    "visao": "mes", "inicio": "2026-08-01", "fim": "2026-08-31",
    "itens": [{
      "fonte": "pendencia", "pendenciaId": 1, "eventoId": null,
      "id": 1, "titulo": "Enviar fatura", "tipo": "pendencia",
      "prioridade": "alta", "prazo": "2026-08-31T14:00:00",
      "status": "aberta", "descricao": null, "fim": null, "clienteId": 2,
      "ucId": null, "usinaId": null, "documentoId": null
    }]
  }
}
```

Para evento, `fonte` e `tipo` são `"evento"`, `eventoId` e `id` são o ID de `AgendaEvent`, `prazo` é o início e `fim` pode ser nulo. Financeiro e Rateio ainda são fontes futuras derivadas, sem duplicação do estado de origem.

### `POST /agenda/eventos`

Requer `pendencias.create` e aceita no máximo 30 requisições/minuto. Corpo: `{ "titulo": string, "inicio": "YYYY-MM-DDTHH:mm", "categoria"?: string, "descricao"?: string, "fim"?: "YYYY-MM-DDTHH:mm" }`. `titulo`, `inicio` e `categoria` (padrão `Operacional`) são obrigatórios; `fim` não pode ser anterior a `inicio`. Retorna o evento criado com `201`.

### `PUT /agenda/eventos/:id` e `DELETE /agenda/eventos/:id`

Requerem respectivamente `pendencias.update` e `pendencias.delete`, também limitados a 30 requisições/minuto. `PUT` usa o mesmo corpo do POST e substitui os campos do evento. `DELETE` cancela o evento (não o exclui fisicamente). IDs de outra empresa retornam `404`.

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

### `GET /rateio/formulario/preview?plantId=`
Leitura tenant-scoped para a revisão antes do download. Retorna a linha fixa da associação (`associacao`, ordem 1 e 0%), beneficiárias renumeradas a partir de 2, `somaPercentual` e `avisos` (inclusive expansão acima de 24 linhas). Não monta o XLSX.

### `POST /rateio/formulario/gerar-excel`
Body: `{ "plantId": number, "responsavelNome": string, "responsavelCpf": string, "linhas"?: [...], "excedenteEnergia": boolean }`. Gera o Formulário Copel no modelo oficial `backend/assets/formulario_copel_rateio.xlsx`; `linhas` preserva as edições somente visuais da revisão e `excedenteEnergia` preenche A11 (`NÃO` por padrão). **Resposta binária** (`application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`). A associação ocupa a primeira linha (0%), a tabela expande sem limite artificial e todos os merges/campos abaixo são deslocados. Bloqueia 400 para pré-requisito, Termo de Adesão ausente ou soma maior que 100%.

### `POST /rateio/formulario/gerar-termos`
Body: `{ "plantId": number }`. Baixa do Google Drive o Termo de Adesão de cada UC beneficiária (mesma ordem alfabética da tabela) e mescla num PDF único. **Resposta binária** (`application/pdf`). Bloqueia com 400 nas mesmas condições da rota acima.
Se o Google Drive/OAuth estiver indisponível, retorna 503 com mensagem clara; isso não invalida um formulário PDF já gerado.

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

`google_drive_root_folder_id` é a pasta raiz exclusiva da empresa autenticada para busca e documentos. Ao alterar essa chave, o cache do Drive da empresa é invalidado.

### `PUT /settings` — Body: `{ "chave": "valor", ... }` (uma ou mais chaves). Cria ou atualiza cada uma. `data` = objeto completo atualizado, igual ao `GET`.

As chaves de Rateio são tenant-scoped: `rateioBufferHabilitado`, `rateioBufferPercentual`, `rateioExigirDocumentoCnpj`, `rateioExigirDocumentoEstatuto` e `rateioExigirTermosAdesao`. As três últimas usam `"true"` por padrão; em `"false"`, a geração de formulário PDF/XLSX não bloqueia pela ausência do respectivo documento. A mesclagem de Termos continua exigindo arquivos reais, pois precisa baixá-los do Drive.

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

Fluxo de autorização de usuário real (PKCE). Depois de conectar e aprovar no Google, a conta ativa é usada diretamente, inclusive sua raiz do Drive — não há ID de pasta obrigatório. Contas ficam salvas em `GoogleAccount`, refresh token criptografado (nunca exposto em nenhum `to_dict`). Uma pasta raiz continua opcional para restringir o OAuth ou obrigatória para a service account compartilhada entre empresas.

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

## Credenciais de API (`/api-credentials`)

Credenciais de integrações pertencem à empresa autenticada e requerem `settings.read` para consulta ou `settings.update` para alteração. Providers iniciais: `resend`, `whatsapp`, `asaas` e `concessionaria`. O segredo é criptografado com `SECRET_ENCRYPTION_KEY` antes de persistir e **nunca** aparece em resposta, erro ou auditoria.

## WhatsApp Meta Cloud API (`/whatsapp`)

Uma integração Meta Cloud API por empresa. O token permanente fica somente em `ApiCredential` cifrada; `phoneNumberId` é globalmente único e identifica a empresa receptora do webhook.

### `GET|PUT|DELETE /whatsapp/integracao`

Consulta, salva ou remove a integração da empresa. `PUT` exige `settings.update`, com `{ phoneNumberId, businessAccountId, accessToken? , displayPhoneNumber?, enabled? }`; `accessToken` é obrigatório no primeiro cadastro e nunca retorna. `POST /whatsapp/integracao/testar` consulta a Meta sob ação explícita do usuário e atualiza somente os dados públicos do número.

### Conversas e mensagens

`GET /whatsapp/conversas` e `GET /whatsapp/conversas/<id>/mensagens` exigem `messages.read`; IDs de outra empresa retornam `404`. `POST /whatsapp/conversas` e `POST /whatsapp/conversas/<id>/mensagens` exigem `messages.send`; o segundo envia texto à Meta e registra `queued`, `sent` ou `failed` no histórico local.

### Templates Meta e webhook

`POST /whatsapp/templates/<id>/submeter` envia somente template WhatsApp `draft` ou `rejected` para aprovação da Meta. `POST /whatsapp/templates/sincronizar` reflete os status remotos. Ambos exigem `settings.update`.

`GET /webhooks/whatsapp` responde ao desafio de verificação com `META_WEBHOOK_VERIFY_TOKEN`. `POST /webhooks/whatsapp` é público, mas exige `X-Hub-Signature-256` validado por HMAC SHA-256 com `META_APP_SECRET`; mensagens e recibos são idempotentes pelo ID da Meta e resolvidos pelo `phone_number_id`, antes de persistir no tenant correto.

### `GET /api-credentials`

Lista as credenciais da empresa. Cada item tem somente `{ id, provider, nome, configurada, criadaEm, atualizadaEm }`.

### `POST /api-credentials`

Body obrigatório: `{ "provider": "resend", "nome": "Principal", "segredo": "..." }`. Retorna 201 com os metadados redigidos da credencial.

### `GET /api-credentials/<id>` · `PUT /api-credentials/<id>` · `DELETE /api-credentials/<id>`

`PUT` aceita `nome` e/ou `segredo`; omitir `segredo` preserva a cifra já gravada. Provider é imutável. IDs de outra empresa retornam 404. A exclusão não revoga nem chama o provedor externo.

### `POST /api-credentials/<id>/testar`

Para API keys Asaas, executa uma consulta autenticada a `/myAccount` usando a chave API cifrada selecionada para o ambiente ativo e retorna `{ "ok": true, "modo": "asaas-api", "provider": "asaas" }`, sem retornar a chave. Credenciais Asaas `webhook_token*` e os demais provedores executam somente dry-run local: verificam que a cifra existe e pode ser lida, sem fazer HTTP, e retornam `modo: "dry-run"`.

---

## Perfis de regra de cobrança (`/billing-rules`)

`GrupoRegraCobranca` é configuração comercial reutilizável. Não representa
assignment, regra já resolvida, cálculo executado ou cobrança emitida.

### `GET /billing-rules` · `GET /billing-rules/<id>`

Requer `billing_rules.read`, disponível às roles financeiras de leitura atuais
(`owner`, `admin`, `financial`, `operator`, `viewer`). Lista e consulta somente
o tenant autenticado; ID de outra empresa responde 404.

### `POST /billing-rules`

Requer `billing_rules.write` (`owner`, `admin`, `financial`). O tenant vem da
autenticação; `empresaId` não é aceito. Body:

```json
{
  "nome": "Associação 20%",
  "descricao": "Perfil reutilizável",
  "ativo": true,
  "padrao": false,
  "calculationMethod": "energia_compensada",
  "tariffSource": "manual",
  "manualTariff": "0.654321",
  "discountType": "percentage",
  "discountValue": "20.000000",
  "tariffBasis": "compensated",
  "energyComponentIndex": null,
  "billingMode": "auto",
  "dueDateBasis": "invoice_due_date",
  "dueDateOffsetDays": -2,
  "monthlyInterest": "1.000000",
  "finePercentage": "2.000000"
}
```

Decimals entram e saem como strings exatas. Campos enum usam os valores C0.
`energyComponentIndex` é obrigatório e não negativo apenas para
`tariffBasis=documented_component`. `ativo` defaulta `true`, `padrao` defaulta
`false`; os demais campos comerciais não recebem default implícito. Sucesso 201.

#### Extensão C4.1 — parâmetros comerciais

POST/PUT/PATCH aceitam também os objetos abaixo; GET os retorna juntamente com
os campos legados. Cada objeto aceita atualização parcial. Omissão preserva o
valor atual; `null` em um campo limpa esse campo. Objetos inteiros `null` e chaves
desconhecidas são recusados com 400. Nenhuma fórmula é executada.

```json
{
  "tariffConfiguration": {
    "companyTariff": "0.734821",
    "tariffHfp": "0.654321",
    "tariffHp": null
  },
  "billingModifiers": {
    "excludePisCofins": true,
    "icmsPolicy": "exclude",
    "excludeTariffFlag": true,
    "gracePeriod": {
      "enabled": true,
      "withoutDiscount": true,
      "durationMonths": 3,
      "start": null,
      "end": null
    },
    "recurringAdditionalCost": "12.345678"
  }
}
```

`companyTariff` é a tarifa comercial da empresa, alias de `manualTariff` (mesma
coluna `manual_tariff`). Se ambos forem enviados, devem ter valores iguais.
Pode coexistir com `tariffSource=invoice`: a referência documental é independente.
`tariffSource` permanece obrigatório por compatibilidade; `manual` ainda exige
tarifa empresa, mas não comanda mais o TariffSelector documental. Não significa
que a estratégia futura obrigatoriamente usará a referência como base matemática.
Tarifas e adicional recorrente usam Numeric(18,6); strings fora da capacidade ou
com precisão excedente são rejeitadas, sem arredondamento. Float JSON não é aceito.

| calculationMethod | Requisito confirmado (sem cálculo) |
|---|---|
| energia_compensada | Contrato legado preservado; base documental depende de F6. |
| economia_gerada | Legado preservado; fórmula pendente. |
| valor_total_fatura | Base futura é o total da concessionária, sem compensação; desconto explícito conforme discountType. |
| tarifa_fixa | Identificador legado preservado, sem conversão automática para outro método. |
| tarifa_fixa_com_desconto | companyTariff obrigatório; aceita `discountType=percentage` com `discountValue` (legado) ou `discountType=none` com `discountValue=null`. |
| tarifa_especifica | companyTariff obrigatório; não exige desconto adicional por inferência. |
| energia_recebida | Configurável sem tarifa obrigatória quando tariffSource=invoice; fórmula/dados exigidos pendentes. |

`tarifa_fixa_com_desconto` com desconto `none` permite configurar a regra sem
duplicar na regra o desconto cadastrado na UC. Na execução operacional C5.5,
`ConsumerUnit.desconto` é o percentual efetivo nos métodos compatíveis; vazio
significa sem desconto e valor inválido bloqueia com `UC_DISCOUNT_INVALID`, sem
snapshot. `tarifa_especifica` não aplica desconto adicional. O método
`tarifa_fixa_com_desconto` ainda retorna `unsupported_calculation_method` ao
executar. Não há fallback para o desconto antigo da regra. Regras legadas com percentual
permanecem preservadas. A migration `u5a8c3d7e2f9` amplia somente a constraint
estrutural e bloqueia downgrade se houver regra nesse novo estado.

`icmsPolicy` aceita `exclude` (**SEM ICMS**, decisão confirmada) ou `null` (não
configurado). Excluir ICMS não autoriza reconstruir tarifa nem selecionar coluna
documental por inferência. Flags novas aceitam boolean/null; null não equivale
a false. Desde C4.2, carência é política reutilizável: `durationMonths` aceita
inteiro positivo (até 2147483647) ou null, somente com `enabled=true`.
Null significa duração não configurada, sem herdar `ConsumerUnit.carencia_meses`.
`start`/`end` são campos **legados**, preservados na resposta para revisão; novos
valores não nulos retornam 400 `INVALID_BILLING_RULE`. Podem ser limpos juntos,
explicitamente, com null. Omissão preserva datas antigas e não as aplica a targets.
Regra com datas legadas bloqueia resolução interna com
`grace_policy_migration_required`, sem fallback inferior. PATCH descritivo continua
permitido; remover datas/alterar duração incrementa revision. Não há conversão
automática de intervalo antigo em duração nem em data da UC.
`inicioContrato` da UC é data contratual, não foi aprovado como início da carência
da instalação; não existe novo campo de UC nem origem temporal automática.
`tariffHp=null` permanece null, sem copiar HFP. O adicional é separado de juros,
multa, tarifa e desconto. Todos os novos campos persistidos começam null.

Mudanças efetivas em método, tarifa empresa, HP/HFP, modificadores, carência e
adicional incrementam revision uma vez por atualização; PATCH idêntico e mudanças
descritivas não incrementam. RBAC/tenant continuam os de C1. ResolvedBillingRule e
BillingRuleSnapshot transportam `tariff_configuration` e `billing_modifiers`,
com Decimal textual e datas ISO no snapshot, sem persistência em Fatura.
Na política de carência do snapshot C4.2 há `enabled`, `without_discount` e
`duration_months`, sem datas globais. Datas do target pertencem somente à memória
da execução futura, com origem auditável. Nenhum endpoint de cálculo foi criado.
Contrato interno C4.2: para Copel 1.3.0/danf3e/DANF3EA4B-V1.06, referência é a
soma das tarifas unitárias documentais de ENERGIA ELET CONSUMO e ENERGIA ELET USO
SISTEMA. CalculationMemory transporta concessionaria_reference_components com
valores textuais e rastreabilidade. Nenhuma coluna comercial/API recebe essa soma
automaticamente; companyTariff/manualTariff continuam tarifa da empresa.

**Contrato interno C5.1 (sem endpoint novo):** engine concreto em
`services/billing_calculation_engine.py`, com a assinatura C0
`calculate(*, invoice: InvoiceNormalized, rule: ResolvedBillingRule,
context: BillingCalculationContext) -> BillingCalculationResult`.
O contexto mantém IDs/competência/timestamp opcional, sem buscar sessão ou banco.
Invoice fornece BillingEnergyInput VALID e coerente com o contexto; regra vem do
RuleResolver. Somente energia_compensada executa: energia canônica × companyTariff,
menos desconto percentage (0..100 inclusivos) sobre o bruto, ou none com valor null.
TariffSource/TariffBasis não substituem energia canônica ou tarifa empresa.

Resultado reutiliza energy_base_kwh/energia_compensada_kwh, tariff_value,
gross_base, discount_amount e hub_amount. Só hub_amount recebe ROUND_HALF_UP em
centavos; bruto/desconto permanecem exatos. CalculationMemory ganha campos opcionais
discount_percentage, effective_company_tariff, net_amount_before_rounding e
monetary_rounding, mantendo energy_source/reference e company_tariff_used.
Decimal é serializado como string. BillingRuleSnapshot preserva parâmetros,
method e revision; calculation_version=1.0. Sem persistência em Fatura.

BillingCalculationError.code distingue invalid_context, required_energy_data_missing,
invalid_energy_input, invalid_company_tariff, invalid_discount,
unsupported_discount_type, unsupported_billing_configuration e
unsupported_calculation_method. Nenhum erro produz resultado financeiro.
Fixed, modificadores ativos, adicional configurado e HP/HFP configurados bloqueiam;
não há aplicação parcial. Juros/multa/vencimento/BillingMode ficam apenas no snapshot.

**Extensão interna C5.2:** mesmo motor/assinatura, agora também aceita
tarifa_fixa e tarifa_especifica. O parâmetro manual existente
TariffConfiguration.company_tariff (coluna manual_tariff; API
companyTariff/manualTariff) representa a tarifa configurada do método escolhido.
Não há novos aliases, campos de tarifa, fallback documental ou migration.
Fixa aplica none/percentage 0..100 sobre E×T; específica calcula E×T sem desconto.
E é exclusivamente a energia canônica VALID. Zero configurado é permitido;
ausência/negativo bloqueiam. Na específica, ausência já bloqueia no DTO C0.

CalculationMemory ganha `desconto_aplicado: bool | null` (nome novo em português):
false e discount_percentage=null na específica; true quando fixa usa percentage,
false para none. Na energia_compensada permanece null por compatibilidade.
Snapshot preserva o desconto originalmente configurado, mesmo não utilizado.
Demais campos e ROUND_HALF_UP somente no líquido final permanecem C5.1.
Nenhum endpoint/persistência; modificadores continuam bloqueados.
tarifa_fixa_com_desconto, valor_total_fatura, economia_gerada e energia_recebida
continuam unsupported_calculation_method, sem conversão automática entre enums.

**Contrato interno C5.3A (sem endpoint novo):**
`DocumentTariffResolver.resolve(invoice: InvoiceNormalized) -> ResolvedDocumentTariffs`
faz somente resolução documental. O resultado não é persistido nem incorporado ao
snapshot F7 nesta sprint.

```text
ResolvedDocumentTariffs
  full_tariff: ResolvedDocumentTariff | null
  compensation_tariff: ResolvedDocumentTariff | null
  compensation_tariff_events: ResolvedCompensationTariffEvent[]
  status: VALID | AMBIGUOUS | MISSING | UNSUPPORTED
  issues: TariffResolutionIssue[]

ResolvedDocumentTariff
  kind: full | compensation | unknown
  value: Decimal | null
  with_taxes: bool | null
  includes_flag: bool | null
  source_item_indexes: int[]
  confidence: Decimal | null
  status: VALID | AMBIGUOUS | MISSING | UNSUPPORTED
  issues: TariffResolutionIssue[]
  evidence: DocumentTariffEvidence[]

ResolvedCompensationTariffEvent
  identity: CompensacaoNormalizada
  te_tariff: Decimal | null
  tusd_tariff: Decimal | null
  combined_tariff: Decimal | null
  includes_flag: bool | null
  with_taxes: bool | null
  source_item_indexes: int[]
  confidence: Decimal | null
  status: VALID | AMBIGUOUS | MISSING | UNSUPPORTED
  issues: TariffResolutionIssue[]
  evidence: DocumentTariffEvidence[]
```

Cada evidência preserva valor/status, label, caminho/campo, source, confidence e
warnings do `ExtractedField`. Decimal serializa como string por `json_safe`; valor
só existe em status VALID. A confiança agregada é o mínimo quando todas as fontes
a informam; qualquer fonte sem confiança mantém o agregado null. Issues reutilizam
`ExtractionIssue` e incluem códigos canônicos de ausência, múltiplos candidatos,
divergência, bandeira e tributação ambíguas.

Tarifa cheia Copel reutiliza a soma C4.2 de tarifas unitárias de consumo + uso do
sistema. A compensação reutiliza `CompensacaoNormalizada` como identidade: somente
`OUTRA_UC + MESMO_POSTO` é cobrável, enquanto injeção própria/local permanece
auditável em `energy_components`. GD-I, GD-II e meses distintos geram eventos
separados; TE/TUSD da mesma identidade representam uma única quantidade física.

Um evento válido mantém compatibilidade com `compensation_tariff`. Múltiplos
eventos só produzem scalar comum quando TE, TUSD, tributação e bandeira são
semanticamente iguais. Tarifas diferentes mantêm o scalar null e os eventos VALID,
sem média ou escolha arbitrária. Duplicidade na mesma identidade e divergência
TE/TUSD permanecem bloqueadas. GD-III é UNSUPPORTED.

Ausência não usa a tarifa cheia como fallback. `preco_unitario_com_tributos`
apenas prova a variante tributada separada; não substitui `tarifa_unitaria` nem
deduz ICMS/PIS/COFINS. Bandeira separada pode provar `includes_flag=false`; sem
prova fica null. Não há acesso a regra/tarifa comercial, cálculo, banco, Flask,
Fatura, ASAAS ou migration. A seleção comercial é definida no contrato C5.3B
abaixo.

**Contrato interno C5.3B (sem endpoint novo):**
`CommercialTariffSelector.select(resolved_tariffs, rule) -> tuple[SelectedCommercialTariff, ...]`
faz somente a escolha comercial por evento e não calcula cobrança.

```text
SelectedCommercialTariff
  event: ResolvedCompensationTariffEvent
  source_kind: configured_fixed | configured_specific | document_full | document_compensation
  selected_tariff: Decimal | null
  document_full_tariff: Decimal | null
  document_compensation_tariff: Decimal | null
  includes_flag: bool | null
  with_taxes: bool | null
  status: VALID | AMBIGUOUS | MISSING | UNSUPPORTED
  issues: BillingCalculationIssue[]
  rule_snapshot: BillingRuleSnapshot
```

`tarifa_fixa` seleciona `company_tariff` como `configured_fixed` e
`tarifa_especifica` como `configured_specific`. Para `energia_compensada`,
`icms_policy=exclude` seleciona `event.combined_tariff` como
`document_compensation`; política null seleciona `full_tariff` como
`document_full`. Esse ramo exige `tariff_source=invoice`; regra manual não é
convertida em documental. Não há fallback entre fontes.

O seletor retorna um item por evento, sem tarifa média ou scalar artificial.
Evento não VALID não fornece `selected_tariff`. Bandeira exige igualdade
tri-state: política true requer `includes_flag=false`, política false requer
true e política null ignora o campo; evidência null bloqueia quando há exigência.
`with_taxes` é evidência transportada, sem lógica tributária. O snapshot preserva
identidade/revisão da regra. Não há cálculo, arredondamento, PIS/COFINS, Fio B,
persistência, endpoint ou migration.

**Contrato interno C5.4 (DONE; sem endpoint novo):**

`BillingModifiers.exclude_gdii_fio_b: bool | null` é exclusivamente em memória;
não é campo aceito ou retornado pela API persistida de grupos. O
`BillingRuleSnapshot` conserva seu valor, inclusive null.

`CommercialDeductionResolver.resolve(invoice=..., rule=..., evidence=())`
retorna `ResolvedCommercialDeductions`. `DocumentDeductionEvidence` liga tipo
`PIS|COFINS`, evento, `ExtractedField` monetário, índices/caminho de
origem e fatura/competência. `ResolvedCommercialDeduction` conserva tipo,
amount Decimal/null, applies_to_event, status canônico, índices, confiança,
issues e evidências. Totais `total_pis`, `total_cofins`, `total_pis_cofins` e
`total_fio_b` são Decimal quando válidos e null quando não resolvidos; regra
desativada produz zero. Não se utiliza o quadro tributário agregado como
evidência vinculada, nem diferenças de tarifas como Fio B. `DocumentDeductionEvidence`
aceita somente PIS/COFINS e `source=DOCUMENT`. A linha original precisa provar
tributo, base_calculo, aliquota, valor e identidade origin/period/gd_classification/
compensation_context/credit_month correspondente ao evento; todos são ExtractedField
com origem. Valor isolado não prova dedução. O resultado conserva `document_tax`
com o quadro fiscal vinculado. Ausência de base/alíquota bloqueia a dedução, mas
não a preservação auditável do valor fiscal global em `document_taxes`.

O engine concreto aceita argumentos opcionais `selected_tariffs`,
`deduction_evidence` e `fio_b_tariffs`, preservando chamadas C5.1/C5.2. O resultado acrescenta
`resolution_status`; bloqueio não fornece `hub_amount`. A memória acrescenta
`event_calculations`, `deduction_resolution`, `post_discount_amount`,
`post_pis_cofins_amount`, `pis_amount`, `cofins_amount`, `fio_b_amount`,
`fio_b_treatment` e `exclude_gdii_fio_b`; reutiliza `pis_cofins_amount`,
`pis_cofins_treatment`, `net_amount_before_rounding` e campos de desconto.
Ordem: bruto → desconto → PIS/COFINS → Fio B → piso zero → arredondamento final.
O líquido aritmético negativo permanece auditável antes do piso; a issue
`DEDUCOES_SUPERAM_VALOR_COBRAVEL` explica a cobrança final zero.

`CalculationMemory.document_taxes` contém `pis`/`cofins`: `source=DOCUMENT`,
`status=RESOLVED|MISSING_DATA|AMBIGUOUS`, base/rate/amount Decimal ou null,
`rate_unit=%` e evidência fiscal original. O quadro fiscal é preservado, inclusive
valores assinados e zero documental, sem cálculo por alíquota e sem dedução
integral/proporcional da compensação. Ausência de base/alíquota não invalida valor
documentado; duplicidade não escolhe candidato. Valores de dedução permanecem
separados em `pis_amount`/`cofins_amount` e exigem vínculo por evento.

`CalculationMemory.fio_b_components` e `ResolvedCommercialDeductions.fio_b_components`
preservam um resultado por evento canônico: `applicable`, `gd_classification`,
competencia, energy_kwh, tusd_fio_b_unit_tariff, tariff_source, transition_rate,
amount, regulatory_basis, evidence e status. O status é
`RESOLVED|NOT_APPLICABLE|UNSUPPORTED|MISSING_DATA|AMBIGUOUS`; amount é null
em todo estado diferente de RESOLVED. Estados financeiros agregados continuam
VALID/MISSING/UNSUPPORTED/AMBIGUOUS por compatibilidade. GD I é NOT_APPLICABLE;
GD III e anos fora de 2023–2028 são UNSUPPORTED. Taxas anuais: .15/.30/.45/.60/.75/.90.
Ano vem da competência da fatura, nunca do crédito nem do relógio do servidor.

`FioBResolver` resolve localmente a tarifa explicitamente documentada no campo
`tusd_fio_b_unit_tariff: ExtractedField` do item TUSD do próprio evento, conferida
contra o item original. Esse campo é contrato estruturado novo; o parser atual
não o extrai sem comprovação de layout. `tarifa_unitaria`/TUSD total não servem.
Na ausência do campo, `RegulatoryTariffRepository` fornece primeiro os
`RegulatoryFioBTariff` publicados na base regulatória; o dataset local versionado
`backend/data/regulatory_tariffs.json` é apenas fallback de compatibilidade fora
do contexto da aplicação. O argumento `fio_b_tariffs` permanece disponível para
registros já validados. Nenhuma fonte é consultada pela rede em runtime. O registro conserva componente,
unidade original/convertida, fonte, referência, id/hash da versão ANEEL, vigência
diária e mensal, distributor, subgroup, modality, unit_tariff (Decimal R$/kWh),
reference, version e dimensões opcionais
tariff_class/tariff_subclass/tariff_period. Todas as dimensões informadas exigem
correspondência documental exata em concessionaria/subgrupo_tarifario/
modalidade_tarifaria/classe_tarifaria/subclasse_tarifaria/posto_tarifario.
Múltiplos registros válidos ou documento ambíguo são AMBIGUOUS. Campo documental
inválido ou sem vínculo não substitui uma tarifa regulatória válida; sua evidência
permanece na auditoria. Sem registro, MISSING_DATA. A primeira linha oficial é
COPEL-DIS/TUSD_FioB da ANEEL Componentes Tarifárias 2026, Resolução Homologatória
3.592/2026: 214.53560037400001 R$/MWh, convertida exatamente para R$/kWh,
vigência 2026-06-24 a 2027-06-23. Como a competência é mensal, somente meses
integralmente contidos (2026-07 a 2027-05) resolvem; meses parciais não recebem
fallback. Atualização futura substitui/adiciona registros versionados após
validação, sem HTTP no cálculo.

Fórmula: quantidade canônica do evento GD II × tarifa TUSD Fio B × transição.
Sem arredondamento intermediário. O modificador `exclude_gdii_fio_b=true` deduz
a soma desses componentes após o desconto e as deduções PIS/COFINS vinculadas.
False/null mantém o cálculo comercial anterior; a auditoria continua disponível.
O tipo monetário legado `GDII_FIO_B` foi removido de `DocumentDeductionEvidence`;
Fio B utiliza exclusivamente tarifa/fórmula/enquadramento.
Em 2026-09-24, a importação CKAN `id=1` publicou 53 registros COPEL-DIS do recurso
`e8717aa8-2521-453f-bf16-fbb9a16eea39`, versão `2026-09-17T15:31:25.510600`, com
cobertura 2026-06-24 a 2027-06-23. A prova C5.4.4 usa B1/CONVENCIONAL/Residencial/
SCEE na competência 2026-09: `214.53560037400001 R$/MWh / Decimal(1000)` resulta
em `0.21453560037400001 R$/kWh`; 1000 kWh GD II (.60) resulta em
`128.721360224400006000` de Fio B e valor final `591.28`. A auditoria preserva
ANEEL, resource_id, versão, COPEL-DIS, valor/unidade original e vigência.
O suporte regulatório Copel está concluído para a vigência importada. PIS/COFINS
específico da compensação continua exigindo vínculo documental; GD III, 2029+,
configuração persistida Fio B e importação automática ANEEL não são implementados.

**C5.4.1 — Base tarifária ANEEL (DONE; operação manual):**

`GET /regulatory-tariffs/status` é somente leitura de plataforma e retorna estado,
quantidade, cobertura e última importação global. `POST /regulatory-tariffs/imports/preview`
recebe `arquivo` CSV e opcionalmente `sourceUrl`/`sourceVersion`; `POST
/regulatory-tariffs/imports/confirm` recebe `{ "previewId": number }`. As duas
as operações exigem `is_platform_admin`; owner/admin comum recebe 403. A prévia é
vinculada ao usuário de plataforma, expira e nunca publica tarifa. Confirmação de
outro usuário responde 404; replay/expiração/conflito retorna 409.
Uma base vazia retorna 200 com `status: "missing"`, zero registros, cobertura nula
e `lastImport: null`, mantendo a primeira importação disponível.
Se o banco regulatório estiver indisponível ou sem o schema necessário, o status
retorna 503; a UI distingue falta de permissão, indisponibilidade e erro interno.

`POST /regulatory-tariffs/imports/preview` aceita CSV de até 100 MiB
(`REGULATORY_TARIFF_MAX_BYTES`, em bytes) e retorna 413 quando excedido. O CSV é
processado em streaming, usado apenas no temporário privado da prévia e removido
antes da resposta; confirmação usa somente o plano persistido, vinculado ao mesmo
administrador de plataforma.

O CSV precisa ser UTF-8 e conter os campos ANEEL `SigNomeAgente`,
`DscComponenteTarifario`, `DscBaseTarifaria`, dimensões tarifárias, valor/unidade,
vigências e referência da resolução. Apenas `TUSD_FioB` + Tarifa de Aplicação +
SCEE + `R$/MWh` é normalizado a `TUSD_FIO_B` R$/kWh com Decimal. A chave natural
inclui distribuidora, dimensões e vigência; conteúdo idêntico é no-op e divergência
é conflito explícito. Dados publicados são globais, sem `empresa_id`.

`POST /regulatory-tariffs/imports/ckan/preview` recebe `{ "distributor": "COPEL-DIS", "year": 2026 }` e exige o mesmo `is_platform_admin`. O backend consulta exclusivamente o host HTTPS oficial configurado da ANEEL, descobre o recurso anual pelo metadata CKAN e usa filtros exatos para `COPEL-DIS`, `TUSD_FioB`, Tarifa de Aplicação, SCEE e `R$/MWh`. A resposta reutiliza integralmente `RegulatoryTariffPreview`; a confirmação continua em `POST /imports/confirm`. Falha de rede/timeout retorna 503, resposta CKAN inválida retorna 502 e nenhum endereço externo é recebido do navegador.

### C5.5 — Diagnóstico de cálculo

`GET /billing-calculations`, `GET /billing-calculations/invoices`,
`POST /billing-calculations/invoices/<id>/execute`, e detalhes de execução/snapshot
exigem respectivamente `billing_calculations.read` e `billing_calculations.execute`.
`GET /billing-calculations/invoices` aceita `page` (padrão 1), `pageSize`
(padrão 50, máximo 100), `q` (nome do cliente ou código da UC), `usinaId`,
`competencia`, `statusProcessamento` (extração ou validação),
`statusCobranca` (status ASAAS ou `sem_cobranca`) e `comPendencia=true|false`.
Os filtros são aplicados antes da paginação, sempre na empresa autenticada.
`data` permanece um array; a resposta acrescenta
`pagination: { page, pageSize, total, pages }`. Cada item inclui
`clienteNome`, `ucCodigo`, `usinas: [{ id, nome }]`,
`valorTotalConcessionaria`, `dataVencimento`, `documentoId`,
`documentoDisponivel`, `temPendencia` e `contextualCharges`, além dos campos
anteriores. `contextualCharges` é um array de zero ou mais
`{ id, statusInterno, asaasStatus, asaasId, valor, mesVencimento, boletoUrl }`
da mesma empresa, UC e competência. Valor e
vencimento podem ser nulos até a extração. `temPendencia` considera somente
pendência aberta vinculada à fatura original. A associação com cobranças
ASAAS por UC e competência é contextual; não existe vínculo persistido entre
os dois documentos, e pode haver várias cobranças no mesmo contexto.
`documentoDisponivel` não é uma URL de acesso; esta lista não concede
visualização ou download do PDF original.
As rotas administrativas equivalentes ficam sob
`/platform/empresas/<empresaId>/billing-calculations` e exigem
`is_platform_admin` com empresa explícita. O resultado nunca chama ASAAS.
Execuções são append-only; somente `CALCULATED` possui snapshot e valor final.
As outras situações retornam diagnóstico sem valor financeiro. A proteção SQL
PostgreSQL é validável opt-in com `TEST_POSTGRES_BILLING_URL` apontando a banco
isolado `test_*`; não usar banco compartilhado.

### C5.5-D — Laboratório isolado de PDFs

`POST /platform/billing-diagnostics/pdf` recebe multipart `arquivo`, exige
`is_platform_admin` e não aceita nem consulta empresa, cliente, UC ou fatura.
O retorno 200 é um diagnóstico técnico estruturado (`executionId`, `status`,
`extractionStatus`, `normalizationStatus`, `billingEligibility`, PDF, extração,
normalização, compensações, campos ausentes, warnings, blockers, 11 etapas,
duração e erro sanitizado), inclusive quando a análise termina em `ERROR`.
`billingEligibility.eligible` só é verdadeiro com energia compensada documental
confiável; consumo nunca preenche compensação.
Validação de PDF inválido retorna 400 e tamanho excedido 413; timeout retorna 504.
Não há cobrança, simulação financeira, snapshot, histórico persistido ou ASAAS.
O preflight CORS `OPTIONS` é respondido antes da autenticação; chamadas `POST`
reais continuam exigindo o token de platform admin.

### F6.1 — Pendência operacional de compensação GD

Após processamento persistente de uma fatura com UC validada, o backend pode criar
uma `Pendencia` de origem `GD_COMPENSATION_UNVERIFIED`. Ela é criada somente quando
uma `PlantConnection` tenant-scoped aponta para usina `Ativa`, com `data_ativacao`
anterior ou igual ao primeiro dia da competência, e a energia compensada não é
`VALID`. A unicidade `(empresa_id, fatura_concessionaria_id, origem)` impede
duplicidade por reprocessamento/concorrência. A resposta padrão de pendência passa
a expor `faturaId`; blocker, competência, status energético e usinas candidatas ficam
em `metadados`. O laboratório `/platform/billing-diagnostics/pdf` não cria essa
pendência.

### `PUT|PATCH /billing-rules/<id>`

Requer `billing_rules.write` e aceita atualização parcial do mesmo contrato.
Alteração financeira incrementa `revision`; desativação usa `{ "ativo": false }`.
Não há DELETE. Duas regras ativas/padrão na mesma empresa retornam 409 com
`DEFAULT_BILLING_RULE_CONFLICT`; estrutura inválida retorna 400 com
`INVALID_BILLING_RULE`. Desativar regra com assignment ativo na mesma empresa
retorna 409 `BILLING_RULE_IN_USE`; desative ou troque os vínculos antes.

---

## Assignments de regra de cobrança (`/billing-rule-assignments`)

`RegraCobrancaAssignment` associa explicitamente um `GrupoRegraCobranca` a um
target do tenant. `GrupoRegraCobranca.padrao` não cria nem substitui assignment
de escopo `company`.

### `GET /billing-rule-assignments` · `GET /billing-rule-assignments/<id>`

Requer `billing_rules.read` (`owner`, `admin`, `financial`, `operator`, `viewer`).
Lista e consulta somente a empresa autenticada; ID de outro tenant responde 404.
O GET de coleção aceita filtros `scopeType`, `clientId`, `consumerUnitId`,
`grupoRegraCobrancaId` e `ativo=true|false`.

### `POST /billing-rule-assignments`

Requer `billing_rules.write` (`owner`, `admin`, `financial`). O tenant vem da
autenticação e `empresaId` é recusado. Bodies suportados:

```json
{ "grupoRegraCobrancaId": 1, "scopeType": "company" }
```

```json
{ "grupoRegraCobrancaId": 2, "scopeType": "client", "clientId": 10 }
```

```json
{ "grupoRegraCobrancaId": 3, "scopeType": "consumer_unit", "consumerUnitId": 55 }
```

Grupo, Client e ConsumerUnit são procurados dentro do tenant. `company` não
aceita target; `client` exige somente `clientId`; `consumer_unit` exige somente
`consumerUnitId`. Grupo inativo não recebe novo assignment ativo. Sucesso 201;
estrutura inválida retorna 400 `INVALID_BILLING_RULE_ASSIGNMENT` e conflito de
assignment ativo para o mesmo target retorna 409 `BILLING_RULE_ASSIGNMENT_CONFLICT`.

### `PUT|PATCH /billing-rule-assignments/<id>`

Requer `billing_rules.write`. `{ "ativo": false }` desativa sem hard delete.
Alterar grupo/target de um assignment ativo desativa a linha anterior e cria uma
nova linha ativa atomicamente, preservando histórico. Histórico inativo não é
reescrito; sua reativação só é aceita sem mudar grupo/target e respeita grupo
ativo/unicidade. Não existe DELETE nem endpoint de resolução nesta sprint.

---

## Faturas (`/faturas`)

Todas as rotas autenticadas são isoladas pela empresa atual. `owner`, `admin` e `financial` podem emitir, sincronizar e cancelar; `operator` e `viewer` só leem. A credencial `provider='asaas'` é obtida da empresa atual e nunca retorna para o cliente.

### `GET /faturas?clienteId=&ucId=&status=&competencia=` · `GET /faturas/<id>`

Lista ou consulta a intenção/espelho local da cobrança ASAAS. IDs de outra empresa retornam 404.
Campos adicionais: `statusInterno` (`aguardando_emissao|emitida|erro_emissao|cancelada|null`),
`paymentProvider` (`asaas|null`) e `externalReference` (`string|null`). `asaasId` agora
aceita `null` antes da conclusão. Campos novos ficam nulos nos legados. `asaasStatus`
mantém o contrato/default `pending`, mas só representa confirmação remota quando
`asaasId` está presente. Nenhum segredo, hash do comando ou cabeçalho ASAAS é retornado.

### `POST /faturas`

Emite boleto ASAAS. Body preservado: `{ "clienteId": 1, "ucId": 2, "valor": 284.90, "mesVencimento": "2026-10-05", "competencia": "2026-09" }`.
Cliente/UC devem ser IDs inteiros positivos da empresa atual, e a UC deve pertencer
ao cliente. Valor finito/positivo dentro de `Numeric(10,2)` e competência `YYYY-MM`
válida são exigidos. Tenant e permissão do ator são validados também pelo service.

B1 confirma intenção local `aguardando_emissao`, referência UUID e chave do comando
antes do ASAAS. A identidade é empresa + cliente + UC + competência + valor
normalizado a centavos + vencimento; `10`, `10.0` e `10.00` identificam o mesmo valor.
Retry idêntico (inclusive após cancelamento) recupera o mesmo registro, sem nova
Fatura/pagamento. Outra versão explícita é escopo futuro. Não há header novo obrigatório.

Sucesso mantém `201` e a Fatura, inclusive em retry resolvido. Resultado ambíguo
retorna `409`, `code: "EMISSAO_PENDENTE"`, `details: { "faturaId": N }` e mensagem
para repetir o mesmo comando. A intenção fica disponível no GET. Após tentativa
de POST remoto, retries somente conciliam por referência, nunca reenviam pagamentos
com base apenas em resposta vazia. Falhas de validação/provider permanecem `400`;
falta de permissão retorna `403`. Não enviar comando alterado para contornar ambiguidade.

### `POST /faturas/<id>/sincronizar` · `POST /faturas/<id>/cancelar`

Consulta ou cancela a cobrança no ASAAS e atualiza o espelho local; não há edição ou exclusão física.
Sem `asaasId`, sincronizar tenta somente conciliação por referência e cancelar
retorna `409 EMISSAO_PENDENTE`. A consulta pode retornar `503` se o provider estiver
indisponível/divergente. Essas ações nunca criam pagamento remoto.

### `GET /faturas/resumo`

Retorna contagens locais por `pending`, `received`, `overdue` e `canceled`, apenas
para registros com `asaasId`. Intenções ainda não emitidas não entram nessas contagens.

### `POST /webhooks/asaas`

Pública, sem Bearer. Body ASAAS: `{ "id": "evt_...", "event": "PAYMENT_RECEIVED", "payment": { "id": "pay_...", "externalReference": "hub-...", "status": "RECEIVED" } }`.
`id` do envelope é a identidade do evento (não o ID do pagamento); aceita IDs ASAAS com `&`.
Campos adicionais são tolerados, sem persistência do payload completo.

Resolve uma única Fatura por `externalReference`, ou por `payment.id` como fallback
não ambíguo. Referências contraditórias são rejeitadas; legados sem referência local
podem usar o ID remoto único. A empresa vem da Fatura, nunca do body/header do cliente.
Exige `asaas-access-token` comparado constant-time com `ApiCredential` da empresa,
`provider=asaas`, `nome=webhook_token_sandbox` ou `webhook_token_producao`.
O ambiente segue `ASAAS_API_BASE_URL`, compartilhado pela instalação como na B1.
`ASAAS_WEBHOOK_TOKEN` global não autentica mais esta rota.

- `200`: `{ "success": true, "message": "...", "data": { "received": true } }`,
  tanto na primeira aplicação quanto em reentrega autenticada do mesmo evento.
- `400`: estrutura/identificadores/campos consumidos inválidos.
- `401`: token inválido/ausente, configuração indisponível, cobrança inexistente,
  ambígua ou identificadores conflitantes; mesma mensagem genérica, sem tenant/IDs.
- `409`: colisão do ID de evento com outro alvo/tipo ou conflito de processamento.
- `422`: evento/status não suportado pelo espelho atual; nenhum efeito/ledger concluído.
- `503`: falha de persistência; rollback permite reentrega.

`payment_webhook_events` tem unicidade global `(provider,event_id)`. Registro,
alteração da Fatura e `processed_at` compartilham um único commit. Duplicatas não
alteram `updated_at`, não reaplicam status/URLs nem repetem efeitos. `status_interno`,
reservas e `asaas_id` permanecem sob responsabilidade da emissão/reconciliação B1.
Eventos e estados aceitos e configuração operacional: `FATURAS.md`, seção B2.

Credenciais ASAAS: preferir `api_key_sandbox`/`api_key_producao`; nomes livres antigos
continuam fallback para a API, excluindo nomes reservados de chave/token. O teste
de `webhook_token*` no CRUD existente retorna `modo=dry-run`, sem chamada externa;
não comprova configuração no ASAAS. Nenhum novo endpoint de credenciais.

---

## Importações (`/importacoes`)

`GET /importacoes/modelo` é público (sem login) e baixa `HUB_Modelo_Importacao.xlsx`, sem cadastros de exemplo. O arquivo versionado em `backend/templates/` define os cabeçalhos, estilos e listas; o download preserva `Instrucoes`, `Clientes`, `UCs` e `Usinas`, com preenchimento a partir da linha 2.

`GET /importacoes/exportar` requer `imports.preview` e exporta somente a empresa autenticada, usando o mesmo modelo e todos os campos nele previstos, incluindo nascimento. Strings são gravadas como texto, nunca como fórmulas. Não é backup completo: campos fora do modelo e conexões de rateio não são exportados.

O preview aceita a aba auxiliar `Instrucoes` (não importada), os cabeçalhos exatos do modelo inclusive `(opcional)`, além dos nomes legados. Linhas vazias são ignoradas. Dias de emissão devem ser inteiros de 1 a 31. Importação continua somente criação: reimportar dados existentes causa conflito; UCs referenciam CPF de cliente criado no mesmo arquivo.

`POST /importacoes/preview` recebe `arquivo` (CSV UTF-8 com `tipo=clientes|ucs|usinas`, ou XLSX com abas `Clientes`, `UCs`, `Usinas`) e requer `imports.preview`. Não cria entidades: persiste um plano tenant/user-scoped com hash e TTL de 20 minutos. Planos expirados, que podem conter PII, são removidos antes de preview/confirmação e pela rotina global `flask purge-import-previews`. Limites: 10 MB, 10 mil linhas, 80 colunas, células de até 2.000 caracteres e três abas; fórmulas/injeção de planilha (`=`, `+`, `-`, `@`), XLSM e ZIP suspeito são rejeitados. A auditoria registra somente empresa, usuário, hash, contagens e resultado — nunca conteúdo de células.

`POST /importacoes/<previewId>/confirmar` requer `imports.commit`, revalida empresa, usuário, expiração e replay e cria Clientes, UCs e Usinas numa única transação. Qualquer conflito/erro faz rollback total. Esta versão é somente criação e não cria conexões UC–usina.

---

## Empresa atual (`/empresas/atual`)

### `GET /empresas/atual`

Requer `empresa.read`. Retorna apenas os dados cadastrais da empresa do usuário autenticado: `{ nome, razaoSocial, cnpj, email, telefone }`. Não expõe nem aceita troca de `id`, `empresa_id`, `slug` ou `status`.

### `PUT /empresas/atual`

Requer `empresa.update` (owner ou admin). Aceita atualização parcial de `nome`, `razaoSocial`, `cnpj`, `email` e `telefone`; `nome` é obrigatório quando enviado, CNPJ deve conter 14 dígitos e e-mail deve ser válido. Campos protegidos ou desconhecidos retornam 400. A rota sempre atua na empresa da sessão, sem aceitar identificador no body ou na URL.

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
