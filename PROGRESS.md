# APP HUB — Progresso

> Leia `VISAO.md` primeiro. Este arquivo é o estado atual, atualizado a cada tarefa concluída.
> Regra: pegue a primeira tarefa `[ ]` de cima pra baixo. Não pule.

Última atualização: 2026-08-06 — sessão grande: sistema de ícones, reforma completa de Usinas (lista + detalhe), sidebar reorganizada em seções, campos de negócio expostos nos formulários de Cliente/UC/Usina, Pendências Sprint 1 (model + CRUD + tela), e migração do backend pra Postgres/Render.

---

## Decisões já resolvidas (não reabrir sem motivo novo)

- [x] **Modo de uso do app:** local/single-user, só o João. Integração futura com sistema do colega será via API entre dois sistemas independentes — não é multi-tenant, não muda a arquitetura de dados local. Ver `VISAO.md` seção 2.
- [x] **Empacotador desktop:** Tauri.
- [x] **Numeração de versão:** `V0.x` até o núcleo fechar, vira `V1.0` de verdade só quando os itens desta seção estiverem todos `[x]`.
- [x] **Plant.percentual_disponivel:** continua campo manual por enquanto (não calculado a partir de `PlantConnection`). Revisar quando o rateio automático (V3.0) for implementado.
- [x] **CPF/CNPJ da UC:** UC tem campo `documento` próprio (pode diferir do CPF do Cliente — ex.: casa no CPF pessoal, empresa no CNPJ do mesmo titular). Sem validação rígida contra o cliente, é campo livre.
- [x] **Código ANEEL:** UC tem `codigo` (atual/legado) e `codigoAneel` (novo padrão nacional de 15 dígitos, REN ANEEL 1.095/2024) como campos separados.

---

## V0.x → V1.0 — Núcleo funcional

### Backend — Banco de dados e models
- [x] SQLAlchemy + Flask-Migrate configurados via `extensions.py` (db/migrate centralizados — não criar instância própria em nenhum outro arquivo, isso já causou bug real de produção).
- [x] Migrations aplicadas em cadeia, testadas inclusive contra banco com dado pré-existente: `45f056e2a73d` (schema inicial) → `cbc335adce4f` (Categoria/Documento/Configuração/GoogleAccount/Log) → `061e810abc38` (users) → `c4b5632aaedd` (campos de negócio extras em Cliente/UC/Usina) → `8f2a1c9d0eab` (categoria opcional em Documento) → `a1f9c2e6d8b3` (cidade/uf/endereco/data_ativacao/responsavel em Usina) → `f3d7b1c9a4e2` (tabelas `pendencias` e `pendencia_comentarios`).
- [x] Models completos: `Client`, `Plant`, `ConsumerUnit`, `PlantConnection`, `Category`, `Document`, `Setting`, `GoogleAccount`, `LogEntry`, `User`, `Pendencia`, `PendenciaComentario`.
- [x] Campos de negócio em Cliente: nome, cpf, email, telefone, concessionaria, status.
- [x] Campos de negócio em UC: codigo, codigoAneel, apelido, documento, endereco, cep, concessionaria, geracaoPropria, diaEmissaoFatura, consumo, baseTarifaria, desconto, tipoLigacao, inicioContrato, terminoContrato, carenciaMeses, percentualDescontoCarencia.
- [x] Campos de negócio em Usina: nome, uc, kwPico, status, percentualDisponivel, marcaInversor, telefoneProprietario, emailProprietario, cidade, uf, endereco, dataAtivacao, responsavel.
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
- [x] `drive_routes.py` não derruba mais o backend se `credentials.json` não existir — erro controlado (503) em vez de crash.
- [x] **`GET/POST/PUT/DELETE /pendencias`** + `GET /pendencias/resumo` + `POST /pendencias/<id>/{resolver,cancelar,reabrir}` + `POST /pendencias/<id>/comentarios` (`pendencia_routes.py` + `pendencia_service.py`). Criação manual (`POST /pendencias`) sempre força `tipo='pendencia'` — `alerta`/`erro` só nascem via `criar_alerta`/`criar_erro`, chamados por regra automática (ainda não implementada, ver V1.5 abaixo). Categorias fixas por tipo em `CATEGORIAS_POR_TIPO` (hoje os 3 tipos compartilham a mesma lista, de propósito — trocar por tipo é só mudar uma chave do dict).
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
- [x] **Sistema de ícones** (`components/Icon.ts`) — SVG inline (stroke=currentColor, sem cor/tamanho fixo), substituindo emoji do sidebar e texto solto (`x`) dos botões de remover.
- [x] **Reforma de Usinas** (`PlantsPage.ts`) — lista com cards de status clicáveis (filtro), busca, tabela sem paginação (rolagem interna via `.data-panel-scroll`); detalhe com painel de informações + resumo (UCs ativas/ocupação) + abas (UCs conectadas ativa, Documentos/Financeiro/Histórico/Logs desabilitadas). `DetailHeader.ts` (órfão, sem CSS) e `_unused-drafts.css` removidos — a tela antiga estava com o detalhe invisível em produção.
- [x] **Sidebar reorganizada em seções** (Gestão/Financeiro/Automações/Configurações), com itens do roadmap futuro visíveis-porém-desabilitados ("Em breve") e rodapé com usuário logado (email/papel, cache leve em `authService.ts`) + versão.
- [x] **Tela de Pendências** (`PendenciasPage.ts`) — lista com cards-filtro por tipo (Pendência/Alerta/Erro), busca, painel de detalhe fixo lateral (não-modal) com badges, ações (resolver/cancelar/reabrir/editar/excluir), comentários e timeline (via `/logs`). Criação manual só gera tipo `pendencia`.

