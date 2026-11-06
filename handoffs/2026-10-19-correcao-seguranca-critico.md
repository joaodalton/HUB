# ARCH-TENANT-1 — correção crítica de isolamento de tenant (handoff)

> Gerado em 2026-10-19. Branch no momento do planejamento: `feat/b2-object-storage-endpoint`. Plano aprovado em conversa, aguardando confirmação explícita do usuário antes de qualquer implementação.

## Problema

`backend/extensions.py` tem o listener `do_orm_execute` que injeta `WHERE empresa_id = <empresa da sessão atual>` em todo SELECT contra modelo com `TenantMixin`. Esse listener **não dispara** quando `Client.query.get(id)` ou `db.session.get(Client, id)` encontra o objeto já no identity map da Session (sem emitir SELECT). Resultado: trocar `g.current_empresa_id` de A para B na mesma Session e chamar `.get()` pelo mesmo PK pode devolver o objeto da empresa A pra empresa B — vazamento de dado entre tenants.

Registrado como **ARCH-TENANT-1** / **TC-1.2** em `PROGRESS.md`, `QUADRO_ESTRUTURAL.md` e `docs/architecture/ARCH-TENANT-1_levantamento.md`. Reproduzido por teste (`backend/tests/security/test_tenant_identity_map.py`, dois casos marcados `@unittest.expectedFailure`). Investigação detalhada de inventário/alternativas já existe em `docs/architecture/ARCH-TENANT-1_levantamento.md` — este handoff não repete o levantamento completo, só consolida a decisão e o plano.

## Achado chave: a correção já existiu e foi perdida por acidente

Commit `a291ed1` ("Bug com o multi-Tenant pois se uma pessoa usar o query.get ou o super().get poderia ver as outras empresas") introduziu `TenantQuery(Query)` e `TenantSession` em `backend/extensions.py`, sobrescrevendo `.get()` pra forçar filtro `empresa_id` mesmo em hit de identity map.

Commit `ec0bf41` ("Acho que reverteu tudo antes do plano do hermes, mas manteve o auth e o pendencia_service") apagou as duas classes como efeito colateral de um revert amplo — não foi removido por bug ou decisão deliberada contra a correção. Sobrou só `TenantMixin` + o listener `do_orm_execute`, que não cobre esse caminho.

Conclusão: não é preciso inventar mecanismo novo. É reintroduzir o padrão `TenantQuery`/`TenantSession`, com assinatura atualizada pra SQLAlchemy 2.x.

## Verificação de conflito entre sessões (feita em 2026-10-19)

Duas sessões peer ativas no momento, ambas confirmaram que não tocam `extensions.py`/`TenantMixin`/`do_orm_execute`/identity map:

- **hub-c0**: só migration pendente (`backend/migrations/versions/x1b4f8c2d9e7_add_platform_worker_flag.py`) e correção de `/platform/funcionarios` + `/platform overview/empresas` (500 por migration não aplicada).
- **hub-d6**: branch `feat/financeiro` (worktree `.worktrees/financeiro`), só LÊ `extensions.py` pra revisão, não edita. Services tocados (`financeiro_service.py`, `automacao_service.py`, `plant_service.py`, `document_service.py`, `asaas_webhook_service.py`, rotas, models `plant.py`/`document.py`/`pendencia.py`, `app.py`) usam `.filter_by()`/`.filter()`, nunca `.query.get()`/`db.session.get()` — sem sobreposição com o fix.

Sem conflito de arquivo identificado até o momento deste handoff. Revalidar se o estado das branches mudar antes de implementar.

## Plano de implementação (aprovado em conversa, aguardando confirmação final pra executar)

1. **Reintroduzir `TenantQuery(Query)` e `TenantSession`** em `backend/extensions.py`:
   - `.get()` sobrescrito: se a classe (`cls`/`entity`) herda `TenantMixin` e existe `g.current_empresa_id` (dentro de request context), força `self.query(cls).filter_by(**{pk: ident}, empresa_id=empresa_id).first()` em vez de delegar pro identity map cru.
   - Assinatura atualizada pra SQLAlchemy 2.x: `Session.get(entity, ident, options=None, populate_existing=False, with_for_update=None, identity_token=None, execution_options=None, bind_arguments=None)`.
   - Sem `g.current_empresa_id` definido, ou classe sem `TenantMixin` (ex: `Empresa`, `User`, `Category`, `Invitation`, `PasswordResetToken` — ver tabela de exceções no levantamento), cai no `super().get(...)` padrão.
