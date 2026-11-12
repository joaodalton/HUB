# Redesenho de Faturas e Financeiro — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Importar PDFs da Copel de qualquer tela, ver cada um extraído/vinculado (ou o motivo exato do erro) em Faturas, e gerar boleto ASAAS em um clique no Financeiro agrupado por usina.

**Architecture:** O pipeline upload → extração → cálculo → emissão → webhook já existe; este plano liga as etapas (cálculo automático, modo unificada/separada na emissão, reprocessar, deletar sem boleto), expõe motivos de erro como dados estruturados e reescreve as duas telas sobre os endpoints existentes mais um endpoint novo de pendentes de boleto. Nenhum motor novo.

**Tech Stack:** Flask + SQLAlchemy + Alembic (backend, `unittest`), TypeScript vanilla + Vite + Vitest (frontend), ReportLab (fixtures PDF, já usado).

**Spec:** `docs/superpowers/specs/2026-11-09-financeiro-faturas-redesign-design.md` (mockup: `.superpowers/brainstorm/28169-1794260788/content/telas-v1.html`). Ler também `AGENTS.md`.

## Global Constraints

- Branch de trabalho: `feat/financeiro-faturas-redesign`, criada a partir de `develop`. Nunca fazer merge em `main`.
- Commits sem trailer `Co-Authored-By`.
- Toda query filtra por `empresa_id` do contexto autenticado; ID de outro tenant responde 404. Testes de rota nova/alterada incluem duas empresas.
- Dinheiro em `Decimal`, nunca `float`. Serializar valores novos como string.
- Arquivos < 500 linhas. Sem dependência nova. Migrations aditivas e reversíveis.
- Sem chamada real ao ASAAS em testes (usar o cliente simulado já usado em `backend/tests/test_fatura_emissao.py`).
- Erro nunca genérico: toda resposta de erro nova carrega `code` e, quando houver, os campos faltantes.
- Frontend: sem framework, reutilizar `DataTable`, `StatusBadge`, `Modal`, `useToast`, `FaturasUi`; textos via `t()` em `frontend/src/i18n/`.
- Mudança de endpoint atualiza `Documentos/md/architecture/API_CONTRACTS.md` no mesmo commit.
- Comandos de teste: backend `cd backend && ./venv/Scripts/python.exe -m unittest tests.<modulo> -v`; frontend `cd frontend && npx vitest run src/__tests__/<arquivo>`.
- Subagentes: `hub-backend-developer` / `hub-frontend-developer` implementam; `hub-backend-reviewer` / `hub-frontend-reviewer` revisam; modelo Sonnet. Tasks 3–7 passam por `hub-security-reviewer`.

## Review Focus

1. **Emissão pendente + recálculo = boleto duplicado.** Existe `Fatura` da mesma UC/competência sem `asaas_id` (timeout no POST) e o usuário clica "Gerar boleto" de novo após a regra mudar: deve reconciliar a emissão pendente, nunca criar segunda cobrança. (Task 5)
2. **Mesmo PDF importado duas vezes / em lote com duplicata:** resultado diz "já importada", sem segunda linha nem segundo cálculo. (Task 9)
3. **Lote com um PDF inválido no meio:** os demais são importados; o inválido aparece no resultado com o motivo. (Task 9)
4. **UC ligada a duas usinas / a nenhuma:** aparece em cada grupo / no grupo "Sem usina"; nunca some. (Task 6)
5. **Webhook de pagamento de boleto separado:** não cria pendência "Pagar concessionária" (o cliente paga a Copel direto). (Task 5)

---

### Task 1: Três faturas Copel fictícias com GD

**Files:**
- Modify: `backend/tests/fixtures/invoices/copel/build_fixture.py`
- Create: `backend/tests/fixtures/invoices/copel/gd1_anon.pdf`, `gd2_anon.pdf`, `gd1_gd2_anon.pdf` e os respectivos `*.expected.json`
- Modify: `backend/tests/fixtures/invoices/copel/README.md` (seção curta "Fixtures GD")
- Test: `backend/tests/test_copel_gd_fixtures.py`

**Interfaces:**
- Produces: `GD_CASES: dict[str, dict]` e `make_gd_pdf(case: str) -> bytes` em `build_fixture.py`; chaves `'gd1'`, `'gd2'`, `'gd1_gd2'`. Executar o módulo como script regrava os três PDFs e JSONs.

Cada caso reutiliza `make_pdf(changes=..., items=...)`. Para os três PDFs não colidirem entre si no upload (hash e chave fiscal), cada caso troca via `changes`: `uc`, `fiscal` (nº da NF), `key`, `reference`, `due`, `total`. Valores fixos:

| caso | uc | reference / due | total | itens GD (label, kWh) |
|---|---|---|---|---|
| gd1 | `000000000000101` | `09/2030` / `10/10/2030` | `R$150,10` | `ENERGIA INJ. OUC MPT TE 08/2030 GDI-I` −120; `ENERGIA INJ. OUC MPT TUSD 08/2030 GDI-I` −120 |
| gd2 | `000000000000102` | `09/2030` / `10/10/2030` | `R$96,40` | `ENERGIA INJ. OUC MPT TE 08/2030 GDII-II` −210; `ENERGIA INJ. OUC MPT TUS 08/2030 GDII-II` −210 |
| gd1_gd2 | `000000000000103` | `09/2030` / `10/10/2030` | `R$184,20` | `... TE 07/2030 GDI-I` −30; `... TUSD 07/2030 GDI-I` −30; `... TE 08/2030 GDII-II` −352; `... TUS 08/2030 GDII-II` −352 |

