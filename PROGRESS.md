# HUB — Progresso
- [ ] STORAGE-1A — ativação operacional R2 iniciada em 2026-09-30; `R2_READY=false`, `STORAGE_1_DONE=false`. Consulta de leitura à conta Cloudflare conectada (`GET /accounts/{account_id}/r2/buckets`) falhou com erro 10042: `Please enable R2 through the Cloudflare Dashboard`. O usuário informou que habilitará o R2 nessa conta; ainda não confirmou a ativação. `backend/.env` e o processo local não continham as seis variáveis de storage R2; nenhuma credencial foi usada ou gravada, nenhum bucket foi criado e nenhuma variável do Render foi alterada. A configuração operacional foi documentada em `DEPLOY.md`, sem alteração de API, schema, frontend ou código de produto.
  - Validação local executada: `rtk cmd /c backend\venv\Scripts\python.exe -m unittest backend.tests.test_object_storage backend.tests.test_fatura_concessionaria_upload` — 36 testes OK (storage simulado); `rtk cmd /c backend\venv\Scripts\python.exe -m unittest discover -s backend\tests` — 648 testes OK, 2 ignorados; `rtk cmd /c backend\venv\Scripts\python.exe -m unittest backend.tests.test_sqlite_migrations` — 21 testes OK; `rtk npm.cmd --prefix frontend run build` — OK, 323 módulos. Esses resultados não comprovam integração real com R2.
  - Aceite real pendente: [ ] bucket privado e sem `r2.dev`/domínio público; [ ] credencial Object Read & Write limitada ao bucket; [ ] escrita, existência física, leitura e remoção de objeto de teste; [ ] upload PDF real pela API com `Document` em R2 e chave opaca; [ ] download pela API com autenticação, `faturas.read`, vínculo, SHA-256, headers e filename; [ ] negação cruzada entre empresas mesmo com IDs/chave conhecidos e contrato do platform admin; [ ] leitura real legada após habilitar R2; [ ] falha de credenciais/provider sem persistência válida ou vazamento; [ ] ausência de segredo em responses/logs e acesso público direto; [ ] configuração e validação de produção. Não houve migração/exclusão de arquivos legados, deploy nem início de STORAGE-2.
- [x] ARCH-PLATFORM-1 — `BOUNDARY_READY=true` para o código validado localmente em 2026-09-29; `SAAS_BILLING_READY=false`. Transporte ASAAS com URL/chave injetadas, `AsaasClient(empresa_id)` tenant preservado, serviço e webhook da plataforma com `PLATFORM_ASAAS_*` exclusivos e ledger próprio de recebimento. `/api/v1/webhooks/asaas` e referências tenant antigas permanecem intactos. Não há emissão, conciliação, ativação, preços, ciclos ou política de inadimplência SaaS; nenhuma credencial real foi usada, webhook externo homologado ou deploy executado. Validação: teste focado de fronteira 45/45 OK, regressões B0–B3 46/46 OK, migrations SQLite 21/21 OK (banco vazio e upgrade desde `v6b9d4e8f3a1`, unicidade e guarda de downgrade), regressão backend final 637 executados, 2 ignorados, 0 falhas; build frontend de produção OK (323 módulos); `git diff --check` focado OK. Revisão independente de arquitetura/segurança PASS após correções de URL vazia, pagamentos outbound de duas empresas/plataforma, falha de commit e concorrência. Gate 1 de código concluído; ativação operacional da conta da plataforma e cobrança SaaS seguem bloqueadas até definição e homologação próprias.
- [ ] STORAGE-1 — implementação de código e gate local concluídos em 2026-09-30; ativação operacional R2 pendente, `R2_READY=false`. `FaturaConcessionaria.document_id` obrigatório continua apontando a `Document`, que guarda provider/ref física; SHA-256 continua apenas na fatura. Novos uploads usam chave opaca no provider S3 configurado para R2 em produção, ou storage local em desenvolvimento/testes. Download autenticado pelo backend exige `faturas.read`, tenant e vínculo da fatura, com rota de administrador de plataforma e empresa explícita; fornece nome sanitizado com cliente, competência e vencimento. Drive/local legados seguem legíveis; Drive foi validado por adapter somente leitura. Não houve migração ou exclusão legada, nem schema/migration nova. O limite 10 MiB/10 páginas, parser, deduplicação e contratos anteriores foram preservados. Validação: 62 testes afetados OK na revisão final (incluem R2 mockado, Drive/local legados, duas empresas, RBAC/admin, hash, duplicata, falhas banco/storage e nome); regressão backend 647 executados, 2 ignorados, 0 falhas antes do último delta no adapter Drive, coberto pelos 62 testes finais; SQLite migrations 21/21 OK em banco vazio e upgrade do estado anterior; frontend build OK (323 módulos); `git diff --check` focado OK. Revisão independente PASS após correção de redirect administrativo e mock do adapter legado. O bucket privado, configuração e leitura real no R2 não puderam ser validados sem infraestrutura/credenciais; não houve deploy. STORAGE-2 não foi iniciada.
- [x] Arquitetura multiagente — Task Contract e pipeline nativo (HUB-12) — 2026-09-30. Criado `docs/TASK_CONTRACT.md` como contrato operacional canônico, com `Base revision`, `Deliverable revision`, `Approval required`, ownership exclusivo de arquivos, gates proporcionais por camada/risco e vínculo dos pareceres à revisão final. O fluxo nativo do Paperclip foi revalidado na HUB-27 com a equipe atual e sem subtarefa artificial de revisão: `pilot-v1` recebeu `BLOCK`, retornou ao HUB Backend Developer por `returnAssignee`, foi reenviado ao mesmo stage como `pilot-v2` e recebeu `PASS` independente do HUB Code Reviewer. O estado final registrou `status=done`, `executionState.status=completed`, `currentParticipant=null`, `returnAssignee.agentId=a494e7d2-3791-49cc-9cd1-6fdee4dbc2a0`, `lastDecisionOutcome=approved` e o stage `297160b0-5bbb-4957-88c8-233b588fff55` concluído. Nenhum arquivo de produto, contrato REST, RBAC, tenancy, migration, credencial ou deploy foi alterado. Validação: parecer final do HUB Code Reviewer em HUB-27 = PASS para `pilot-v2`; `git diff --check -- docs/TASK_CONTRACT.md PROGRESS.md` OK.
- [x] Faturas: estilo do filtro Competência — 2026-09-29. O campo nativo de mês recebeu a mesma superfície, borda, altura e estado de foco dos demais filtros da tela, usando tokens do tema; o calendário nativo acompanha os modos claro e escuro. Apenas CSS foi alterado, sem mudar o valor ou a lógica de filtragem. Validação: build de produção Vite OK (323 módulos) e `git diff --check` no CSS OK. Sem servidor local ou teste visual em navegador nesta entrega.
- [x] UI-3 follow-up — 2026-09-29. Revisao independente corrigiu a classificacao da lista inicial vazia de Faturas (nao mais tratada como filtro ativo) e adicionou acao de tentativa de novo carregamento aos estados de erro de Clientes, Usinas, UCs, Pendencias e Faturas. Validacao final registrada abaixo.
- [x] Configurações: OAuth local, Asaas e divisão da página — 2026-09-29. Corrigido `backend/.env` local para permitir OAuth HTTP explícito com `FLASK_DEBUG=true`, callback em localhost e retorno ao frontend local; exemplo e instruções em `backend/.env.example`/`DEPLOY.md`. A integração Asaas agora solicita tipo (chave API ou token do webhook) e ambiente, gera automaticamente os nomes técnicos exigidos pelo backend, distingue os dois segredos na interface e permite adicionar outra credencial mesmo quando já existe uma. `SettingsPage.ts` foi dividido por seção e ações em oito arquivos, todos com no máximo 269 linhas, preservando contratos e fluxos existentes. Validação: configuração OAuth local aceita por `_configure_transport_security()` sem servidor; TypeScript sem erros; ESLint sem erros (16 avisos de complexidade); build Vite OK (317 módulos); `git diff --check` OK. Nenhum deploy ou migration.
- [x] UI-F3 — Padronização visual, busca automática e tema global — 2026-09-28. Infraestrutura local de tema adicionada com `ThemePreference` (`dark`, `light`, `system`) persistido em `localStorage` como `hub_theme`; `data-theme` no elemento raiz aplica tokens semânticos `--hub-*`, e `Sistema` acompanha `prefers-color-scheme` sem reload. O Dark segue padrão e compatível com a aparência salva existente; o tema claro define hierarquia própria de fundo, superfícies, bordas, texto e estados. Header ganhou alternância imediata ☀️/🌙; Configurações → Aparência passou a expor Escuro, Claro e Sistema. Layout global é a primeira etapa migrada por aliases de compatibilidade; Faturas é a página piloto, sem cores literais próprias em seus estados e sem alteração dos contratos/billing/upload. A busca de cliente/UC preserva filtros e paginação, aplica filtro após 300 ms de inatividade, cancela o timer ao continuar digitando, evita consulta redundante e restaura a listagem ao limpar. Páginas restantes continuam na migração gradual por tokens. Validação: `npm --prefix frontend run build` OK (TypeScript + Vite, 310 módulos) e `git diff --check` OK. Sem alteração de backend, API, migration ou deploy.
- [x] Workflow de CI reconstruído — 2026-09-28. `ci.yml` valida backend e frontend em `push` para `develop`/`main` e em PR para `main`; após cinco execuções bem-sucedidas de `develop` desde o último commit em `main`, abre uma PR de promoção. O merge usa a SHA testada, e falhas na PR de promoção geram Issue sem duplicação. O secret `PROMOTION_TOKEN` foi configurado e o workflow foi integrado em `develop` pelas PRs #65 e #66. Validação: YAML aceito pelo parser; localmente, 591 testes de backend OK (2 ignorados), ESLint sem erros (113 avisos), TypeScript OK e build Vite OK (309 módulos); no GitHub, as execuções `36433236092` e `36433702320` passaram em testes, lint/build e contagem de promoção. As actions usam v7 para evitar o aviso de runtime Node 20. Nenhuma promoção para `main` foi executada nesta tarefa.
- [x] Consolidacao financeira e faturas — 2026-09-28. O branch `develop` reune o upload de faturas da concessionaria, identidade documental de UC, regras de cobranca, calculo e diagnostico financeiro, tarifas regulatorias e migrations reversiveis ate `v6b9d4e8f3a1`. As fixtures Copel versionadas sao anonimizadas; PDFs privados continuam ignorados. Validacao final: regressao backend com 591 testes OK (2 ignorados), historico Alembic SQLite com 20 testes OK, build de producao frontend OK (309 modulos) e revisao independente de tenancy, FKs compostas, RBAC e segredos sem achados remanescentes apos a correcao das fixtures. Sem deploy ou migration de producao nesta entrega.
- [ ] Hotfix F6.2 — upload operacional HTTP 503, 2026-09-26. Causa comprovada no ambiente de desenvolvimento: o refresh token OAuth ativo da empresa 1 não é descriptografável com a `SECRET_ENCRYPTION_KEY` atual (`cryptography.fernet.InvalidToken` → `ValueError` em `GoogleAccount.get_refresh_token()`); a rota `client_routes.upload_concessionaria_invoice` converte a exceção em `503 DOCUMENT_STORAGE_UNAVAILABLE` com corpo `{"code":"DOCUMENT_STORAGE_UNAVAILABLE","error":"Armazenamento de documentos indisponivel."}`. A falha ocorre em `drive_service._build_oauth_credentials`, após extração e vínculo da UC, antes do envio ao Drive e antes da persistência. PostgreSQL respondeu `SELECT 1`; revisão Alembic `u5a8c3d7e2f9`. O PDF real `SegundaViaCopel.pdf` foi lido sem upload: layout Copel reconhecido, UC documental de 15 dígitos com uma correspondência canônica em `ConsumerUnit.codigo` da empresa 1 e cliente existente. Contagens antes/depois da investigação: 1 Documento e 0 faturas concessionárias na empresa 1. O fallback para conta de serviço agora também cobre falha de descriptografia do token; teste isolado reproduziu 503 antes do ajuste e comprova sucesso com fallback, 503 sem credencial alternativa e ausência de gravação parcial. Neste ambiente, `credentials.json` não existe, portanto o upload real continua bloqueado até restaurar a chave correta ou reconectar OAuth. O POST real com o PDF foi rejeitado pela revisão automática por poder enviar dados sensíveis ao Google Drive e persistir a fatura; seu traceback durante a requisição não foi capturado. Traceback completo da inicialização do Drive foi capturado em leitura: antes da correção termina em `InvalidToken`/`ValueError`; depois, no fallback, em `FileNotFoundError` de `credentials.json`. Arquivos: `backend/services/drive_service.py`, `backend/tests/test_fatura_concessionaria_upload.py`, `PROGRESS.md`. Validação: upload focado 23 OK; regressão backend 586 OK (2 ignorados); migrations SQLite 20 OK; build frontend OK (309 módulos). Sem deploy ou merge.
- [ ] Sprint UI-R1 — responsividade global, 2026-09-26. Corrigida a cascata que ocultava o menu móvel e deixava a sidebar `sticky`; sidebar usa `--sidebar-width` (200 px em >=1440, 180 px em 1367–1439, 160 px em 1025–1366, 64 px em 769–1024; menu recolhível em <=768). Ícones, texto, rodapé e navegação por teclado/foco foram preservados; menu fecha ao voltar ao desktop. Área central, painéis e formulários usam `min-width:0`; tabelas mantêm tamanho legível e rolam no próprio wrapper; filtros de Faturas passam de 3 para 2 colunas em <=760 e 1 em <=520. Inspeção estática cobriu 1920, 1440, 1280, 1024, 768, 390 e transições 768/769 e 1024/1025. Build e lint frontend OK; revisão independente do menu PASS; `git diff --check` OK. Validação visual no navegador, redução progressiva real e regressão visual de todos os módulos pendentes porque nenhuma superfície de navegador estava disponível neste ambiente. Sem alterações de backend, deploy ou merge.
- [x] Sprint CAD-1 — validação e normalização dos cadastros, 2026-09-26. UC Copel aceita 12 dígitos (prefixo `000`) ou 15 dígitos e preserva zeros; `codigo_aneel` permanece legado sem participar do vínculo de faturas. Cadastro, edição, importação, upload, processamento e cálculo operacional usam a identidade documental canônica; outras concessionárias mantêm seus códigos. Nenhuma UC existente foi migrada, e correspondências ambíguas continuam bloqueadas. Cliente usa nome obrigatório com trim e limite 200, CPF com verificadores e telefone brasileiro opcional no contrato atual, validado quando informado; UC.documento usa CPF/CNPJ com verificadores quando alterado. Formulários mostram erros junto aos campos no tema do HUB e preservam valores legados intocados. Migration reversível amplia `clients.nome` de 150 para 200, com guarda contra truncamento no downgrade. Validação: regressão backend 585 testes OK (2 ignorados); migrations SQLite 20 OK, incluindo banco vazio e upgrade de estado anterior; testes focados de importação, UC e tenancy 39 OK; build frontend OK (309 módulos); lint OK (0 erros, 112 avisos); `git diff --check` OK. O PDF operacional real da empresa 1 não foi reimportado nesta entrega. Sem deploy ou merge.
- Revisão CAD-1, 2026-09-27: vínculo documental Copel agora exige concessionária correspondente, além de código e empresa; `PUT /clients` sem `ucs` preserva UCs/status e rejeita com 404 um ID de UC alheia antes de alterar vínculos. Código/documento inválido em `POST/PUT /ucs` retorna 400, cliente inexistente retorna 404, CPF duplicado retorna 409, e códigos de outras concessionárias são preservados sem normalização. Validação manual rejeita dígitos Unicode em telefone/CPF/CNPJ. Nos formulários, a validação alcança as UCs aninhadas, mostra o campo com erro e mantém cadastros legados intocados. Validação executada: 74 testes focados CAD-1 OK, mais 34 testes focados após a correção de CPF duplicado; regressão final backend 591 executados, 2 ignorados, 0 falhas; migrations SQLite 20 OK (banco vazio e upgrade anterior); build frontend OK (309 módulos); lint 0 erros e 113 avisos; `git diff --check` OK. Revisão independente PASS nos fluxos de cadastro; a correção posterior de CPF duplicado foi coberta por teste novo e regressão final. Interação no navegador e upload com PDF real não foram repetidos. Sem deploy ou merge.
- [ ] Ajuste de identidade da UC no upload operacional, 2026-09-26. O 422 observado foi `{"code":"UC_NOT_FOUND","error":"UC da fatura nao encontrada nesta empresa."}`. FaturasPage envia `FormData` com `arquivo` para a rota da empresa selecionada. Upload, processamento e calculo passam a comparar somente `ConsumerUnit.codigo` com a UC documental, com empresa explicita; `codigo_aneel` fica preservado no banco sem uso no CRUD ou matching. A interface exibe um unico campo UC. A fixture Copel sem GD continua importavel quando ha match unico; ausencia de GD afeta a cobranca posterior. Após CAD-1, códigos Copel de 12 dígitos também são reconhecidos pela correspondência canônica sem migração automática; a correspondência da UC real da empresa 1 com o PDF ainda não foi verificada, pois o valor documental de 15 dígitos não foi fornecido. O upload operacional não foi repetido. Validação histórica desta etapa: teste novo primeiro falhou (201 em vez de 422); suites focadas de upload, processamento e calculo 55 OK; regressao completa 575 executados, 573 aprovados, 2 ignorados; migrations SQLite 19 OK; frontend `tsc && vite build` OK (308 modulos); `git diff --check` OK. Sem deploy ou merge.


- [x] Hotfix — **500 no contexto das empresas resolvido no banco de desenvolvimento**, 2026-09-25.
  `GET /api/v1/dashboard/resumo` foi reproduzido antes da correção com
  `psycopg2.errors.UndefinedColumn: pendencias.fatura_concessionaria_id` em
  `dashboard_service.py:91`. O Neon apontado por `backend/.env` estava em
  `q1e6a4b9c2d7`, sem essa coluna; o código F6.1 já a selecionava. A lista
  de Pendências e a nova lista de faturas também usavam o mesmo campo; as três
  rotas foram reproduzidas em SQLite temporário na revisão `q1`, todas com
  `OperationalError: no such column: pendencias.fatura_concessionaria_id`.
  Após confirmação explícita do usuário de que o endpoint é de desenvolvimento,
  foram aplicadas apenas nele as migrations `r2f7b5c0d3e8`, `s3c8d1e6f9a2`,
  `t4d9e2a7c1b5` e `u5a8c3d7e2f9`; `flask db current` confirmou
  `u5a8c3d7e2f9 (head)`. Nenhuma migration foi aplicada em produção.
  - Antes do upgrade: oito Pendências existentes; a cadeia adiciona tabelas
    de cálculo, proteção de imutabilidade, coluna nullable/FK/unicidade F6.1
    e ajuste reversível de CHECK comercial. Teste novo `q1 → head` preserva
    Pendência anterior e a nova coluna. Suíte SQLite: **18 OK**; regressão
    backend completa: **574 executados, 572 OK, 2 ignorados, 0 falhas**.
  - Após o upgrade, GET de dashboard, clientes, UCs, usinas, faturas e
    Pendências retornou **200** para owner comum e administrador da plataforma
    em empresa selecionada. A lista explícita de faturas da plataforma
    retornou **200**; a rota tenant sem escopo explícito retornou **403**.
    Cliente de outra empresa retornou **404** para o usuário comum.
    `git diff --check` sem erros. Não houve deploy ou merge.

- [ ] Sprint UI-F2 — **PARTIAL**, 2026-09-25. Faturas ganhou listagem de
  documentos da concessionária com filtros no servidor, paginação, cliente,
  UC, todos os vínculos de usina comprovados, valor/vencimento, processamento,
  pendências abertas e cobranças ASAAS contextuais (zero ou várias por UC e
  competência). O detalhe separa documento, cobrança, pendências e histórico;
  o upload existente recarrega a lista. A emissão pela interface exige uma
  fatura selecionada, validada e sem pendência aberta; valor e vencimento
  comerciais seguem informados pelo operador. O PDF original não oferece
  acesso fictício. Operator/viewer conservam a listagem legada de cobranças,
  pois não possuem `billing_calculations.read`.
  - Contrato `GET /billing-calculations/invoices`: filtros antes da paginação,
    metadados `pagination`, valores documentais e cobranças contextuais
    tenant-scoped. Sem FK entre original e cobrança, nenhuma associação é
    apresentada como documentalmente comprovada.
  - Validação executada: `rtk npm.cmd --prefix frontend run build` **OK**
    (TypeScript e Vite, 308 módulos); `rtk npm.cmd --prefix frontend run lint`
    **0 erros, 111 warnings**; `git diff --check` sem erros de whitespace;
    compilação Python (`py_compile`) do backend novo **OK**. Revisão
    independente: **CHANGES_REQUIRED** pelos limites abaixo.
  - Pendente para DONE: `POST /faturas` ainda não recebe o ID do documento
    nem verifica os bloqueios F6.1; uma chamada direta pode contornar a trava
    da interface. A lista unificada também não está autorizada para
    operator/viewer pela permissão atual. Não houve prova de navegação em
    browser, de isolamento HTTP com duas empresas nem regressão Python:
    `.venv/Scripts/python.exe` não existe neste workspace. Os comandos de
    regressão backend e migrations SQLite foram tentados e não iniciaram.
    Sem deploy ou merge.