2. **Ligar as classes customizadas**: trocar `db = SQLAlchemy()` por `db = SQLAlchemy(query_class=TenantQuery, session_options={'class_': TenantSession})`.
3. **Manter o listener `do_orm_execute` como está** — ele já cobre SELECT comum (`Query.filter()`, `select()`); a mudança só tapa o buraco específico do identity map em `.get()`.
4. **Virar os testes de regressão pra verde**: remover `@unittest.expectedFailure` dos dois casos em `backend/tests/security/test_tenant_identity_map.py` (`test_legacy_query_get_does_not_return_previous_tenants_identity`, `test_session_get_does_not_return_previous_tenants_identity`) e confirmar que passam como asserção normal.
5. **Cobertura de teste adicional** (não só os dois testes existentes):
   - Cenário completo A→B→A alternando contexto na mesma Session, pra PK existente e pra PK inexistente (não pode revelar se o PK existe em outro tenant — resposta deve ser `None`/404 igual a "não existe").
   - `populate_existing=True` e `with_for_update` não podem vazar nem quebrar.
   - Relationships lazy/eager carregados antes da troca de contexto.
   - `refresh()` e `merge()` sob contexto trocado.
   - Fluxos reais que trocam `g.current_empresa_id` no mesmo processo: platform admin entrar/usar/saír de empresa (`platform_routes.py`), platform billing (`billing_calculation_routes.py`), webhook ASAAS (`asaas_webhook_service.py`), imports/jobs sequenciais.
   - Confirmar que escrita (mutação + commit) num objeto obtido via `.get()` sob tenant errado é bloqueada, não só leitura.
6. **Regressão completa obrigatória antes de considerar pronto**:
   - Suíte de backend completa (`python -m unittest discover -s tests`).
   - Migrations SQLite completas (upgrade a partir de banco vazio e a partir de estado anterior).
   - Build frontend (não deveria ser afetado, mas confirmar).
   - `git diff --check`.
7. **Revisão independente** via `hub-backend-reviewer` (e `hub-security-reviewer` dado que é bug de isolamento tenant) antes de merge — nunca auto-aprovar essa mudança.

## Explicitamente fora de escopo deste fix

- Session separada por tenant / unidade de trabalho isolada (opção "G" do levantamento) — mudança arquitetural grande, exigiria aprovação própria.
- Regra de lint/CI (AST) banindo getter cru em modelos `TenantMixin` — defesa em profundidade útil, mas não bloqueia esse fix; fica como débito técnico futuro.
- Qualquer alteração em `TenantMixin` em si ou no listener `do_orm_execute`.

## Riscos a observar durante implementação

- Overhead de performance: `.get()` passa a sempre emitir SELECT com filtro em vez de usar cache do identity map pra modelos tenant — aceitável dado que é correção de segurança, mas vale medir se algum hot path depende de cache-hit de `.get()`.
- `with_for_update`/`populate_existing` tinham tratamento específico na versão original (`a291ed1`) que foi simplificado/removido no revert — revisar se a versão reintroduzida precisa repassar esses kwargs pro `query()` interno ou só pro fallback `super().get()`.
- Qualquer fluxo que dependa hoje (mesmo sem saber) do comportamento de cache do identity map pode mudar de contagem de queries — não deve mudar resultado, só custo.

## Regras globais ativas (lembrar na próxima sessão)

- Orquestrador, não implementador — implementação vai pro `hub-backend-developer`, revisão pro `hub-backend-reviewer`/`hub-security-reviewer`, nunca escrever o código de produto direto nesta sessão.
- Subagentes sempre em Sonnet 5, não Opus.
- Nada é implementado sem confirmação explícita do usuário sobre este plano.
- Revalidar com sessões peer ativas (`ListAgents`) se o estado delas mudou, antes de despachar a implementação.
