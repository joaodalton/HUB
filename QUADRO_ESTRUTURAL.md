# QUADRO_ESTRUTURAL.md

> Análise git da evolução estrutural do backend — o que entrou, o que saiu,
> os erros que motivaram cada mudança e o estado atual. Atualizado a cada
> sessão relevante; não é log de commits, é o *porquê* por trás deles.

## Status do repositório

```
develop  →  origin/develop
HEAD     →  ec0bf41 (local, develop)
branch   →  develop (tracking origin/develop)
```

Commits mais recentes na linha atual (develop, topo → base):

| commit | autor | mensagem | data |
|--------|-------|----------|------|
| ec0bf41 | joaodalton | Acho que reverteu tudo antes do plano do hermes, mas manteve o auth e o pendencia_servie | 2026-08-27 |
| 01ba8ac | joaodalton | edição minima no frontend | 2026-08-27 |
| c7f5d29 | joaodalton | Corrigi finalmente o erro do multitenant dar errado quando eu mudava de usina, agora finalmente deu certo essa porcaria, tbm tem o arquivo da pendencia | 2026-08-27 |
| b6648b0 | joaodalton | feat: multitenant, páginas clientes/plantas/ucs/usuários e início de faturas | 2026-08-26 |
| 3db5bdd | joaodalton | TESTE COM O CLAUDE CODE 20x QUE A KPA DISPONIBILIZOU DURANTE 15MIN, FOI TUDO ISSO QUE FOI FEITO. NECESSARIO A REVISAO DE TUDO POSTERIORMENTE | 2026-08-17 |
| a291ed1 | joaodalton | Bug com o multi-Tenant pois se uma pessoa usar o query.get ou o super().get poderia ver as outras empresas e as infos delas | 2026-08-18 |
| ec0bf41 | (develop atual) | HEAD local sobre develop | 2026-08-27 |

> `ec0bf41` é o commit que reverteu a maioria das mudanças de `b6648b0` mas manteve
> o auth e o `pendencia_service`. O diff `b6648b0 → ec0bf41` mostra 78.905 linhas
> removidas e 1.454 adicionadas — é a reversão documentada abaixo.

---

## Commit por commit — o que mudou e por quê

### 3db5bdd — "TESTE COM O CLAUDE CODE 20x..."

```
Data: 2026-08-17
Arquivos: 46 | +4104 / -579
```

**O que entrou:** primeira versão completa do multi-tenant estrutural:
- `backend/extensions.py` com `TenantMixin`, `TenantQuery`, `TenantSession` e o listener `do_orm_execute`
- `backend/services/permission_service.py` (306 linhas) — sistema de permissões por papel
- `backend/services/automacao_service.py` (479 linhas) — regras automáticas de pendências
- `backend/models/pendencia.py` com `PendenciaComentario`
- Migrations multi-tenant: `multi_tenant_v1.py` (172 linhas)
- Seed `backend/scripts/criar_empresa.py` e scripts de platform admin
- Frontend: páginas Clients, Plants, UCs, Users, Pendencias com estilos completos
- `API_CONTRACTS.md`, `SPRINT_01.md`, `SPRINT_02.md`, `PROGRESS.md` inicializados
- `backend/tests/` com conftest e testes de auth/empresas/multitenant

**Erros conhecidos nesse commit:**
- `99d751e` (um commit antes) admitia: "Inicio do multi-trenant, mas esta com uns bugs no app.py e no user_service" — o commit que introduz o multi-tenant já vinha com bugs.
- `a291ed1` (commit seguinte) admite o bug de segurança: `query.get()` e `super().get()` ignoram o filtro de tenant e podem vazar dados entre empresas.

**Motivo da reversão parcial (ec0bf41):**
Esse commit foi feito em sessão "TESTE COM CLAUDE CODE 20x" — 20 agentes autônomos rodando em 15 minutos. O autor explica na mensagem: "FOI TUDO ISSO QUE FOI FEITO. NECESSARIO A REVISAO DE TUDO POSTERIORMENTE". Não era produção-ready — era um pullback para revisar. O ec0bf41 reverteu o que não estava validado, mas manteve o auth e pendencia_service que já estavam funcionando.

---

