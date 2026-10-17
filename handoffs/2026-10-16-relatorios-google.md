# Handoff — Relatórios: Google Docs/Sheets/Slides a partir dos dados do HUB

Data: 2026-10-16

## Task

Criar uma página "Relatórios" no HUB que gera Google Docs/Sheets/Slides
reais (não exportação de `.docx`/`.xlsx`/`.pptx`) a partir de dados já
existentes no sistema — Cadastro (clientes/UCs/usinas), Financeiro (faturas)
e Rateio (por usina/UC) — reaproveitando a conta Google OAuth já conectada
por empresa (`GoogleAccount`), excluindo dado sigiloso.

Spec: `docs/superpowers/specs/2026-10-16-relatorios-google-design.md`
Plano: `docs/superpowers/plans/2026-10-16-relatorios-google.md` (13 tasks,
executado via subagent-driven-development)

## Pipeline executado

13 tasks, cada uma com implementador fresco + revisor fresco (hub-backend-
developer/hub-backend-reviewer para Tasks 1-9, hub-frontend-developer/hub-
frontend-reviewer para Tasks 10-12), mais 2 gates holísticos:

1. Task 9 — revisão holística do backend inteiro (Tasks 1-8): **BLOCK** na
   primeira passada (2 bugs reais escondidos por mocks: `valor` de fatura
   vinha como `float` e quebrava os renderizadores; chave de documento do
   cliente estava errada e a máscara de CPF nunca ativava). Corrigidos num
   fix dispatch, re-review **PASS**.
2. Task 12 — revisão holística do frontend (Tasks 10-12): **PASS**
   (com notas não-bloqueantes de acessibilidade, resolvidas na própria
   Task 12).
3. Task 13 — gate de segurança final (`hub-security-reviewer`, obrigatório
   por convenção do projeto para qualquer mudança em OAuth/RBAC/dado
   pessoal): **BLOCK** na primeira passada, **PASS_WITH_NOTES** depois do
   fix. Ver seção "Achados de segurança corrigidos" abaixo — isto é a parte
   mais importante deste handoff.

Todas as rulings do controller (decisões tomadas sem pausar o fluxo, quando
um achado de revisão conflitava com o texto literal do plano) estão
registradas no ledger `` .superpowers/sdd/2026-10-16-relatorios-google/progress.md ``
deste worktree, incluindo o motivo e o custo de cada uma estar errada.

## O que foi implementado

### Backend
- `backend/services/permission_service.py` — permissão nova `reports.read`
  (owner/admin/financial, não operator/viewer).
- `backend/config.py` — `GOOGLE_DRIVE_SCOPES` ganhou `drive.file` ao lado do
  `drive.readonly` já existente (ver seção de segurança — os scopes
  `documents`/`spreadsheets`/`presentations` propostos originalmente na spec
  foram REMOVIDOS por serem excessivamente amplos).
- `backend/services/google_reports_auth.py` (novo) — `get_report_credentials`,
  checa se a conta Google ativa tem `drive.file` concedido antes de qualquer
  chamada ao Google; `ReportScopeError`/`ReportAccountMissingError`.
- `backend/services/google_report_renderers.py` (novo) — `ReportTable`
  (forma canônica `title/headers/rows`), `render_as_doc`/`render_as_sheet`/
  `render_as_slide`, cada um cria o arquivo nativo via Drive API e escreve o
  conteúdo via a API de conteúdo respectiva (Docs/Sheets/Slides).
- `backend/services/reports_service.py` (novo) — `gerar_relatorio`,
  orquestra credencial → pasta de destino → coleta de dado → renderização.
  `_coletar_cadastro` (mascara CPF), `_coletar_financeiro` (distingue
  `statusInterno` de `asaasStatus`, inclui cliente/UC), `_coletar_rateio`.
- `backend/routes/report_routes.py` (novo) — `GET /reports/tipos`,
  `POST /reports/gerar`, RBAC `reports.read`, rate limit `10/min`,
  mapeamento de erro (400/404 `GOOGLE_ACCOUNT_MISSING`/409
  `GOOGLE_SCOPE_MISSING`/201).
