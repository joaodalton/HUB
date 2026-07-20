APP HUB — Progresso

Leia VISAO.md primeiro. Este arquivo é o estado atual, atualizado a cada tarefa concluída. Regra: pegue a primeira tarefa [ ] de cima pra baixo. Não pule.

Última atualização: 2026-07-12 — revisão arquitetural (Claude): bug crítico de schema encontrado, padrão de documentação de API definido, itens de estabilidade do .exe listados.

🔴 Bloqueador — resolver antes de qualquer tarefa de CRUD

Encontrado na revisão de 2026-07-12, comparando os arquivos reais entre si (não confie nisso sem checar no repositório de verdade):

A migration que existe de fato (backend/migrations/versions/45f056e2a73d_initial_core_schema.py) só cria clients, plants, consumer_units, plant_connections.
O checklist de "Banco de dados local" abaixo registra que uma migration 652c22edc58c gerou também categories, documents, google_accounts, logs, settings — arquivo que não apareceu em nenhuma revisão de código feita até agora.
backend/app.py só importa Client, Plant, ConsumerUnit, PlantConnection dentro de create_app(). Nenhuma importação de Category/Document/Setting/GoogleAccount/LogEntry.
Conclusão possível: os models de Categoria, Documento, Configuração, GoogleAccount e Log foram marcados como [x] concluídos no checklist, mas nunca foram criados de fato — ou foram criados e nunca importados em app.py, então o flask db migrate nunca os viu.

Antes de começar a API de Cliente/UC/Usina:

 Confirmar diretamente no repositório real se backend/models/category.py, document.py, setting.py, google_account.py, log_entry.py existem.
 Se existirem: importar em create_app() junto dos outros models e rodar flask db migrate de novo pra pegar o que ficou de fora.
 Se não existirem: recriar (o VISAO.md já define o formato esperado pra cada um) e então migrar.
 Depois de corrigido, atualizar os checkboxes de "Banco de dados local" abaixo pra refletir o estado real — hoje eles dizem "Feito" pra coisa que aparentemente não está.
Decisões em aberto (resolver antes de travar arquitetura)
 Modo de uso do app: local/single-user (SQLite) ou multi-máquina (servidor)? — default atual: local/SQLite, conforme VISAO.md seção 2.
 Empacotador desktop: Tauri ou Electron? — default atual: Tauri.
 Reconciliar numeração de versão — resolvido: mantém V0.x (fase atual, instável) até o núcleo funcional abaixo estar completo e estável, aí vira V1.0 de verdade. Marcos seguintes mantêm V1.5, V2.0, V3.0, V4.0, V5.0.
V0.x → V1.0 — Núcleo funcional
Estrutura de pastas
 Confirmado direto no repositório real (prints de 12h atrás) — a estrutura bate com a seção 4 de VISAO.md, mais madura do que o inicialmente assumido:
backend/: database/, models/ (com drive_item.py), routes/ (config_routes, drive_routes, health_routes), services/ (database_config_service, drive_service), utils/ (api_response.py, files.py), app.py, config.py, requirements.txt.
frontend/src/: components/ (Client Card, DashboardCards, DataTable, ErrorBoundary, Header, Loading, PlantCard, ReservedPanel, ResultsList, SearchPanel, Sidebar, Toast), hooks/ (useGlobalLoading, useToast), layouts/ (BaseLayout), pages/ (Agenda, Clients, Documents, Placeholder, Plants, Settings), services/ (apiClient.ts, router.ts, documentRules.ts já existem — mais completo do que eu esperava), styles/ (app.css).
 backend/models/ e backend/database/ já existem — não recriar, só completar o que falta dentro deles (ver abaixo).
 Confirmar se os arquivos deste Project (Claude) foram corrigidos/ressincronizados com o repositório real antes de qualquer sessão do Codex usar esses arquivos como referência.
Critério de pronto: arquivos centrais abertos direto no repositório real (backend/app.py, frontend/package.json, backend/requirements.txt, README.md) e confirmados como coerentes com suas funções.
Feito: HUB-main.zip foi extraído em C:\Users\deadj\Documents\HUB\HUB-main; a estrutura e os arquivos centrais batem com a arquitetura esperada, sem troca evidente de conteúdo.
Banco de dados local
 backend/models/drive_item.py já existe (dataclass DriveItem) — manter, é modelo de apoio pro Drive, não é entidade de banco.
 Escolher ORM (sugestão: SQLAlchemy) e ferramenta de migration (sugestão: Alembic ou Flask-Migrate).
Critério de pronto: dependências declaradas, configuração DATABASE_URL com fallback SQLite local, extensões inicializadas no Flask e importação do app validada sem erro de sintaxe.
Feito: escolhido SQLAlchemy com Flask-Migrate/Alembic; backend/app.py inicializa db/migrate, backend/config.py define SQLALCHEMY_DATABASE_URI via DATABASE_URL com fallback SQLite local, e requirements.txt declara as dependências.
Validação: .\venv\Scripts\python.exe -m py_compile app.py config.py database\__init__.py services\drive_service.py routes\drive_routes.py e .\venv\Scripts\python.exe -c "from app import app; print(app.url_map)" passaram.
 Modelo Cliente.