- [ ] Sprint UI-C1 — **PARTIAL**, 2026-09-24. Regras de cobrança têm listagem,
  busca/filtros, editor em rota própria, ajuda contextual, RBAC, seleção por UC
  com retorno seguro e confirmação de impacto. O padrão efetivo é o assignment
  `company`; sem ele, a empresa pode criar uma regra padrão por fluxo guiado,
  escolhendo método/tarifa explicitamente. Não há seed automático nem desconto
  presumido. A edição de regra herdada não cria vínculo direto na UC.
  - O desconto operacional vem de `ConsumerUnit.desconto` (`20` ou `20%` = 20%,
    vazio = nenhum), com validação no CRUD e importação; valor legado inválido
    bloqueia nova execução. `tarifa_especifica` ignora desconto adicional.
    Snapshots anteriores permanecem imutáveis. A migration `u5a8c3d7e2f9`
    aceita `none/null` em `tarifa_fixa_com_desconto`, preserva legados e bloqueia
    downgrade com dados incompatíveis. Esse método continua não executável.
  - Faturas mostra PDFs da concessionária separados das cobranças ASAAS.
    O botão "Enviar PDF" fica ao lado de "Emitir cobrança", sem seletor de
    cliente: o backend extrai a UC documental e vincula o cliente apenas se
    houver correspondência única na empresa (`codigo`/`codigo_aneel`). Layout,
    UC ou vínculo ambíguos falham antes do armazenamento; duplicata legada com
    cliente divergente retorna conflito, sem reescrever a fonte. A rota por
    cliente permanece compatível. Administrador da plataforma exige empresa
    explicitamente selecionada. Upload não emite cobrança, não chama ASAAS,
    não altera Storage e não antecipa a validação F7 da UC.
  - Validação final 2026-09-25 após o upload automático: regressão backend
    **571 executados, 569 aprovados, 0 falhas, 2 ignorados**; suíte focal de
    upload **16 OK** (inclui UC de outro tenant, ambiguidade, RBAC, deduplicação
    e conflito com cliente legado). Suíte focal anterior de
    importação/cálculo/regras/migrations **63 OK**; `tsc && vite build`
    **OK (307 módulos)**; ESLint **0 erros, 106 warnings**;
    `git diff --check` **OK**. Revisão independente do fluxo novo: **PASS**.
  - Pendente para DONE: prova de navegação/DOM em navegador para busca,
    criação/edição e retorno UC → Regras → UC, indisponível no runner frontend
    atual. A migration foi validada em SQLite vazio/upgrade anterior; ainda não
    houve prova em PostgreSQL isolado. Nenhum deploy ou merge.

- [x] Sprint C5.4.1 — **DONE**, 2026-09-24. A base regulatória global agora
  possui migration, `RegulatoryTariff`/importação/prévia duráveis, endpoints
  protegidos por `is_platform_admin` e cartão em Configurações. O fluxo é API
  CKAN oficial ou CSV ANEEL UTF-8 → prévia privada com hash SHA-256/TTL → confirmação transacional
  e idempotente → `RegulatoryTariffRepository` → Fio B. Não há HTTP em runtime.
  - O parser aceita somente colunas oficiais ANEEL exigidas e componente
    `TUSD_FioB` em Tarifa de Aplicação/SCEE/R$/MWh; rejeita schema, unidade,
    dimensão ou componente não comprovado. Decimal é persistido como texto exato
    para manter precisão também em SQLite. Conflito de chave natural não sobrescreve.
  - Primeira publicação real: importação `id=1`, `completed`, 53 criados e zero
    mantidos, em 2026-09-24T14:47:56. O CKAN ANEEL forneceu o recurso
    `e8717aa8-2521-453f-bf16-fbb9a16eea39`, versão
    `2026-09-17T15:31:25.510600`, para COPEL-DIS, com cobertura de 2026-06-24
    a 2027-06-23. Os 53 registros persistem no PostgreSQL migrado até
    `q1e6a4b9c2d7 (head)`.
  - Diagnóstico/correção 2026-09-24: o PostgreSQL configurado estava em
    `l6f1a5b8c2d4`, sem as tabelas `regulatory_tariff_*`, o que explicava o 500
    do status. Com autorização explícita, a cadeia `m7 → n8 → o9 → p0 → q1`
    foi aplicada e `flask db current` confirmou `q1e6a4b9c2d7 (head)`. O status
    retorna 503 para indisponibilidade; a UI informa permissão, conexão e erro
    interno separadamente.
  - Validação desta correção: teste isolado de status vazio, prévia, confirmação,
    autorização e indisponibilidade **4 OK**; `npm --prefix frontend run build` OK;
    `git diff --check` OK.
  - Validação: testes de importação/regulatório/Fio B **39 OK**; migration SQLite
    executada; frontend (`tsc && vite build`) aprovado; regressão backend **504 OK**
    (somente warnings preexistentes); `git diff --check` aprovado.
  - C5.4.3: CSV ANEEL passou a aceitar até 100 MiB por configuração exclusiva,
    com cópia/hash incremental em temporário privado, leitura streaming e remoção
    em `finally`. A confirmação permanece baseada no plano persistido; o comando
    `purge-regulatory-tariff-previews` limpa previews expiradas e órfãos. Histórico
    visual e HUB Storage permanecem fora do escopo. O limite externo do Render não
    está documentado publicamente e precisa ser comprovado em ambiente não produtivo.

  - CKAN, 2026-09-24: `POST /imports/ckan/preview` consulta somente o host oficial,
    descobre o recurso anual por metadata e filtra COPEL-DIS/TUSD_FioB/Tarifa de
    Aplicação/SCEE/R$/MWh; prévia e confirmação reutilizam o contrato existente.
    Leitura real do recurso `e8717aa8-2521-453f-bf16-fbb9a16eea39` retornou 53
    registros, versão `2026-09-17T15:31:25.510600`; a prévia foi confirmada e
    publicou os 53 registros acima. Histórico visual de importações continua pendente.
  - Interface: os seletores do modal ANEEL usam explicitamente os tokens escuros do
    HUB, inclusive as opções nativas, para preservar contraste e legibilidade.

- [x] Sprint C5.4 — **DONE**, 2026-09-24. O fluxo Fio B fecha com tarifa ANEEL
  real publicada no PostgreSQL; `backend/data/regulatory_tariffs.json` permanece
  somente como fallback compatível fora do contexto da aplicação. O registro E2E é
  COPEL-DIS,
  `TUSD_FioB`, B1 Convencional/Residencial/SCEE, Tarifa de Aplicação,
  Resolução Homologatória 3.592/2026. A fonte, id/hash do recurso, valor bruto
  `214.53560037400001 R$/MWh`, conversão exata a R$/kWh e vigência diária
  2026-06-24–2027-06-23 ficam auditáveis no registro.
  - `RegulatoryTariffRepository` lê primeiro os 53 registros regulatórios publicados
    e fornece `RegulatoryFioBTariff` ao `FioBResolver`; não há HTTP em cobrança.
  - Competências mensais só são elegíveis quando totalmente contidas na vigência:
    2026-07 a 2027-05. Junho/2026 e junho/2027 permanecem MISSING_DATA, evitando
    aplicação retrospectiva por "latest tariff". Documento válido continua tendo
    prioridade sobre REGULATORY; ambiguidade documental bloqueia.
  - O parser/normalizador Copel agora preserva classe e subclasse Residencial já
    observadas no PDF, permitindo a correspondência exata da dimensão ANEEL.
  - GD I é NOT_APPLICABLE; GD II usa .15/.30/.45/.60/.75/.90 em 2023–2028;
    GD III e 2029+ são UNSUPPORTED. TE/TUSD continuam um único kWh canônico.
  - Ordem preservada: bruto → desconto → PIS/COFINS vinculados → Fio B → piso
    zero → ROUND_HALF_UP final. Quadros fiscais agregados não são deduzidos nem
    rateados. `fio_b_components` preserva GD, competência, energia, tarifa,
    fonte, vigência, referência, versão, transição, valor e evidências.
  - Prova C5.4.4: para competência 2026-09, B1/CONVENCIONAL/Residencial/SCEE,
    1000 kWh e GD II (.60), o valor original `214.53560037400001 R$/MWh` foi
    convertido com Decimal para `0.21453560037400001 R$/kWh`; o Fio B foi
    `128.721360224400006000`, chegou ao `CommercialDeductionResolver` e o
    `BillingCalculationEngine` concluiu `591.28` após desconto de 20%. A memória
    preserva fonte ANEEL, resource_id/URL, versão, COPEL-DIS, valores e vigência.
  - Validação C5.4.4: prova live opt-in contra PostgreSQL **1 OK**; repositório,
    Fio B, deduções comerciais e engine **79 OK**; migration SQLite verde;
    regressão backend **513 passed, 0 failed, 1 skipped**; build frontend verde e
    `git diff --check` sem erros. Sem deploy, merge ou nova importação.

- [ ] Sprint C5.5 — **PARTIAL**, 2026-09-24. O cálculo passou a ter execução e
  snapshot financeiro tenant-scoped, idempotente e auditável; a API e o diagnóstico
  administrativo usam seleção explícita de empresa e não acionam ASAAS. O snapshot
  somente existe para `CALCULATED`; `REVIEW_REQUIRED`, `MISSING_DATA`,
  `UNSUPPORTED` e `ERROR` preservam tentativa sem valor financeiro. A migration
  `s3c8d1e6f9a2` protege snapshots e execuções contra UPDATE/DELETE no PostgreSQL.
  O teste direto da trigger exige `TEST_POSTGRES_BILLING_URL` em banco isolado
  `test_*` e permanece pendente; não usar dev/produção. Histórico ANEEL e HUB
  Storage continuam pendentes.

- [x] C5.5-D — **Laboratório isolado de PDFs**, 2026-09-24. Platform admin usa
  `POST /api/v1/platform/billing-diagnostics/pdf` para validar PDF, extrair com o
  parser Copel e normalizar inteiramente em memória. Não recebe empresa/cliente/UC,
  não cria registro, snapshot ou cobrança e não chama ASAAS. Retorna 11 etapas,
  campos, compensações, warnings, blockers e erro sanitizado. O limite reutiliza
  o PDF de fatura (10 MiB/10 páginas); `BILLING_DIAGNOSTIC_TIMEOUT_SECONDS=20`
  limita a espera e o pool é limitado a duas análises. Histórico e simulação não
  são persistidos. O preflight CORS `OPTIONS` passa sem autenticação, mas o
  `POST` continua exigindo platform admin. O teste focado teve **9 OK**.
  - Hotfix F6/C5.5-D: a leitura de itens passa a iniciar na primeira linha que
    delimita todas as colunas da tabela, evitando que texto de "Segunda Via" ou
    histórico vire item financeiro. Complemento de endereço é preservado, CPF
    mascarado é `not_present` informativo e campos opcionais de iluminação
    pública não geram warning. O diagnóstico separa extração, normalização e
    elegibilidade GD; sem compensação comprovada permanece bloqueado, sem
    converter consumo. Regressão anonimizada: 4 itens, consumo, tarifas,
    tributos, total e ausência de compensação; **78 OK**.

- [x] F6.1 — **DONE no escopo implementado**, 2026-09-24. Itens opcionais de iluminação pública não
  geram ausência fiscal falsa; o processamento operacional cria Pendência
  `GD_COMPENSATION_UNVERIFIED` idempotente por empresa/fatura/origem quando UC
  validada possui usina Ativa com ativação anterior à competência e compensação não
  comprovada. O laboratório permanece sem efeitos colaterais.
  - Validação final: regressão backend **557 executados, 555 passed, 0 failed,
    2 skipped**; testes focados de pendência/laboratório **10 OK**; migration SQLite
    em banco vazio e upgrade de `s3c8d1e6f9a2` para `t4d9e2a7c1b5` com pendência
    anterior **OK**; índice UNIQUE em `(empresa_id, fatura_concessionaria_id,
    origem)` inspecionado e duplicata rejeitada; build frontend (`tsc && vite build`)
    **OK, 300 módulos**; `git diff --check` **OK**. Revisão independente: **PASS**.
  - Testes cobrem UC sem vínculo, usina inativa ou ativada após a competência,
    pendência com expectativa GD e compensação ausente, repetição da fatura, duas
    chamadas concorrentes em sessões separadas, múltiplas usinas sem atribuição
    artificial, laboratório sem pendência e GET lista/detalhe de outra empresa.
    Conferidos os vínculos de cliente, UC, documento, fatura e `plantIds`.
  - Limite conhecido: `PlantConnection` não possui início/fim de vigência ou estado
    próprio; a expectativa usa `Plant.status` e `Plant.data_ativacao`. Não existe
    notificação interna por usuário: a Pendência/listagem e `LogEntry` são o aviso
    interno disponível. Não houve envio externo. A prova de concorrência/constraint
    nesta validação foi em SQLite isolado; PostgreSQL não foi exercitado.

- [x] Sprint C5.3B — **Seleção comercial de tarifa por evento DONE**,
  2026-09-17; **C5.3 DONE, C5 global PARTIAL e F6 PARTIAL**.
  Files: contrato/serviço puro `commercial_tariff_selector.py`, testes e
  documentação. Depends-on: C5.3A/A.1 e `ResolvedBillingRule`; C5.1/C5.2
  preservadas.
  - Criados `CommercialTariffSource`, `SelectedCommercialTariff` e
    `CommercialTariffSelector`. O serviço recebe somente contratos resolvidos e
    retorna uma seleção imutável por `ResolvedCompensationTariffEvent`, com
    `BillingRuleSnapshot`, origem, tarifa selecionada, referências documentais,
    bandeira, tributação, status e issues auditáveis.
  - `tarifa_fixa` usa `company_tariff` como `configured_fixed`; `tarifa_especifica`
    usa o mesmo parâmetro como `configured_specific`. O engine C5.1/C5.2 não foi
    alterado: fixa segue 1000 × 0,70 com 20% = 560,00; específica segue 700,00
    sem desconto adicional.
  - Para `energia_compensada`, `icms_policy=exclude` seleciona
    `document_compensation` do próprio evento e política null seleciona
    `document_full`. ICMS é apenas critério de seleção. Não há dedução tributária,
    PIS/COFINS, Fio B, média, fallback ou arredondamento. O ramo documental exige
    `tariff_source=invoice`, sem reinterpretar regra manual C5.1.
  - Múltiplos eventos preservam quantidade, identidade, GD-I/GD-II, mês e tarifas
    distintas. Evento não VALID bloqueia sua própria seleção. Tarifa cheia e de
    compensação ausentes nunca substituem uma à outra.
  - Bandeira segue a matriz tri-state aprovada: política true exige
    `includes_flag=false`, false exige true e null não restringe. Evidência null
    bloqueia quando há exigência, inclusive para tarifa configurada. `with_taxes`
    é somente transportado e não dispara cálculo.
  - Testes C5.3A/C5.3B: **41 OK**. Gate financeiro focado: **118 OK**. Gate
    integrado parser/F6/F7/C4.3/C5.1/C5.2/C5.3A/A.1/B/tenant/migrations:
    **313 OK em 117,755s**. Regressão backend completa: **443 testes OK em
    141,090s**, acima do baseline 426, somente com avisos preexistentes.
  - Histórico Alembic SQLite vazio: **15 OK em 103,284s**. `py_compile` e build
    frontend (`tsc && vite build`) verdes. Revisão crítica read-only sem achados
    remanescentes; `git diff --check`, diff/status e confirmação de zero migration
    concluídos.
  - Zero endpoint, persistência, migration ou acesso a parser/PDF/banco/provider.
    C5.4, PIS/COFINS, Fio B, carência, economia, valor total, HP/HFP,
    BillingPolicy, Fatura e ASAAS não foram iniciados.

Comandos C5.3B executados:

```powershell
cd backend
rtk cmd /c venv\Scripts\python.exe -m unittest tests.test_commercial_tariff_selector tests.test_document_tariff_resolver
rtk cmd /c venv\Scripts\python.exe -m unittest tests.test_invoice_parsers tests.test_copel_parser tests.test_copel_deep tests.test_copel_energy tests.test_invoice_normalization tests.test_invoice_compensation tests.test_invoice_processing_persistence tests.test_tariff_selector tests.test_billing_calculation_contracts tests.test_billing_calculation_engine tests.test_calculo_tarifas tests.test_document_tariff_resolver tests.test_commercial_tariff_selector tests.test_billing_rule_resolver tests.test_grupo_regra_cobranca tests.test_regra_cobranca_assignment tests.test_tenant_service_lookups tests.test_sqlite_migrations
rtk cmd /c venv\Scripts\python.exe -m unittest discover -s tests
rtk cmd /c venv\Scripts\python.exe -m unittest tests.test_sqlite_migrations
rtk cmd /c venv\Scripts\python.exe -m py_compile services\commercial_tariff_selector.py tests\test_commercial_tariff_selector.py
cd ..
rtk npm.cmd --prefix frontend run build
```

- [x] Sprint C5.3A.1 — **Validação GD real Copel e tarifas por evento DONE**,
  2026-09-17; **C5.3 PARTIAL, C5 global PARTIAL e F6 PARTIAL**.
  Files: parser Copel, normalização física de compensação, resolver tarifário
  documental, fixtures estruturadas sanitizadas, testes e documentação.
  Depends-on: F6/F7/C4.3/C5.3A; C5.1/C5.2 preservadas.
  - `MinimalExtractor`, parser Copel atual e inspeção dos line items foram
    executados, nessa ordem, sobre três PDFs privados reais não versionados.
    Nenhum nome, documento, endereço, UC ou chave fiscal foi copiado para fixtures.
  - O parser 1.3.0 passou a estruturar os labels comprovados de ENERGIA INJETADA
    local e ENERGIA INJ. OUC MPT, componentes TE/TUSD, GD-I/GD-II, mês de origem,
    bandeira separada e ambas as colunas tarifárias. Valores negativos documentais
    e o spill da descrição para a coluna de unidade são tratados no parser; o
    resolver continua sem regex de layout.
  - `CompensacaoNormalizada` permanece a identidade canônica. Somente eventos
    OUTRA_UC + MESMO_POSTO alimentam `energia_compensada_cobravel_kwh`; energia
    própria/local permanece auditável em `energy_components`. Evidência real:
    1.240 kWh locais não foram somados aos 2.400 kWh OUC.
  - Criado `ResolvedCompensationTariffEvent` e adicionado
    `compensation_tariff_events`. A fatura real com GD-I 30 kWh e GD-II 352 kWh
    produz dois eventos VALID e total 382 kWh. GD-I preserva TE 0.310850 + TUSD
    0.457170 = 0.768020; GD-II preserva TE 0.310850 + TUSD 0.328431 = 0.639281.
  - Um evento, ou múltiplos com TE/TUSD/tributação/bandeira semanticamente iguais,
    pode manter `compensation_tariff` escalar. Tarifas diferentes mantêm o scalar
    null e issue `TARIFA_COMPENSACAO_ESCALAR_INAPLICAVEL`, sem média, primeiro,
    último, maior ou menor. Duplicidade na mesma identidade e divergência TE/TUSD
    continuam bloqueadas; GD-III permanece UNSUPPORTED.
  - Bandeira de consumo/injeção separada prova `includes_flag=false` na respectiva
    tarifa. `tarifa_unitaria` e `preco_unitario_com_tributos` permanecem distintos;
    nenhuma regra comercial de bandeira/tributo foi aplicada. Tarifa cheia Copel
    permaneceu 0.310850 + 0.457170 = 0.768020.
  - Gate integrado parser/F6/F7/C4.3/C5.1/C5.2/C5.3A/C5.3A.1/tenant:
    **276 testes OK em 11,393s**. Histórico Alembic SQLite verde. Regressão backend
    completa: **426 testes OK em 119,381s**, somente avisos SQLAlchemy preexistentes.
    Zero migration, endpoint, persistência, cálculo comercial ou frontend.
  - F6 segue PARTIAL por prudência multi-layout, cobertura incompleta de saldo/
    expiração e ausência de GD-III. C5.3B não foi iniciada.

- [x] Sprint C5.3A — **Tariff Resolution Contract DONE**, 2026-09-17;
  **C5.3 PARTIAL e C5 global PARTIAL**.
  Files: `document_tariff_resolver.py`, delegação da composição documental no
  `tariff_selector.py`, teste focado, `.gitignore` e documentação. Depends-on:
  F7/C4.2/C4.3; C5.1/C5.2 preservadas. Critério: tarifas documentais cheia e de
  compensação resolvidas somente com evidência estruturada, Decimal/origem/
  confiança/warnings preservados, ausência/ambiguidade bloqueadas e zero cálculo.
  - Criados `DocumentTariffKind`, `ResolvedDocumentTariff`,
    `ResolvedDocumentTariffs` e `DocumentTariffEvidence`. Status reutiliza os
    estados canônicos VALID/AMBIGUOUS/MISSING/UNSUPPORTED. Valor não VALID é null;
    evidência mantém índice, caminho/campo, source, confidence e warnings.
  - Tarifa cheia Copel reutiliza a decisão C4.2: soma exata de tarifa_unitaria de
    energia_elet_consumo + energia_elet_uso_sistema. Não usa valor total,
    quantidade, preço com tributos, tarifa_base, grupo tarifário ou tabela externa.
    TariffSelector C4.2 delega essa mesma composição, sem lógica duplicada.
  - Compensação reutiliza `BillingEnergyInput`/classificação TE/TUSD C4.3. O
    comportamento original de evento único foi ampliado pela C5.3A.1: múltiplos
    eventos válidos não são ambiguidade e nunca copiam a tarifa cheia.
  - Bandeira separada já classificada permite includes_flag=false; ambiguidade
    mantém null+issue. Variante `preco_unitario_com_tributos` associada prova que
    a tarifa_unitaria escolhida é sem tributos; ausência mantém with_taxes=null.
    Nenhum ICMS/PIS/COFINS/bandeira comercial é calculado ou aplicado.
  - Criado `test_document_tariff_resolver.py` com **18 testes**: soma cheia,
    total ignorado, Decimal exato, componente ausente, compensação válida/ausente,
    candidatos múltiplos, origem, confiança, warnings, bandeira, tributos,
    tarifa_base/grupo sem inferência e pureza.
  - Gate C5.3A + selector C4.2: **37 testes OK**. Gate integrado parser/F7/C4.2/
    C4.3/C5.1/C5.2/C5.3A: **216 testes OK em 3,254s**. Regressão completa backend:
    **413 testes OK em 121,853s**, com somente avisos SQLAlchemy preexistentes.
    py_compile dos quatro arquivos Python, `git diff --check`, checks dos arquivos
    novos, revisão de código/diff e `git status` concluídos.
  - Zero migrations, endpoint, persistência ou frontend. InvoiceNormalized,
    CompensacaoNormalizada, RuleResolver e strategies C5.1/C5.2 não foram alterados.
    F6 segue PARTIAL: compensação usa fixtures sintéticas, sem novo PDF GD real.
    C5.3B, seleção comercial, Fio B, BillingPolicy, Fatura e ASAAS não iniciados.

