# APP HUB — Progresso

> Leia `VISAO.md` primeiro. Este arquivo é o estado atual, atualizado a cada tarefa concluída.
> Regra: pegue a primeira tarefa `[ ]` de cima pra baixo. Não pule.

Última atualização: (o Codex atualiza esta linha a cada sessão) — ainda não iniciado após a criação deste documento.

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
- [ ] Confirmar se os arquivos deste Project (Claude) foram corrigidos/ressincronizados com o repositório real antes de qualquer sessão do Codex usar esses arquivos como referência.

### Banco de dados local
- [x] `backend/models/drive_item.py` já existe (dataclass `DriveItem`) — manter, é modelo de apoio pro Drive, não é entidade de banco.
- [ ] Escolher ORM (sugestão: SQLAlchemy) e ferramenta de migration (sugestão: Alembic ou Flask-Migrate).
- [ ] Modelo Cliente.
- [ ] Modelo UC (FK para Cliente, FK opcional para Usina).
- [ ] Modelo Usina.
- [ ] Modelo Documento (FK para UC, FK para Categoria).
- [ ] Modelo Categoria.
- [ ] Modelo Configuração.
- [ ] Modelo GoogleAccount.
- [ ] Modelo Log.
- [ ] Migration inicial rodando limpa em banco vazio.

### CRUD Cliente / UC / Usina (ligar ao banco, hoje está em memória/localStorage no front)
- [ ] API de Cliente (GET/POST/PUT/DELETE) usando o banco novo.
- [ ] API de UC, com vínculo a Cliente e Usina.
- [ ] API de Usina.
- [ ] Frontend de Clientes consumindo a API nova (hoje usa `localStorage` com a chave `hub.operations.v1` — não remover a tela/fluxo, só trocar a fonte de dados).
- [ ] Frontend de Usinas consumindo a API nova.
- [ ] Migrar dados de exemplo/mock existentes, se fizer sentido, ou começar limpo (decidir com o usuário).

### Google Drive OAuth
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

- —