Critério de pronto: modelo SQLAlchemy criado em backend/models/, exportado por backend/models/__init__.py, com campos usados hoje pela tela de Clientes e validação de importação do app passando.
Feito: criado backend/models/client.py com tabela clients, campos principais usados pela tela atual (nome, CPF/CNPJ, email, concessionária, status, UC/usina/consumo resumidos) e timestamps.
Validação: db.metadata.tables lista clients e db.create_all() executou sem erro em SQLite local.
 Modelo UC (FK para Cliente, FK opcional para Usina).
Critério de pronto: modelo SQLAlchemy criado com FK obrigatória para Cliente, FK opcional para Usina, campos atuais de UC e relacionamento de conexões/rateio preservado para expansão.
Feito: criado ConsumerUnit com FK para clients, FK opcional para plants, campos atuais da tela e tabela auxiliar plant_connections para conexão UC↔Usina com percentual.
 Modelo Usina.
Critério de pronto: modelo SQLAlchemy criado com campos usados hoje pela tela de Usinas e relacionamento reverso com UCs.
Feito: criado Plant com nome, UC, kW pico, geração média, status e percentual disponível.
 ⚠️ Modelo Documento (FK para UC, FK para Categoria) — status real não confirmado, ver bloqueador no topo do arquivo antes de assumir concluído.
Critério de pronto: modelo SQLAlchemy criado com vínculo opcional a Cliente, FK opcional a UC e FK obrigatória a Categoria.
 ⚠️ Modelo Categoria — status real não confirmado, ver bloqueador no topo do arquivo.
Critério de pronto: modelo SQLAlchemy criado para classificar documentos, com nome único e tipo/descrição opcionais.
 ⚠️ Modelo Configuração — status real não confirmado, ver bloqueador no topo do arquivo.
Critério de pronto: modelo SQLAlchemy chave/valor criado para configurações persistidas no banco.
 ⚠️ Modelo GoogleAccount — status real não confirmado, ver bloqueador no topo do arquivo.
Critério de pronto: modelo SQLAlchemy criado para múltiplas contas Google OAuth, sem hardcode de credenciais, com refresh token efetivamente criptografado (não só o campo nomeado assim).
 ⚠️ Modelo Log — status real não confirmado, ver bloqueador no topo do arquivo.
Critério de pronto: modelo SQLAlchemy criado para registrar ações, entidade afetada e metadados.
 ⚠️ Migration inicial rodando limpa em banco vazio — a migration real encontrada (45f056e2a73d) só cobre Cliente/UC/Usina/PlantConnection. Precisa nova migration depois de resolver os 5 models acima.
CRUD Cliente / UC / Usina (ligar ao banco, hoje está em memória/localStorage no front)

Padrão obrigatório pra essa seção inteira (adicionado 2026-07-12): todo endpoint novo nasce documentado de um jeito que dá pra mexer sem IA depois. Regras:

Um blueprint por domínio — routes/clients_routes.py, routes/ucs_routes.py, routes/plants_routes.py. Nunca misturar domínios no mesmo arquivo de rotas.
Cada rota leva um comentário de uma linha em cima explicando método, path e o shape do payload:
python
# POST /clients — cria cliente. Body: {nome, cpf, email, concessionaria, ucs: ClientUc[]}. Retorna ClientRow.
to_dict() de cada model continua sendo a ÚNICA fonte do formato que vai pro frontend — nunca montar JSON solto dentro da função de rota.
Toda mudança de campo no backend (nome, tipo, campo novo) muda o tipo TS correspondente em frontend/src/services/operationsService.ts (ClientRow, PlantRow, ClientUc) no mesmo commit — os dois nunca podem descrever formatos diferentes.
Ao terminar essa seção inteira, criar API_CONTRACTS.md na raiz do projeto listando: endpoint, método, payload de entrada, formato de resposta, pra toda rota ativa. É esse arquivo que se abre pra adicionar campo sem precisar perguntar pra IA onde mexer.
Decisão de design pendente antes de codar: Plant.percentual_disponivel hoje é um campo manual solto, não calculado a partir das PlantConnection reais — nada impede hoje que duas conexões somem mais de 100% de uma usina. Decidir: vira campo calculado (100 − soma dos percentuais já conectados) ou continua manual com validação na escrita? Registrar a escolha aqui antes de implementar.
 API de Cliente (GET/POST/PUT/DELETE) usando o banco novo.
 API de UC, com vínculo a Cliente e Usina.
 API de Usina.
 Frontend de Clientes consumindo a API nova (hoje usa localStorage com a chave hub.operations.v1 — não remover a tela/fluxo, só trocar a fonte de dados).
 Frontend de Usinas consumindo a API nova.
 Migrar dados de exemplo/mock existentes, se fizer sentido, ou começar limpo (decidir com o usuário).
 Mover a regra de status do cliente (getClientStatus, hoje só em frontend/src/services/operationsService.ts) pro backend — quando a API existir, o status não pode ser calculado nos dois lados ao mesmo tempo.