Comandos C5.3A executados em `backend`:

```powershell
rtk proxy .\venv\Scripts\python.exe -m unittest tests.test_document_tariff_resolver tests.test_tariff_selector
rtk proxy .\venv\Scripts\python.exe -m unittest tests.test_invoice_parsers tests.test_copel_parser tests.test_copel_deep tests.test_copel_energy tests.test_invoice_normalization tests.test_invoice_compensation tests.test_invoice_processing_persistence tests.test_tariff_selector tests.test_billing_calculation_contracts tests.test_billing_calculation_engine tests.test_calculo_tarifas tests.test_document_tariff_resolver
rtk proxy .\venv\Scripts\python.exe -c "import os,unittest; os.environ['SENTRY_DSN']=''; r=unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.discover('tests')); raise SystemExit(not r.wasSuccessful())"
```

- [x] Sprint C5.2 — **CONCLUÍDA**, 2026-09-16; **C5 global PARCIAL**.
  Arquivos: motor/estratégias, memória C0,
  testes e documentação. Depends-on: C4.3/C5.1. Critério: tarifa fixa aplica
  desconto, específica não aplica e registra a decisão; energia canônica,
  precisão/rounding C5.1 e regressão preservados. Sem migration/persistência.
  - EstrategiaTarifaFixa e EstrategiaTarifaEspecifica no mesmo módulo do motor,
    compartilhando validações e aritmética C5.1. Energia somente require_valid().
    Fixa: E×T menos percentual 0..100. Específica: E×T, sem desconto adicional.
    Decimal integral nos intermediários; ROUND_HALF_UP somente no líquido final.
  - Reutilizado parâmetro manual existente company_tariff/manual_tariff conforme
    método, sem aliases, fallback para tarifa documental ou schema novo.
    Ausência/negativo bloqueiam; zero explícito válido. Snapshot mantém regra,
    revisão e desconto configurado, mesmo quando este não participa do cálculo.
  - Memória ganha desconto_aplicado em português: false na específica e percentual
    utilizado null; fixa indica se percentage participa. C5.1 mantém null nesse
    campo opcional. Novas classes/mensagens/documentação em português; nomes
    persistidos e contratos anteriores preservados para compatibilidade.
  - Criado test_calculo_tarifas.py com **21 testes**. Testes numéricos/segurança
    C5.1 intactos. Única expectativa anterior atualizada: lista de métodos ainda
    não suportados, removendo tarifa_fixa/especifica que C5.2 implementou.
    tarifa_fixa_com_desconto continua distinto e não suportado, assim como
    valor_total_fatura/economia_gerada/energia_recebida. Sem alias automático.
  - Verificação focada C5.2/C5.1/C0: **64 testes OK em 0,097s**.
    Regressão completa backend: **395 testes OK em 142,161s**, incluindo
    normalização/F1–F7, C0–C5.2, tenant e 15 testes de migrations. Bancos temporários,
    Sentry desligado; somente avisos SQLAlchemy preexistentes, sem falhas.
    py_compile dos quatro arquivos Python, git diff --check, checks dos arquivos
    não rastreados, revisão de código/diff e git status concluídos.
  - Documentação: FATURAS_E_COBRANCAS.md e API_CONTRACTS.md com semântica da
    tarifa por método, memória e limites. `.gitignore` libera teste novo.
    Zero migrations; model/API pública/parser/normalizer/RuleResolver inalterados.
    Alterações preexistentes de outras tarefas preservadas. Sem commit/push.
  - Limites: F6 segue sem comprovação GD real; testes energéticos sintéticos.
    Modificadores, HP/HFP, tributos, bandeira e adicional continuam bloqueados.
    Sem C5.3/C5.4, seleção documental, BillingPolicy, Fatura ou ASAAS.

Comandos C5.2 executados em `backend`:

```powershell
rtk proxy .\venv\Scripts\python.exe -m unittest tests.test_calculo_tarifas tests.test_billing_calculation_engine tests.test_billing_calculation_contracts
rtk proxy .\venv\Scripts\python.exe -c "import os,unittest; os.environ['SENTRY_DSN']=''; r=unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.discover('tests')); raise SystemExit(not r.wasSuccessful())"
rtk proxy .\venv\Scripts\python.exe -m py_compile services/billing_calculation_engine.py services/billing_calculation_contracts.py tests/test_billing_calculation_engine.py tests/test_calculo_tarifas.py
```

- [x] Página de Faturas — **refino visual HUB e seleção em lista**, 2026-09-16.
  Layout reorganizado com toolbar, seis cards derivados de dados reais, busca e
  filtros por referência/status/cliente/UC. A tabela começa com seleção individual
  e seleção de todos os resultados visíveis antes da coluna Referência; seleção
  não abre detalhes e permanece durante filtros. Cores usam somente os tokens do
  HUB. Emissão, detalhes e contratos existentes foram preservados; upload em lote,
  parser e identificação automática de UC não foram simulados sem endpoint real.
  Build frontend de produção verde (`tsc && vite build`).

- [x] Sprint C5.1 — **DONE**, 2026-09-16; **C5 global PARTIAL**.
  Files: contratos C0, engine/strategy,
  testes e documentação. Depends-on: C0–C4.3. Critério: energia canônica VALID
  × tarifa empresa, desconto percentual, memória/snapshot e regressão completa
  verde; sem persistência, migration, provider ou outros métodos/modificadores.
  - Criado billing_calculation_engine.py com engine concreto e única strategy
    CompensatedEnergyBillingStrategy. ABCs/assinatura C0 preservadas. Coerência
    dos IDs/fonte/competência conferida em memória; nenhuma consulta tenant/banco.
  - require_valid() obrigatório; energia/tarifa Decimal finitos não negativos.
    company_tariff/manual_tariff é comercial, sem referência/total concessionária.
    gross_base=E×T; discount_amount=gross×P/100; líquido=bruto−desconto.
    Desconto none ou percentage 0..100 inclusivos; fixed bloqueado explicitamente.
  - Contexto Decimal local preserva intermediários exatos. Somente hub_amount
    arredonda para centavos ROUND_HALF_UP. Bruto/desconto não arredondados;
    memória tipada ganha percentage, tarifa efetiva, líquido antes de rounding
    e identificação do rounding. Snapshot imutável mantém método/revision/regra.
  - BillingCalculationError com códigos controlados; métodos não implementados,
    HP/HFP, modificadores ativos e adicional configurado bloqueiam sem cálculo
    parcial. Política financeira permanece somente no snapshot, sem execução.
  - Criados 22 testes C5.1: fórmula, percentuais, precisão/contexto global,
    rounding final, estados ausentes/inválidos, contextos divergentes, snapshot,
    determinismo, dispatch, isolamento dos demais valores e bloqueios de escopo.
    Nenhum teste anterior removido/alterado. `.gitignore` libera o novo teste.
  - Gate integrado C0–C5.1/normalizer/F7 inicial: **233 OK em 10,541s**.
    Após cobertura adicional numérica, regressão completa backend:
    **374 OK em 122,430s**, incluindo F1–F7, tenant e migrations (15 testes).
    Bancos temporários/Sentry desligado, avisos SQLAlchemy preexistentes.
    py_compile dos três módulos Python, git diff --check, revisão de diff,
    checks dos arquivos untracked e git status concluídos. Sem commit/push.
  - FATURAS_E_COBRANCAS.md e API_CONTRACTS.md documentam fórmula, memória,
    compatibilidade, erros e rounding. Zero migrations; parser/normalizer/C4.3
    inalterados. Sem Fatura, BillingPolicy, ASAAS, endpoints ou frontend.
  - Limitação: F6 ainda não comprova compensação GD em PDF real; entrada Copel
    atual permanece UNSUPPORTED e bloqueada. Testes comerciais são sintéticos.
    Próximos métodos/modificadores dependem de sprint autorizada. Não iniciados.

Comandos C5.1 executados em `backend`:

```powershell
rtk proxy .\venv\Scripts\python.exe -c "import os,unittest; os.environ['SENTRY_DSN']=''; s=unittest.TestSuite(unittest.defaultTestLoader.discover('tests',pattern=p) for p in ('test_invoice*.py','test_billing*.py','test_tariff_selector.py','test_copel*.py','test_grupo_regra_cobranca.py','test_regra_cobranca_assignment.py','test_fatura_processing.py')); r=unittest.TextTestRunner(verbosity=1).run(s); raise SystemExit(not r.wasSuccessful())"
rtk proxy .\venv\Scripts\python.exe -c "import os,unittest; os.environ['SENTRY_DSN']=''; r=unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.discover('tests')); raise SystemExit(not r.wasSuccessful())"
rtk proxy .\venv\Scripts\python.exe -m py_compile services/billing_calculation_contracts.py services/billing_calculation_engine.py tests/test_billing_calculation_engine.py
```

- [ ] Sprint C4.3 — **contrato canônico implementado; PARTIAL global**, 2026-09-16.
  Critério: TE/TUSD não duplicarem energia, divergências bloquearem total,
  BillingEnergyInput canônico persistir em F7 e regressão verde. Sem cobrança/C5.
  Files: invoice_compensation.py, schemas/normalizer/F7, contrato abstrato C0,
  testes sintéticos e persistência, documentação. Depends-on: F6/F7/C4.2.
  - Criados CompensacaoNormalizada, ComponenteCompensacao e BillingEnergyInput
    dentro do fluxo normalizador. Campo canônico somente deriva dos eventos
    válidos; engine futuro usa require_valid(), nunca descrições/linhas Copel.
    Estado VALID/AMBIGUOUS/MISSING/UNSUPPORTED, Decimal exato e fonte/competência.
  - TE/TUSD agrupados por origem/posto/mês/GD/contexto documental comprovado.
    -1000/-1000 → 1000, sinais originais preservados. Meses/contextos distintos
    permanecem eventos separados. DIVERGENCIA_COMPONENTES_COMPENSACAO, pares
    incompletos, duplicidades, referências reutilizadas e unidade/quantidade
    inválidas bloqueiam total inteiro, sem subtotal silencioso.
  - MUC/OUC → MESMA_UC/OUTRA_UC; MPT/OPT → MESMO_POSTO/OUTRO_POSTO;
    GD_I/GD_II/GD_III/UNKNOWN somente estruturado, sem regex nova. Mês crédito
    independente de competência. Impostos/tarifas/valor e metadados preservados
    nos componentes; saldo, injeção, consumo, demanda, disponibilidade e rateio
    esperado não alimentam compensação cobrável.
  - ParsedInvoice ganha compensation_supported=false por default. Parser Copel
    inalterado: fixture real continua UNSUPPORTED para compensação; F6 PARTIAL.
    Cenários TE/TUSD/GD são explicitamente sintéticos, não evidência de layout.
  - F7 fornece ID tenant-safe da fatura e persiste billing_energy_input no snapshot
    já existente, sem migration ou reprocessamento de históricos. Validação
    documental F7 não substitui o gate energético. C4.2 tarifa permanece intacta.
  - Matriz NORMALIZATION RULES / COMMERCIAL RULES / SAFETY RULES documentada em
    FATURAS_E_COBRANCAS.md; extensão do snapshot descrita em API_CONTRACTS.md.
    `.gitignore` libera somente o teste novo. Sem endpoint, ASAAS ou fórmula comercial.
  - Gate C4.3 inicial **11 OK em 0,304s**; gate integrado normalizer/F7/C0–C4.3
    **212 OK em 14,590s**. py_compile dos sete arquivos Python OK. Regressão backend
    completa **352 OK em 125,358s**, incluindo F1–F7, tenant e 15 testes de migrations.
    Bancos temporários, Sentry desligado; avisos SQLAlchemy preexistentes sem falhas.
    git diff --check, checks de arquivos untracked, revisão do diff/código e
    git status concluídos. Sem commit/push ou banco externo.
  - Riscos/limites: origem do contexto por layout depende de amostras reais;
    contrato conservador exige par TE/TUSD completo, eventos de componente único
    precisam de evidência específica. Decisões comerciais C4.2 permanecem abertas.
    C5 não iniciada; mudanças preexistentes preservadas.

Comandos C4.3 executados em `backend`:

```powershell
rtk proxy .\venv\Scripts\python.exe -c "import os,unittest; os.environ['SENTRY_DSN']=''; s=unittest.TestSuite(unittest.defaultTestLoader.discover('tests',pattern=p) for p in ('test_invoice*.py','test_billing*.py','test_tariff_selector.py','test_copel*.py','test_grupo_regra_cobranca.py','test_regra_cobranca_assignment.py','test_fatura_processing.py')); r=unittest.TextTestRunner(verbosity=1).run(s); raise SystemExit(not r.wasSuccessful())"
rtk proxy .\venv\Scripts\python.exe -c "import os,unittest; os.environ['SENTRY_DSN']=''; r=unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.discover('tests')); raise SystemExit(not r.wasSuccessful())"
rtk proxy .\venv\Scripts\python.exe -m py_compile services/invoice_compensation.py services/invoice_normalization_service.py services/invoice_parsers/schemas.py services/fatura_processing_service.py services/billing_calculation_contracts.py tests/test_invoice_compensation.py tests/test_invoice_processing_persistence.py
```

- [ ] Sprint C4.2 — **PARTIAL global; contratos implementados**, 2026-09-16.
  Critério: política reutilizável sem datas globais ativas, bloqueios documentais,
  memória auditável e matriz por método; regressão verde. C5 não iniciada.
  Files: contratos C0, model/service C1, resolver C3, selector C4, migration nova,
  testes correspondentes, FATURAS_E_COBRANCAS.md, API_CONTRACTS.md, PROGRESS.md.
  Depends-on: C0–C4.1; nenhuma strategy/engine concreta.
  - Complemento de produto confirmado: TariffSelector compõe referência Copel
    1.3.0/danf3e/DANF3EA4B-V1.06 somando tarifa_unitaria de ENERGIA ELET CONSUMO
    e ENERGIA ELET USO SISTEMA. Usa categorias documentais normalizadas e item_index,
    sem PDF, banco ou condicionais Copel no motor. Não usa totais, quantidades,
    preço com tributos, company_tariff ou divisão valor/kWh. Referência independe
    da base comercial/GD. Componentes completos preservados no resultado e memória.
    Decimal com contexto suficiente para soma exata, sem arredondamento.
    Ausências/falhas → concessionaire_tariff_components_missing;
    ambiguidade/duplicidade → concessionaire_tariff_ambiguous, sempre value=None.
    Layouts não aprovados continuam bloqueados; não generalizar composição Copel.
  - GracePeriod agora contém enabled/without_discount/duration_months, sem datas
    globais. API durationMonths: inteiro positivo ou null. Novas start/end não
    nulas são recusadas; datas C4.1 permanecem legadas, sem conversão/limpeza
    automática. Resolver bloqueia grace_policy_migration_required, sem fallback.
    Limpeza explícita conjunta e duração alteram revision; descrição não altera.
  - Verificados ConsumerUnit.inicio_contrato, termino_contrato, carencia_meses,
    percentual_desconto_carencia, created_at, sem_usina_desde e Plant.data_ativacao.
    Nenhum contrato os define como início da carência da instalação. Sem campo
    novo na UC, sem herança automática ou data inventada. Calendário/origem e a
    frase "apenas valor da concessionária" permanecem decisão de produto.
  - CalculationBlockCode + pré-condição required_document_value: ausência de
    tributos/base sem bandeira/decomposição ICMS/energia produz issue critical
    específico. None não vira zero; nenhuma reconstrução ou fórmula é executada.
    Layouts sem composição aprovada usam tariff_reference_representation_required; a referência
    documental não é requisito global para métodos baseados na tarifa empresa.
  - CalculationMemory tipada transporta fontes, tarifa empresa/referência,
    tratamentos/valores tributários, desconto original, carência e adicional.
    Método/revisão/parâmetros permanecem no snapshot; energia/desconto efetivo/
    resultado nos campos existentes do resultado. Mapas de memória legados aceitos.
    HP null permanece null; fallback HFP/HP somente contratado para dados horários
    confiáveis. Adicional recorrente vem após base/desconto, separado de juros/multa.
  - Migration p0d5f9a2b4c6 adiciona duration nullable e CHECK, preservando datas,
    revisão e dados existentes. Downgrade bloqueia perda de duração configurada.
    Migrations anteriores intactas; SQL PostgreSQL compilado, sem banco externo.
  - Matriz normativa em FATURAS_E_COBRANCAS.md: núcleo valor_total_fatura
    READY_TO_IMPLEMENT; métodos com energia elegível/fórmula não definida
    BLOCKED_BY_BUSINESS_DECISION; energia_recebida e compensação também
    BLOCKED_BY_DOCUMENT_DATA. Compatibilidade de modificadores explicitamente
    separada da prontidão do núcleo. Nenhuma interpretação jurídica adicionada.
  - Validações focadas: **83 testes C0–C4.2 OK em 8,361s**; migrations isoladas
    **15 OK em 95,971s** (SQLite vazio, upgrade/downgrade, preservação e guards,
    SQL PostgreSQL offline). py_compile dos 11 arquivos Python OK.
    Após composição Copel confirmada, regressão backend completa:
    **341 OK em 125,635s**, incluindo C0–C4.2, F1–F7/tenant e
    migrations. Testes em bancos temporários, Sentry desligado; avisos SQLAlchemy
    preexistentes sem falhas. git diff --check, checagem de arquivos untracked,
    revisão de diff/código e git status concluídos. Sem commit/push.
    Complemento Copel: gate inicial de selector/contratos **39 OK em 0,249s**;
    teste adicional de ordem/unidades/totais/zero também aprovado na regressão.
    py_compile dos três arquivos Python alterados no complemento OK. Nenhuma
    migration adicional à p0d5f9a2b4c6 foi necessária para composição documental.
  - API_CONTRACTS.md atualizado para duração e transição compatível de carência.
    Sem endpoint novo, frontend, snapshot em Fatura, cálculo ou ASAAS. Mudanças
    preexistentes da worktree preservadas; nenhuma migration em ambiente real.

Comandos C4.2 executados em `backend`:

```powershell
rtk proxy .\venv\Scripts\python.exe -c "import os,unittest; os.environ['SENTRY_DSN']=''; s=unittest.TestSuite(unittest.defaultTestLoader.discover('tests',pattern=p) for p in ('test_billing*.py','test_grupo_regra_cobranca.py','test_regra_cobranca_assignment.py','test_tariff_selector.py')); r=unittest.TextTestRunner(verbosity=1).run(s); raise SystemExit(not r.wasSuccessful())"
rtk proxy .\venv\Scripts\python.exe -c "import os,unittest; os.environ['SENTRY_DSN']=''; r=unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.loadTestsFromName('tests.test_sqlite_migrations')); raise SystemExit(not r.wasSuccessful())"
rtk proxy .\venv\Scripts\python.exe -c "import os,unittest; os.environ['SENTRY_DSN']=''; r=unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.discover('tests')); raise SystemExit(not r.wasSuccessful())"
rtk proxy .\venv\Scripts\python.exe -m py_compile services/billing_calculation_contracts.py models/grupo_regra_cobranca.py services/grupo_regra_cobranca_service.py services/billing_rule_resolver.py services/tariff_selector.py migrations/versions/p0d5f9a2b4c6_grace_policy_duration.py tests/test_billing_calculation_contracts.py tests/test_grupo_regra_cobranca.py tests/test_billing_rule_resolver.py tests/test_tariff_selector.py tests/test_sqlite_migrations.py
```