### Documentação viva
- [x] **`API_CONTRACTS.md` criado** — todo endpoint ativo documentado.
- [x] `API_CONTRACTS.md` atualizado com as rotas de `/pendencias` (CRUD, resolver/cancelar/reabrir/comentarios, resumo) e o filtro novo de `/logs`.

### Deploy
- [x] **Backend rodando na nuvem (Render) com Postgres**, saindo do SQLite local. `config.py` normaliza `postgres://` → `postgresql://`. `psycopg2-binary` e `gunicorn` adicionados ao `requirements.txt`. Start Command: `gunicorn -w 2 -b 0.0.0.0:$PORT app:app`.
- [ ] Start Command ainda não roda a migration sozinho a cada deploy (sugestão: `flask db upgrade && gunicorn ...`) — hoje precisa rodar `flask db upgrade` manualmente do PC local apontando `DATABASE_URL` pra URL externa do Postgres do Render.
- [ ] Frontend ainda não confirmado onde/como está publicado — `VITE_API_BASE_URL` precisa apontar pro backend do Render em produção.

---

## Transversal — Empacotamento (.exe)
**Decisão revista em 2026-08-06:** não é mais o plano principal por agora — Render (ou outro servidor de back+front) virou o caminho principal. `.exe`/Tauri fica pra depois, possivelmente só quando a V5 fechar. Nada da lista abaixo foi tocado, e não é prioridade:
- [ ] Trocar Werkzeug por `waitress` no build de produção.
- [ ] Path do SQLite não pode ser relativo ao `backend/` no `.exe`.
- [ ] `FLASK_DEBUG` forçado `false` no build.
- [ ] Ciclo de vida do processo via sidecar do Tauri.
- [ ] Porta fixa sem fallback.
- [ ] Backend empacotado com PyInstaller.
- [ ] Projeto Tauri criado em `desktop/`.
- [ ] Instalador testado em máquina limpa.

---

## V1.5 — Refinamento operacional
- [x] **Pendências — Sprint 1**: model (`tipo`/`categoria`/`origem`/`prioridade`/`status`, vínculo opcional a Cliente/UC/Usina/Documento), comentários, CRUD completo, tela com cards-filtro/busca/painel de detalhe/comentários/timeline. Criação manual só gera tipo `pendencia`.
- [ ] **Pendências — Sprint 2**: regra automática "UC sem usina vinculada" — sem scheduler no projeto, a checagem roda sob demanda: ao abrir a tela de Pendências (sincroniza sozinha) e por um botão manual "Verificar agora". Cria `alerta` pra UC sem `PlantConnection`, sem duplicar se já existir uma aberta; resolve sozinha se a UC ganhar usina depois.
- [ ] Dashboard inteligente com métricas reais (hoje é item desabilitado "Em breve" na sidebar).
- [ ] **Agenda operacional real** — hoje é grade estática com 3 itens de exemplo, sem backend.
- [ ] Importação em massa de Cliente/UC/Usina via planilha Excel.