Google Drive OAuth
 Fluxo OAuth 2.0 (login interativo, autorizar, salvar refresh token).
 Refresh token salvo de forma segura no banco (não em texto puro sem proteção).
 Suporte a mais de uma conta Google conectada.
 Tela de gerenciamento de contas (trocar conta ativa).
 Fluxo antigo baseado em credentials.json continua funcionando até o OAuth estar validado — só remover depois de confirmado.
Documentos
 Módulo de Documentos ligado ao banco (Categoria, vínculo a UC/Cliente).
 Upload, busca, filtro, download — mantendo a experiência de busca/reserva/ZIP que já existe hoje no Drive.
Configurações
 Aba Banco de dados (Google Drive + SQL futuro) já existe.
 Aba Aparência (cor + logo) já existe.
 Ajustar aba Banco de dados pra refletir SQLite local em vez de "SQL futuro" genérico, se a decisão em aberto acima for confirmada.
Transversal — Empacotamento (.exe)

Itens novos encontrados na revisão de 2026-07-12, além do checklist original:

Trocar o servidor de dev do Flask (Werkzeug) por waitress no build empacotado — Werkzeug não é feito pra rodar de forma permanente como processo de fundo de um app desktop.
SQLALCHEMY_DATABASE_URI hoje é relativo a BASE_DIR do backend (backend/config.py) — não pode ir pro .exe assim. Empacotado, essa pasta pode ser somente-leitura (Program Files) ou temporária (PyInstaller --onefile). O banco tem que morar em pasta de dados do usuário (ex.: %APPDATA%/APP_HUB/hub.db).
Garantir que FLASK_DEBUG vá false fixo no build de produção, independente do que estiver no .env de dev — debug ligado expõe o debugger interativo do Werkzeug (risco de execução de código arbitrário via console web).
Usar o "sidecar" do Tauri pra gerenciar o ciclo de vida do processo do backend (start/kill), pra não deixar hub-backend.exe órfão rodando depois que o app fecha — causa mais comum de "na segunda vez que abro, trava".
Porta fixa (API_PORT=8000) sem fallback — se a porta estiver ocupada (inclusive por processo órfão do ponto anterior), o app não sobe. Checar disponibilidade antes de subir ou ter porta alternativa.
CORS hoje é CORS(app) sem allowlist e não há autenticação em nenhuma rota — resolver antes do empacotamento, não depois (ver seção de segurança da revisão).
 Backend empacotado com PyInstaller, testado como .exe isolado fora do ambiente de dev.
 Projeto Tauri (ou Electron, conforme decisão em aberto) criado em desktop/.
 App desktop sobe o .exe do backend como subprocesso automaticamente.
 Instalador .msi/.exe gerado.
 Testado numa máquina limpa, sem Python/Node instalado.
V1.5 — Refinamento operacional
 Pendências.
 Dashboard inteligente com métricas reais.
 Agenda operacional funcional (hoje é grade estática com 3 itens de exemplo).
V2.0 — Cobrança
 Integração ASAAS.
 WhatsApp.
 Cobranças automáticas.
V3.0 — Financeiro / Rateios
 Importação de fatura/planilha.
 Cálculo automático de rateio.
 Relatórios + exportação Excel/PDF.
 Histórico de competências.
V4.0 — Monitoramento
 Integração com APIs de inversores.
 Alertas automáticos.
V5.0 — Automação
 Motor de automações.
 Portal do cliente.
Log de decisões tomadas durante o desenvolvimento

(o Codex adiciona uma linha aqui sempre que resolver uma ambiguidade sozinho, pra você poder revisar depois)

2026-07-08: enquanto o usuário não responder sobre single-user vs multi-máquina, mantido o default da visão: SQLite local.
2026-07-08: escolhido SQLAlchemy + Flask-Migrate/Alembic para banco local e migrations.
2026-07-08: drive_service passou a inicializar o cliente Google Drive sob demanda para permitir que o app Flask suba sem credentials.json; rotas do Drive retornam erro claro se a credencial faltar.
2026-07-08: o modelo Client usa nomes internos em inglês e to_dict() compatível com os nomes atuais do frontend em português para facilitar a troca futura de localStorage por API.
2026-07-08: criada tabela plant_connections além das entidades listadas para preservar o comportamento atual de uma UC conectada a múltiplas usinas com percentuais.
2026-07-12: revisão arquitetural (Claude) a partir dos arquivos colados no chat — encontrado descompasso entre a migration real (só 4 tabelas) e o checklist (que marcava 5 models adicionais como concluídos, ver bloqueador no topo do arquivo). Definido padrão obrigatório de documentação pra toda rota que fala com o frontend. Listados ajustes de estabilidade pro empacotamento .exe (waitress, path do banco em %APPDATA%, debug off forçado, ciclo de vida do processo via sidecar do Tauri, CORS/autenticação). search_files em drive_service.py tem risco de injeção de query por concatenar input sem escapar — não corrigido ainda, só registrado.