### a291ed1 — Bug de multi-Tenant (query.get bypass)

```
Data: 2026-08-18
Arquivos: 16 | +307 / -45
```

**O erro:**
> "Bug com o multi-Tenant pois se uma pessoa usar o query.get ou o super().get
> poderia ver as outras empresas e as infos delas, oq é perigoso para o saas."

O `TenantMixin` injeta o filtro `empresa_id` via listener `do_orm_execute`, que só intercepta `SELECT`s. Mas `Query.get()` e `Session.get()` podem devolver instâncias do identity map sem emitir SELECT — bypassando o filtro.

**O que entrou:**
- `TenantQuery` (subclasse de `Query`) — transforma `.get()` em consulta explícita com filtro de tenant para modelos com `TenantMixin`
- `TenantSession` (subclasse de `Session`) — protege `db.session.get()` com o mesmo raciocínio
- `db = SQLAlchemy(query_class=TenantQuery, session_options={'class_': TenantSession})`
- `backend/scripts/tornar_platform_admin.py` — script administrativo para conceder `is_platform_admin`
- Rota de platform admin em `empresa_routes.py`, decorator `require_permission`, `is_platform_admin` no model `User`

**O que saiu/alterado:**
- `backend/extensions.py` foi refeito inteiro (de ~80 linhas para ~140) — `TenantMixin` agora é mais robusto
- `backend/models/user.py` ganhou `is_platform_admin = db.Column(db.Boolean, nullable=False, default=False)`
- `backend/routes/auth_routes.py` ajustado para usar `is_platform_admin`
- `backend/utils/auth.py` atualizado

**Causa raiz:** O SQLAlchemy `identity map` cacheia objetos carregados. Se um objeto de empresa A foi carregado numa request, numa request seguinte o `Session.get()` retorna o objeto do cache sem consultar o banco — e o listener `do_orm_execute` não é acionado. Isso quebra o isolamento multi-tenant.

**Resumo técnico:** O listener `do_orm_execute` filtra todo SELECT. Mas `Session.get(id)` primeiro olha no identity map; se o objeto já estiver lá (de uma query anterior na mesma sessão), ele devolve sem emitir SELECT, sem passar pelo filtro. `TenantSession.get()` resolve isso forçando uma query explícita com `empresa_id` para modelos com `TenantMixin`.

---

### b6648b0 — feat: multitenant, páginas e faturas

```
Data: 2026-08-26
Arquivos: 78 (filtrado: sem obsidian/frontend) | +massivo / -833
```

**O que entrou:**
- `backend/models/fatura.py` — modelo de fatura (ASAAS, valor, competência, vencimento)
- `backend/services/fatura_service.py` (220 linhas) — servico de faturas
- `backend/routes/fatura_routes.py` (88 linhas) — CRUD de faturas
- `backend/routes/empresa_routes.py` completamente alterado (~295 linhas modificadas)
- `backend/services/empresa_service.py` com `update_empresa`
- `backend/integrations/asaas_client.py` (137 linhas) — integração ASAAS
- `backend/integrations/resend_client.py` (42 linhas) — integração Resend
- `backend/routes/bulk_import_export_routes.py` (82 linhas) — import/export em lote
- `backend/services/bulk_import_export_service.py` (302 linhas)
- `backend/migrations/versions/ae38ae40f4a9_add_faturas.py` (58 linhas) — cria tabela `faturas`
- `backend/test_bulk_endpoints.py`, `backend/test_debug_oauth.py`
- Frontend: páginas FaturasPage, EmpresasPage, serviços de fatura/empresa, styles

**Como o extensions.py chegou até aqui:**
O b6648b0 não alterou o `extensions.py` — ele herdou o estado do c7f5d29 (que herdava o a291ed1).
O extensions.py com `TenantQuery` + `TenantSession` foi introduzido em a291ed1 e permaneceu.

**O que o ec0bf41 reverteu desse commit:**
Tudo que não era auth ou pendencia_service — faturas, ASAAS, Resend, bulk import/export,
empresa_routes.py (voltou ao estado anterior), routes/fatura_routes.py, models/fatura.py,
services/fatura_service.py, integrations/, migrations/ae38ae40f4a9 (arquivo apagado do repo,
mas o banco ainda referencia ele — ver seção abaixo).