Todos mantêm as quatro linhas de `ITEMS` antes das linhas GD. Tarifas das linhas GD: copiar as de `gd_events_sanitized.json` (`ouc_gdi_gdii_2026_09`). Formato numérico igual ao de `ITEMS` (vírgula decimal).

- [ ] **Step 1: Teste falhando** em `test_copel_gd_fixtures.py` (mesmo esqueleto de import de `test_copel_energy.py`):

```python
EXPECTED = {'gd1': {'GD_I': Decimal('120')}, 'gd2': {'GD_II': Decimal('210')},
            'gd1_gd2': {'GD_I': Decimal('30'), 'GD_II': Decimal('352')}}

def test_each_case_extracts_only_its_gd_classes(self):
    for case, expected in EXPECTED.items():
        parsed = CopelDANF3EParser().parse(make_gd_pdf(case))
        comps = [c for c in parsed.energy_components if c['category'].value == 'compensated']
        by_gd = {}
        for c in comps:  # TE e TUSD da mesma identidade = uma quantidade fisica
            by_gd.setdefault((c['gd_classification'].value, c['credit_month'].value), set()).add(abs(c['amount_kwh'].value))
        totals = {}
        for (gd, _), amounts in by_gd.items():
            self.assertEqual(len(amounts), 1)
            totals[gd] = totals.get(gd, Decimal('0')) + amounts.pop()
        self.assertEqual(totals, expected)

def test_tus_is_normalized_to_tusd(self): ...   # gd2: componentes == {'TE', 'TUSD'}
def test_committed_pdfs_match_generator(self): ...  # bytes de <case>_anon.pdf == make_gd_pdf(case)
def test_expected_json_matches_normalizer(self): ...  # InvoiceNormalizer().normalize(parsed) confere uc, competencia '2030-09', vencimento, total e a lista de componentes do expected.json
```

- [ ] **Step 2:** Rodar `tests.test_copel_gd_fixtures` — FAIL (`make_gd_pdf` inexistente).
- [ ] **Step 3:** Implementar `GD_CASES`/`make_gd_pdf` e o bloco `__main__` que grava PDFs e JSONs; rodar o script; commitar os arquivos gerados. Se o parser não ler alguma linha (ex.: label longo estourando a coluna do gerador), ajustar o **gerador** (fonte/posição), não o parser; se for defeito real do parser, parar e reportar.
- [ ] **Step 4:** Rodar `tests.test_copel_gd_fixtures tests.test_copel_energy tests.test_copel_deep tests.test_copel_parser` — PASS.
- [ ] **Step 5:** Commit `test: fixtures Copel ficticias com GD I, GD II e ambas`.

### Task 2: Motivos de erro e totais GD por fatura na API

**Files:**
- Create: `backend/services/invoice_problems.py`
- Modify: `backend/routes/billing_calculation_routes.py` (`_invoices`, só o dict de saída)
- Modify: `backend/services/fatura_concessionaria_upload_service.py` (mensagens de rejeição)
- Test: `backend/tests/test_invoice_problems.py`; estender `backend/tests/test_billing_calculation_routes.py`

**Interfaces:**
- Produces:
  - `invoice_problems(invoice: FaturaConcessionaria) -> list[dict]` — itens `{'code': str, 'message': str, 'fields': list[str]}`.
  - `gd_totals(invoice: FaturaConcessionaria) -> dict` — `{'gdIKwh': str | None, 'gdIIKwh': str | None}`; soma, por classe GD, o valor absoluto de cada evento (mês distinto soma; TE/TUSD do mesmo evento conta uma vez), lendo `dados_normalizados['invoice']['energy_components']`; `None` quando não há evento da classe ou não há extração.
  - Cada linha de `GET /billing-calculations/invoices` ganha `gdIKwh`, `gdIIKwh`, `problemas`. Cada item de `contextualCharges` ganha `invoiceUrl`, `billingMode` (Task 5 cria as colunas; até lá `None` via `getattr`).

Códigos e mensagens de `invoice_problems` (pt-BR, exatos):

| condição | code | message |
|---|---|---|
| `status_extracao == 'recebida'` | `NOT_PROCESSED` | `Fatura ainda não processada.` |
| `status_extracao == 'erro'` | `EXTRACTION_FAILED` | `Não foi possível ler o PDF.` |
| `status_extracao == 'layout_nao_reconhecido'` | `LAYOUT_NOT_RECOGNIZED` | `Layout de fatura não reconhecido (suportado: Copel DANF3E V1.06).` |
| `status_validacao == 'uc_nao_encontrada'` | `UC_NOT_FOUND` | `UC {codigo_uc_extraido} não está cadastrada em nenhum cliente.` |
| `status_validacao == 'uc_pertence_outro_cliente'` | `UC_OTHER_CLIENT` | `UC {codigo_uc_extraido} pertence a outro cliente.` |
| `status_validacao == 'revisao_necessaria'` | `MISSING_FIELDS` | `Faltou ler: {campos separados por vírgula}.` — `fields` = caminhos das issues críticas gravadas em `dados_normalizados['validation']`; sem campos identificáveis: code `REVIEW_REQUIRED`, message = mensagens das issues críticas unidas por `; ` |

