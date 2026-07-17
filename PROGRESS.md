# APP HUB — Progresso

> Leia `VISAO.md` primeiro. Este arquivo é o estado atual, atualizado a cada tarefa concluída.
> Regra: pegue a primeira tarefa `[ ]` de cima pra baixo. Não pule.

Última atualização: 2026-07-08 — modelos do núcleo e migration inicial concluídos.

---

## Decisões em aberto (resolver antes de travar arquitetura)

- [ ] **Modo de uso do app:** local/single-user (SQLite) ou multi-máquina (servidor)? — *default atual: local/SQLite, conforme `VISAO.md` seção 2.*
- [ ] **Empacotador desktop:** Tauri ou Electron? — *default atual: Tauri.*
- [x] ~~Reconciliar numeração de versão~~ — resolvido: mantém `V0.x` (fase atual, instável) até o núcleo funcional abaixo estar completo e estável, aí vira `V1.0` de verdade. Marcos seguintes mantêm `V1.5, V2.0, V3.0, V4.0, V5.0`.

---

## V0.x → V1.0 — Núcleo funcional

### Estrutura de pastas
- [x] Confirmado direto no repositório real (prints de 12h atrás) — a estrutura bate com a seção 4 de `VISAO.md`, mais madura do que o inicialmente assumido:
  - `backend/`: `database/`, `models/` (com `drive_item.py`), `routes/` (`config_routes`, `drive_routes`, `health_routes`), `services/` (`database_config_service`, `drive_service`), `utils/` (`api_response.py`, `files.py`), `app.py`, `config.py`, `requirements.txt`.
  - `frontend/src/`: `components/` (Client Card, DashboardCards, DataTable, ErrorBoundary, Header, Loading, PlantCard, ReservedPanel, ResultsList, SearchPanel, Sidebar, Toast), `hooks/` (useGlobalLoading, useToast), `layouts/` (BaseLayout), `pages/` (Agenda, Clients, Documents, Placeholder, Plants, Settings), `services/` (**apiClient.ts, router.ts, documentRules.ts** já existem — mais completo do que eu esperava), `styles/` (app.css).
- [x] `backend/models/` e `backend/database/` já existem — **não recriar**, só completar o que falta dentro deles (ver abaixo).
- [x] Confirmar se os arquivos deste Project (Claude) foram corrigidos/ressincronizados com o repositório real antes de qualquer sessão do Codex usar esses arquivos como referência.
  - Critério de pronto: arquivos centrais abertos direto no repositório real (`backend/app.py`, `frontend/package.json`, `backend/requirements.txt`, `README.md`) e confirmados como coerentes com suas funções.
  - Feito: `HUB-main.zip` foi extraído em `C:\Users\deadj\Documents\HUB\HUB-main`; a estrutura e os arquivos centrais batem com a arquitetura esperada, sem troca evidente de conteúdo.

### Banco de dados local
- [x] `backend/models/drive_item.py` já existe (dataclass `DriveItem`) — manter, é modelo de apoio pro Drive, não é entidade de banco.
- [x] Escolher ORM (sugestão: SQLAlchemy) e ferramenta de migration (sugestão: Alembic ou Flask-Migrate).
  - Critério de pronto: dependências declaradas, configuração `DATABASE_URL` com fallback SQLite local, extensões inicializadas no Flask e importação do app validada sem erro de sintaxe.
  - Feito: escolhido SQLAlchemy com Flask-Migrate/Alembic; `backend/app.py` inicializa `db`/`migrate`, `backend/config.py` define `SQLALCHEMY_DATABASE_URI` via `DATABASE_URL` com fallback SQLite local, e `requirements.txt` declara as dependências.
  - Validação: `.\venv\Scripts\python.exe -m py_compile app.py config.py database\__init__.py services\drive_service.py routes\drive_routes.py` e `.\venv\Scripts\python.exe -c "from app import app; print(app.url_map)"` passaram.
