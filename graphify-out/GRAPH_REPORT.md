# Graph Report - HUB  (2026-08-19)

## Corpus Check
- 172 files · ~70,247 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1124 nodes · 3213 edges · 73 communities (70 shown, 3 thin omitted)
- Extraction: 94% EXTRACTED · 6% INFERRED · 0% AMBIGUOUS · INFERRED: 189 edges (avg confidence: 0.93)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- Agenda And Pendencias
- Plants And Rateio
- Pendencias Domain
- Backend Extensions
- Google Accounts
- Empresa Routes
- Configuration Routes
- Reserved Panel
- Client Cards
- Settings Page
- Client Form Data
- Category Model
- Frontend Error Boundary
- UI Icon Factory
- Rateio Page
- Appearance Settings
- Backend Configuration
- API Client
- Category Picker
- Frontend TypeScript
- Automation Service
- Users Page
- Consumer Units Page
- API Contracts
- Startup Commands
- Clients Page
- Plants Page
- Frontend Package
- Invitation Model
- Rateio Workflow
- Backend Application
- Sidebar Navigation
- Frontend Bootstrap
- Authentication Routes
- Hub Versioning
- Empresa Model
- Settings Workflow
- Authentication Service
- Plant Distribution
- Database Configuration
- Migration Environment
- Log Entry Model
- Multi Tenant Architecture
- Health Routes
- Drive Item Model
- Graphify Instructions

## God Nodes (most connected - your core abstractions)
1. `createElement()` - 172 edges
2. `success_response()` - 83 edges
3. `error_response()` - 71 edges
4. `LogService` - 57 edges
5. `createIcon()` - 35 edges
6. `Config` - 33 edges
7. `createBaseLayout()` - 28 edges
8. `ConsumerUnit` - 26 edges
9. `createPlantsPage()` - 26 edges
10. `createRateioPage()` - 26 edges

## Surprising Connections (you probably didn't know these)
- `Intelligent Rateio Engine` --semantically_similar_to--> `Pendencia Automation Engine`  [INFERRED] [semantically similar]
  RATEIO.md → PENDENCIAS.md
- `REST API` --conceptually_related_to--> `Flask Backend Dependency`  [INFERRED]
  README.md → backend/requirements.txt
- `REST API` --conceptually_related_to--> `Frontend Application Shell`  [INFERRED]
  README.md → frontend/index.html
- `create_app()` --uses--> `Config`  [INFERRED]
  backend/app.py → backend/config.py
- `registro()` --uses--> `Config`  [INFERRED]
  backend/routes/empresa_routes.py → backend/config.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **HUB Operational Platform** — concept_rest_api, concept_pendencia_engine, concept_rateio_engine [INFERRED 0.75]
- **Tenant Data Isolation Flow** — concept_multi_tenancy, concept_tenant_mixin, concept_rest_api [EXTRACTED 1.00]

## Communities (73 total, 3 thin omitted)

### Community 0 - "Agenda And Pendencias"
Cohesion: 0.06
Nodes (72): createAgendaPage(), createDayPanel(), createMonthGrid(), createMonthHeader(), createWeekdaysRow(), groupByDate(), loadAll(), renderContent() (+64 more)