Rejeições no upload (PDF não é salvo quando a UC lida não pertence a nenhum cliente — comportamento atual de `_client_from_document`, mantido): garantir que cada `_fail` de `_validate_pdf`/`_client_from_document` tenha mensagem específica; a de UC ausente passa a ser `UC {codigo} não está cadastrada em nenhum cliente. Cadastre a UC e importe de novo.` com code `UC_NOT_FOUND`; PDF sem UC legível: `Não foi possível ler o código da UC no PDF.` code `UC_NOT_READABLE`.

- [ ] **Step 1: Testes falhando** — `test_invoice_problems.py`: um caso por linha da tabela (objeto `FaturaConcessionaria` em memória) com `assertEqual` no dict inteiro; `gd_totals` com `dados_normalizados` obtido processando `make_gd_pdf('gd1_gd2')` → `{'gdIKwh': '30', 'gdIIKwh': '352'}`, `'gd1'` → `{'gdIKwh': '120', 'gdIIKwh': None}`, fatura sem extração → ambos `None`. Rota: linha da listagem contém as três chaves novas; upload de PDF com UC não cadastrada devolve 4xx com `code == 'UC_NOT_FOUND'` e o código da UC na mensagem.
- [ ] **Step 2:** Rodar — FAIL.
- [ ] **Step 3:** Implementar. Reutilizar o que `services/invoice_compensation.py` já oferece para identidade de evento, em vez de reimplementar o agrupamento, se a função servir sem cálculo comercial.
- [ ] **Step 4:** Rodar `tests.test_invoice_problems tests.test_billing_calculation_routes tests.test_fatura_concessionaria_upload` — PASS.
- [ ] **Step 5:** Atualizar `API_CONTRACTS.md`; commit `feat: motivos de erro e totais GD na listagem de faturas`.

### Task 3: Deletar sem boleto e Reprocessar

**Files:**
- Modify: `backend/services/invoice_document_service.py`
- Modify: `backend/services/fatura_concessionaria_upload_service.py`
- Modify: `backend/routes/billing_calculation_routes.py`
- Test: `backend/tests/test_invoice_delete_reprocess.py`

**Interfaces:**
- Produces:
  - `has_active_boleto(invoice: FaturaConcessionaria) -> bool` em `invoice_document_service.py`: existe `Fatura` da mesma empresa, `consumer_unit_id` e `competencia` com `asaas_id IS NOT NULL` e `asaas_status NOT IN ('canceled','refunded')`. `False` se a fatura não tem UC/competência.
  - `has_pending_emission(invoice) -> Fatura | None`: `Fatura` do mesmo contexto com `asaas_id IS NULL` e `status_interno IN ('aguardando_emissao','erro_emissao')`.
  - `InvoiceHasBoletoError` substitui `InvoiceHasCalculationError`; resposta 409 `code='INVOICE_HAS_BOLETO'`, mensagem `Esta fatura já tem boleto gerado e não pode ser excluída. Cancele o boleto antes.` Emissão pendente também bloqueia (mesmo erro).
  - `delete_invoice` passa a remover execuções e snapshots de cálculo e todas as pendências da fatura antes de removê-la.
  - `reprocess_invoice(invoice_id: int, empresa_id: int) -> dict` em `fatura_concessionaria_upload_service.py`, retorno igual a `_result(invoice, False)`; exceções `LookupError` (404) e `InvoiceUploadError` code `REPROCESS_NOT_ALLOWED` (409).
  - Rotas `POST /api/v1/billing-calculations/invoices/<id>/reprocess` (tenant, `faturas.create`, limiter `10 per minute`) e a equivalente em `platform_billing_calculation_routes`.

Regras de `reprocess_invoice`: permitido só quando não há boleto ativo nem emissão pendente **e** (`status_extracao IN ('recebida','erro','layout_nao_reconhecido')` **ou** `status_validacao IN ('uc_nao_encontrada','uc_pertence_outro_cliente','revisao_necessaria')`). Passos: ler o PDF com `load_invoice_pdf`; apagar execuções/snapshots de cálculo; zerar na fatura os campos de extração (snapshots JSON, identidade do parser, identificação/datas/valores extraídos, `consumer_unit_id`) e voltar para `recebida`/`pendente`; commit; `FaturaProcessingService().process(...)`; em sucesso sem issue crítica, fechar (`status='resolvida'` ou o valor de "fechada" usado por `Pendencia`) as pendências `ORIGEM_ERRO_PROCESSAMENTO` da fatura; com issue crítica, manter/registrar a pendência como no upload.