- [ ] Sprint C4.1 — **Modelo tarifário implementado; PARTIAL para liberação de C5**, 2026-09-16.
  Critério: separar classificação/referência concessionária/tarifa empresa/método/
  modificadores, preservar legados, revision/snapshot e regressão. Estrutura e API
  entregues; referência documental, fórmulas e origem temporal automática ainda
  exigem decisões. **C5 não iniciada. ICMS confirmado como SEM ICMS (`exclude`).**
  - C0: TariffConfiguration, BillingModifiers e GracePeriod; três métodos novos
    tarifa_fixa_com_desconto, tarifa_especifica e energia_recebida. Quatro métodos
    anteriores preservados, sem renome/inferência de fórmulas. Snapshot transporta
    objetos completos e rule_version; não é persistido em Fatura.
  - C1: API aceita objetos aninhados com PATCH parcial; companyTariff é alias de
    manualTariff, na mesma coluna Numeric(18,6). HP/HFP, exclusão PIS/COFINS/ICMS/
    bandeira, carência temporal e adicional recorrente possuem campos nullable.
    Validação rejeita float, arredondamento implícito, alias conflitante, datas
    inválidas e combinações estruturais não suportadas. Todas as alterações
    financeiras efetivas incrementam revision; descrição/PATCH idêntico não.
  - Migration nova o9c4e8f1a3b5 (após C2), dez campos nullable, CHECKs de método,
    tarifa/percentual, ICMS e carência. Legados sem valores inventados ou revisão
    alterada. Downgrade preserva dados: bloqueia se remover configuração C4.1.
    C1/C2 migrations intactas. Nenhuma tabela adicional.
  - C3 preserva precedência consumer_unit > client > company, lookup tenant-safe,
    assignments explícitos e padrao ≠ fallback. Apenas transporta novos DTOs.
  - C4: selector exclusivamente documental; nunca lê tarifa empresa. Referência
    concessionaria_reference_tariff_kwh/value permanece None com issues enquanto
    não houver critério entre tarifa_unitaria/preco_unitario_com_tributos. Política
    de excluir ICMS não autoriza reconstrução. Sem cálculo, desconto ou emissão.
  - Parser Copel 1.3.0 + normalizer: grupo B, subgrupo B1 e modalidade CONVENCIONAL
    pela evidência da fixture existente; ausências null, sem default cadastral,
    tabelas de preços ou novas amostras GD. F6 permanece PARTIAL.
  - Carência habilitada admite datas explícitas juntas/ordenadas ou origem pendente;
    sem determinar automaticamente início, limites ou desconto. HP null não copia
    HFP. Adicional recorrente separado de multa/juros; nenhuma regra legal criada.
  - Validação final: **209 testes OK em 13,168s** no gate C0–C4.1/F1–F7/tenant;
    **329 testes OK em 123,420s** na regressão completa. Migrations isoladas:
    **13 OK em 96,416s**, incluindo SQLite vazio, upgrade/roundtrip com perfil e
    assignment antigos, CHECKs, proteção de downgrade e SQL PostgreSQL compilado.
    PostgreSQL externo não executado. Testes temporários, Sentry desligado; avisos
    SQLAlchemy preexistentes sem falhas. Primeiro gate detectou âncora B1 na mesma
    linha das leituras; corrigida e validada nos gates finais.
  - py_compile dos 15 arquivos Python envolvidos OK; git diff --check e checagem
    dos arquivos ainda untracked sem erros de whitespace; revisão de diff/código
    e git status realizados. Worktree preexistente preservada, sem commit/push.
  - Atualizados FATURAS_E_COBRANCAS.md (matriz/decisões), API_CONTRACTS.md (extensão
    C1) e este registro. `.gitignore` libera três testes existentes afetados.
  - Antes de C5: definir referência documental, fórmulas/quantidade elegível por
    método, origem/limites temporais da carência e warning/bloqueio para dados
    tributários/bandeira ausentes. Não liberar engine a partir de configuração
    estrutural apenas. Sem frontend, ASAAS, BillingPolicy ou snapshot em Fatura.

Comandos C4.1 executados em `backend`:

```powershell
rtk proxy .\venv\Scripts\python.exe -c "import os,unittest; os.environ['SENTRY_DSN']=''; r=unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.loadTestsFromName('tests.test_sqlite_migrations')); raise SystemExit(not r.wasSuccessful())"
rtk proxy .\venv\Scripts\python.exe -c "import os,unittest; os.environ['SENTRY_DSN']=''; s=unittest.TestSuite(unittest.defaultTestLoader.discover('tests',pattern=p) for p in ('test_tariff_selector.py','test_billing*.py','test_grupo_regra_cobranca.py','test_regra_cobranca_assignment.py','test_invoice*.py','test_copel*.py','test_fatura_processing.py','test_fatura_concessionaria*.py','test_tenant*.py')); r=unittest.TextTestRunner(verbosity=1).run(s); raise SystemExit(not r.wasSuccessful())"
rtk proxy .\venv\Scripts\python.exe -c "import os,unittest; os.environ['SENTRY_DSN']=''; r=unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.discover('tests')); raise SystemExit(not r.wasSuccessful())"
rtk proxy .\venv\Scripts\python.exe -m py_compile services/billing_calculation_contracts.py models/grupo_regra_cobranca.py services/grupo_regra_cobranca_service.py services/billing_rule_resolver.py services/tariff_selector.py services/invoice_normalization_service.py services/invoice_parsers/copel.py migrations/versions/o9c4e8f1a3b5_billing_tariff_configuration.py tests/test_billing_calculation_contracts.py tests/test_grupo_regra_cobranca.py tests/test_billing_rule_resolver.py tests/test_tariff_selector.py tests/test_copel_energy.py tests/test_invoice_processing_persistence.py tests/test_sqlite_migrations.py
```

Registros abaixo descrevem as entregas históricas; C4.1 substitui a seleção manual de C4.

- [ ] Sprint C4 — **TariffSelector — PARTIAL**, 2026-09-16.
  Critério de pronto: selecionar tarifa manual/documental conforme contrato,
  preservar Decimal/rastreabilidade, bloquear ambiguidades/ausências sem fallback,
  independência de banco/PDF e regressão verde. Caminho invoice de sucesso pendente:
  falta decisão comercial entre tarifa_unitaria e preco_unitario_com_tributos.
  - Criado `services/tariff_selector.py`: seleção manual integral; diagnóstico
    invoice por categoria consumed ou componente explicitamente referenciado.
    GD1/GD2/compensated sem suporte comprovado bloqueiam. Não há cálculo/energia
    somada, desconto, acesso a banco, parser/PDF ou efeito externo.
  - TariffSelectionResult e candidatos preservam Decimal, status, label, campo,
    referência documental, confidence e issues. Sem primeira/maior/menor tarifa,
    fallback entre fontes ou inferência por valor/kWh. Manual ausente é explícito.
  - Invoice não seleciona nenhuma coluna sem política comercial definida:
    tariff_representation_required, inclusive com só uma coluna disponível.
    Tarifa unitária não é declarada automaticamente como sem tributos/TE/TUSD.
  - Documentado contrato/limite em FATURAS_E_COBRANCAS.md, seção Sprint C4.
    `.gitignore` libera somente o novo teste C4. API_CONTRACTS.md, contratos C0,
    models e C3 não alterados. Sem migration nova. **C5 não iniciada.**
  - Validação: C4 **15 OK**; gate C0–C4/F1–F7/tenant **203 OK em 9,100s**;
    regressão backend completa **321 OK em 90,798s**, incluindo **11 migrations
    SQLite**. py_compile dos dois arquivos novos, git diff --check, revisão dos
    arquivos novos/diff e git status executados. Bancos temporários, fixture
    anônima existente, Sentry desligado; avisos SQLAlchemy preexistentes sem falhas.
    Nenhum banco externo foi usado. Teste de seleção invoice bem-sucedida permanece
    pendente da decisão comercial; a sprint não está READY_FOR_C5.

Comandos C4 executados em `backend`:

```powershell
rtk proxy .\venv\Scripts\python.exe -c "import os,unittest; os.environ['SENTRY_DSN']=''; r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.discover('tests',pattern='test_tariff_selector.py')); raise SystemExit(not r.wasSuccessful())"
rtk proxy .\venv\Scripts\python.exe -c "import os,unittest; os.environ['SENTRY_DSN']=''; s=unittest.TestSuite(unittest.defaultTestLoader.discover('tests',pattern=p) for p in ('test_tariff_selector.py','test_billing*.py','test_grupo_regra_cobranca.py','test_regra_cobranca_assignment.py','test_invoice*.py','test_copel*.py','test_fatura_processing.py','test_fatura_concessionaria*.py','test_tenant*.py')); r=unittest.TextTestRunner(verbosity=1).run(s); raise SystemExit(not r.wasSuccessful())"
rtk proxy .\venv\Scripts\python.exe -c "import os,unittest; os.environ['SENTRY_DSN']=''; r=unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.discover('tests')); raise SystemExit(not r.wasSuccessful())"
rtk proxy .\venv\Scripts\python.exe -m py_compile services/tariff_selector.py tests/test_tariff_selector.py
```

- [x] Sprint C3 — **RuleResolver — READY_FOR_C4**, 2026-09-15.
  Pronto quando: precedência explícita consumer_unit > client > company, DTO C0
  completo, bloqueios distinguíveis, tenant/contexto validados, leitura sem efeitos
  e regressão verde. Critérios atendidos; **C4 não iniciada**.
  - Criado `services/billing_rule_resolver.py`: RuleResolver usa a empresa de
    `g.current_empresa_id`, valida Client/UC e sua relação, e reutiliza os lookups
    exatos C2/C1. `padrao` não participa; não há mistura de parâmetros entre grupos.
  - Assignment inativo é ignorado. Primeiro assignment ativo com grupo inativo
    bloqueia (`inactive_rule_assigned`), sem fallback inferior. Demais códigos:
    `no_rule_configured`, `invalid_context`, `assignment_inconsistent`,
    `target_not_found`. Falhas técnicas permanecem distintas dos bloqueios de domínio.
  - Retorna ResolvedBillingRule C0 completo, Decimal/None preservados, revision
    atual como rule_version textual, source_id do target e assignment_id na metadata.
    Lookups C1/C2 ganharam refresh opcional sem mudar o default dos consumidores.
  - Read-only: sessão limpa obrigatória, sem autoflush/commit/rollback. Testes
    comparam todas as tabelas antes/depois e verificam somente SELECTs tenant-scoped,
    no máximo oito no caminho completo. Cache ORM obsoleto também foi testado.
  - Validação final: C3 **20 OK** + C0/C1/C2 **37 OK** + F1–F7/tenant **131 OK**
    no gate combinado de **188 testes em 12,365s**. Regressão completa **306 OK
    em 91,706s**, incluindo **11 migrations SQLite** (banco vazio, upgrades e
    proteções de downgrade). py_compile dos seis arquivos Python alterados OK;
    git diff --check, revisão de diff/arquivos novos e git status executados.
    Python exigiu execução autorizada fora do sandbox; testes em bancos temporários,
    Sentry desligado. Avisos SQLAlchemy preexistentes não causaram falhas.
  - Atualizadas expectativas históricas de C1/C2 que exigiam ausência do resolver;
    preservados os testes funcionais. `.gitignore` permite versionar testes C1/C3
    anteriormente alcançados pelo ignore amplo. Mudanças preexistentes preservadas.
  - Documentação de domínio atualizada na seção 28. Nenhuma API pública mudou;
    API_CONTRACTS.md não foi alterado nesta C3. Sem migration nova, cálculo,
    tarifa documental, BillingPolicy, snapshot de Fatura, ASAAS ou frontend.
  - Limite: leitura usa a transação do chamador, sem lock contra edição concorrente
    nem snapshot persistido. PostgreSQL real não foi executado nesta C3. F6 segue
    PARTIAL por amostras GD; homologação externa ASAAS continua fora desta entrega.

Comandos C3 executados em `backend` (gate e regressão incluem testes C3):

```powershell
rtk proxy .\venv\Scripts\python.exe -c "import os,unittest; os.environ['SENTRY_DSN']=''; s=unittest.TestSuite(unittest.defaultTestLoader.discover('tests',pattern=p) for p in ('test_billing_rule_resolver.py','test_billing_calculation_contracts.py','test_grupo_regra_cobranca.py','test_regra_cobranca_assignment.py','test_invoice*.py','test_copel*.py','test_fatura_processing.py','test_fatura_concessionaria*.py','test_tenant*.py')); r=unittest.TextTestRunner(verbosity=1).run(s); raise SystemExit(not r.wasSuccessful())"
rtk proxy .\venv\Scripts\python.exe -c "import os,unittest; os.environ['SENTRY_DSN']=''; r=unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.discover('tests')); raise SystemExit(not r.wasSuccessful())"
rtk proxy .\venv\Scripts\python.exe -m py_compile services/billing_rule_resolver.py services/grupo_regra_cobranca_service.py services/regra_cobranca_assignment_service.py tests/test_billing_rule_resolver.py tests/test_grupo_regra_cobranca.py tests/test_regra_cobranca_assignment.py
```

- [x] Sprint C2 — **persistência do RegraCobrancaAssignment — READY_FOR_C3**, 2026-09-15.
  `RegraCobrancaAssignment`/`regra_cobranca_assignments` associa explicitamente
  um GrupoRegraCobranca aos escopos C0 `company`, `client` ou `consumer_unit`.
  - `CHECK` impede combinações inválidas de target. Índices únicos parciais
    PostgreSQL/SQLite garantem no banco no máximo um assignment ativo por empresa,
    Client e UC; concorrência Client/UC retorna conflito controlado e deixa um ativo.
  - Grupo, Client e UC são validados no tenant autenticado; IDs cross-tenant ficam
    inacessíveis. Grupo inativo não recebe novo assignment ativo.
  - Troca de regra é transacional: desativa a linha anterior e insere nova ativa,
    preservando histórico. Não há DELETE. Desativar posteriormente o grupo não
    altera assignments existentes; o tratamento fica explicitamente para C3.
  - API `/api/v1/billing-rule-assignments` oferece listar/buscar/criar/atualizar e
    filtros exatos de target. Leitura reutiliza `billing_rules.read`; escrita,
    `billing_rules.write`. `padrao` não cria assignment `company`.
  - Migration `n8b3d7e0f2a4` é reversível quando vazia e bloqueia downgrade com
    histórico. Nenhum backfill ou assignment implícito foi criado.
  - Validação: C2 **10 testes OK**; C0/C1/C2 **37 OK**; F1–F7/tenant **131 OK**;
    migrations SQLite **11 OK em 66,364s**; regressão backend completa **286 OK
    em 83,748s**. Os três índices parciais foram compilados para PostgreSQL;
    `py_compile`, `git diff --check`, revisão de diff e status foram executados.
    Avisos SQLAlchemy preexistentes não causaram falhas. Nenhuma migration foi
    aplicada a banco externo nesta C2.
  - Nenhum RuleResolver, precedência, fallback, ResolvedBillingRule, cálculo,
    BillingPolicy, Fatura, ASAAS ou frontend foi implementado. STOP antes de C3.

- [x] Sprint C1 — **persistência do GrupoRegraCobranca — READY_FOR_C2**, 2026-09-15.
  `GrupoRegraCobranca`/`grupos_regra_cobranca` cria perfis comerciais reutilizáveis
  tenant-aware, sem assignment, precedência ou execução. Os seis enums persistidos
  derivam dos contratos C0; Decimal usa `Numeric(18,6)`/string exata e as invariantes
  de tarifa manual, desconto e componente documentado existem no service e no banco.
  - Ausência de regra/default é válida. Índice único parcial por empresa protege
    concorrência de múltiplos grupos simultaneamente ativos e padrão em PostgreSQL
    e SQLite. Não há backfill/default comercial. Desativação usa `ativo=false`;
    não há DELETE e downgrade com perfis é bloqueado.
  - `revision` inicia em 1 e incrementa em alteração financeira relevante; mudanças
    descritivas, ativação e padrão não criam falsa revisão matemática. Nenhum snapshot
    em Fatura foi criado.
  - Service e API `/api/v1/billing-rules` oferecem listar/buscar/criar/atualizar.
    Leitura segue o financeiro atual; escrita é restrita a owner/admin/financial.
    IDs de outro tenant respondem 404 e `empresaId` do request é recusado.
  - Nenhum RegraCobrancaAssignment, RuleResolver, estratégia, cálculo, BillingPolicy,
    mudança em Fatura/FaturaConcessionaria, ASAAS ou frontend foi implementado.
    `padrao` continua apenas indicação administrativa; C2 exigirá assignment
    explícito de escopo Empresa e C3 resolverá somente assignments explícitos.
  - Validação: C1 **9 testes OK**; gate C0/C1/F1–F7/tenant/RBAC **162 OK**;
    migrations SQLite **10 OK**; regressão backend completa **275 OK em 74,919s**.
    O índice parcial foi compilado para o dialeto PostgreSQL; `py_compile`, revisão
    de diff, `git diff --check` e status executados. Avisos SQLAlchemy preexistentes
    não causaram falhas. Nenhuma migration foi aplicada a banco externo nesta C1.

- [x] Sprint C0 — **contratos do motor de cobrança — READY_FOR_C1**, 2026-09-15.
  Pronto quando: DTOs/enums/interfaces, snapshot imutável, Decimal/serialização
  exatos, validações estruturais e regressão verdes. Sem fórmula/persistência.
  STOP antes de C1.
  - Criado `services/billing_calculation_contracts.py`: contexto com IDs/competência
    e timestamp opcional explícito, ResolvedBillingRule, snapshot imutável,
    BillingCalculationResult, issues financeiras e ABCs de engine/strategy.
    Nenhum model SQLAlchemy entra no contrato; nenhuma fórmula foi implementada.
  - Enums fechados: escopo company/client/consumer_unit, quatro métodos já
    documentados, fonte invoice/manual, desconto percentage/fixed/none, bases
    energéticas explícitas, modos auto/unified/separate, bases de vencimento e
    severidades. Company significa global da empresa, não global cross-tenant.
  - Decimal finito obrigatório quando fornecido; tarifa manual exige valor,
    percentage/fixed exigem desconto, offset inteiro aceita ambos os sinais.
    Índice explícito para base documented_component; nenhuma seleção executada.
    Não há defaults zero, arredondamento ou disponibilidade GD inventada.
  - Snapshot captura regra e metadata em JSON textual imutável; mutações da
    origem/cópias não afetam histórico. Resultado suporta memória aninhada,
    warnings/issues próprios e valores opcionais. `to_dict()` projeta identidade
    do snapshot/contexto, sem duplicar fontes divergentes. Serializer F7 reutilizado
    preserva Decimal textual exato, datas ISO, enums/null e rejeita float.
  - Versão única `CALCULATION_ENGINE_VERSION='1.0'`: versão inicial de contrato,
    não motor executável. Engine/strategy são abstratos; sem registry ou estratégia
    fake permanente. BillingPolicy apenas transportada como configuração da regra.
  - Testes C0: **18 OK**. Gate C0/F1–F7/tenant: **149 OK em 5,269s**.
    Regressão backend: **265 OK em 71,890s**, incluindo **9 migrations SQLite**.
    `py_compile`: **2 arquivos OK**. Diff/novos revisados, whitespace sem erros
    e git status executado. Runtime local autorizado; bancos isolados e Sentry
    desligado; avisos SQLAlchemy preexistentes não causaram falhas.
  - Documentados contrato/enums/limites na seção 29 de FATURAS_E_COBRANCAS.md.
    API_CONTRACTS.md não alterado nesta C0: nenhuma API mudou. Rateio, desconto
    textual/base tarifária legados da UC e emissão B1/B2 permaneceram intactos.
  - Abertos antes de C5: fórmulas (especialmente economia_gerada/tarifa_fixa),
    seleção de tarifa, limites/compatibilidades de parâmetros comerciais,
    requisitos documentais por estratégia, arredondamento/calendário e instante
    de geração. IDs no DTO não substituem autorização/isolamento do futuro resolver.
    F6 permanece PARTIAL e B3 continua sem homologação externa ASAAS.
  - Sem C1, persistência/CRUD de regras, resolução de precedência, cálculo,
    BillingPolicy real, cobrança, ASAAS, frontend, novas dependências ou migrations.
    Alterações preexistentes preservadas. **C1 não iniciada.**

Comandos C0 executados em `backend`:

```powershell
rtk proxy .\venv\Scripts\python.exe -c "import os,unittest; os.environ['SENTRY_DSN']=''; r=unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.discover('tests',pattern='test_billing_calculation_contracts.py')); raise SystemExit(not r.wasSuccessful())"
rtk proxy .\venv\Scripts\python.exe -c "import os,unittest; os.environ['SENTRY_DSN']=''; s=unittest.TestSuite(unittest.defaultTestLoader.discover('tests',pattern=p) for p in ('test_billing_calculation_contracts.py','test_invoice*.py','test_copel*.py','test_fatura_processing.py','test_fatura_concessionaria*.py','test_tenant*.py')); r=unittest.TextTestRunner(verbosity=1).run(s); raise SystemExit(not r.wasSuccessful())"
rtk proxy .\venv\Scripts\python.exe -c "import os,unittest; os.environ['SENTRY_DSN']=''; r=unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.discover('tests')); raise SystemExit(not r.wasSuccessful())"
rtk proxy .\venv\Scripts\python.exe -m py_compile services/billing_calculation_contracts.py tests/test_billing_calculation_contracts.py
```