- `backend/services/drive_service.py` — `_build_oauth_credentials()`
  corrigido pra usar os scopes realmente concedidos no refresh de token (ver
  segurança).

### Frontend
- `frontend/src/services/reportsService.ts` (novo).
- `frontend/src/pages/ReportsPage.ts` (novo) — 3 cards, seletor de
  formato (Doc/Sheet/Slide), aviso + botão "Reconectar conta Google" quando
  falta scope.
- Item de navegação em `frontend/src/components/Sidebar.ts` (seção
  "Financeiro") + ícone novo em `Icon.ts` + rota em `router.ts`.
- CSS em `frontend/src/styles/settings.css`.
- Testes: `frontend/src/__tests__/ReportsPage.test.ts`.

## Achados de segurança corrigidos (IMPORTANTE — leia antes de usar em produção)

O gate de segurança bloqueou a primeira versão por dois motivos reais,
ambos corrigidos nesta entrega:

1. **Escopo OAuth excessivo.** A spec original pedia `drive.file` +
   `documents` + `spreadsheets` + `presentations`. Os 3 últimos são scopes
   AMPLOS — dão acesso de leitura/escrita a TODO Doc/Sheet/Slide
   pré-existente do usuário, não só aos arquivos que o HUB cria. Reduzido
   pra só `drive.file` (escopo per-arquivo, só cobre o que o próprio app
   cria/abre) — que já é suficiente pra usar as APIs de Docs/Sheets/Slides
   nos arquivos criados pelo fluxo desta feature, segundo a documentação
   pública do Google.
2. **Refresh de token quebrava contas já conectadas.** O código original
   fixava `scopes=Config.GOOGLE_DRIVE_SCOPES` (a lista atual/ampliada) no
   refresh — uma conta conectada ANTES dessa mudança (só com
   `drive.readonly`) teria o refresh rejeitado pelo Google (`invalid_scope`).
   Corrigido pra usar os scopes realmente concedidos (`account.scopes`).

## Ajuste pós-review final (findings do whole-branch review)

A revisão final de branch completo encontrou e corrigiu mais 2 pontos antes
do merge:

1. **Campo de competência adicionado na UI.** A spec pedia esse campo e a
   Task 11 não incluiu — `ReportsPage.ts` agora mostra `<input type="month">`
   nos cards Financeiro/Rateio (não no Cadastro, que não usa esse filtro).
   Isso também reduz o risco de timeout do item 6 abaixo, já que o usuário
   pode escopar o relatório por competência em vez de sempre pegar o
   histórico inteiro do tenant.
2. **Slides não tenta mais `insertText` com célula vazia** (`_render_as_slide`),
   evitando uma rejeição provável da API do Google quando Cadastro/Financeiro
   têm campo em branco (ex. UC/Usina sem documento, fatura sem status).

## Riscos e limitações que NÃO foram corrigidos nesta entrega (ação necessária antes/durante produção)

1. **[Validar antes de depender da feature] Pasta de destino pode falhar com `drive.file`.**
   `_pasta_relatorios` usa a pasta raiz configurada pelo admin
   (`google_drive_root_folder_id` ou env), que não foi criada pelo próprio
   HUB. Com escopo `drive.file` (acesso per-arquivo), `files.create` com
   `parents=[pasta que o app não criou]` pode falhar com
   `insufficientParentPermissions`/404 — isso não foi possível confirmar
   sem uma credencial Google real (ambiente de dev não tem `.env` com
   credencial). **Antes de liberar pra uso real: testar com uma conta e
   pasta reais.** Se falhar, duas saídas possíveis: (a) criar uma subpasta
   "Relatórios HUB" pelo próprio app (aí ela conta como criada pelo app, e
   `drive.file` cobre), ou (b) cair pra raiz do Drive (`My Drive`, sem
   `parents`) quando a pasta configurada não foi criada pelo app.