Antes de implementar a remoção de snapshots: ler `backend/tests/test_billing_snapshot_immutability.py`. Se houver guarda de ORM/DB contra delete de snapshot, a exclusão da fatura sem boleto é a exceção autorizada pela spec; implementá-la no ponto único `delete_invoice`/`reprocess_invoice` e manter os testes de imutabilidade de UPDATE passando.

- [ ] **Step 1: Testes falhando** (`IsolatedTestRuntime`, duas empresas, PDF de `make_gd_pdf`):
  - delete com cálculo e sem boleto → 200, fatura/execuções/snapshots/pendências removidos;
  - delete com `Fatura` `asaas_id='pay_1'`, `asaas_status='pending'` → 409 `INVOICE_HAS_BOLETO`; com `asaas_status='canceled'` → 200;
  - delete com `Fatura` sem `asaas_id` e `status_interno='erro_emissao'` → 409;
  - delete de ID da empresa B autenticado como A → 404, nada removido;
  - reprocess de fatura `uc_nao_encontrada`/`revisao_necessaria` após corrigir o cadastro → `status_validacao == 'valida'`, pendência de erro fechada;
  - reprocess de fatura `valida` → 409 `REPROCESS_NOT_ALLOWED`; com boleto ativo → 409; outro tenant → 404.
- [ ] **Step 2:** Rodar — FAIL.
- [ ] **Step 3:** Implementar.
- [ ] **Step 4:** Rodar o módulo novo + `tests.test_billing_calculation_routes tests.test_billing_snapshot_immutability tests.test_fatura_concessionaria_upload tests.test_invoice_processing_persistence` — PASS.
- [ ] **Step 5:** `API_CONTRACTS.md`; commit `feat: excluir fatura sem boleto e reprocessar extracao`.

### Task 4: Cálculo automático após vínculo

**Files:**
- Modify: `backend/services/fatura_concessionaria_upload_service.py`
- Test: estender `backend/tests/test_fatura_concessionaria_upload.py`

**Interfaces:**
- Produces: `_auto_calculate(invoice_id: int) -> None`, chamada ao final de `upload_invoice` (não duplicata) e de `reprocess_invoice`, somente quando `status_validacao == 'valida'`. Usa `BillingCalculationService().execute(invoice_id)` (exige sessão limpa: chamar após os commits). Qualquer exceção é logada (`current_app.logger.error`, sem dados do PDF) e engolida: o upload continua 201.

- [ ] **Step 1: Testes falhando:** upload de PDF com UC cadastrada e regra de cobrança atribuída → existe 1 `BillingCalculationExecution` para a fatura; upload sem regra → upload 201 e execução com status bloqueado (ou nenhuma), sem exceção; upload duplicado → nenhuma execução nova.
- [ ] **Step 2:** FAIL. **Step 3:** Implementar. **Step 4:** PASS, incluindo `tests.test_e2e_upload_calculo_cobranca`.
- [ ] **Step 5:** Commit `feat: calculo automatico apos importar fatura`.

### Task 5: Modo unificada/separada na emissão, link de pagamento e webhook

**Files:**
- Create: `backend/migrations/versions/<rev>_fatura_billing_mode_uc_debito_automatico.py`
- Modify: `backend/models/fatura.py`, `backend/models/consumer_unit.py`
- Modify: `backend/services/fatura_service.py`, `backend/services/asaas_webhook_service.py`, `backend/services/financeiro_service.py`
- Modify: rota/serviço de UC que serializa e atualiza `ConsumerUnit` (localizar com grep por `to_dict` da UC e pelo update de UC)
- Test: `backend/tests/test_billing_mode_emissao.py`; estender `test_asaas_webhook.py`, `test_financeiro_service.py`, `test_sqlite_migrations.py`

**Interfaces:**
- Produces:
  - Colunas: `faturas.billing_mode` `String(20)` nulo (`'unified'|'separate'`), `faturas.invoice_url` `String(2048)` nulo, `consumer_units.debito_automatico` `Boolean NOT NULL DEFAULT false`. `Fatura.to_dict()` ganha `billingMode`, `invoiceUrl`; a UC serializa/aceita `debitoAutomatico`.
  - `resolve_billing_mode(rule_mode: str, debito_automatico: bool) -> str` em `fatura_service.py`: `'unified'`→`'unified'`; `'separate'`→`'separate'`; `'auto'`→`'separate'` se `debito_automatico` senão `'unified'`.
  - `gerar_boleto_concessionaria(fatura_concessionaria_id, empresa_id, user_id) -> dict` (mesma assinatura) com novo comportamento abaixo; o dict devolvido inclui `billingMode`, `invoiceUrl`, `boletoUrl`, `faturaConcessionariaId`.
  - `emitir(data, ...)` aceita `data['billingMode']` opcional e grava em `Fatura.billing_mode` na criação.