- [x] Sprint F7 — **InvoiceNormalizer + Validator — READY_FOR_C0**, 2026-09-15.
  Pronto quando: contrato canônico sem inferências financeiras, matching exato
  tenant-scoped, snapshots transacionais sem overwrite, testes e regressão verdes.
  F6 permanece PARTIAL; STOP antes de C0/C1.
  - Criados InvoiceNormalized/InvoiceNormalizer e InvoiceValidator/resultado
    puro, sem Flask/SQLAlchemy nas duas camadas. Contrato canônico usa FieldMap
    com status/fontes/confiança; identidade/contexto internos separados do parser.
    Datas/competência/CEP/UF/documento legível normalizados, sem arredondamento.
  - Preservados Decimal, zero explícito versus ausência/não examinado/não suporte,
    failed/ambiguous, tarifas por item, histórico curto sem século inferido e
    componentes energéticos individuais. Nenhuma tarifa comercial escolhida.
    GD-I/GD-II não equivalem a injeção e todos os campos não suportados seguem null.
  - Obrigatórios derivados do Core F4 critical: UC, competência, número/série/
    chave fiscal, vencimento, consumo, total, além do emissor reconhecido.
    Opcionais ausentes não invalidam. Valida não significa autorização de cálculo.
  - ProcessingService usa Registry, normalizer, validator e matching exato por
    codigo OU codigo_aneel com empresa_id explícito; múltiplas candidatas geram
    revisão. UC de outro Client gera conflito sem mudar Cliente/UC/fatura.client_id.
    UC de outro tenant não participa. Match aceito fornece id/número cadastral.
  - Persistência padrão transacional: identidade, snapshots completos bruto e
    normalizado+validação, campos estruturais/datas, vínculo UC e status separados.
    JSON preserva Decimal como string exata e datas ISO. Colunas Numeric F1 ficam
    sem projeção F7 para não arredondar; snapshots são a fonte documental canônica.
    Sem migration ou alteração do parser copel/1.2.0.
  - Mesmo hash continua dedupe F2; chave igual/hash diferente no tenant gera
    revisão sem descartar documento anterior. Lock por empresa/candidatas no
    PostgreSQL e atualização CAS tenant/hash/updated_at/ausência de snapshots
    protegem a primeira persistência. Comparação JSON null usa cast textual,
    evitando igualdade indisponível no JSON PostgreSQL. Testado em SQLite.
  - Qualquer snapshot, identificação/vínculo/valores extraídos prévios bloqueia
    sobrescrita, mesmo sem cobrança; precisa histórico versionado para evoluir.
    persist=False preserva diagnóstico em memória e cobertura F3–F6 anterior.
    Falhas técnicas/commit fazem rollback completo e mantêm estado anterior,
    retornando erro redigido. Sessão deve ser dedicada/sem trabalho de outro fluxo.
  - F7: **34 testes OK**. Gate F1–F7/tenant: **131 OK em 4,749s**.
    Regressão backend final: **247 OK em 76,194s**, incluindo **9 migrations
    SQLite**. py_compile: **13 arquivos OK**. Diff/novos revisados, whitespace
    sem erros e git status executado. Runtime local autorizado, Sentry desligado,
    bancos isolados. Avisos SQLAlchemy preexistentes não causaram falhas.
  - Atualizados FATURAS_E_COBRANCAS.md e API_CONTRACTS.md (snapshot no objeto já
    retornado pelo upload idempotente). Nenhum endpoint/processamento automático,
    fila, frontend, dependência, regra financeira, ASAAS, Pendência ou Agenda.
    Nenhum dado privado usado/persistido nos testes F7; fixture anônima existente.
  - Riscos/limites: concorrência real PostgreSQL F7 não homologada, política de
    locks por tenant conservadora, projeções numéricas não preenchidas e nenhum
    histórico de reprocessamento. F6 mantém uma amostra real sem GD comprovado.
    Alterações preexistentes preservadas; **C0/C1 não iniciadas**.

Comandos F7 executados em `backend`:

```powershell
rtk proxy .\venv\Scripts\python.exe -c "import os,unittest; os.environ['SENTRY_DSN']=''; s=unittest.TestSuite(unittest.defaultTestLoader.discover('tests',pattern=p) for p in ('test_invoice*.py','test_copel*.py','test_fatura_processing.py','test_fatura_concessionaria*.py','test_tenant*.py')); r=unittest.TextTestRunner(verbosity=1).run(s); raise SystemExit(not r.wasSuccessful())"
rtk proxy .\venv\Scripts\python.exe -c "import os,unittest; os.environ['SENTRY_DSN']=''; r=unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.discover('tests')); raise SystemExit(not r.wasSuccessful())"
rtk proxy .\venv\Scripts\python.exe -c "import pathlib,py_compile; files=list(pathlib.Path('services/invoice_parsers').glob('*.py'))+[pathlib.Path(p) for p in ('services/fatura_processing_service.py','services/invoice_normalization_service.py','services/invoice_validation_service.py','tests/test_invoice_normalization.py','tests/test_invoice_processing_persistence.py','tests/test_fatura_processing.py')]; [py_compile.compile(str(p),doraise=True) for p in files]; print('py_compile OK',len(files))"
```

- [ ] Sprint F6 — **classificação energética documental — PARTIAL**, 2026-09-15.
  Pronto quando: componentes individuais com status/fontes/Decimal, somente
  labels comprovados classificados, ausências/ambiguidade testadas e regressão
  verde. Única amostra não comprova GD-I/GD-II: entrega parcial, sem F7.
  - Revisadas visualmente as duas páginas e a camada textual do PDF privado.
    Comprovados ENERGIA ELET CONSUMO, ENERGIA ELET USO SISTEMA, ENERGIA CONS.
    B.AMARELA, consumo do medidor e histórico. Ficha de Compensação é bancária;
    modalidade tarifária e avisos de débito não comprovam GD. Sem conhecimento
    externo ou cópia de dados pessoais. Original intacto e ignorado pelo Git.
  - Parser `copel/1.2.0`, layout preservado. `energy_components` aditivo no
    ParsedInvoice reutiliza tuplas de FieldMap: label/categoria/kWh/unidade e
    índice da linha original, com source/confidence/issues. Três regras exact
    via ItemMatcher: consumed para consumo, other para uso do sistema/bandeira.
    Componentes repetidos não colapsam; resumo reutiliza consumo do medidor.
  - Campos separados gd1_kwh/gd2_kwh/injeção/compensação/saldo não têm valores:
    not_present + issue info de suporte ausente. Não é prova de ausência de GD
    na instalação. Item desconhecido em kWh: ambiguous/unclassified + info;
    empate não escolhe candidato; unidade incompatível falha sem converter.
  - Fixture PDF e gerador F4/F5 inalterados; expected JSON e README ampliados.
    Validação privada confirmou três componentes com referência às quantidades
    originais sem imprimir valores. Uma amostra real, nenhum caso GD fabricado.
  - Testes F6: **12 OK**. Gates F1–F6/tenant: **97 OK em 2,952s**.
    Regressão backend: **213 OK em 82,158s**, incluindo **9 migrations SQLite**.
    `py_compile`: **14 arquivos OK**. Revisão do código/diff/novos, whitespace
    e git status executados. Python local fora da sandbox, Sentry desligado,
    bancos isolados; avisos SQLAlchemy preexistentes sem falhas.
  - Para concluir: amostras reais com GD-I/GD-II explicitamente distinguidos
    por label/legenda e unidade; injeção versus compensação; demonstrativo de
    créditos anterior/utilizado/acumulado/atual/expiração; origem/beneficiário
    quando houver múltiplas linhas. Detalhamento em FATURAS_E_COBRANCAS.md.
  - Sem cálculo, soma GD, normalizer, inferência cadastral, atualização de UC,
    ASAAS, persistência, frontend, novas dependências ou migrations. Registry,
    ProcessingService e RawExtraction preservados. **F7 não iniciada.**

Comandos F6 executados em `backend` (mais inspeção privada sem saída de valores):

```powershell
rtk proxy .\venv\Scripts\python.exe -c "import os,unittest; os.environ['SENTRY_DSN']=''; s=unittest.TestSuite(unittest.defaultTestLoader.discover('tests',pattern=p) for p in ('test_copel*.py','test_invoice_parsers.py','test_fatura_processing.py','test_fatura_concessionaria*.py','test_tenant*.py')); r=unittest.TextTestRunner(verbosity=1).run(s); raise SystemExit(not r.wasSuccessful())"
rtk proxy .\venv\Scripts\python.exe -c "import os,unittest; os.environ['SENTRY_DSN']=''; r=unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.discover('tests')); raise SystemExit(not r.wasSuccessful())"
rtk proxy .\venv\Scripts\python.exe -c "import pathlib,py_compile; files=list(pathlib.Path('services/invoice_parsers').glob('*.py'))+[pathlib.Path(p) for p in ('services/fatura_processing_service.py','tests/test_invoice_parsers.py','tests/test_fatura_processing.py','tests/test_copel_parser.py','tests/test_copel_deep.py','tests/test_copel_energy.py','tests/fixtures/invoices/copel/build_fixture.py')]; [py_compile.compile(str(p),doraise=True) for p in files]; print('py_compile OK',len(files))"
```

- [x] Sprint F5 — **Copel Deep Extraction — READY_FOR_F6**, 2026-09-15.
  Pronto quando: itens/tarifas/tributos/histórico/medidor/avisos comprovados,
  matcher extensível, fixture anônima expandida e regressão verde. Sem cálculo,
  atualização de UC ou classificação GD-I/GD-II. STOP antes de F6.
  - Parser `copel/1.1.0`, layout DANF3EA4B V1.06. Reutilizados mapas de
    ExtractedField de ParsedInvoice: quatro itens, duas colunas de tarifa,
    PIS/COFINS e ICMS por item, quadro de ICMS/COFINS/PIS, 13 competências
    históricas, medidor e quatro avisos. Nenhuma classe/model financeiro paralelo.
  - ItemMatcherRule/ItemMatcher suportam exact/prefix/contains/regex/priority;
    empate mantém candidatos. Produção mapeia somente os quatro labels reais
    descritos em FATURAS_E_COBRANCAS.md. Original preservado; desconhecido gera
    info e segue sem classificação. Colunas vazias não viram zero.
  - Decimal preservado, sem arredondamento, cálculo de tributos, escolha de
    tarifa ou soma energética. Histórico conserva mês/ano documental com dois
    dígitos de ano, sem inferência de século/meses faltantes. Consumo do medidor
    reutiliza o campo F4 do resumo, sem deduzir diferença de índices.
  - Amostra privada: confirmados 4 itens, 3 tributos, 13 meses e 4 avisos;
    18 valores numéricos das três linhas completas foram comparados com as
    colunas originais, sem imprimir/copiar valores privados para testes/docs.
    PDF privado não alterado e continua ignorado. Fixture reconstruída anônima,
    expected JSON e gerador expandidos; renderização revisada e sem imagens/QR
    ou dados pessoais reais. Não há segunda amostra real.
  - Testes F5: **19 OK** (18 Deep/matcher + 1 integração comprovando ausência
    de atualização da UC). Gates F1–F5/tenant: **85 OK em 2,042s**. Regressão
    backend completa: **201 OK em 71,159s**, incluindo **9 migrations SQLite**.
    `py_compile`: **13 arquivos OK**; `git diff --check`, revisão de diff/novos
    e `git status` executados. Venv local fora da sandbox, Sentry desligado e
    bancos isolados. Avisos SQLAlchemy preexistentes não causaram falhas.
  - A expansão visual da fixture revelou confusão entre cabeçalho COFINS dos
    itens e quadro tributário; corrigida delimitação por alíquota com % e fim
    da linha antes da regressão final. Testes cobrem coluna ilegível, vazio,
    item desconhecido inclusive inicial, lacunas de histórico, deslocamento,
    precisão e preservação separada de labels adversariais de energia/crédito.
  - Limites: somente linhas simples/colunas observadas; sem OCR/multi-layout,
    injeção/compensação/saldos ou GD comprovados. Aliases documentais não são
    categorias comerciais. Aviso de cadastro de débito não significa débito
    ativo. F6 precisa de amostra GD real apropriada; **F6 não iniciada**.
  - Sem normalizer, matching, mutação de UC/fatura/status, cálculo, cobrança,
    ASAAS, novas dependências, schema/migration, HTTP, frontend ou deploy.
    Atualizados este registro, FATURAS_E_COBRANCAS.md e README da fixture.

Comandos F5 executados em `backend`:

```powershell
rtk proxy .\venv\Scripts\python.exe -c "import os,unittest; os.environ['SENTRY_DSN']=''; s=unittest.TestSuite(unittest.defaultTestLoader.discover('tests',pattern=p) for p in ('test_copel*.py','test_invoice_parsers.py','test_fatura_processing.py','test_fatura_concessionaria*.py','test_tenant*.py')); r=unittest.TextTestRunner(verbosity=1).run(s); raise SystemExit(not r.wasSuccessful())"
rtk proxy .\venv\Scripts\python.exe -c "import os,unittest; os.environ['SENTRY_DSN']=''; r=unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.discover('tests')); raise SystemExit(not r.wasSuccessful())"
rtk proxy .\venv\Scripts\python.exe -c "import pathlib,py_compile; files=list(pathlib.Path('services/invoice_parsers').glob('*.py'))+[pathlib.Path(p) for p in ('services/fatura_processing_service.py','tests/test_invoice_parsers.py','tests/test_fatura_processing.py','tests/test_copel_parser.py','tests/test_copel_deep.py','tests/fixtures/invoices/copel/build_fixture.py')]; [py_compile.compile(str(p),doraise=True) for p in files]; print('py_compile OK',len(files))"
```

- [x] Sprint F4 — **Copel Parser Core — READY_FOR_F5**, 2026-09-15.
  Pronto quando: reconhecimento por múltiplas âncoras observadas no PDF real,
  campos core com status/confiança e Decimal, fixture anonimizada, integração
  via Registry e regressão completa verde. Não avançar para F5.
  - Implementado `CopelDANF3EParser`, identidade `copel/1.0.0`, layout
    `danf3e/DANF3EA4B-V1.06`. Reconhecimento booleano mantém F3 e exige cinco
    âncoras: emissor, CNPJ público, DANF3E, título fiscal e versão do formulário.
  - Core comprovado: UC, competência documental MM/AAAA, número/série/chave
    fiscal, emissão/vencimento, três datas de leitura, consumo do medidor,
    total, nome e componentes do endereço. Todos usam ExtractedField; Decimal
    sem arredondamento. CPF mascarado é failed/warning, sem inventar dígitos.
    Confiança 0.95 é heurística de candidato único, não calibração estatística.
  - `FullTextExtractor` genérico e `RawExtraction.page_texts` preservam colunas
    e páginas, compatíveis com F3. Extração por labels/blocos/regex contextual,
    sem coordenadas absolutas no parser. Cabeçalhos gráficos da amostra exigem
    reconhecer a estrutura textual das linhas de UC/resumo/leituras.
  - `default_registry()` registra Copel; ProcessingService usa essa factory sem
    conhecimento da concessionária. Fluxo testado do registro tenant-scoped e
    bytes/hash até ParsedInvoice. Sem persistir status, bruto ou normalizado;
    `parsed` não equivale a validação final. Upload F2 permanece inalterado.
  - Uma fatura privada de duas páginas inspecionada, core na primeira; resultado
    real: 20 found e CPF mascarado failed. UC/chave/titular/competência/total
    conferidos contra texto original sem registrar valores pessoais em testes
    ou documentação. PDF original continua em private/, ignorado e não rastreado.
    Proteção adicional de .gitignore para o caminho fora de private/ onde o
    arquivo foi encontrado inicialmente; o usuário o moveu para private/.
  - Criados PDF reconstruído anônimo, expected JSON, gerador reproduzível e nota
    de proveniência. Dados fictícios, sem imagens/QR/boleto/metadata privados;
    renderização revisada. Deslocamento sintético preserva resultados, mas não
    é segunda amostra real: multi-layout e outras versões não homologados.
  - Testes F4: **23 OK** (22 parser + 1 integração). Gates F4/F3/F1/F2/tenant/
    migrations: **75 OK em 49,510s**, incluindo **9 migrations SQLite**.
    Regressão backend completa: **182 OK em 65,314s**. `py_compile`: **11 arquivos
    OK**; `git diff --check`, revisão de diff/novos e `git status` executados.
    Venv local fora da sandbox, Sentry desligado, bancos isolados. Avisos
    preexistentes de FK cíclica/identity map não causaram falhas.
  - Limites: sem CNPJ de titular comprovado, complemento de endereço separado,
    OCR, dados avançados, normalização, matching, cálculo, cobrança ou ASAAS.
    Sem novas dependências, frontend, contrato HTTP, migration ou deploy.
    Documentação: FATURAS_E_COBRANCAS.md seção 13 e README da fixture.
    READY_FOR_F5 refere-se somente ao Core observado; **F5 não iniciada**.

Comandos F4 executados em `backend`, além dos comandos de regressão/compile F3:

```powershell
rtk proxy .\venv\Scripts\python.exe -c "import os,unittest; os.environ['SENTRY_DSN']=''; result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.discover('tests',pattern='test_copel_parser.py')); raise SystemExit(not result.wasSuccessful())"
rtk proxy .\venv\Scripts\python.exe -c "import os,unittest; os.environ['SENTRY_DSN']=''; suite=unittest.TestSuite(unittest.defaultTestLoader.discover('tests',pattern=p) for p in ('test_copel_parser.py','test_invoice_parsers.py','test_fatura_processing.py','test_fatura_concessionaria*.py','test_tenant*.py','test_sqlite_migrations.py')); result=unittest.TextTestRunner(verbosity=1).run(suite); raise SystemExit(not result.wasSuccessful())"
rtk proxy .\venv\Scripts\python.exe -c "import pathlib,py_compile; files=list(pathlib.Path('services/invoice_parsers').glob('*.py'))+[pathlib.Path(p) for p in ('services/fatura_processing_service.py','tests/test_invoice_parsers.py','tests/test_fatura_processing.py','tests/test_copel_parser.py','tests/fixtures/invoices/copel/build_fixture.py')]; [py_compile.compile(str(p),doraise=True) for p in files]; print('py_compile OK:',len(files),'arquivos')"
```

- [x] Sprint F3 — **Framework do extrator — READY_FOR_F4**, 2026-09-15.
  Pronto quando: contratos por campo/issues/extração/ParsedInvoice versionado,
  extração mínima e registry com ambiguidade controlada, serviço sem efeitos
  externos ou persistência, testes F3/F1/F2/tenant e regressão backend verdes.
  Escopo termina em ParsedInvoice; não avançar para F4.
  - Criados `invoice_parsers/{schemas,base,registry,extraction}.py` e pacote:
    campos com quatro status, issues com três severidades, RawExtraction com
    páginas/metadata/words/tables opcionais, ParsedInvoice documental extensível
    e identidade centralizada de parser/layout. Decimal preservado, float
    rejeitado nos valores dos campos; coordenadas geométricas podem usar float.
  - MinimalExtractor reutiliza pypdf e lê texto apenas da primeira página.
    Registry vazio por padrão; fake somente nos testes. Seleção única, ausência
    e ambiguidade controladas, sem escolher o primeiro em conflito.
  - `FaturaProcessingService.process(fatura_id, document=pdf_bytes)` consulta
    fatura/Documento no tenant ativo, verifica SHA-256 e retorna resultado em
    memória. Sem download/API externa, commit, dados financeiros ou gravação
    de status. Persistência/status e adaptador de obtenção do PDF ficam para F4;
    `parsed` não equivale a `extraida`. Upload F2 não dispara processamento.
  - Validação focada: **43 testes OK** (F3 **25**, F1/F2 **13**, tenant **5**).
    Regressão completa: **159 testes OK em 66,368s**, incluindo os **9** testes
    de migrations SQLite. `py_compile` **8 arquivos OK**; `git diff --check`,
    revisão de diff/arquivos novos e `git status` executados.
  - Runtime: venv `backend/venv`, Python 3.13 fora da sandbox após bloqueio de
    acesso ao executável; SENTRY_DSN vazio, dados sintéticos e bancos isolados.
    A execução inicial encontrou email ausente na fixture F3, corrigido antes
    da regressão final. Avisos preexistentes de FK cíclica no teardown e
    identity map em importação não causaram falhas.
  - Documentação arquitetural confirmada na seção 13 de
    `FATURAS_E_COBRANCAS.md`. Sem contrato HTTP novo, migration, dependência,
    frontend, cálculo, normalizer, parser Copel, credenciais reais ou deploy.
    Alterações anteriores do worktree preservadas. STOP F3; F4 não iniciada.

Comandos F3, em `backend` (SENTRY_DSN desabilitado antes dos imports):

```powershell
rtk proxy .\venv\Scripts\python.exe -c "import os,unittest; os.environ['SENTRY_DSN']=''; suite=unittest.TestSuite(unittest.defaultTestLoader.discover('tests', pattern=p) for p in ('test_invoice_parsers.py','test_fatura_processing.py','test_fatura_concessionaria*.py','test_tenant*.py')); result=unittest.TextTestRunner(verbosity=1).run(suite); raise SystemExit(not result.wasSuccessful())"
rtk proxy .\venv\Scripts\python.exe -c "import os,unittest; os.environ['SENTRY_DSN']=''; result=unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.discover('tests')); raise SystemExit(not result.wasSuccessful())"
rtk proxy .\venv\Scripts\python.exe -c "import pathlib,py_compile; paths=list(pathlib.Path('services/invoice_parsers').glob('*.py'))+[pathlib.Path('services/fatura_processing_service.py'),pathlib.Path('tests/test_invoice_parsers.py'),pathlib.Path('tests/test_fatura_processing.py')]; [py_compile.compile(str(p),doraise=True) for p in paths]; print('py_compile OK:',len(paths),'arquivos')"
```

- [x] Sprint F2 — **Upload seguro, armazenamento e deduplicação da FaturaConcessionaria**, 2026-09-15.
  `POST /api/v1/clients/<clientId>/invoices/upload` recebe um PDF, exige
  `faturas.create` (`owner`/`admin`/`financial`), resolve Cliente e tenant pelo
  contexto autenticado, valida extensão/MIME/magic bytes/integridade/criptografia,
  tamanho e páginas, calcula SHA-256 antes do armazenamento e reutiliza o
  `DocumentService`/Google Drive. Os limites são configuráveis, com defaults de
  10 MiB e 10 páginas.
  - Duplicidade sequencial retorna o registro mais antigo sem novo Documento;
    corrida é arbitrada pela unique `empresa_id + arquivo_hash`, recupera o
    vencedor e não retorna 500. Documento e fonte são gravados na mesma transação
    de banco; upload remoto novo é compensado em falha, sem apagar arquivo já
    reutilizado pelo vencedor concorrente.
  - Cobertura F2: PDF válido, extensão/MIME/magic falsos, corrompido, vazio,
    criptografado, limites, dedupe sequencial/concorrente, dois tenants, RBAC e
    cleanup pós-storage. Nenhum parser, extração, matching, UC, cálculo, cobrança,
    ASAAS, PUT ou frontend foi criado.
  - Validação: F2/Document **10 testes OK**; F1 + F2 + tenant **18 testes OK**;
    migrations SQLite **9 OK**; regressão backend completa **134 testes OK**; `py_compile`
    e `git diff --check` passaram. Não havia suíte dedicada de Document; seu
    fluxo de preparação/commit/cleanup é exercitado diretamente pela F2.