---

### c7f5d29 — "Corregi finalmente o erro do multitenant..."

```
Data: 2026-08-27
Arquivos: 2 | +109 / -18
```

**O erro corrigido:**
O multi-tenant estava "dando errado quando mudava de usina" — ou seja, ao navegar entre
usinas/empresas, o filtro de tenant não estava sendo aplicado corretamente em algumas
consultas, vazando dados ou retornando vazio.

**O que mudou:**
- `backend/services/pendencia_service.py` — 115 linhas modificadas (bulk de código de
  criação/validação de pendências)
- `backend/utils/auth.py` — 12 linhas (ajuste no middleware de auth, `g.current_empresa_id`)

**Motivo da mudança:**
O middleware de auth não estava setando `g.current_empresa_id` corretamente em todas
as rotas, ou o listener `do_orm_execute` não estava filtrando porque `g.current_empresa_id`
era None quando não deveria. O diff mostra trabalho pesado no `pendencia_service.py`
para validar referências cruzadas de tenant (cliente, UC, usina, documento pertencem à
mesma empresa) e no `auth.py` para corrigir a propagação do contexto.

---

### ec0bf41 — "Acho que reverteu tudo antes do plano do hermes..."

```
Data: 2026-08-27
Arquivos: 89 | +1345 / -78887
```

**O que foi revertido (detalhado):**

| Arquivo | O que era | Status após reversão |
|---------|-----------|---------------------|
| `backend/migrations/versions/ae38ae40f4a9_add_faturas.py` | Migration que cria tabela `faturas` | **Apagado do repo** (arquivo removido, mas o banco pode ainda estar nessa versão — causou o problema que resolvemos na sessão atual) |
| `backend/models/fatura.py` | Modelo Fatura | Apagado |
| `backend/services/fatura_service.py` | Serviço de faturas | Apagado |
| `backend/routes/fatura_routes.py` | CRUD de faturas | Apagado |
| `backend/integrations/asaas_client.py` | Cliente ASAAS | Apagado |
| `backend/integrations/resend_client.py` | Cliente Resend | Apagado |
| `backend/routes/bulk_import_export_routes.py` | Rotas bulk | Apagado |
| `backend/services/bulk_import_export_service.py` | Serviço bulk | Apagado |
| `backend/routes/empresa_routes.py` | Versão nova (~295 linhas) | Revertido para versão anterior (qual a que tinha antes do b6648b0) |
| `backend/services/empresa_service.py` | Versão com `update_empresa` | Revertido (perdeu o `update_empresa`) |
| `backend/test_bulk_endpoints.py`, `backend/test_debug_oauth.py` | Testes | Apagados |
| Frontend: FaturasPage, EmpresasPage, serviços de fatura/empresa | Telas e services | Revertidos/apagados |

**O que foi mantido (não revertido):**
- `backend/services/pendencia_service.py` — permanece (é o coração do sistema de pendências)
- `backend/utils/auth.py` — permanece (middleware de auth com `g.current_empresa_id`)
- `backend/routes/auth_routes.py` — permanece (login, bootstrap, password reset)
- `backend/models/user.py` — permanece (com `is_platform_admin`)
- `backend/extensions.py` — **não foi revertido totalmente**. O diff mostra `-25 linhas` no extensions.py — significa que as subclasses `TenantQuery` e `TenantSession` foram removidas, mas o `TenantMixin` e o listener `do_orm_execute` permaneceram. Veja o estado atual abaixo.

**O que entrou (não estava antes):**
- `backend/routes/platform_routes.py` (52 linhas) — rotas de platform admin
- `backend/test_path_impersonation.py` (351 linhas) — teste de segurança contra path traversal/impersonação
- `security_test.py` (299 linhas) — teste de segurança geral
- `list_security_issues.py` (97 linhas) — script de auditoria de segurança
- `push_to_github.py` (68 linhas) — script de push (provavelmente autenticado com token)

---

## O problema da migration `ae38ae40f4a9`