- [x] Modelo Cliente.
  - Critério de pronto: modelo SQLAlchemy criado em `backend/models/`, exportado por `backend/models/__init__.py`, com campos usados hoje pela tela de Clientes e validação de importação do app passando.
  - Feito: criado `backend/models/client.py` com tabela `clients`, campos principais usados pela tela atual (`nome`, CPF/CNPJ, email, concessionária, status, UC/usina/consumo resumidos) e timestamps.
  - Validação: `db.metadata.tables` lista `clients` e `db.create_all()` executou sem erro em SQLite local.
- [x] Modelo UC (FK para Cliente, FK opcional para Usina).
  - Critério de pronto: modelo SQLAlchemy criado com FK obrigatória para Cliente, FK opcional para Usina, campos atuais de UC e relacionamento de conexões/rateio preservado para expansão.
  - Feito: criado `ConsumerUnit` com FK para `clients`, FK opcional para `plants`, campos atuais da tela e tabela auxiliar `plant_connections` para conexão UC↔Usina com percentual.
- [x] Modelo Usina.
  - Critério de pronto: modelo SQLAlchemy criado com campos usados hoje pela tela de Usinas e relacionamento reverso com UCs.
  - Feito: criado `Plant` com nome, UC, kW pico, geração média, status e percentual disponível.
- [x] Modelo Documento (FK para UC, FK para Categoria).
  - Critério de pronto: modelo SQLAlchemy criado com vínculo opcional a Cliente, FK opcional a UC e FK obrigatória a Categoria.
  - Feito: criado `Document` com vínculo opcional a Cliente/UC, FK obrigatória a Categoria e referência de armazenamento.
- [x] Modelo Categoria.
  - Critério de pronto: modelo SQLAlchemy criado para classificar documentos, com nome único e tipo/descrição opcionais.
  - Feito: criado `Category` com nome único, tipo e descrição.
- [x] Modelo Configuração.
  - Critério de pronto: modelo SQLAlchemy chave/valor criado para configurações persistidas no banco.
  - Feito: criado `Setting` chave/valor.
- [x] Modelo GoogleAccount.
  - Critério de pronto: modelo SQLAlchemy criado para múltiplas contas Google OAuth, sem hardcode de credenciais.
  - Feito: criado `GoogleAccount` para OAuth com refresh token criptografado/serializado em campo dedicado, escopos e conta ativa.
- [x] Modelo Log.
  - Critério de pronto: modelo SQLAlchemy criado para registrar ações, entidade afetada e metadados.
  - Feito: criado `LogEntry` com ação, entidade, mensagem e metadados.
- [x] Migration inicial rodando limpa em banco vazio.
  - Critério de pronto: migration inicial Alembic/Flask-Migrate criada e aplicada em SQLite vazio, gerando todas as tabelas do núcleo.
  - Validação: `flask --app app db migrate -m "initial core schema"` gerou `backend/migrations/versions/652c22edc58c_initial_core_schema.py`; `flask --app app db upgrade` aplicado em SQLite vazio gerou `alembic_version`, `categories`, `clients`, `consumer_units`, `documents`, `google_accounts`, `logs`, `plant_connections`, `plants`, `settings`.

### CRUD Cliente / UC / Usina (ligar ao banco, hoje está em memória/localStorage no front)
- [x] API de Cliente (GET/POST/PUT/DELETE) usando o banco novo.
  - Feito: `backend/routes/client_routes.py` completo e registrado em `app.py`; `client_service.py` trata CPF duplicado (409) e diferencia UC nova (UUID) de UC existente (id numérico).
  - Pendente dentro do mesmo módulo: `_sync_connections` ainda vincula UC↔Usina por nome da usina (string), não por `plant_id`. Precisa trocar para lookup por id antes de expor isso pro frontend real, senão renomear uma usina quebra vínculos existentes silenciosamente.
- [ ] API de UC dedicada (GET/PUT/DELETE por UC, fora do payload aninhado de Cliente).
- [ ] API de Usina (GET/POST/PUT/DELETE) — ainda não existe `plant_routes.py` nem blueprint registrado.
- [ ] Frontend de Clientes consumindo a API nova (hoje usa `localStorage` com a chave `hub.operations.v1` — não remover a tela/fluxo, só trocar a fonte de dados).
- [ ] Frontend de Usinas consumindo a API nova.
- [ ] Migrar dados de exemplo/mock existentes, se fizer sentido, ou começar limpo (decidir com o usuário).