- [x] Sprint F1 — **Fundação da FaturaConcessionaria**, 2026-09-15.
  `FaturaConcessionaria`/`faturas_concessionarias` foi criada com `TenantMixin`,
  FKs explícitas para Cliente/UC/Documento, status protegidos por checks,
  energia em `Numeric(18,6)`, valor total em `Numeric(18,2)` e JSON para dados
  brutos/normalizados. Cliente e Documento são obrigatórios; UC é nullable até o
  matching futuro. Hash é único por empresa; chave fiscal tem índice não único,
  permitindo mesma chave com conteúdo diferente para revisão posterior.
  - Migration `l6f1a5b8c2d4` após B2: upgrade, schema (33 colunas), quatro FKs,
    constraints/índices e ciclo downgrade vazio/upgrade passaram no PostgreSQL
    Neon dev; downgrade com fonte persistida é bloqueado e foi validado em SQLite.
  - Validação: F1 **3 testes OK**; tenant **5 OK**; migrations **9 OK**;
    regressão backend completa em blocos, **124 testes OK**. `py_compile` passou.
    Nenhum endpoint, contrato de API, frontend, upload, hash service, parser,
    normalizer, matching, cálculo, Copel, ASAAS ou vínculo em `Fatura` foi criado.

- [ ] Sprint B3 — **PARTIAL: homologação da fundação ASAAS**, 2026-09-14.
  - PostgreSQL de desenvolvimento configurado localmente (Neon; FLASK_DEBUG=true,
    ASAAS Sandbox) subiu de h2b7c1d9e4f6 até k5e0f4a9b7c1. A inspeção
    confirmou asaas_id nullable, unicidades B1
    (empresa_id + emission_key, external_reference), check de workflow,
    ledger B2 provider + event_id e os índices de tenant/Fatura.
    O alvo estava sem Faturas antes do upgrade; logo a compatibilidade de
    registros legados foi confirmada pela suíte de migration SQLite, não por uma
    linha legada pré-existente nesse PostgreSQL.
  - Concorrência em PostgreSQL real: duas emissões equivalentes com provedor
    simulado produziram uma Fatura, um POST remoto e retry no mesmo ID. Duas
    entregas concorrentes do mesmo evento produziram um ledger, status
    received e duas respostas idempotentes; token de outra empresa e token
    inválido receberam 401. Os dados B3 efêmeros e seus logs foram removidos ao
    final. Isto não representa emissão ASAAS real.
  - **BLOCKED externo:** não há nenhuma ApiCredential(provider='asaas')
    disponível no banco dev, nem endpoint público não produtivo configurado para
    o Sandbox. Para concluir: criar empresa(s) de teste, cadastrar
    api_key_sandbox e webhook_token_sandbox distintos por empresa,
    publicar o endpoint de homologação /api/v1/webhooks/asaas e configurar
    webhook Sandbox com sendType=SEQUENTIALLY. Não usar produção.
  - A API ASAAS atual suporta filtro por externalReference; a reconciliação real
    permanece bloqueada apenas pela credencial Sandbox. Eventos distintos fora
    de ordem podem regredir asaas_status: B2 deduplica apenas o mesmo event_id.
    A documentação ASAAS declara ordem somente com entrega sequencial, ainda não
    comprovada na conta Sandbox.
  - Ambiente ASAAS segue global por instalação (ASAAS_API_BASE_URL), embora API
    key/token sejam por empresa. A seleção ambiente-por-empresa continua dívida
    do follow-up da Sprint D2; não foi refatorada nesta B3.
  - Validação final: regressão backend completa em blocos equivalentes a
    unittest discover, **120 testes OK**; B0/B1/B2 46, tenant/credenciais 14,
    demais regressões 52 e migrations 8. git diff --check passou. Nenhum arquivo
    frontend ou contrato foi alterado nesta B3, portanto build frontend não foi
    necessário.

- [x] Sprint B2 — Webhook ASAAS multi-tenant e idempotência de eventos, 2026-09-14.
  Baseline inicial confirmada: **98 testes OK**. Implementação local concluída e
  regressão final: **120 testes OK em 54,916s**, sem credenciais/cobranças reais.
  - Rota pública valida envelope, resolve exatamente uma Fatura por referência
    B1 ou ID remoto não ambíguo, carrega token cifrado da empresa/ambiente e usa
    `secrets.compare_digest`. Lookup cross-tenant privado/mínimo, sem helper de bypass.
  - Ledger `PaymentWebhookEvent` / `payment_webhook_events`, tenant-aware, guarda
    IDs/tipo/hash e timestamps, nunca payload completo. Unicidade global
    `(provider,event_id)` confirmada na documentação ASAAS. Flush/IntegrityError
    arbitram concorrentes; Fatura + evento + `processed_at` têm commit único.
    Duplicata autenticada retorna 200 sem repetir efeito nem alterar timestamps.
  - Emissão/retry/reconciliação/reserva B1 intactos. Removido apenas o antigo
    processador de webhook inseguro de `fatura_service`; teste B1 da ausência
    de ID adaptado à rota nova. Nenhuma tabela Cobranca ou nova fronteira de emissão.
  - ApiCredential reutilizada: tokens `webhook_token_sandbox`/`webhook_token_producao`,
    API keys nomeadas por ambiente com fallback legado que exclui tokens.
    Ambiente segue a URL da instalação B1; não implementada troca independente
    por empresa. Token global não autentica B2. UI existente recebeu somente
    instruções/rótulos compatíveis; teste de webhook token é exclusivamente local.
  - Migration nova `k5e0f4a9b7c1` após `j4d9e3f8a6b0`: somente tabela/índices de
    eventos, sem modificar Fatura/dados históricos. Histórico SQLite vazio,
    upgrade sobre B1 com Fatura legada, unicidade, downgrade vazio/roundtrip e
    bloqueio de downgrade com ledger não vazio passaram. Nenhum banco real migrado.
  - Suítes incluídas na regressão final: B2 **20**, Faturas B0/B1 **26**, tenant
    **5**, credenciais **9**, migrations **8**; demais regressões também verdes.
    Concorrência B2 testada com duas requisições/conexões reais SQLite; falhas
    após atualização e no commit reverteram ambos os registros.
  - Build final TypeScript/Vite **OK**; `git diff --check`, revisão de diffs,
    arquivos novos e `git status` executados. Worktree já continha alterações
    anteriores, preservadas. Avisos SQLAlchemy preexistentes de FK cíclica em
    teardown e identity map em importação não causaram falhas.
  - Limites: sem homologação ASAAS Sandbox real ou concorrência PostgreSQL;
    eventos diferentes não são ordenados pelo ledger. Configurar entrega
    sequencial; estados/eventos fora do conjunto documentado recebem 422 sem
    commit e precisam de acompanhamento operacional. Configurar tokens por
    empresa **antes** de ativar B2. Futuras notificações externas exigirão
    entrega durável própria; nenhuma automação foi criada.
  - Documentação: `FATURAS.md` (B2/ativação/estados/limites), `FATURAS_E_COBRANCAS.md`
    (arquitetura confirmada), `API_CONTRACTS.md` e este registro. Skills lean-build
    e migration mantiveram a evolução aditiva e o downgrade protegido.
  - STOP: nenhum deploy, F0/F1, parser, cálculo, FaturaConcessionaria ou sprint
    posterior. Recomenda-se homologar B2 em Sandbox e PostgreSQL antes da próxima sprint.

Comando final, a partir de `backend`, no venv existente fora da sandbox
(`SENTRY_DSN` vazio antes dos imports; bancos temporários dos testes):

```powershell
rtk proxy .\venv\Scripts\python.exe -c "import os,unittest; os.environ['SENTRY_DSN']=''; result=unittest.TextTestRunner().run(unittest.defaultTestLoader.discover('tests')); raise SystemExit(not result.wasSuccessful())"
```

Na raiz: `rtk proxy npm.cmd --prefix frontend run build`,
`rtk proxy git diff --check`, `rtk proxy git status --short` e revisão de `git diff`.

- [ ] Sprint B1 — **PARTIAL (gate global)**, 2026-09-14. Implementação e testes específicos concluídos: `Fatura` persiste intenção/referência UUID antes do ASAAS; chave única por empresa identifica o comando; reserva atômica e durável escolhe um emissor; timeout/queda/erro pós-POST não liberam retry cego; conciliação valida referência, customer e valores. Rotas finas, service único, sem tabela Cobranca. Migration `j4d9e3f8a6b0` preserva legados e impede downgrade destrutivo do diário B1. Detalhes operacionais em `FATURAS.md` (B1).
  - Runtime: venv Python 3.13 funciona fora da sandbox; o anterior `did not find executable ... Python313 ... Acesso negado` era restrição da sandbox. Baseline B0: 3 testes OK. Testes posteriores desligaram `SENTRY_DSN` antes dos imports para não enviar telemetria.
  - Suíte focada final: **26 testes OK**, incluindo concorrência com duas sessões/conexões reais em SQLite, reserva em voo, falha de commit, timeout, reconciliação, RBAC e dois tenants.
  - Migrations: **7 testes OK**, incluindo histórico SQLite vazio, upgrade de legado, roundtrip downgrade/upgrade e recusa de downgrade após intenção B1. Nenhuma migration aplicada a banco real.
  - Bateria ampliada: credenciais **8/8 OK**; tenant **4/5 OK**, com erro existente em desconexão UC/usina reproduzido isoladamente. Regressão completa executou **94 casos, 2 erros**: `test_rateio_documentos.py:31` contém `SyntaxError: '(' was never closed`; `test_tenant_service_lookups.py:111` falha com `could not convert string to float: ''` porque `uc_service.sync_connections()` preenche percentual ausente com string vazia. Ambos fora de B1 e preservados; o último ajuste de cancelamento foi validado na suíte focada final.
  - Frontend: `rtk proxy npm.cmd --prefix frontend run build` **OK fora da sandbox** (primeira tentativa bloqueada pelo acesso do esbuild). Apenas contrato TypeScript atualizado para `asaasId` nullable e metadados B1, sem tela nova.
  - `git diff --check`, revisão de diffs e `git status` executados; alterações anteriores preservadas. Sem deploy, cobrança real, parser ou avanço a B2. PostgreSQL concorrente e ASAAS Sandbox real não homologados nesta sessão.

Comandos efetivamente usados, a partir de `backend`, fora da sandbox:

```powershell
rtk proxy .\venv\Scripts\python.exe -c "import os,unittest; os.environ['SENTRY_DSN']=''; suite=unittest.defaultTestLoader.discover('tests',pattern='test_fatura*.py'); result=unittest.TextTestRunner(verbosity=1).run(suite); raise SystemExit(not result.wasSuccessful())"
rtk proxy .\venv\Scripts\python.exe -c "import os,unittest; os.environ['SENTRY_DSN']=''; suite=unittest.defaultTestLoader.discover('tests',pattern='test_sqlite_migrations.py'); result=unittest.TextTestRunner(verbosity=2).run(suite); raise SystemExit(not result.wasSuccessful())"
rtk proxy .\venv\Scripts\python.exe -c "import os,unittest,warnings; os.environ['SENTRY_DSN']=''; warnings.simplefilter('ignore',DeprecationWarning); suite=unittest.defaultTestLoader.discover('tests'); result=unittest.TextTestRunner(verbosity=1).run(suite); raise SystemExit(not result.wasSuccessful())"
```

Critério pendente para fechar o gate global: corrigir separadamente as duas falhas
acima e obter regressão completa verde. Antes de B2, manter as reservas B1 intactas;
O criterio acima foi atendido pela Sprint FIX-BASELINE; B2 deve resolver tenant/token
e deduplicar eventos por provider/event_id, sem criar pagamentos.

- [x] Sprint FIX-BASELINE — 2026-09-14. Corrigido o parêntese ausente no teste de
  formulário XLSX de Rateio e o valor padrão de percentual ausente em
  `sync_connections()`; a busca das conexões persistidas também preserva o registro
  de desconexão quando a relação ORM já estava carregada. Rateio (4), tenant (5),
  Faturas B0/B1 (26) e regressão completa do backend passaram. Nenhum trabalho de
  B2 foi iniciado.

- [x] Sprint B0 — Compatibilidade e RBAC de Faturas: `Fatura` foi declarada como persistência física da Cobrança HUB, sem tabela paralela; `FaturaConcessionaria` permanece a origem documental futura e imutável; `operator` agora lê Faturas sem ações financeiras. Cobertura de rota para owner/admin/financial/operator/viewer validada em 2026-09-14: 3 testes do baseline OK no venv existente fora da sandbox; teste de legados adicionado em B1 também passou.

- [x] Issues #50, #51, #34 e #27: eliminadas consultas N+1 de pendências, separado health check de prontidão do banco, registrada a data real de UC sem usina e adicionada senha de concessionária identificada por CPF/CNPJ, sem retorno do segredo. Evidência: suíte Python focada e build do frontend executados em 2026-09-11.

- [x] Integração Asaas passou a identificar a chave API corretamente, separar o token de webhook e testar a conectividade real de forma explícita, sem expor segredos.

- [x] Revisão visual curta: botões e seletores reutilizam os controles-base do HUB; Agenda, Rateio e Mensagens deixaram de referenciar tokens inexistentes. Evidência: `npm.cmd --prefix frontend run build` aprovado em 2026-09-11.

- [x] CI de promoção reconstruído em 2026-09-28: testes de backend e frontend em `develop`, `main` e PRs para `main`; após cinco execuções aprovadas de `develop` desde o último commit de `main`, o workflow abre PR, valida a integração antes do merge e registra falha em Issue. O secret `PROMOTION_TOKEN` foi criado no GitHub. Validação: parser YAML aceitou os gatilhos e os quatro jobs; a primeira execução remota (`36433236092`) passou em backend, lint/build frontend e contagem de promoção. As actions foram atualizadas para v7 após o runner alertar sobre a descontinuação do Node 20 na execução delas.

- [x] Configurações → Geral → Rateio agora permite desativar temporariamente, por empresa, as exigências de CNPJ, estatuto e Termos de Adesão para testar a geração de PDF/XLSX sem anexos. O padrão continua seguro (todas ligadas); soma de percentuais, UC geradora e responsável permanecem obrigatórios.

- [x] Refatoração estrutural da tela de Rateio: `RateioPage.ts` passou de 1.159 para 67 linhas; wizard, formulário Copel e utilitários foram separados por responsabilidade em `frontend/src/pages/rateio/`, todos abaixo de 350 linhas. A regra de qualidade voltou a validar `RateioPage.ts`. Evidência: build e lint do frontend aprovados em 2026-09-09.

- [x] Sprint A — Planos, Assinatura e enforcement de cota: catálogo Starter em arquivo, Assinatura/LimiteContratado e migration com backfill vitalício para empresa 1; POST de Cliente/UC/Usina/Usuário bloqueia somente acima da cota, com fail-open sem assinatura. Evidência: testes de cota, migrations SQLite e regressão backend aprovados.

- [x] Sprint — Formulário de Rateio em Excel: modelo oficial `formulario_copel_rateio.xlsx`, associação fixa na linha 1 (0%), beneficiárias a partir da linha 2, A11 configurável antes do download, prévia e expansão com reconstrução de merges. Termos de Adesão continuam PDF mesclado; CNPJ/Estatuto continuam downloads separados. Validação de build passou; runtime Python local bloqueado por Python313 sem acesso.

- [x] Modelo padrão de importação/exportação adotado a partir de `HUB_Modelo_Importacao.xlsx`. Download público `/api/v1/importacoes/modelo` sem exemplos, botão em Importações inclusive para perfis sem permissão de importar; exportação autenticada usa as mesmas abas, cabeçalhos, estilos e listas. Campos opcionais mapeados, linhas vazias ignoradas e dias inteiros validados. Evidência: 10 testes de `tests.test_importacoes` passaram (arquivo real, download anônimo, RBAC, duas empresas, preview/commit/export); `npm.cmd --prefix frontend run build` passou. Sem deploy nesta entrega.

> Leia `VISAO.md` primeiro. Este arquivo é o estado atual, atualizado a cada tarefa concluída.
> **Documentos relacionados:** `VISAO.md` · `ARCHITECTURE.md` · `API_CONTRACTS.md` · `CONTRIBUTING.md`
> Regra: pegue a primeira tarefa `[ ]` de cima pra baixo. Não pule.

## HOTFIX — revogação de convite (2026-09-28)

- `revogar_convite` agora persiste `revoked` com `commit()` e retorna somente o dicionário do convite; removido o acesso indevido a `commit` e `token_cru`.
- Validação executada: `python -m py_compile backend/services/invitation_service.py` passou; teste isolado da função cobriu `pending` (retorno `dict`, um commit) e `revoked`/`expired`/`accepted` (ValueError, sem commit).
- Suíte `python -m unittest discover -s backend\\tests` tentada, mas indisponível neste ambiente: `.venv` do projeto ausente e Python disponível sem `sentry_sdk`/`flask`. Os cenários HTTP e criação/reenvio dependem desse ambiente e permanecem sem validação de integração.

Última atualização: 2026-09-24 — planejamento V2.5 (centralização de arquivos e auditoria de importações) adicionado; HUB subido localmente (backend + frontend).

- 2026-09-02: Corrigida a migration `e6a8c0d2f4b6` para PostgreSQL (`true/false` em coluna booleana), aplicada até o head no banco de desenvolvimento; migrations SQLite e modelo Fatura passaram nos testes.
- 2026-09-02: Convites passaram a gerar link HTTPS com `FRONTEND_URL=https://hub-frontend-fnm6.onrender.com`; CORS local mantém `localhost` e `127.0.0.1` somente em debug. Investigado e corrigido o `Failed to fetch` do login: havia processo Flask antigo ocupando a porta e o backend foi reiniciado com a sintaxe atual.
- 2026-09-02: Empresas ganharam detalhe administrativo com impersonation, cadastro, documentos, uso/limites, edição, suspensão/reativação e atalho para Usuários; `UsersPage` ganhou edição e aba de Convites com revogação/reenvio.
- 2026-09-02: Financeiro ASAAS preparado em Sandbox: `Client.asaas_customer_id`, `Fatura` tenant-aware, cliente ASAAS por credencial da empresa, emissão/listagem/detalhe/sincronização/cancelamento/resumo, webhook autenticado e tela Faturas/modal. Falta homologação externa com uma conta/chave Sandbox por empresa.

- 2026-09-01: OAuth Google passa a usar a raiz da conta conectada sem exigir ID de pasta; a pasta permanece como limite opcional no OAuth e obrigatório no fallback de service account.

- 2026-09-01: Rateio, formulário Copel e resolução automática de pendências passaram a buscar Usina/UC/Cliente por `id` e `empresa_id`; regressão cobre IDs da Empresa B já presentes no identity map durante operação da Empresa A.

- 2026-08-31: busca de documentos corrigida para configuração multi-tenant: Configurações > Banco de Dados salva a pasta raiz do Google Drive por empresa e invalida o cache ao alterar; o frontend mostra o motivo real do 503.

---

## Decisões já resolvidas (não reabrir sem motivo novo)

- [x] **Numeração de versão:** `V0.x` até o núcleo fechar, vira `V1.0` de verdade só quando os itens desta seção estiverem todos `[x]`.
- [x] **Plant.percentual_disponivel:** ⚠️ nota desatualizada até 2026-08-19 dizia "continua manual" -- na prática, `percentual_disponivel_efetivo()` (`models/plant.py`) já calcula automaticamente (`100 - reserva_percentual`) sempre que a usina tem produção mensal cadastrada, e só cai no campo manual quando não há produção. `PlantCard.ts` ainda mostra o campo "Disponível para rateio (%)" como editável mesmo quando ele é ignorado pela API nesse caso (a API já devolve `percentualManual: false/true` pra distinguir) -- **TODO:** esconder/desabilitar esse campo no formulário quando `percentualManual === false`. Registrado como tarefa pendente, não decisão em aberto.
- [x] **CPF/CNPJ da UC:** UC tem campo `documento` próprio (pode diferir do CPF do Cliente — ex.: casa no CPF pessoal, empresa no CNPJ do mesmo titular). Sem validação rígida contra o cliente, é campo livre.
- [x] **Código ANEEL:** UC tem `codigo` (atual/legado) e `codigoAneel` (novo padrão nacional de 15 dígitos, REN ANEEL 1.095/2024) como campos separados.
- [x] **Deploy completo (Fase 1):** HUB roda 100% na nuvem — Postgres (Neon, projetos separados dev/produção), backend (Render Web Service), frontend (Render Static Site), documentos no Google Drive. Não depende mais do `python hub.py iniciar` pra existir, só pra desenvolver/testar.
- [x] **Autenticação e papéis (Fase 1 de Segurança):** cookie HttpOnly + CSRF + rate limit + headers de segurança + roles `owner`/`admin`/`operator`/`financial`/`viewer`, com regressão de isolamento e revogação de sessão. Auto-cadastro condicionado a `SIGNUP_CODE` (ver `.env.production.example`).
- [ ] **Regra de cálculo do rateio automático** — segue sem definição. Bloqueia qualquer início de V3.0. Precisa de conversa dedicada com o João antes de qualquer linha de código.

---

## V0.x → V1.0 — Núcleo funcional