**O que aconteceu:**
1. b6648b0 criou `backend/migrations/versions/ae38ae40f4a9_add_faturas.py` e aplicou no banco.
2. ec0bf41 apagou o arquivo da migration do repo (pois as faturas foram revertidas).
3. Mas o banco de desenvolvimento ainda estaria na versão `ae38ae40f4a9` — o Alembic registra a versão aplicada na tabela `alembic_version`, e o arquivo da migration sumiu do filesystem.
4. Resultado: o Alembic não consegue achar a migration para fazer downgrade ou upgrade — erro "revision not found" ou "multiple heads" (porque a cadeia de head quebrou quando o arquivo sumiu).

**Como se manifesta:**
- `flask db current` ou `flask db upgrade` falham com erro de revision inexistente
- O banco pode estar em uma versão que o repo não tem mais o arquivo correspondente
- Outras migrations novas (como a nossa `a2c8f4e1b9d6`) podem criar "multiple heads" no Alembic porque a cadeia está quebrada

**Estado atual (após nossa correção na sessão de hoje):**
- Reconstruímos o arquivo `ae38ae40f4a9_add_faturas.py` a partir do blob do git (commit b6648b0)
- Corrigimos o `down_revision` da nossa migration de `multi_tenant_v1` para `c9190fb66b9f` (o head real da cadeia)
- Fazemos downgrade para `c9190fb66b9f` (derruba tabela faturas, volta ao estado sem faturas)
- Aplicamos `a2c8f4e1b9d6` (nossa migration de documentos fixos)
- Removemos o arquivo reconstruído de `ae38ae40f4a9` (deixando apenas a nossa migration como head única)

---

## O extensions.py — estado após os 3 commits de multi-tenant

**Estado atual confirmado (lei o arquivo em 2026-08-28):**

```
backend/extensions.py (43 linhas, timestamp 2026-08-28):
- Tem TenantMixin? SIM (linha 14-25)
- Tem listener do_orm_execute? SIM (linha 28-43)
- Tem TenantQuery? NÃO — removido pelo ec0bf41
- Tem TenantSession? NÃO — removido pelo ec0bf41
- db = SQLAlchemy(query_class=..., session_options=...)? NÃO
  → é db = SQLAlchemy() simples (linha 9)
```

O extensions.py atual é exatamente a versão "somente TenantMixin + do_orm_execute".
As subclasses `TenantQuery` e `TenantSession` (que protegem contra o bypass do
identity map) **foram removidas** pelo ec0bf41.

**Consequência:** A mitigação estrutural contra vazamento de dados entre empresas
via SELECTs é mantida (99% do caso, inclui lazy-load de relacionamentos), mas a
brecha do identity map voltou — `Session.get(id)` e `Query.get(id)` podem devolver
objetos de outra empresa se estiverem no cache. O authorship aceita esse risco como
"hotfix vs. trabalho de sprint separado, com teste dedicado antes de ir pra frente".

**Evolutivo do extensions.py pelos commits:**

| commit | o que fez no extensions.py |
|--------|---------------------------|
| 3db5bdd | Introduziu `TenantMixin`, listener `do_orm_execute`, provavelmente `TenantQuery`/`TenantSession` iniciais |
| a291ed1 | Adicionou/refineu `TenantQuery` e `TenantSession` para proteger `Query.get()` e `Session.get()` do bypass do identity map |
| c7f5d29 | Ajustou o middleware de auth para garantir `g.current_empresa_id` sempre setado (não alterou extensions.py diretamente, mas afeta seu comportamento) |
| ec0bf41 | Removeu `TenantQuery` e `TenantSession`, manteve só `TenantMixin` + listener `do_orm_execute` (43 linhas finais) |

---

## Resumo dos erros que motivaram as mudanças