2. **Contas já conectadas mantêm o scope amplo até reconectar.** O fix do
   refresh (ponto 2 acima) faz o token continuar válido com os scopes que
   JÁ foram concedidos — não reduz retroativamente. Uma conta conectada
   antes desta entrega, se por acaso já tinha scopes amplos de alguma
   iteração anterior de teste, só perde esse acesso quando o usuário
   desconectar e reconectar (ou revogar manualmente no
   https://myaccount.google.com/permissions). Orientar reconexão nas notas
   de release se alguma conta de teste tiver passado por isso.
3. **Verificação do app OAuth pelo Google.** `drive.file` é "non-sensitive"
   (não precisa de verificação formal pro escopo em si), mas
   `drive.readonly` (que o projeto já usava antes desta feature) é
   "restricted" — exige verificação do app + avaliação de segurança CASA
   pra uso em produção fora do modo "Testing" do Google Cloud Console. Em
   modo Testing, só funciona pra contas de teste cadastradas lá, e o
   `refresh_token` expira em 7 dias. Isso é pré-existente ao projeto (não
   nasceu com esta feature), mas vale confirmar o status de verificação
   antes de abrir Relatórios pra clientes reais fora da lista de teste.
4. **`backend/.env.example` documenta `GOOGLE_DRIVE_SCOPES=.../auth/drive`**
   (Drive inteiro) como exemplo — se o ambiente de produção seguir
   literalmente esse exemplo em vez do default reduzido do código, a
   redução de escopo desta entrega fica sem efeito prático. Revisar a
   variável de ambiente real de produção antes de depender da redução de
   escopo como mitigação de segurança.
5. **Arquivo órfão no Drive em caso de falha durante a renderização.** Se o
   arquivo nativo já foi criado via Drive API e a escrita de conteúdo
   falhar depois (ex. `valor` inesperado, erro de rede), o arquivo fica
   vazio/parcial no Drive — sujeira operacional, sem risco de segurança
   confirmado (fica no Drive da própria empresa, privado, sem
   compartilhamento). Sem limpeza automática nesta entrega.
6. **Sem fila de job.** Geração de relatório é síncrona — relatório grande
   pode sofrer timeout de request. Sem mitigação nesta entrega.
7. **Minors registrados no ledger, não corrigidos** (baixo risco, sem
   vazamento de dado): `oauth_service.py` grava os scopes PEDIDOS, não os
   concedidos (o Google ainda impõe o que foi de fato autorizado, então não
   há furo, só imprecisão de log); `competencia` no body da rota não tem
   validação de tipo (erro genérico, sem vazamento); lista de tipos válidos
   de relatório repetida em 3 lugares no código (`_TIPOS_VALIDOS`,
   `_COLETORES`, `_TIPOS` da rota) — oportunidade de DRY numa limpeza
   futura.

## Validação final

- Backend: 732 testes, 0 falhas reais (2 skipped, 2 expected failures,
  mesma contagem de antes da feature).
- Frontend: 33 testes (6 arquivos), 0 falhas; build de produção OK.
- Revisão independente: backend PASS (após 1 fix round na Task 5 e 1 na
  Task 6), holístico backend PASS (após 1 fix round na Task 9), frontend
  PASS (com notas resolvidas), segurança PASS_WITH_NOTES (após 1 fix round
  na Task 13).

## Arquivos (branch `feat/relatorios-google`, baseada em `feat/b2-object-storage-endpoint`)

Backend: `permission_service.py`, `config.py`, `drive_service.py`,
`google_reports_auth.py` (novo), `google_report_renderers.py` (novo),
`reports_service.py` (novo), `report_routes.py` (novo), `app.py`, testes
correspondentes.

Frontend: `reportsService.ts` (novo), `ReportsPage.ts` (novo),
`Sidebar.ts`, `Icon.ts`, `router.ts`, `settings.css`, `ReportsPage.test.ts`
(novo).