Comportamento de `gerar_boleto_concessionaria`, nesta ordem:
1. Validações atuais de dados faltantes (`DadosIncompletosError`).
2. Se `has_pending_emission(invoice)` devolver uma `Fatura`: reemitir **com os dados dela** (`valor`, `mes_vencimento`, `billing_mode` gravados) via `emitir` — mesma `emission_key`, sem recalcular. (Review Focus 1.)
3. Se `has_active_boleto(invoice)`: devolver o `to_dict()` do boleto existente (idempotente), sem novo cálculo.
4. Recalcular: `BillingCalculationService().execute(invoice.id)`; sem snapshot resultante → `CalculoCobrancaPendente` com a etapa/bloqueio da execução em `details` (`{'stage': ..., 'blockers': [...]}`); a rota devolve isso em `details`.
5. `mode = resolve_billing_mode(<billing_mode do regra_snapshot>, uc.debito_automatico)`; `valor = snapshot.valor_final` (separate) ou `snapshot.valor_final + invoice.valor_total_concessionaria` (unified).
6. `emitir({... 'valor': str(valor), 'billingMode': mode})`.

`_apply_payment` e o webhook (`_aplicar`) gravam `invoice_url` a partir de `payment['invoiceUrl']` e deixam `boleto_url` só com `bankSlipUrl` quando presente (mantendo o fallback atual quando `bankSlipUrl` vier vazio). No webhook `received`: chamar `criar_pendencia_pagar_concessionaria` somente se `fatura.billing_mode != 'separate'` (legado `None` mantém o comportamento atual).

- [ ] **Step 1: Testes falhando:**
  - `resolve_billing_mode`: as 4 combinações.
  - regra `unified`, hub `100.00`, Copel `71.05` → `Fatura.valor == Decimal('171.05')`, `billing_mode == 'unified'`; regra `separate` → `100.00`, `'separate'`; regra `auto` + UC `debito_automatico=True` → `'separate'`.
  - emissão pendente (Fatura sem `asaas_id`, valor `150.00`) + regra alterada → segunda chamada usa `150.00`, total de `Fatura` da UC/competência continua 1 e o cliente ASAAS simulado recebe no máximo 1 POST de cobrança.
  - boleto ativo → segunda chamada devolve o mesmo `id`, zero POST.
  - cálculo bloqueado (sem regra) → 422 `BILLING_CALCULATION_REQUIRED` com `details.stage == 'RULE_RESOLUTION'`.
  - cliente sem e-mail → 400 com mensagem `Cliente sem email cadastrado.` (já existente; fixar em teste).
  - webhook `PAYMENT_RECEIVED` com `billing_mode='separate'` → nenhuma `Pendencia` `pagar_concessionaria`; com `'unified'` e com `None` → cria uma.
  - payload com `invoiceUrl` e `bankSlipUrl` → ambos gravados.
  - migration: upgrade em SQLite vazio e downgrade (`test_sqlite_migrations`).
  - outra empresa: `gerar-boleto` de fatura do tenant B como A → 404.
- [ ] **Step 2:** FAIL. **Step 3:** Implementar (gerar a migration com `flask db revision`, editar à mão, `server_default` para o booleano).
- [ ] **Step 4:** Rodar módulo novo + `tests.test_fatura_emissao tests.test_asaas_webhook tests.test_financeiro_service tests.test_sqlite_migrations tests.test_e2e_upload_calculo_cobranca` — PASS.
- [ ] **Step 5:** `API_CONTRACTS.md`; commit `feat: modo unificada/separada na emissao e link de pagamento`.

### Task 6: Endpoint de pendentes de boleto por usina

**Files:**
- Modify: `backend/services/financeiro_service.py`, `backend/routes/financeiro_routes.py`
- Test: estender `backend/tests/test_financeiro_routes.py`

**Interfaces:**
- Consumes: `has_active_boleto` (Task 3), `resolve_billing_mode` (Task 5).
- Produces: `listar_pendentes_boleto(empresa_id: int) -> list[dict]` e `GET /api/v1/financeiro/pendentes-boleto` (`billing_calculations.read`). Resposta `data`:

```json
[{"usinaId": 3, "usinaNome": "Usina Norte", "itens": [{
  "invoiceId": 12, "clienteId": 5, "clienteNome": "Ana Reis", "ucId": 9, "ucCodigo": "000555444333222",
  "competencia": "2026-10", "dataVencimento": "2026-11-20",
  "valorConcessionaria": "71.05", "valorHub": "168.75", "valorCobrar": "239.80",
  "billingMode": "unified", "emissaoPendente": false,
  "bloqueio": null}]}]
```

Regras: entram faturas com `consumer_unit_id` não nulo, `status_validacao == 'valida'` e sem boleto ativo. Grupos por usina conectada à UC (`PlantConnection` da mesma empresa); UC em N usinas aparece nos N grupos; sem usina → grupo `{"usinaId": null, "usinaNome": null}` por último; demais grupos por nome; itens por nome do cliente. `valorHub` = `valor_final` do snapshot mais recente; `billingMode`/`valorCobrar` pelas regras da Task 5; sem snapshot → os três `null`. `bloqueio` (primeiro que se aplicar), `{'code', 'message'}`:

| condição | code | message |
|---|---|---|
| cliente sem e-mail | `CLIENT_EMAIL_MISSING` | `Cliente sem e-mail cadastrado.` |
| sem vencimento / valor Copel | `INVOICE_DATA_INCOMPLETE` | `Faltou na fatura: {campos}.` |
| nenhuma execução | `NOT_CALCULATED` | `Cobrança ainda não calculada.` |
| última execução bloqueada em `RULE_RESOLUTION` | `RULE_MISSING` | `Cliente sem regra de cobrança.` |
| última execução bloqueada em outra etapa | `CALCULATION_BLOCKED` | `Cálculo bloqueado em {stage}: {blockers}.` |

Sem paginação. Evitar N+1 (carregar snapshots/execuções/boletos das faturas em consultas `IN`).

- [ ] **Step 1: Testes falhando:** agrupamento (UC em 2 usinas → 2 grupos; sem usina → grupo nulo no fim); fatura com boleto `pending` fora, com boleto `canceled` dentro; fatura `revisao_necessaria` fora; cada linha de `bloqueio`; `valorCobrar` unified = hub + Copel; empresa B não vê nada da A; sem permissão → 403.
- [ ] **Step 2:** FAIL. **Step 3:** Implementar. **Step 4:** PASS (`tests.test_financeiro_routes tests.test_financeiro_service`).
- [ ] **Step 5:** `API_CONTRACTS.md`; commit `feat: endpoint de clientes pendentes de boleto por usina`.

### Task 7: Revisão de segurança do backend

- [ ] **Step 1:** Rodar a suíte completa: `cd backend && ./venv/Scripts/python.exe -m unittest discover -s tests` — PASS.
- [ ] **Step 2:** Despachar `hub-security-reviewer` sobre o diff das Tasks 2–6 (tenancy, RBAC das rotas novas, idempotência financeira, webhook). Corrigir todo BLOCK via `hub-backend-developer` e repetir até PASS/PASS_WITH_NOTES.

### Task 8: Serviços do frontend

**Files:**
- Modify: `frontend/src/services/billingCalculationsService.ts`, `frontend/src/services/financeiroService.ts`, `frontend/src/services/faturasService.ts`
- Test: `frontend/src/__tests__/financeiroService.test.ts`, novo `frontend/src/__tests__/billingCalculationsService.test.ts`

**Interfaces:**
- Produces:

```ts
// billingCalculationsService.ts
export type InvoiceProblem = { code: string; message: string; fields: string[] };
// BillingInvoice ganha: gdIKwh: string | null; gdIIKwh: string | null; problemas: InvoiceProblem[];
// contextualCharges[i] ganha: invoiceUrl: string | null; billingMode: 'unified' | 'separate' | null;
export async function reprocessBillingInvoice(invoiceId: number, empresaId?: number): Promise<BillingUpload>;
export async function calculateBillingInvoice(invoiceId: number, empresaId?: number): Promise<BillingExecution>;
// FaturaRow (faturasService.ts) ganha: billingMode, invoiceUrl, faturaConcessionariaId

// financeiroService.ts
export type PendenteBoleto = { invoiceId: number; clienteId: number; clienteNome: string; ucId: number; ucCodigo: string;
  competencia: string; dataVencimento: string | null; valorConcessionaria: string | null; valorHub: string | null;
  valorCobrar: string | null; billingMode: 'unified' | 'separate' | null; emissaoPendente: boolean;
  bloqueio: { code: string; message: string } | null };
export type PendentesUsina = { usinaId: number | null; usinaNome: string | null; itens: PendenteBoleto[] };
export async function getPendentesBoleto(): Promise<PendentesUsina[]>;
```

`apiClient` já propaga `message` do backend no `Error`; confirmar que `code`/`details` ficam acessíveis no erro (se não, expor no erro existente sem mudar os consumidores).

- [ ] **Step 1:** Testes Vitest: cada função chama o path/método certo (`/financeiro/pendentes-boleto`, `/billing-calculations/invoices/7/reprocess` POST, variante plataforma com `empresaId`) e propaga erro da API. **Step 2:** FAIL. **Step 3:** Implementar. **Step 4:** PASS.
- [ ] **Step 5:** Commit `feat(frontend): servicos de pendentes de boleto e reprocessar`.

### Task 9: Botão global "Importar faturas"

**Files:**
- Create: `frontend/src/components/InvoiceImportButton.ts`
- Modify: `frontend/src/components/Header.ts`, `frontend/src/components/ConcessionariaInvoicesPanel.ts` (remover `createConcessionariaUploadButton`, apontar consumidores para o novo), `frontend/src/i18n/faturas.ts`, CSS em `frontend/src/styles/faturas.css`
- Test: `frontend/src/__tests__/InvoiceImportButton.test.ts`

**Interfaces:**
- Produces:
  - `createInvoiceImportButton(): HTMLElement | null` — `null` para quem não é `owner|admin|financial` (mesma regra de papel do botão atual, incluindo platform admin com empresa selecionada).
  - Evento `window` `'hub:invoices-imported'` (`CustomEvent<{ imported: number; duplicates: number; failed: number }>`) disparado ao fim de cada lote com ao menos um sucesso.
  - Constante exportada `INVOICES_IMPORTED_EVENT = 'hub:invoices-imported'`.