## V2.0 — Cobrança e automação de mensagens
- [ ] Integração ASAAS (boleto).
- [ ] Integração WhatsApp pra disparo automático dos eventos da Agenda.
- [ ] Cobranças automáticas.

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

- 2026-07-19: resolvida a dúvida de single-user vs multi-máquina (ver seção de decisões resolvidas). Vindo do GDASH, levantada lista extensa de campos de negócio pra Cliente/UC/Usina — triada entre "adota agora" (dado estático) e "ignora por enquanto" (tudo que é calculado ou depende de integração ainda não construída: economia total, saldo de crédito, gráficos de geração em tempo real, etc.).

- 2026-07-20/21: sessão focada destravou em sequência — bug de duas instâncias `SQLAlchemy()` brigando (client_routes 500), blueprint de cliente nunca registrado, os 5 models faltando (criados e testados), autenticação completa (bootstrap/login/middleware, chave vazada no `.env.example` detectada e trocada), CRUD de UC avulso, backend de Documentos + Categorias, `localStorage` eliminado do frontend inteiro (Clientes, Usinas, Aparência), `iniciar.py` corrigido (venv apontava pra pasta errada, PID errado).

- 2026-07-22: campos de negócio completos adicionados a Cliente/UC/Usina a partir de comparação com o GDASH; migration testada especificamente contra banco com dado pré-existente (achado e corrigido: `geracao_propria NOT NULL` sem default quebraria em banco real). `PROGRESS.md` reescrito do zero pra parar de arrastar informação desatualizada.

- 2026-07-26 (aprox., commit "OAuth do Google Drive completo e testado"): OAuth 2.0 real implementado — fluxo PKCE, `GoogleAccount` com refresh token criptografado, múltiplas contas, `drive_service.py` priorizando a conta OAuth ativa. Junto veio a tela de Configurações → Banco de dados (Google Drive / SQL) e a lista de contas Google conectadas.

- 2026-07-27: tela de UCs (`/ucs`) e tela de Documentos implementadas, ambas consumindo API real. `API_CONTRACTS.md` criado documentando todo endpoint ativo, inclusive os de `/config/database` e `/oauth/google` que não estavam rastreados. `PROGRESS.md` atualizado pra bater com o estado real do código (zip conferido, não só relato).

- 2026-08-03: **Migração de dados (SQLite → Postgres)** — Etapa 3 do plano de deploy. Script pontual `backend/scripts/migrate_sqlite_to_postgres.py`, testado com cópia de dado real antes de entregar (contagens, ordem de FK, reset de sequence, idempotência). `users` fica fora por padrão (evita duplicar/colidir com o admin já criado durante o teste da Etapa 2). Documentos físicos (`backend/uploads/`) não precisaram de nenhuma ação nessa etapa — só passam a importar na Etapa 7 (Render, filesystem efêmero).

- 2026-08-06: sessão longa — sistema de ícones (`Icon.ts`), reforma completa de Usinas (lista + detalhe, achado e corrigido bug real: `DetailHeader.ts` sem CSS, tela de detalhe invisível em produção), sidebar reorganizada em seções, campos de negócio nos 3 formulários (`formFields.ts` centralizado), Pendências Sprint 1 completo, migração do backend pra Postgres/Render (`config.py`, `requirements.txt`), `API_CONTRACTS.md` atualizado com `/pendencias` e `/logs`. **Decisão revista:** `.exe`/Tauri deixou de ser o plano principal — Render (ou outro servidor) é o caminho agora. Pendente pra próxima sessão: Pendências Sprint 2 (regra automática de UC sem usina).