| Erro | Commit que resolveu | Symptoma | Causa | Solução |
|------|---------------------|----------|-------|---------|
| Multi-tenant não isola dados entre empresas | a291ed1 | `User.query.get(id)` de uma empresa devolve usuário de outra empresa via identity map | `Session.get()` bypassa o listener `do_orm_execute` porque não emite SELECT | `TenantSession.get()` e `TenantQuery.get()` forçam query explícita com `empresa_id` (depois removidos no ec0bf41) |
| Multi-tenant quebra ao mudar de usina | c7f5d29 | Ao navegar entre usinas, dados vazam ou aparecem vazios | `g.current_empresa_id` não estava sendo setado corretamente em todas as rotas, ou listener não filtrava | Ajuste no `auth.py` (middleware) + validação de referências cruzadas no `pendencia_service.py` |
| Faturas revertidas, migration sumida do repo | ec0bf41 (reverteu b6648b0) | Após reversão, banco ainda referencia migration `ae38ae40f4a9` que não existe mais no filesystem | Reversão apagou o arquivo mas não desafiou o banco | Reconstruir arquivo da migration (do git), fazer downgrade, corrigir `down_revision` das novas migrations |
| Multiple heads no Alembic | Consequência da migração sumida + nossa migration nova | `flask db upgrade` falha com "multiple heads" ou "revision not found" | Cadeia quebrada quando o arquivo da migration sumiu | Reconstituir arquivo, alinhar `down_revision` ao head corrente, fazer downgrade + upgrade |

---

## O que ficou, o que foi removido (estado atual do repo vs. b6648b0)

### O que **não existe mais** no repo (foi revertido pelo ec0bf41):

- Módulo de Faturas (`models/fatura.py`, `services/fatura_service.py`, `routes/fatura_routes.py`)
- Integrações: ASAAS (`integrations/asaas_client.py`), Resend (`integrations/resend_client.py`)
- Bulk import/export (`routes/bulk_import_export_routes.py` + `services/bulk_import_export_service.py`)
- `migrations/ae38ae40f4a9_add_faturas.py` (arquivo removido — mas banco pode estar nessa versão)
- Frontend: `FaturasPage`, versão nova de `EmpresasPage` (voltou ao estado anterior), serviços de fatura
- Testes: `test_bulk_endpoints.py`, `test_debug_oauth.py`

### O que **permanece** e está funcionando:

- Auth completo (`routes/auth_routes.py`, `utils/auth.py`, `models/user.py` com `is_platform_admin`)
- Pendencias (`services/pendencia_service.py`, `models/pendencia.py`, `routes/pendencia_routes.py`)
- Multi-tenant estrutural no `extensions.py` (TenantMixin + do_orm_execute — sem TenantQuery/TenantSession)
- Permissões (`services/permission_service.py`)
- Automação de pendências (`services/automacao_service.py`)
- Rateio (`services/rateio_service.py`, `routes/rateio_routes.py`)
- Documentos (`services/document_service.py`, `routes/document_routes.py`)
- Clientes, UCs, Usinas (models + services + routes)

---

## Estado atual — o que precisamos vigiar

1. **extensions.py sem TenantQuery/TenantSession**: A brecha do identity map voltou.
   `Session.get(id)` e `Query.get(id)` podem devolver objetos de outra empresa se
   estiverem no cache do SQLAlchemy. A causa: o SQLAlchemy usa identity map por sessão;
   se um objeto foi carregado em uma request anterior (mesma sessão DB), o `Session.get(id)`
   devolve o objeto do cache sem emitir SELECT, sem passar pelo listener `do_orm_execute`.
   É um risco real, mas foi aceito como trade-off. Pra fechar, seria necessário reaproveitar
   `TenantQuery` e `TenantSession` do a291ed1 — mas é mudança arquitetural de risco, não
   hotfix.

2. **Migration `ae38ae40f4a9` sumida**: O arquivo não existe mais no repo (apagado pelo ec0bf41).
   Qualquer pessoa que clone o repo e tente rodar `flask db upgrade` sobre um banco que já
   aplicou essa migration vai encontrar erro. Nossa sessão reconstruiu o arquivo
   temporariamente para resolver, mas o repositório oficial dele continua sem o arquivo.

3. **Múltiplos heads no Alembic**: Se houver duas heads (porque a migration sumida criou
   uma bifurcação na cadeia), o `flask db upgrade head` vai falhar. Precisa ser resolvido
   com merge das heads ou downgrade para uma delas.

4. **`empresa_routes.py` revertido**: Foi revertido para o estado anterior ao b6648b0.
   Se o frontend espera endpoints que só existiam na versão do b6648b0 (como endpoints de
   atualização de empresa), eles vão quebrar.

---

*Documento gerado em 2026-08-28 a partir de análise git. Atualizar com os próximos
commits relevantes.*