Comportamento: `<input type="file" multiple accept=".pdf,application/pdf">`; envia os arquivos **em sequência** (o endpoint tem limite de 10/min; ao receber 429, parar e marcar os restantes como "não enviados: limite de envios por minuto, tente novamente"). Ao terminar:
- toast de sucesso `"{n} fatura(s) importada(s) e vinculada(s)."` quando n > 0; duplicatas contam em `"{n} já importada(s)."`;
- se houver qualquer falha, abre um modal (componente `Modal` existente) "Resultado da importação" listando **cada arquivo** com nome e resultado (importada / já importada / mensagem de erro do backend); o modal só fecha por ação do usuário;
- fora de `/faturas`, o toast/modal traz a ação "Ver em Faturas" (`navigate('/faturas')`).

`Header.ts`: inserir o botão em `header-controls`, antes do `ThemeToggle`.

- [ ] **Step 1: Testes falhando** (mock de `uploadTenantBillingInvoice`): 3 arquivos, o 2º rejeita com `Error('UC 000111222333444 não está cadastrada em nenhum cliente. Cadastre a UC e importe de novo.')` → 3 chamadas, modal lista 3 linhas e contém a mensagem literal, evento disparado com `{imported: 2, duplicates: 0, failed: 1}`; resposta `duplicate: true` → conta em duplicatas, sem modal; papel `viewer` → `null`; nenhum sucesso → evento não disparado.
- [ ] **Step 2:** FAIL. **Step 3:** Implementar. **Step 4:** PASS + `npm run build`.
- [ ] **Step 5:** Commit `feat(frontend): importar faturas em lote de qualquer tela`.

### Task 10: Tela Faturas

**Files:**
- Rewrite: `frontend/src/pages/FaturasPage.ts` (≤ 300 linhas); Modify: `faturasInvoiceActions.ts`, `frontend/src/components/FaturasUi.ts`, `frontend/src/i18n/faturas.ts`, `frontend/src/styles/faturas.css`
- Delete: `frontend/src/pages/faturasCreateModal.ts` (cobrança manual sai da tela; confirmar por grep que não há outro consumidor)
- Test: reescrever `frontend/src/__tests__/FaturasPage.test.ts`

**Interfaces:**
- Consumes: Task 8 (tipos, `reprocessBillingInvoice`, `deleteBillingInvoice`, `downloadBillingInvoice`), Task 9 (`createInvoiceImportButton`, `INVOICES_IMPORTED_EVENT`).

Tabela conforme o mockup (Tela 1), colunas nesta ordem: Competência · Cliente / UC · Usina · Extração · GD I · GD II · Valor Copel · Boleto · Ações.
- Extração: badge `Extraída` (success) quando `problemas` vazio; senão badge `Erro` (danger) e, abaixo, cada `problema.message` em texto.
- GD: `"{n} kWh"` ou `—`.
- Boleto (do `contextualCharges` mais recente não cancelado): `Sem boleto` (neutral), `Aguardando pagamento` (warning: `pending`/`overdue` — `overdue` mostra `Vencido`), `Pago` (success: `received`).
- Ações: `PDF` sempre; `Boleto` (abre `boletoUrl`) e `Link` (copia `invoiceUrl ?? boletoUrl` e dá toast `Link de pagamento copiado.`) quando há boleto; `Fatura Copel` não é ação separada aqui (o `PDF` da linha já é ela); `Reprocessar` quando `problemas` não vazio e sem boleto; `Deletar` quando sem boleto, com confirmação em `Modal` (`Excluir a fatura de {cliente} ({competência})? Esta ação não pode ser desfeita.`).
- Toda ação termina em toast: sucesso com texto específico (`Fatura excluída.`, `Fatura reprocessada e vinculada.`) ou erro com a `message` do backend; reprocesso que ainda resulta em problema mostra toast de erro com o primeiro `problema.message`.
- Filtros mantidos via `listState`: busca, status (extração/boleto), usina, competência; paginação existente. Botão de importar no topo da tela (mesmo componente). Escuta `INVOICES_IMPORTED_EVENT` e recarrega; remove o listener quando a página sai do DOM.
- Clique na linha continua abrindo `faturasInvoiceDetail` (funcionalidade existente preservada).
- Regras de papel/plataforma-admin existentes (`canIssue`, empresa de teste id 1) preservadas.

- [ ] **Step 1: Testes falhando:** uma linha por fatura; fatura com `problemas: [{code:'UC_NOT_FOUND', message:'UC 000111222333444 não está cadastrada em nenhum cliente.', fields:[]}]` mostra a mensagem literal e o botão Reprocessar; fatura com boleto `received` mostra `Pago`, tem Boleto/Link e não tem Deletar; `gdIKwh:'30', gdIIKwh:null` → `30 kWh` e `—`; Deletar confirma, chama `deleteBillingInvoice` e dá toast; erro 409 mostra a mensagem do backend; estado vazio e estado de erro com "tentar novamente"; evento de importação recarrega.
- [ ] **Step 2:** FAIL. **Step 3:** Implementar. **Step 4:** PASS + `npm run build` + `npm run lint`.
- [ ] **Step 5:** Commit `feat(frontend): tela de faturas importadas`.

### Task 11: Tela Financeiro e painel pós-boleto