### Backend — Banco de dados e models
- [x] SQLAlchemy + Flask-Migrate configurados via `extensions.py` (db/migrate centralizados — não criar instância própria em nenhum outro arquivo, isso já causou bug real de produção).
- [x] Migrations aplicadas em cadeia, testadas inclusive contra banco com dado pré-existente: `45f056e2a73d` (schema inicial) → `cbc335adce4f` (Categoria/Documento/Configuração/GoogleAccount/Log) → `061e810abc38` (users) → `c4b5632aaedd` (campos de negócio extras em Cliente/UC/Usina) → `8f2a1c9d0eab` (categoria opcional em Documento) → `a1f9c2e6d8b3` (cidade/uf/endereco/data_ativacao/responsavel em Usina) → `f3d7b1c9a4e2` (tabelas `pendencias` e `pendencia_comentarios`).
- [x] Models completos: `Client`, `Plant`, `ConsumerUnit`, `PlantConnection`, `Category`, `Document`, `Setting`, `GoogleAccount`, `LogEntry`, `User`, `Pendencia`, `PendenciaComentario`.
- [x] Campos de negócio em Cliente: nome, cpf, email, telefone, concessionaria, status, data de nascimento (`data_nascimento`, migration `b7c3e5a1d9f4`, exposta na API como `dataNascimento`).
- [x] Campos de negócio em UC: codigo, codigoAneel, apelido, documento, endereco, cep, concessionaria, geracaoPropria, diaEmissaoFatura, consumo, baseTarifaria, desconto, tipoLigacao, inicioContrato, terminoContrato, carenciaMeses, percentualDescontoCarencia.
- [x] Campos de negócio em Usina: nome, uc, kwPico, status, percentualDisponivel, marcaInversor, telefoneProprietario, emailProprietario, cidade, uf, endereco, dataAtivacao, responsavel.
- [ ] **Faltam em Usina:** número de módulos e potência do módulo (Wp por módulo, provavelmente — confirmar com o João o nome de exibição certo). Campo novo em `models/plant.py` + migration + exposição no `PlantCard.ts`/`plantService.ts`, seguindo o mesmo padrão dos campos que já existem.
- [x] `GoogleAccount.refresh_token` criptografado de verdade via `utils/crypto.py` (Fernet, chave em `SECRET_ENCRYPTION_KEY`) — nunca aparece em `to_dict()`.

### Backend — API
- [x] `POST /auth/bootstrap` (cria o admin uma única vez), `POST /auth/login` (retorna token assinado via `itsdangerous`, expira em 7 dias).
- [x] Middleware (`utils/auth.py`) protege toda rota exceto `/`, `/auth/login`, `/auth/bootstrap`, `/oauth/google/authorize`, `/oauth/google/callback` — testado: sem token dá 401, token forjado dá 401, token válido passa.
- [x] `GET/POST/PUT/DELETE /clients` — inclui sincronização de UCs aninhadas.
- [x] `GET/POST/PUT/DELETE /ucs` — CRUD avulso, além de aninhado dentro de `/clients`. Lógica de conexão UC-Usina (`sync_connections`, por `plantId`) compartilhada entre os dois, sem duplicação.
- [x] `GET/POST/PUT/DELETE /plants`.
- [x] `GET/POST /categories`.
- [x] `GET/POST/PUT/DELETE /documents` + `GET /documents/<id>/download` — upload/download de arquivo real em disco (`backend/uploads/`, fora do git), testado byte a byte.
- [x] `GET/PUT /settings` — configuração chave/valor (hoje usado só por Aparência).
- [x] **`GET /config/database` + `POST /config/database/{provider,google-drive,sql,test}`** — tela de "Banco de dados" em Configurações escolhe entre Google Drive (service account) e SQL (cadastro de credencial pronto, driver real ainda não plugado), persistido no `.env` via `dotenv`.
- [x] **OAuth 2.0 do Google completo** (`oauth_routes.py` + `services/oauth_service.py`) — fluxo de autorização com PKCE, múltiplas contas (`GoogleAccount`, refresh token criptografado no banco), `GET/POST/DELETE /oauth/google/accounts...`. `drive_service.py` já prioriza a conta OAuth ativa e só cai pro `credentials.json` de service account se não houver conta conectada ou o refresh falhar — sem duplicidade entre os dois caminhos.
- [x] **OAuth Google sem ID de pasta:** após login e consentimento, o Drive usa a raiz da conta OAuth da própria empresa. A pasta raiz segue opcional para organizar/restringir OAuth e obrigatória apenas no fallback por service account compartilhada.
- [x] `drive_routes.py` não derruba mais o backend se `credentials.json` não existir — erro controlado (503) em vez de crash.
- [x] **`GET/POST/PUT/DELETE /pendencias`** + `GET /pendencias/resumo` + `POST /pendencias/<id>/{resolver,cancelar,reabrir}` + `POST /pendencias/<id>/comentarios` + `POST /pendencias/verificar` + `GET /pendencias/regras` (`pendencia_routes.py` + `pendencia_service.py` + `automacao_service.py`). Criação manual (`POST /pendencias`) sempre força `tipo='pendencia'` — `alerta`/`erro` só nascem via automação. Motor de automação implementa 4 regras: UC sem usina, cliente sem UC, campos obrigatórios faltando, documentos obrigatórios faltando — com resolução automática quando a situação é corrigida.
- [x] `GET /logs` ganhou filtro opcional `entidade`/`entidadeId` (usado pra timeline de uma Pendência específica). `LogService` passou a gravar `entidade_id` de verdade (coluna existia desde sempre, nunca tinha sido preenchida).

### Frontend
- [x] Login (tela + guarda de rota — sem token, qualquer página redireciona pra `/login`).
- [x] Clientes: 100% via API real (`clientsService.ts`), zero `localStorage`.
- [x] Usinas: 100% via API real (`plantService.ts`).
- [x] Aparência (cor, logo): via API real (`/settings`), zero `localStorage`.
- [x] `localStorage` eliminado do projeto inteiro.
- [x] **Tela de UCs** — rota `/ucs` consome a API real (`ucsService.ts`).
- [x] **Tela de Documentos** (`DocumentsPage.ts` + `documentsService.ts`).
- [x] **Configurações → Banco de dados** — troca de provedor, credenciais, teste, contas Google OAuth.
- [x] Formulário de Cliente/UC/Usina expõe os campos de negócio (telefone do cliente; código ANEEL, documento, endereço, CEP, concessionária, geração própria, dia de emissão, contrato, carência e desconto de carência na UC; marca do inversor e contato do proprietário na Usina). Helpers de campo (`createInput`/`createSelect`/`createCheckboxField`) centralizados em `components/formFields.ts`, reaproveitados por `ClientCard.ts`, `UcCard.ts` e `PlantCard.ts`.
- [x] **Sistema de ícones** (`components/Icon.ts`) — SVG inline (stroke=currentColor, sem cor/tamanho fixo), substituindo emoji do sidebar e texto solto (`x`) dos botões de remover. Ícones novos adicionados depois do lote inicial (conferir `Icon.ts` pra lista atual completa — não documentado nome a nome nesta sessão).
- [x] **Reforma de Usinas** (`PlantsPage.ts`) — lista com cards de status clicáveis (filtro), busca, tabela sem paginação (rolagem interna via `.data-panel-scroll`); detalhe com painel de informações + resumo (UCs ativas/ocupação) + abas (UCs conectadas ativa, Documentos/Financeiro/Histórico/Logs desabilitadas). `DetailHeader.ts` (órfão, sem CSS) e `_unused-drafts.css` removidos — a tela antiga estava com o detalhe invisível em produção.
- [x] **Sidebar reorganizada em seções** (Gestão/Financeiro/Automações/Configurações), com itens do roadmap futuro visíveis-porém-desabilitados ("Em breve") e rodapé com usuário logado (email/papel, cache leve em `authService.ts`) + versão.
- [x] **Tela de Pendências** (`PendenciasPage.ts`) — lista com cards-filtro por tipo (Pendência/Alerta/Erro), busca, painel de detalhe fixo lateral (não-modal) com badges, ações (resolver/cancelar/reabrir/editar/excluir), comentários e timeline (via `/logs`). Criação manual só gera tipo `pendencia`.
- [x] **Tela de Usuários** (`UsersPage.ts`) — owner/admin cria acesso direto com senha temporária e ativa/desativa contas; senha nunca é exibida, edição/exclusão não suportadas não são simuladas na UI. Contas criadas assim devem trocar a senha no primeiro acesso.

### Documentação viva
- [x] **`API_CONTRACTS.md` criado** — todo endpoint ativo documentado.
- [x] `API_CONTRACTS.md` atualizado com as rotas de `/pendencias` (CRUD, resolver/cancelar/reabrir/comentarios, resumo, verificar, regras) e o filtro novo de `/logs`.

### Deploy
- [x] **Backend rodando na nuvem (Render) com Postgres**, saindo do SQLite local. `config.py` normaliza `postgres://` → `postgresql://`. `psycopg2-binary` e `gunicorn` adicionados ao `requirements.txt`. Start Command: `gunicorn -w 2 -b 0.0.0.0:$PORT app:app`.
- [ ] Start Command ainda não roda a migration sozinho a cada deploy (sugestão: `flask db upgrade && gunicorn ...`) — hoje precisa rodar `flask db upgrade` manualmente do PC local apontando `DATABASE_URL` pra URL externa do Postgres do Render.
- [x] **Histórico Alembic validado em SQLite vazio:** `backend/tests/test_sqlite_migrations.py` executa `flask db upgrade` até a head e confere `api_credentials`. Em 2026-08-31, passou após tornar as migrations legadas `e5f9a3b2c7d4` (conversão numérica) e `d1e5f8a2b4c7` (unicidade de GoogleAccount) compatíveis com SQLite, preservando os caminhos PostgreSQL. O teste também cobre valores legados válidos/malformados, precisão/overflow `NUMERIC(p,2)` e bloqueia downgrade quando emails duplicados entre tenants perderiam a unicidade global.
- [x] Frontend confirmado publicado no Render. `VITE_API_BASE_URL` apontando pro backend do Render em produção.

---

## V1.5 — Refinamento operacional

- [x] Senha da concessionária da UC pode ser revelada sob demanda por owner/admin e copiada nos cadastros de UC e Cliente; permanece cifrada, fora de listagens e com auditoria sem o valor. Evidência: teste de rota e build do frontend executados em 2026-09-11.
- [x] **Pendências — Sprint 1**: model (`tipo`/`categoria`/`origem`/`prioridade`/`status`, vínculo opcional a Cliente/UC/Usina/Documento), comentários, CRUD completo, tela com cards-filtro/busca/painel de detalhe/comentários/timeline. Criação manual só gera tipo `pendencia`.
- [x] **Pendências — Sprint 2**: motor de automação implementado (`automacao_service.py` + `GET /pendencias/verificar` + `GET /pendencias/regras`). Regras automáticas implementadas:
  - UC sem usina vinculada há 7+ dias (cria alerta)
  - Cliente sem UC cadastrada (cria pendência)
  - Campos obrigatórios faltando no cliente (cria pendência)
  - Documentos obrigatórios faltando (cria pendência)
  - Resolução automática quando situação é corrigida
  - Sem duplicação de pendências existentes
  - Verificação automática ao abrir a tela de Pendências
  - Botão "Verificar agora" na toolbar
- [x] **Formulário Copel de Rateio (Associações)** (`RATEIO.md` seções 8-10): revisão editável, checagem de Termos e geração no modelo XLSX oficial. A associação é linha fixa 1 (0%), a escolha de excedente é feita antes do download e a planilha expande sem teto mantendo os merges. Termos seguem PDF mesclado; CNPJ e Estatuto seguem downloads separados.
- [x] **Dashboard operacional:** `GET /dashboard/resumo` entrega, em tempo real e no tenant ativo, fila de pendências abertas (priorizada), abertas/vencidas/vencendo em 7 dias/resolvidas no mês, totais e status de Clientes/Usinas, totais de UCs e documentos por categoria. A tela `/dashboard` consome esse contrato, é a página inicial e apresenta métricas, fila operacional e estados de carregamento/erro/vazio. O payload respeita RBAC: métricas de um domínio sem permissão de leitura são omitidas (`disponivel: false`), sem vazamento indireto. Build do frontend validado em 2026-08-31.
- [x] **Hardening OAuth de transporte:** `OAUTHLIB_INSECURE_TRANSPORT` não é mais habilitado no import e `OAUTHLIB_RELAX_TOKEN_SCOPE` foi removido, preservando a validação padrão de escopos. HTTP é aceito apenas em desenvolvimento local explicitamente configurado (`FLASK_DEBUG=true`, `OAUTH_ALLOW_INSECURE_TRANSPORT=true`, callback/frontend loopback); qualquer outro ambiente exige callback e frontend HTTPS absolutos, sem credenciais/fragmentos, e remove a exceção herdada do processo.
- [x] **Credenciais de API por empresa:** `ApiCredential` armazena segredo somente criptografado (`SECRET_ENCRYPTION_KEY`) para Resend, WhatsApp, ASAAS e concessionárias. CRUD em `/api-credentials` é tenant-scoped, não serializa segredo e registra auditoria sem valores sensíveis. O endpoint de teste é dry-run local, sem chamadas externas.
- [x] **Agenda operacional (Pendências + eventos)** — `GET /agenda` combina pendências abertas com `prazo` e eventos próprios, tenant-scoped e protegido por `pendencias.read`, com filtros de intervalo (máximo 93 dias-calendário) e visões dia/semana/mês. A tela cria pendência pelo mesmo endpoint de `/pendencias`, portanto prazo/status continuam sincronizados sem cópia de estado; eventos têm CRUD cancelável em `/agenda/eventos`, com permissões e rate limit. Financeiro e Rateio continuam como fontes futuras.
- [x] **Dados cadastrais da empresa atual:** `GET`/`PUT /empresas/atual` expõem e atualizam somente nome, razão social, CNPJ, e-mail e telefone da empresa autenticada. Escrita é limitada a owner/admin; slug, status e IDs são protegidos e o contrato/testes cobrem isolamento e validação.
- [x] **Importação em massa de Cliente/UC/Usina:** rota e tela de preview + confirmação para CSV UTF-8 ou XLSX (abas Clientes/UCs/Usinas), somente criação e sem conexões UC–usina. O plano fica temporariamente no servidor, tenant/user-scoped; confirmação é atômica e protegida contra replay. Parsing tem limites, bloqueio de fórmulas e resposta controlada para arquivos inválidos. Previews com PII expiram e são removidos por comando operacional `flask purge-import-previews`; auditoria guarda apenas hash, contagens e resultado. CPF agora é único por empresa. Em 2026-08-31: 13 testes de importação/migration, 36 testes de regressão e build do frontend aprovados; revisão de segurança aprovada.
- [x] **Templates de mensagem V1.5-C:** tela `/templates` e API tenant-scoped para criar, editar, remover, restaurar e pré-visualizar templates de e-mail/WhatsApp sem qualquer envio. Templates globais legados foram copiados por empresa na migration e estão somente em leitura por compatibilidade; provisionamento de empresa cria seus padrões na mesma transação. Prévia usa texto seguro, corpo/variáveis são validados, links exigem HTTPS e a auditoria é redigida. Em 2026-08-31: 43 testes de regressão e build do frontend passaram; revisão de segurança aprovada.
- [x] **Meta Cloud API e Mensagens:** cada empresa configura um número Meta com token cifrado, `phone_number_id` exclusivo e teste explícito de conexão. A inbox `/mensagens` registra conversas e status de entrega isolados por empresa; o webhook assinado resolve primeiro o número Meta e é idempotente. Templates WhatsApp têm estado/categoria de aprovação e podem ser submetidos/sincronizados com a Meta. Evidência: 70 testes backend, migrations SQLite e build frontend aprovados em 2026-09-10; falta somente cadastrar as credenciais reais da Meta no ambiente e em cada empresa.
- [x] **Isolamento do estado OAuth:** a limpeza de estados OAuth expirados executada durante uma requisição agora é limitada explicitamente à empresa atual; teste de regressão confirma que iniciar OAuth em uma empresa não remove estado de outra. O build do frontend também está sem aviso de import dinâmico/estático do cliente HTTP.
- [x] **Lookups de domínio tenant-scoped:** autenticação, Cliente, UC, Usina, Pendência e Documento deixaram de usar `Query.get()` para modelos de domínio; buscas e referências agora filtram explicitamente a empresa atual. Regressão A/B cobre criação/edição de UC aninhada, update/delete de entidades estrangeiras, vínculo de pendência e conexão de usina entre empresas.
- [x] **Infraestrutura de testes isolada:** fixtures de backend restauram ambiente, configuração e limiter após cada módulo, permitindo executar a mesma bateria tanto por módulo quanto diretamente, em ordem normal ou invertida, sem dependência de estado global.
- [x] **Ativação segura de usuários:** `PUT /users/<id>/ativo` aceita somente booleano real e revoga tokens anteriores a cada transição de status via `session_version`; testes cobrem token antigo, RBAC, owner/self e isolamento entre empresas (2026-08-31).
- [x] **Troca obrigatória de senha:** contas com `must_change_password` só acessam identidade, logout e `POST /auth/alterar-senha`; a troca confirma a senha atual, valida a nova, limpa a flag, revoga o token anterior e renova o cookie. Cobertura direta inclui bloqueio de API, falhas de validação, auditoria redigida e desbloqueio (2026-08-31).

## V2.0 — Cobrança e automação de mensagens
- [ ] Integração ASAAS (boleto). **Pronto quando:** cada empresa emite/lista/cancela/sincroniza faturas com sua própria credencial ASAAS Sandbox cifrada; Cliente guarda o `asaas_customer_id`; webhook público autenticado atualiza status sem cruzar tenants; tela Faturas consome todas as rotas.
  Implementação local concluída e validada (migration, isolamento, rotas e build); pendente somente teste ponta a ponta contra conta ASAAS Sandbox real.
- [ ] Integração WhatsApp pra disparo automático dos eventos da Agenda.
- [ ] Cobranças automáticas.

## V2.5 — Centralização de arquivos e auditoria de importações (planejamento)
Esta seção é exclusivamente de planejamento e documentação. A implementação não é iniciada agora; o objetivo é definir escopo, dependências e critério de pronto antes de qualquer linha de código ou migration. Não migrar, nem excluir, documentos existentes nesta tarefa.

### 2.5-A — Histórico de importações ANEEL
Adicionar à tela Configurações → Base tarifária ANEEL uma seção de histórico contendo, para cada tentativa/publicação:
- Nome do CSV original.
- Data e hora da importação.
- Usuário responsável.
- URL oficial de origem.
- Hash SHA-256 do arquivo.
- Status: prévia, publicado, rejeitado, conflito ou expirado.
- Quantidade de registros processados, aceitos e rejeitados.
- Relatório de validação.
- Acesso autorizado ao CSV original.

Reutilizar os registros e contratos já existentes da C5.4.1 (`RegulatoryTariffImport`, `RegulatoryTariffPreview` e `regulatory_tariff_import_service.py`). Apenas estender a apresentação e os contratos de leitura quando o histórico existente já atender; não criar uma segunda tabela de importações se a existente cobrir o requisito. Decisão documentada antes de qualquer migration.

### 2.5-B — Hub Storage (serviço centralizado de armazenamento privado)
Planejar um serviço centralizado de armazenamento privado para documentos do HUB, com estrutura lógica:
- `regulatory/aneel/imports/`
- `regulatory/aneel/reports/`
- `companies/{empresa_id}/invoices/`
- `companies/{empresa_id}/billing/`
- `companies/{empresa_id}/payments/`
- `companies/{empresa_id}/clients/`
- `companies/{empresa_id}/plants/`
- `audit/import-reports/`

O serviço deve ser uma abstração reutilizável de armazenamento, aproveitando a integração atual com Google Drive (`drive_service.py` + `document_service.py`) e deixando explícita a interface de backend para integração futura com Cloudflare R2 (ou outro provedor de objeto storage). Não introduzir dependência nova sem necessidade; o primeiro provedor concreto continua sendo o já existente.

Regras não-negociáveis do serviço:
- Preservar isolamento multi-tenant: todo acesso ao storage deve ser escopado à `empresa_id` da sessão, nunca confiar em cliente/UC informados pelo frontend.
- Controle de acesso via RBAC existente, alinhado aos perfis da rota de Documentos.
- Metadados em PostgreSQL, separados do blob: quem, quando, origem, hash, provedor, referência e política.
- SHA-256 do conteúdo antes de persistir; imutabilidade de documentos financeiros (boleto, fatura, comprovante, assinatura de protocolo) — nenhuma sobrescrita silenciosa.
- Versionamento quando o documento for editável por natureza; imutabilidade quando for comprovante/recibo/protocolo.
- Políticas de retenção explicitadas por categoria, com registro de expiração/arquivamento auditável.
- Não armazenar arquivos permanentes no filesystem efêmero do Render — esse filesystem é indicado apenas para previews temporários, uploads em trânsito e logs rotativos, nunca como fonte durável de documento de negócio.

### 2.5-C — Migração (planejamento, sem execução)
Nesta tarefa não migrar nem excluir documentos existentes. Antes de qualquer plano de migração, mapear onde cada categoria vive hoje:
- Documentos operacionais/gerais: `Document.storage_provider='google_drive'` com `storage_ref=fileId` do Google Drive, via `document_service.py` / `drive_service.py`.
- FaturaConcessionaria: upload via `fatura_concessionaria_upload_service.py`, com arquivo persistente no provedor configurado e `arquivo_hash` SHA-256.
- Importações em massa: `ImportPreview` com `arquivo_hash`, plano transientes e auditoria via `LogEntry`, sem armazenamento permanente do arquivo origem hoje.
- Base regulatória ANEEL: `RegulatoryTariffImport`/`RegulatoryTariffPreview`, com hash e `source_url`, sem upload de blob permanente no HUB hoje.
- Anexos legados locais: `backend/uploads/` (filesystem efêmero), usado somente para documentos antigos já persistidos antes da migração para o Drive.