### Community 1 - "Plants And Rateio"
Cohesion: 0.07
Nodes (50): PlantConnection, Plant, Se producao_media_manual estiver preenchida, ela manda (caixinha única…, Retorna (percentual, e_manual). Se houver produção cadastrada, o percentual é…, RateioHistorico, destroy(), destroy_connection(), index() (+42 more)

### Community 2 - "Pendencias Domain"
Cohesion: 0.11
Nodes (37): Pendencia, PendenciaComentario, cancelar(), comentar(), destroy(), index(), listar_regras(), route (+29 more)

### Community 3 - "Backend Extensions"
Cohesion: 0.12
Nodes (37): Toda tabela que pertence a uma empresa herda daqui em vez de repetir a coluna…, TenantMixin, Client, ConsumerUnit, destroy(), index(), route, show() (+29 more)

### Community 4 - "Google Accounts"
Cohesion: 0.09
Nodes (34): GoogleAccount, Setting, accounts(), activate(), authorize(), callback(), destroy(), route (+26 more)

### Community 5 - "Empresa Routes"
Cohesion: 0.08
Nodes (39): get_by_slug(), index(), route, Lista empresas apenas para quem opera a plataforma., Fluxo de cadastro inicial: 1. Pessoa informa dados da empresa + seus dados 2.…, Busca empresa publica por slug., registro(), _require_platform_admin() (+31 more)

### Community 6 - "Configuration Routes"
Cohesion: 0.09
Nodes (32): database_config(), route, test_database(), update_google_drive(), update_provider(), update_sql(), download_zip(), route (+24 more)

### Community 7 - "Reserved Panel"
Cohesion: 0.12
Nodes (33): createReservedPanel(), render(), ReservedPanelOptions, createResultsPanel(), render(), setCount(), setLoading(), setMessage() (+25 more)

### Community 8 - "Client Cards"
Cohesion: 0.15
Nodes (29): ClientCardOptions, createClientCard(), createEmptyUc(), createUcEditor(), createUcPanel(), renderList(), createDetailHeader(), DetailHeaderOptions (+21 more)

### Community 9 - "Settings Page"
Cohesion: 0.09
Nodes (31): CATEGORIES, CategoryDefinition, categoryMessage(), createCategoryNav(), createComingSoonPanel(), createDatabasePanel(), createGeralPanel(), createGoogleAccountsSection() (+23 more)

### Community 10 - "Client Form Data"
Cohesion: 0.11
Nodes (27): ClientFormData, ClientDetailViewOptions, createClientDetailView(), createHeader(), createInfoField(), createInfoPanel(), createTabsPanel(), createUcSection() (+19 more)

### Community 11 - "Category Model"
Cohesion: 0.16
Nodes (24): Category, Document, index(), route, store(), destroy(), download(), index() (+16 more)

### Community 12 - "Frontend Error Boundary"
Cohesion: 0.12
Nodes (20): createErrorBoundary(), createHeader(), HeaderOptions, createLoading(), loadingState, setGlobalLoading(), createToastContainer(), showToast() (+12 more)

### Community 13 - "UI Icon Factory"
Cohesion: 0.18
Nodes (28): createIcon(), createIdNameCell(), createPlantsPage(), confirmDeletePlant(), confirmRemoveConnection(), connectedUcs(), createConnectedUcsActions(), createConnectedUcsTable() (+20 more)

### Community 14 - "Rateio Page"
Cohesion: 0.19
Nodes (24): createRateioPage(), connectedUcsCount(), createFunilStat(), createProducaoMediaHint(), createProducaoStat(), createReservaField(), loadAll(), loadPreview() (+16 more)

### Community 15 - "Appearance Settings"
Cohesion: 0.15
Nodes (22): createAppearancePanel(), previewColors(), createColorField(), readFileAsDataUrl(), renderLogoPreview(), adjustLightness(), hexToRgb(), hexToRgba() (+14 more)

### Community 16 - "Backend Configuration"
Cohesion: 0.15
Nodes (15): Config, _filtrar_por_empresa(), Impede que uma busca por PK ignore o escopo do tenant. ``Query.get()`` e…, TenantQuery, PasswordResetToken, _ensure_configured(), Retorna True se a tentativa de envio foi feita, False se RESEND_API_KEY nao…, send_email() (+7 more)

### Community 17 - "API Client"
Cohesion: 0.17
Nodes (19): apiBlob(), apiRequest(), apiUpload(), buildCsrfHeader(), buildJsonHeaders(), MUTATING_METHODS, readCsrfCookie(), readErrorMessage() (+11 more)

### Community 18 - "Category Picker"
Cohesion: 0.19
Nodes (18): createCategoryPicker(), renderOptions(), createClientDocumentsPanel(), loadDocuments(), renderDocuments(), createDocumentLinkModal(), DocumentLinkModalOptions, ApiResponse (+10 more)

### Community 19 - "Frontend TypeScript"
Cohesion: 0.10
Nodes (20): compilerOptions, allowImportingTsExtensions, isolatedModules, lib, module, moduleDetection, moduleResolution, noEmit (+12 more)

### Community 20 - "Automation Service"
Cohesion: 0.17
Nodes (19): _cliente_cadastro_completo(), _cliente_tem_documentos_obrigatorios(), criar_pendencia_alerta(), _ja_existe_pendencia_ativa(), Para cada cliente que não possui UC vinculada, cria uma pendência de alta…, Verifica campos obrigatórios faltando no cliente: Nome, CPF, Email, Telefone,…, Verifica se o cliente possui os documentos obrigatórios: Documento de…, Verifica se o cliente tem todos os campos obrigatórios preenchidos. (+11 more)

### Community 21 - "Users Page"
Cohesion: 0.21
Nodes (17): createUsersPage(), handleCreate(), handleDelete(), handleUpdate(), loadUsers(), renderContent(), createUsersTable(), getRoleBadgeClass() (+9 more)

### Community 22 - "Consumer Units Page"
Cohesion: 0.23
Nodes (17): createUcsPage(), confirmDeleteUc(), createUcDetailPanel(), loadAll(), openUcEditor(), renderContent(), saveUc(), formatUcDate() (+9 more)

### Community 23 - "API Contracts"
Cohesion: 0.14
Nodes (18): HUB API Contracts, HUB Architecture, Flask Backend Dependency, API Response Envelope, Document Categories, Google Drive Document Storage, Google OAuth 2.0 PKCE, Pendencia Automation Engine (+10 more)

### Community 24 - "Startup Commands"
Cohesion: 0.23
Nodes (13): _esperar_url(), iniciar(), _mostrar_ultimas_linhas(), Path, parar(), find_pids(), kill_tree(), port_in_use() (+5 more)

### Community 25 - "Clients Page"
Cohesion: 0.20
Nodes (17): createClientsPage(), createClientEditor(), handleDeleteFromDetail(), loadClients(), renderContent(), renderDetailView(), saveClient(), loadClients() (+9 more)

### Community 26 - "Plants Page"
Cohesion: 0.13
Nodes (17): savePlant(), createStatusBadge(), ApiResponse, createPlant(), deletePlant(), getAvailablePlants(), getPlants(), PlantPayload (+9 more)

### Community 27 - "Frontend Package"
Cohesion: 0.12
Nodes (16): dependencies, @sentry/browser, devDependencies, typescript, vite, name, private, scripts (+8 more)

### Community 28 - "Invitation Model"
Cohesion: 0.21
Nodes (12): Invitation, aceitar_convite(), _buscar_convite_valido(), criar_convite(), _gerar_token(), Retorna (convite.to_dict(), token_cru) -- o token cru so existe nesse retorno,…, Usado pela tela de aceite pra mostrar 'voce foi convidado pra <empresa> como…, verificar_convite() (+4 more)

### Community 29 - "Rateio Workflow"
Cohesion: 0.16
Nodes (13): defaultCompetencia(), RESERVA_PRESETS, Stage, ApiResponse, confirmarSelecaoRateio(), getQualificacao(), RateioConfirmacaoResultado, RateioDistribuicaoConexao (+5 more)

### Community 30 - "Backend Application"
Cohesion: 0.23
Nodes (11): create_app(), User, fetch_sqlite_rows(), main(), Script PONTUAL -- roda uma vez, migrando os dados reais do SQLite local…, Depois de inserir com id explicito, a sequence do Postgres nao sabe que avancou…, reset_sequence(), main() (+3 more)

### Community 31 - "Sidebar Navigation"
Cohesion: 0.25
Nodes (13): createLogoutButton(), createSidebar(), createSidebarLink(), createUserCard(), createVersionTag(), initialsFor(), refreshSidebarBrand(), roleLabel() (+5 more)

### Community 32 - "Frontend Bootstrap"
Cohesion: 0.21
Nodes (11): app, router, ensureSession(), isAuthenticated(), config, createRouter(), ensureAppearanceLoaded(), redirect() (+3 more)

### Community 33 - "Authentication Routes"
Cohesion: 0.32
Nodes (12): aceitar_convite_route(), bootstrap(), esqueci_senha(), login(), logout(), me(), route, redefinir_senha_route() (+4 more)

### Community 34 - "Hub Versioning"
Cohesion: 0.32
Nodes (12): HUB_VERSION, createLoginField(), createLoginIllustration(), createLoginPage(), createLoginView(), createRegisterView(), render(), switchTo() (+4 more)

### Community 35 - "Empresa Model"
Cohesion: 0.27
Nodes (7): Empresa, main(), Cria uma empresa (tenant) nova + um convite pro primeiro owner definir a…, criar_empresa_com_owner(), gerar_slug(), Gera um slug simples a partir do nome da empresa., Cria Empresa + Owner na mesma transacao. Args: data: { 'empresa': { 'nome': str…

### Community 36 - "Settings Workflow"
Cohesion: 0.42
Nodes (11): createSettingsPage(), changeCategory(), handleActivateAccount(), handleDisconnectAccount(), handleSaveRateioConfig(), loadGoogleAccounts(), loadRateioConfig(), loadRecentLogs() (+3 more)

### Community 37 - "Authentication Service"
Cohesion: 0.36
Nodes (8): authenticate(), decode_token(), generate_token(), _get_serializer(), Mesma checagem de token de _require_auth, mas sem forçar 401 se não autenticado…, resolve_current_user_optional(), verify_password(), URLSafeTimedSerializer

### Community 38 - "Plant Distribution"
Cohesion: 0.31
Nodes (9): createPlantDistribuicaoModal(), loadSuggestionsAndRender(), renderBody(), recalcTotal(), formatNumber(), PlantDistribuicaoModalOptions, PlantDistribuicaoModalUc, atualizarDistribuicao() (+1 more)

### Community 39 - "Database Configuration"
Cohesion: 0.22
Nodes (3): ApiResponse, DatabaseConfig, DatabaseProvider

### Community 40 - "Migration Environment"
Cohesion: 0.39
Nodes (7): get_engine(), get_engine_url(), get_metadata(), Run migrations in 'offline' mode. This configures the context with just a URL…, Run migrations in 'online' mode. In this scenario we need to create an Engine…, run_migrations_offline(), run_migrations_online()

### Community 41 - "Log Entry Model"
Cohesion: 0.29
Nodes (3): LogEntry, index(), route

### Community 42 - "Multi Tenant Architecture"
Cohesion: 0.67
Nodes (4): Multi-Tenant HUB, TenantMixin Automatic Isolation, Sprint 01 Tenant Identity, Sprint 02 Multi-Tenant and Google OAuth

## Knowledge Gaps
- **116 isolated node(s):** `DriveItem`, `name`, `private`, `version`, `type` (+111 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `createElement()` connect `Client Cards` to `Agenda And Pendencias`, `Hub Versioning`, `Settings Workflow`, `Plant Distribution`, `Reserved Panel`, `Settings Page`, `Client Form Data`, `Frontend Error Boundary`, `UI Icon Factory`, `Rateio Page`, `Appearance Settings`, `Category Picker`, `Users Page`, `Consumer Units Page`, `Clients Page`, `Plants Page`, `Rateio Workflow`, `Sidebar Navigation`?**
  _High betweenness centrality (0.102) - this node is a cross-community bridge._
- **Why does `success_response()` connect `Category Model` to `Authentication Routes`, `Pendencias Domain`, `Backend Extensions`, `Google Accounts`, `Empresa Routes`, `Configuration Routes`, `Plants And Rateio`, `Log Entry Model`?**
  _High betweenness centrality (0.029) - this node is a cross-community bridge._
- **Why does `error_response()` connect `Empresa Routes` to `Authentication Routes`, `Pendencias Domain`, `Backend Extensions`, `Google Accounts`, `Plants And Rateio`, `Configuration Routes`, `Authentication Service`, `Category Model`, `Backend Application`?**
  _High betweenness centrality (0.027) - this node is a cross-community bridge._
- **Are the 36 inferred relationships involving `LogService` (e.g. with `index()` and `callback()`) actually correct?**
  _`LogService` has 36 INFERRED edges - model-reasoned connections that need verification._
- **What connects `DriveItem`, `name`, `private` to the rest of the system?**
  _116 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Agenda And Pendencias` be split into smaller, more focused modules?**
  _Cohesion score 0.062342342342342344 - nodes in this community are weakly interconnected._
- **Should `Plants And Rateio` be split into smaller, more focused modules?**
  _Cohesion score 0.07270865335381464 - nodes in this community are weakly interconnected._