**Files:**
- Rewrite: `frontend/src/pages/FinanceiroPage.ts`; Create: `frontend/src/pages/financeiroBoletoPanel.ts`
- Modify: i18n do financeiro, CSS; formulário de UC (localizar o editor de UC — `ClientCardUcEditor.ts`/`UcsPage.ts`) para o checkbox "Débito automático na concessionária"
- Test: `frontend/src/__tests__/FinanceiroPage.test.ts`, `frontend/src/__tests__/financeiroBoletoPanel.test.ts`

**Interfaces:**
- Consumes: `getPendentesBoleto`, `gerarBoletoConcessionaria`, `calculateBillingInvoice`, `downloadBillingInvoice`, `INVOICES_IMPORTED_EVENT`.
- Produces: `openBoletoPanel(fatura: FaturaRow, opts: { invoiceId: number; empresaId?: number; onClose: () => void }): void`.

Tela (mockup, Tela 2): um bloco por usina — cabeçalho `{usinaNome ?? 'Sem usina'}` + `"{n} cliente(s) aguardando boleto"` — e tabela: Cliente / UC · Competência · Valor Copel · Valor a cobrar · Tipo · ações.
- Tipo: `Unificada` / `Separada` / `—`.
- `bloqueio` presente: a célula "Valor a cobrar" mostra `bloqueio.message` (danger) e "Gerar boleto" fica `disabled`; com code `NOT_CALCULATED` aparece o botão `Calcular` (chama `calculateBillingInvoice`, toast, recarrega).
- `emissaoPendente`: botão vira `Retomar emissão`.
- "Gerar boleto": desabilita durante a chamada; sucesso → toast `Boleto gerado para {cliente} — {valor}, vence {data}.` e `openBoletoPanel`; erro → toast com a `message` do backend (para `BILLING_CALCULATION_REQUIRED`, acrescentar etapa/bloqueios de `details`).
- Botão pequeno (ícone de engrenagem, `aria-label` "Configurar regra de cobrança") ao lado: `navigate('/ucs?ucId={ucId}')` — a tela de UC já contém a seção de regra (`UcBillingRuleSection`); confirmar o parâmetro pelo `returnPath` de `BillingRuleEditorPage.ts`.
- Estado vazio: `Nenhum cliente aguardando boleto.` Estado de erro com "tentar novamente". Recarrega no evento de importação.
- O dashboard antigo (abas clientes/usinas, cards, listas de pendências) é removido da página; `getFinanceiroDashboard` e seu teste permanecem.

Painel (`Modal`): título `Boleto gerado`; `Baixar boleto` (abre `boletoUrl`), `Copiar link de pagamento` (`invoiceUrl ?? boletoUrl`), e `Fatura Copel (PDF)` (`downloadBillingInvoice(invoiceId)`) **somente** quando `fatura.billingMode === 'unified'`. Fechar → `onClose` recarrega a lista (o cliente some).

- [ ] **Step 1: Testes falhando:** dois grupos renderizados com contagem; linha com `bloqueio RULE_MISSING` mostra `Cliente sem regra de cobrança.` e botão desabilitado; clique em Gerar boleto chama o serviço com `invoiceId`, abre o painel e, ao fechar, recarrega; painel com `billingMode:'unified'` tem 3 ações, com `'separate'` e com `null` tem 2 (sem "Fatura Copel"); erro do backend vira toast com a mensagem literal; estado vazio.
- [ ] **Step 2:** FAIL. **Step 3:** Implementar (inclui checkbox de débito automático na UC, com teste de que o valor é enviado como `debitoAutomatico`). **Step 4:** PASS + `npm run build` + `npm run lint`.
- [ ] **Step 5:** Commit `feat(frontend): financeiro por usina com gerar boleto`.

### Task 12: Documentação, validação final e revisão

- [ ] **Step 1:** Atualizar `Documentos/md/architecture/FATURAS_E_COBRANCAS.md`: §35 (fatura da concessionária junto do boleto só na unificada), §32 (resolução `auto` implementada), nota de que exclusão/reprocesso sem boleto substituem o bloqueio de reprocessamento da F7; `Documentos/md/architecture/PENDENCIAS.md` (pendência de pagar concessionária não nasce em boleto separado).
- [ ] **Step 2:** Validação completa, colando a saída real: suíte backend (`unittest discover -s tests`), `tests.test_sqlite_migrations`, `npm --prefix frontend run build`, `npm --prefix frontend test`, `npm --prefix frontend run lint`.
- [ ] **Step 3:** Verificação manual em ambiente local com ASAAS sandbox: cadastrar três UCs com os códigos `000000000000101/102/103`, importar os três PDFs GD pelo botão do cabeçalho, conferir GD I/GD II na tela Faturas, gerar um boleto unificado e um separado, conferir o painel. Se não houver credencial sandbox configurada, registrar como não executado.
- [ ] **Step 4:** `hub-frontend-reviewer` sobre Tasks 8–11 e `hub-code-reviewer` sobre a branch inteira; corrigir BLOCKs.
- [ ] **Step 5:** Orquestrador registra a entrega e as evidências em `Documentos/md/history/PROGRESS.md`; commit `docs: redesenho de faturas e financeiro`.