Com esse mapeamento, planejar a migração por categoria, em ordem que preserva dados e não interrompe fluxos ativos, com rollback reversível e validação byte-a-byte de hashes quando aplicável. Decisão de quando e como migrar cada categoria fica para a implementação concreta; nesta tarefa fica apenas o inventário e o plano.

### 2.5-D — Documentação e critérios de aceite
Atualizar `PROGRESS.md`, `API_CONTRACTS.md` e a documentação de domínio afetada quando a sprint for iniciada. Critérios de pronto para a sprint (a serem validados na implementação, não aqui):
- Histórico de importações ANEEL exposto com todos os campos da seção 2.5-A, restrito a administrador de plataforma quando o dado for global, e a empresa quando o registro for por tenant.
- Hub Storage com interface por categoria, isolamento multi-tenant verificado com pelo menos duas empresas, hash SHA-256 persistido, imutabilidade comprovada para documentos financeiros e política de retenção configurável e auditável.
- Migração documentada por categoria, com inventário de armazenamento atual e plano sem perda de dados, validado em banco de teste antes de qualquer execução em ambiente real.
- Build do frontend e regressão backend verdes; nenhuma alteração destrutiva de modelo ou migration irreversível sem critério explícito.

### S — Storage e auditoria de importações (planejamento)
- [ ] Histórico de importações ANEEL na tela Configurações → Base tarifária ANEEL (seção 2.5-A).
- [ ] Hub Storage: abstração reutilizável de armazenamento privado (seção 2.5-B).
- [ ] Inventário e plano de migração sem perda de dados (seção 2.5-C).
- [ ] Documentação, dependências e critérios de aceite (seção 2.5-D).

> Leia `VISAO.md` primeiro. Este arquivo é o estado atual, atualizado a cada tarefa concluída.
> **Documentos relacionados:** `VISAO.md` · `ARCHITECTURE.md` · `API_CONTRACTS.md` · `CONTRIBUTING.md`
> Regra: pegue a primeira tarefa `[ ]` de cima pra baixo. Não pule.

## V3.0 — Financeiro / Rateios
- [ ] **Regra de cálculo do rateio automático ainda não definida** — decisão de negócio, precisa de conversa com o João antes de qualquer linha de código.
- [ ] Botão de rateio automático por Usina.
- [ ] Importação de fatura e planilha de rateio.
- [ ] Relatórios + exportação Excel/PDF.
- [ ] Histórico de competências.

## V4.0 — Monitoramento
- [ ] Integração com APIs de inversores.
- [ ] Leitura automatizada de fatura das concessionárias (robô/ML).
- [ ] Alertas automáticos de produção/falha.

## V5.0 — Automação
- [ ] Motor de automações.
- [ ] Portal do cliente.
- [ ] Integração com SunHub via API.

---

## Log de decisões tomadas durante o desenvolvimento

- 2026-07-08 a 2026-07-12: fundação inicial (SQLAlchemy, migrations, models Cliente/UC/Usina, revisão arquitetural que achou o bug dos 5 models faltando).

- 2026-07-19: vindo do GDASH, levantada lista extensa de campos de negócio pra Cliente/UC/Usina — triada entre "adota agora" (dado estático) e "ignora por enquanto" (tudo que é calculado ou depende de integração ainda não construída: economia total, saldo de crédito, gráficos de geração em tempo real, etc.).

- 2026-07-20/21: sessão focada destravou em sequência — bug de duas instâncias `SQLAlchemy()` brigando (client_routes 500), blueprint de cliente nunca registrado, os 5 models faltando (criados e testados), autenticação completa (bootstrap/login/middleware, chave vazada no `.env.example` detectada e trocada), CRUD de UC avulso, backend de Documentos + Categorias, `localStorage` eliminado do frontend inteiro (Clientes, Usinas, Aparência), `iniciar.py` corrigido (venv apontava pra pasta errada, PID errado).

- 2026-07-22: campos de negócio completos adicionados a Cliente/UC/Usina a partir de comparação com o GDASH; migration testada especificamente contra banco com dado pré-existente (achado e corrigido: `geracao_propria NOT NULL` sem default quebraria em banco real). `PROGRESS.md` reescrito do zero pra parar de arrastar informação desatualizada.

- 2026-07-26 (aprox., commit "OAuth do Google Drive completo e testado"): OAuth 2.0 real implementado — fluxo PKCE, `GoogleAccount` com refresh token criptografado, múltiplas contas, `drive_service.py` priorizando a conta OAuth ativa. Junto veio a tela de Configurações → Banco de dados (Google Drive / SQL) e a lista de contas Google conectadas.

- 2026-07-27: tela de UCs (`/ucs`) e tela de Documentos implementadas, ambas consumindo API real. `API_CONTRACTS.md` criado documentando todo endpoint ativo, inclusive os de `/config/database` e `/oauth/google` que não estavam rastreados. `PROGRESS.md` atualizado pra bater com o estado real do código (zip conferido, não só relato).

- 2026-08-03: **Migração de dados (SQLite → Postgres)** — Etapa 3 do plano de deploy. Script pontual `backend/scripts/migrate_sqlite_to_postgres.py`, testado com cópia de dado real antes de entregar (contagens, ordem de FK, reset de sequence, idempotência). `users` fica fora por padrão (evita duplicar/colidir com o admin já criado durante o teste da Etapa 2). Documentos físicos (`backend/uploads/`) não precisaram de nenhuma ação nessa etapa — só passam a importar na Etapa 7 (Render, filesystem efêmero).

- 2026-08-04 a 2026-08-09: **Fase 1 de deploy fechada por completo** — Etapa 4 (CORS restrito), Etapa 5 (config por ambiente + `.env.production.example` + `FLASK_DEBUG` seguro por padrão), Etapa 6 (Neon de produção, segundo projeto separado do de dev), Etapa 7 (Render backend via Gunicorn — descoberto e corrigido: `state` do OAuth do Google guardado em memória quebrava com mais de 1 worker, resolvido migrando pra tabela `Setting` no banco), Etapa 8 (Render frontend, com a pegadinha de que `_redirects` é sintaxe do Netlify, não do Render — SPA rewrite é configurado no dashboard). Upload de documento migrado de disco local pra Google Drive (`services/drive_service.py`: `find_duplicate`/`upload_file`), com deduplicação por MD5 — evita subir cópia idêntica de novo. `DEPLOY.md` criado, documentando toda a infraestrutura, variáveis de ambiente e os aprendizados do caminho.

- 2026-08-06: sessão longa — sistema de ícones (`Icon.ts`), reforma completa de Usinas (lista + detalhe, achado e corrigido bug real: `DetailHeader.ts` sem CSS, tela de detalhe invisível em produção), sidebar reorganizada em seções, campos de negócio nos 3 formulários (`formFields.ts` centralizado), Pendências Sprint 1 completo, migração do backend pra Postgres/Render (`config.py`, `requirements.txt`), `API_CONTRACTS.md` atualizado com `/pendencias` e `/logs`. **Decisão revista:** `.exe`/Tauri deixou de ser o plano principal — Render (ou outro servidor) é o caminho agora. Pendente pra próxima sessão: Pendências Sprint 2 (regra automática de UC sem usina).

- 2026-08-09: **Fase 1 de Segurança** — cookie `HttpOnly` substituindo o token no `sessionStorage` (vulnerável a roubo via XSS). Descoberta importante no caminho: `onrender.com` está na Public Suffix List, então backend e frontend em subdomínios diferentes do Render contam como **sites diferentes** pro navegador — `SameSite=Lax` (pedido original) só funciona de verdade com uma regra de rewrite no Render fazendo o frontend "espelhar" `/api/*` pro backend, deixando os dois same-origin do ponto de vista do navegador. Implementado junto: proteção CSRF (cookie duplo, `hub_csrf` legível por JS + header `X-CSRF-Token`, só exigido quando a autenticação veio de cookie — não quando vem de `Bearer` no header, usado em teste manual via curl/Invoke-RestMethod), headers de segurança (`HSTS`, `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`), rate limit no login (`flask-limiter`, 5/min por IP, `storage_uri='memory://'` — funciona certo com 1 worker, fica "por processo" se aumentar workers no futuro), e sistema de papéis (`admin`/`viewer`), com o `viewer` sendo barrado globalmente no middleware pra qualquer método que não seja leitura, sem precisar de trava por rota. Adicionado também: tela **Configurações → Usuários** (admin cria/ativa/desativa conta, com trava contra auto-desativação) e auto-cadastro público na tela de login, protegido por `SIGNUP_CODE` (variável de ambiente — vazio desliga a funcionalidade por padrão; auto-cadastro força `papel='viewer'` no backend, nunca aceita `admin` vindo do formulário, mesmo se alguém tentar forjar isso na requisição). HTTPS obrigatório não precisou de código — confirmado que o Render já redireciona HTTP→HTTPS na borda antes de chegar na aplicação.
- **Nota de processo:** essa sessão teve um caso real de arquivo trocado no copy-paste manual (`auth_routes.py` e `oauth_routes.py` colados um no lugar do outro), que derrubou o backend local com um erro difícil de diagnosticar à distância (processo morrendo em silêncio, sem log). Resolvido isolando camada por camada (`python -c "print(...)"` → `app.py` direto → `Get-Content` de cada arquivo suspeito). Fica registrado como lembrete: ao aplicar múltiplos arquivos inteiros na mesma sessão, conferir o nome do Blueprint (`grep`/`Select-String` por `= Blueprint(`) antes de rodar, não só depois que já quebrou.

- 2026-08-11: sessão de polimento visual e telas — **design tokens de padronização** adicionados (`--radius-input/button/card/modal`, `--shadow-sm/md/lg`, `--space-1..5`, `--control-height`, `--icon-size`), aplicados em botões, inputs, modais, cards/painéis, tabelas e sidebar (reduzida ~25%, com breakpoints de resolução em 1366/1024/780px e rolagem interna própria no menu — corrigido bug real de sobreposição do rodapé em telas mais baixas). Campo `data_nascimento` em Cliente confirmado e documentado (ver acima). **Bug real encontrado e corrigido:** `pendencias.css` nunca estava importado em `app.css` — o painel lateral de detalhe de Pendências (sticky, grid de 2 colunas) nunca tinha efeito nenhum, apesar do CSS já existir e estar correto; adicionado o `@import` faltante. Junto: painel de detalhe ganhou seção "Detalhes" lendo `Pendencia.metadados` (JSON livre) de forma genérica, pronta pra quando a Sprint 2 (alerta/erro automático) começar a preencher esse campo. **Tela de login redesenhada** (`LoginPage.ts`/`login.css`): split-screen com ilustração de rede conectada (usina/painel solar/prédio/casas em SVG de traço fino — não é a arte 3D isométrica do mockup original, isso é trabalho de design/render, não reproduzível via CSS/SVG à mão), campos com ícone, mostrar/ocultar senha, alternância entre login e cadastro por código de convite (mantido, não removido), rodapé com ping real no health check (`GET /`) e versão. Adicionado o checkbox **"Lembrar meu acesso"**: como a autenticação já usa cookie `HttpOnly` (não há mais `token` manipulável via JS), a decisão de persistência não pode ser feita no frontend — `POST /auth/login` ganhou o campo opcional `lembrar` (bool, default `false`) e `set_auth_cookies()` em `utils/auth.py` passou a aceitar `remember: bool`, omitindo `max_age` quando `False` (cookie de sessão nativo, some ao fechar o navegador) e usando `TOKEN_MAX_AGE_SECONDS` (7 dias) quando `True`.

Pendente de teste/validação antes de marcar `[x]`: sprint desta mesma sessão simplificando Configurações → Banco de Dados (só OAuth) e movendo Usuários pra página própria na sidebar (ver instruções abaixo) — aplicar, testar e só então atualizar este arquivo, seguindo a regra de sempre (`VISAO.md` seção 6, item 5: não marcar concluído sem validar).

- 2026-08-13: **Sprint 2 de Pendências — Automação Implementada**. Motor de automação completo (`automacao_service.py`) seguindo as regras de `PENDENCIAS.md`:
  - **UC sem usina**: Verifica UC sem conexão há 7+ dias, cria alerta `tipo='alerta'` com metadados (dias sem usina, data de criação). Não duplica se já existir pendência aberta.
  - **Cliente sem UC**: Cria pendência quando cliente não tem UC vinculada.
  - **Campos obrigatórios**: Verifica nome, CPF, email, telefone, data de nascimento. Cria pendência listando campos faltando.
  - **Documentos obrigatórios**: Verifica documento de identidade, fatura, termo de adesão. Cria pendência listando documentos faltando.
  - **Resolução automática**: Quando UC ganha usina, campos são preenchidos ou UC é adicionada, as pendências correspondentes são resolvidas automaticamente.
  - **Novas rotas**: `POST /pendencias/verificar` (executa todas as regras) e `GET /pendencias/regras` (lista de regras disponíveis).
  - **Frontend**: Verificação automática ao abrir a tela de Pendências (em background), botão "Verificar agora" na toolbar com feedback visual. Ícone `refresh` adicionado ao sistema de ícones.
  - **Polimento visual**: Reforma completa do frontend (tokens, botões, layout responsivo, tables, modais, login, agenda, pendências).

- 2026-08-29: **Formulário Copel de Rateio implementado (4 sprints)**. Descoberta importante no meio do caminho: o PDF oficial da Copel (anexado pelo João) **não tem linha de tabela pra UC geradora** — são 2 campos de texto separados no topo da página 1 ("UC geradora nº" e "UC beneficiária âncora nº"), diferente do que a Sprint 2 tinha presumido a partir só do CSV. Corrigido antes do overlay: `montar_tabela_formulario` passou a expor `ucGeradora`/`ucAncora` como campos de topo (ambos = `Plant.uc`, decisão confirmada com o João: a âncora é sempre a própria usina) e a tabela ficou só com as 24 linhas de beneficiárias. Confirmado também que o bloco "NÃO" (classificação de excedente) é texto fixo do template, não checkbox — nenhuma ação necessária ali. Coordenadas de overlay calibradas via `pdfplumber` (extração de posição de palavras/linhas/retângulos) direto no PDF oficial, não chutadas. Template fica versionado em `backend/assets/formulario_copel_associacao.pdf` (não é segredo, entra no Git normalmente).
- [x] UI-1 — Design System e acessibilidade — 2026-09-29. Tokens semânticos completados para superfície elevada, texto secundário, informação, foco, disabled e backdrop, preservando aliases existentes e os temas claro/escuro. Componentes reutilizáveis adicionados para `StatusBadge` com texto+ícone, estados distintos de vazio/filtro/erro, skeletons de lista/tabela, tooltip, modal com foco/Escape e drawer com foco/Escape; toast agora tem contexto semântico e ARIA. Clientes, Usinas, UCs, Faturas e Pendências usam o estado padronizado de tabela, e badges foram consolidados nas telas aplicáveis. Nenhum endpoint, contrato REST, RBAC, tenancy, dependência ou persistência foi alterado. Validação: `npm --prefix frontend run build` OK (TypeScript + Vite, 321 módulos); `git diff --check` dos arquivos da entrega OK. `npm --prefix frontend run lint` executado, mas permanece vermelho por 4 erros preexistentes nas alterações concorrentes (`Loading.ts`: 3 logs diretos; `FaturasPage.ts`: limite de 350 linhas), além dos warnings históricos. Inspeção estática confirmou ausência de cores literais nos CSS específicos de Clientes, Usinas, Faturas e Pendências; validação visual em navegador não pôde ser automatizada porque o portal Maestri/CLI não está disponível neste ambiente.
- [x] UI-2 — Navegação, sidebar e padrão de página — 2026-09-29. `BaseLayout` agora oferece sidebar expandida/recolhida em desktop, com preferência exclusivamente visual em `localStorage`, controle por teclado, foco visível, `aria-controls`/`aria-expanded` e identificação dos itens compactos por tooltip nativo e `aria-label`. A navegação foi consolidada em Operação, Financeiro e Gestão, sem os destinos futuros desabilitados e preservando rotas, destaque ativo e a visibilidade de Empresas exclusiva do administrador de plataforma. Clientes, Usinas, UCs, Faturas e Pendências passaram a compartilhar a hierarquia título, contexto, ações, filtros, resumo e conteýo sem remover funções. Em 1024px, a sidebar permanece na grade com 180px quando expandida e 64px quando recolhida; o menu sobreposto continua restrito a até 768px. Validação: `npm --prefix frontend run build` OK (TypeScript + Vite, 321 módulos); `git diff --check` dos arquivos da UI-2 OK; revisão estática independente confirmou responsividade estrutural, rotas e acessibilidade. O `git diff --check` global segue vermelho apenas por whitespace/CRLF em `DEPLOY.md`, alteração concorrente fora da UI-2; validação visual real em navegador não esteve disponível neste ambiente.

- [x] UI-3 — Busca instantânea, filtros e URL state — 2026-09-29. Criado o padrão reutilizável de estado de listagem para serializar busca, filtros, página e seleção na URL, com busca debounced em 300 ms. Clientes, Usinas, UCs e Pendências usam filtro/paginação local por preservarem os contratos de listagem completos; Faturas preserva a paginação e os filtros remotos já suportados, com contador de requisição contra respostas obsoletas. A seleção de detalhe permanece recuperável no link e o fechamento mantém os filtros e a página. Nenhum endpoint, contrato REST, RBAC, tenancy, dependência ou persistência foi alterado. Validação: `npm --prefix frontend run build` OK (TypeScript + Vite, 322 módulos). `git diff --check` foi executado; os únicos apontamentos são whitespace/CRLF preexistentes em `DEPLOY.md`, alteração concorrente fora desta entrega.
- [x] UI-4 — Faturas: master/detail e histórico auditável — 2026-09-29. O detalhe de Faturas passou do modal para o drawer responsivo compartilhado, com foco confinado, Escape, retorno de foco à linha e abertura de linhas por Enter/Espaço. A seleção continua em `selecionada` sem remover busca, filtros ou página; o contexto Cliente › UC › Usina navega apenas por IDs e rotas já existentes. A timeline usa o recebimento e os estados persistidos da fatura e consulta `GET /billing-calculations?invoiceId=` seguido dos detalhes auditáveis das execuções, tanto na rota tenant quanto na rota administrativa da empresa explicitamente selecionada; ausência de execuções é comunicada e nenhum evento de pagamento/ASAAS é inferido. Avisos e ações existentes de cobrança e pendências foram preservados. Nenhum endpoint, contrato REST, RBAC, regra ASAAS, migration ou dependência foi alterado. Validação: `npm --prefix frontend run build` OK (TypeScript + Vite, 322 módulos); `git diff --check` dos arquivos da entrega OK.
- [x] UI-5 — Produtividade: Pendências, Dashboard, Quick Actions e Palette — 2026-09-29. Pendências abertas são ordenadas por status, prioridade e prazo, distinguem “precisa de ação”, “aguardando informação” e “informativa” por badge semântico, e o detalhe oferece somente navegação contextual para registros realmente vinculados ou explica objetivamente sua ausência. O dashboard continua consumindo exclusivamente `GET /dashboard/resumo`, usa skeleton e erro recuperável, omite integralmente métricas indisponíveis por permissão e removeu gráficos decorativos. `BaseLayout` ganhou ações rápidas e palette Ctrl/Cmd+K restrita a rotas existentes e ao papel atual, com filtro local apenas de ações, setas, Enter, Escape, foco confinado e restauração de foco; nenhuma busca global, endpoint, contrato, migration ou dependência foi criada. Validação: `npm --prefix frontend run build` OK (TypeScript + Vite, 323 módulos); `git diff --check` dos arquivos da entrega OK.

- [x] Taxonomia canônica da sidebar corrigida — 2026-09-29. A navegação agora apresenta Operação (Clientes, UCs, Usinas, Rateio e Documentos), Financeiro (Faturas e Regras de cobrança) e Gestão (Dashboard, Templates, Mensagens, Pendências, Agenda e Configurações), na ordem aprovada. Usuários foi preservado em Administração com a mesma visibilidade anterior; Empresas permanece nessa seção e visível somente ao administrador de plataforma. Nenhuma rota, contrato REST, RBAC, tenancy, persistência ou dependência foi modificada. Validação: revisão independente aprovada após a correção; `npm --prefix frontend run build` OK (TypeScript + Vite, 323 módulos); `git diff --check -- frontend/src/components/Sidebar.ts` OK.

- [x] Tamanho dos ícones da Command Palette corrigido — 2026-09-29. Os ícones de cada ação passaram a usar explicitamente o token visual do HUB `--icon-size` (18px). O seletor de tipografia foi restringido ao bloco de texto para não converter o contêiner SVG em grade e permitir seu crescimento. Nenhuma rota, contrato REST, RBAC, tenancy, persistência ou dependência foi modificada. Validação: `npm --prefix frontend run build` e `git diff --check -- frontend/src/styles/command-palette.css PROGRESS.md` executados nesta entrega.

- [x] Ações rápidas e tema ajustados — 2026-09-29. O ícone do gatilho da Command Palette agora também usa explicitamente `--icon-size` (18px). A palette continua navegando apenas por rotas existentes e autorizadas, mas passou a explicar seu uso e a disponibilizar atalhos visíveis `1–9` para os destinos, além de setas, Enter, Esc e Ctrl/Cmd+K; clique e Enter executam a mesma navegação. O alternador de tema foi removido de todos os cabeçalhos: Escuro, Claro e Sistema permanecem exclusivamente em Configurações → Aparência. Nenhuma rota, contrato REST, RBAC, tenancy, persistência ou dependência foi modificada. Validação: `npm --prefix frontend run build` OK (TypeScript + Vite, 323 módulos); `git diff --check` dos arquivos da entrega OK.