### Google Drive OAuth
- [ ] `drive_service.py` ainda inicializa o cliente Google na importação do módulo (`drive_service = GoogleDriveService()` no fim do arquivo). Como `drive_routes` é sempre registrado em `app.py`, isso derruba o Flask inteiro se `credentials.json` não existir — não é isolado à rota do Drive. Fix de lazy-init (mover a criação do client pra dentro de cada método, com erro tratado) já foi desenhado antes e precisa ser aplicado.
- [ ] Fluxo OAuth 2.0 (login interativo, autorizar, salvar refresh token).
- [ ] Refresh token salvo de forma segura no banco (não em texto puro sem proteção).
- [ ] Suporte a mais de uma conta Google conectada.
- [ ] Tela de gerenciamento de contas (trocar conta ativa).
- [ ] Fluxo antigo baseado em `credentials.json` continua funcionando até o OAuth estar validado — só remover depois de confirmado.

### Documentos
- [ ] Módulo de Documentos ligado ao banco (Categoria, vínculo a UC/Cliente).
- [ ] Upload, busca, filtro, download — mantendo a experiência de busca/reserva/ZIP que já existe hoje no Drive.

### Configurações
- [x] Aba Banco de dados (Google Drive + SQL futuro) já existe.
- [x] Aba Aparência (cor + logo) já existe.
- [ ] Ajustar aba Banco de dados pra refletir SQLite local em vez de "SQL futuro" genérico, se a decisão em aberto acima for confirmada.

---

## Transversal — Empacotamento (.exe)

- [ ] Backend empacotado com PyInstaller, testado como `.exe` isolado fora do ambiente de dev.
- [ ] Projeto Tauri (ou Electron, conforme decisão em aberto) criado em `desktop/`.
- [ ] App desktop sobe o `.exe` do backend como subprocesso automaticamente.
- [ ] Instalador `.msi`/`.exe` gerado.
- [ ] Testado numa máquina limpa, sem Python/Node instalado.

---

## V1.5 — Refinamento operacional
- [ ] Pendências.
- [ ] Dashboard inteligente com métricas reais.
- [ ] Agenda operacional funcional (hoje é grade estática com 3 itens de exemplo).

## V2.0 — Cobrança
- [ ] Integração ASAAS.
- [ ] WhatsApp.
- [ ] Cobranças automáticas.

## V3.0 — Financeiro / Rateios
- [ ] Importação de fatura/planilha.
- [ ] Cálculo automático de rateio.
- [ ] Relatórios + exportação Excel/PDF.
- [ ] Histórico de competências.

## V4.0 — Monitoramento
- [ ] Integração com APIs de inversores.
- [ ] Alertas automáticos.

## V5.0 — Automação
- [ ] Motor de automações.
- [ ] Portal do cliente.

---

## Log de decisões tomadas durante o desenvolvimento
(o Codex adiciona uma linha aqui sempre que resolver uma ambiguidade sozinho, pra você poder revisar depois)

- 2026-07-08: enquanto o usuário não responder sobre single-user vs multi-máquina, mantido o default da visão: SQLite local.
- 2026-07-08: escolhido SQLAlchemy + Flask-Migrate/Alembic para banco local e migrations.
- 2026-07-08: `drive_service` passou a inicializar o cliente Google Drive sob demanda para permitir que o app Flask suba sem `credentials.json`; rotas do Drive retornam erro claro se a credencial faltar.
- 2026-07-08: o modelo `Client` usa nomes internos em inglês e `to_dict()` compatível com os nomes atuais do frontend em português para facilitar a troca futura de `localStorage` por API.
- 2026-07-08: criada tabela `plant_connections` além das entidades listadas para preservar o comportamento atual de uma UC conectada a múltiplas usinas com percentuais.
- 2026-07-17: revisão de código confirmou API de Cliente completa e registrada (estava marcada como pendente). Confirmado que Bug 4 (`_sync_connections` por nome de usina) e o eager-init do `drive_service.py` continuam sem correção aplicada — próximas tarefas prioritárias antes de ligar o frontend na API real.