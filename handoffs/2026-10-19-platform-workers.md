# Platform Workers — handoff

> Gerado em 2026-10-19. Branch: `feat/b2-object-storage-endpoint`. HEAD: `9228c32`. Mesclado local (sem push).

## O que foi feito

Novo nivel de acesso global `platform_worker` — view-only em qualquer empresa (fiscalizacao interna / demo pra investidor), nunca escreve nada. Mais a pagina "Funcionarios" (admin-only) pra criar/listar/revogar essas contas.

- **Spec**: `docs/superpowers/specs/2026-10-18-platform-workers-design.md`
- **Plano**: `docs/superpowers/plans/2026-10-18-platform-workers.md`
- **8 commits de implementacao** (TDD, review por task) + **2 commits de correcao** achados em review:
  - `964838d` feat: add is_platform_worker flag to User
  - `7183c36` feat: add platform_worker read-only bypass to RBAC
  - `8c8bfed` fix: update stale alembic head assertions to x1b4f8c2d9e7 *(regressao achada em review, nao prevista no plano)*
  - `e584739` feat: let platform_worker enter companies read-only, block writes globally
  - `0204154` test: worker entrar/sair switches to a second company
  - `c720faa` feat: allow platform_worker to read platform overview and company list
  - `0c7aacd` feat: admin-only funcionarios CRUD for platform_worker accounts
  - `ae4966e` test: confirm /auth/me exposes isPlatformWorker
  - `cd203c2` / `96920e6` feat+fix: add Funcionarios page for platform_worker management
  - `5a1f26f` feat: route platform_worker into the platform shell read-only
  - `880fb28` fix: add Funcionarios nav link to platform shell for admins *(gap do plano, nao coberto por nenhuma task)*
  - `9228c32` fix: resolve platform_worker deadlock, logout, visibility and audit leak *(achado no review final de branch — ver abaixo)*

## Arquivos principais tocados

- `backend/models/user.py`, `backend/migrations/versions/x1b4f8c2d9e7_add_platform_worker_flag.py`
- `backend/services/permission_service.py`, `backend/utils/auth.py`
- `backend/routes/platform_routes.py`, `backend/routes/platform_worker_routes.py` (novo), `backend/services/platform_worker_service.py` (novo)
- `backend/routes/auth_routes.py`
- `frontend/src/services/{authService,router,platformWorkerService}.ts`, `frontend/src/components/Sidebar.ts`, `frontend/src/layouts/{BaseLayout,PlatformLayout}.ts`, `frontend/src/pages/PlatformFuncionariosPage.ts` (novo)
- Testes: `backend/tests/test_platform_worker_boundary.py`, `backend/tests/test_platform_worker_management.py`, `backend/tests/test_permission_service.py` (estendido), `backend/tests/test_sqlite_migrations.py` (corrigido), `frontend/src/__tests__/PlatformFuncionariosPage.test.ts`

## Decisoes de seguranca tomadas (rulings)

- `can()`/`can_any()`: bypass do worker restrito a acoes terminadas em `.read` — nunca `True` incondicional como o admin (evita escalonamento fora do fluxo HTTP, onde o bloqueio de escrita do middleware nao se aplica).
- Bloqueio global de escrita fica no middleware (`utils/auth.py`), chaveado so por metodo HTTP + allowlist de 2 endpoints (`entrar`/`sair`/`alterar-senha`/`logout`), nao rota por rota.
- `empresa_id` "de casa" de todo worker e uma empresa interna dedicada (`plataforma-interna`, get-or-create), nunca uma empresa de cliente real.
- Criacao de worker rejeita (400) qualquer `is_platform_admin`/`isPlatformAdmin` no payload — nunca ignora silenciosamente.

## Bugs criticos achados no review final de branch (ja corrigidos, commit `9228c32`)

Nenhum era de seguranca (o bloqueio de escrita se manteve solido o tempo todo) — eram bugs de integracao entre tasks que nenhum review por task sozinho conseguiria pegar:

1. **Deadlock de senha**: worker criado tem `must_change_password=True`, mas o bloqueio de escrita rejeitava `POST /auth/alterar-senha` — worker ficava trancado pra sempre. Corrigido (endpoint adicionado a allowlist).
2. **Logout bloqueado**: `POST /auth/logout` tambem caia no bloqueio — sessao nunca invalidada de verdade no servidor. Corrigido.
3. **Worker invisivel na UI**: `/auth/me` so expunha `platformViewEmpresaId` pra admin — worker que "entrava" numa empresa nunca via isso refletido, router jogava ele de volta pro `/platform`. Corrigido (`/auth/me` + `BaseLayout.ts` agora cobrem admin-or-worker).
4. **Vazamento de log de auditoria**: criacao/revogacao de worker podia gravar no log de uma empresa de cliente real (cookie de visualizacao stale de outro admin). Corrigido (`empresa_id` explicito, sempre a empresa interna).

## Findings Minor deixados de lado (parked, nao sao seguranca)

- Log de entrar/sair de worker registra como "Administrador da plataforma" (deveria dizer "fiscal"/worker).
- Email de worker revogado nao pode ser reaproveitado (lista filtra so `is_platform_worker=True`).
- Sem validacao de input na criacao (email mal formado, corpo nao-dict vira 500).
- `_get_or_create_internal_empresa` tem race benigna na primeira criacao concorrente.
- Empresa interna aparece na listagem/overview de plataforma como empresa normal.
- Esconder botoes de criar/editar nas telas de tenant quando `isPlatformWorker` (pedido no spec original) **nao foi implementado** — backend ja bloqueia a escrita e mostra toast de erro claro, mas a UI nao esconde os botoes. Spec: secao 5 do design doc.
- Nomenclatura inconsistente "Funcionarios"/"Funcionários" entre `Sidebar.ts` e `PlatformLayout.ts`.

## Estado do working tree (nao commitado, nao e meu)

Mesmo desde antes dessa feature comecar — nao mexi nisso:

```
M .claude/settings.json / .claudian/claudian-settings.json / .mcp.json
M ARCHITECTURE.md / PROGRESS.md / README.md / backend/.env.example
M backend/routes/billing_calculation_routes.py
M backend/services/fatura_service.py
M backend/tests/test_billing_calculation_routes.py
M frontend/src/components/ClientCard.ts, cadastroFields.ts
M frontend/src/pages/EmpresasPage.ts, PlatformCompaniesPage.ts, faturasInvoiceDetail.ts, settingsGeneral.ts
M frontend/src/styles/modals.css
?? REGRAS.md, Response, backend/Status, backend/grande, backend/somente,
   backend/validateField(telefone.input, backend/tests/test_delete_user_physical.py (5 testes falhando, pre-existente)
```

## Build/teste pos-merge (verificado)

- Backend: suite completa sem falhas, exceto `test_delete_user_physical.py` (untracked, pre-existente, nao relacionado).
- Frontend: 36/36 testes, `tsc --noEmit` limpo.
- Nada foi enviado pro remoto — merge e so local em `feat/b2-object-storage-endpoint`.

## Processo usado

`superpowers:brainstorming` → design doc com builder-check → `superpowers:writing-plans` → `superpowers:subagent-driven-development` em worktree isolado (`.worktrees/platform-workers`, ja removido apos merge), 8 tasks + review por task + review final de branch (Opus) + 1 leva de fix + re-review escopado, conforme o processo manda.
