# APP HUB — Progresso

> Leia [[VISAO]] primeiro. Este arquivo é o estado atual, atualizado a cada tarefa concluída.
> **Documentos relacionados:** [[VISAO]] · [[ARCHITECTURE]] · [[API_CONTRACTS]] · [[CONTRIBUTING]]
> Regra: pegue a primeira tarefa `[ ]` de cima pra baixo. Não pule.

Última atualização: 2026-08-13 — Sprint 2 de Pendências (automação completa), polimento visual do frontend, tela de Usuários reformulada com tabela, edição e exclusão.

---

## Decisões já resolvidas (não reabrir sem motivo novo)

- [x] **Modo de uso do app:** local/single-user, só o João. Integração futura com sistema do colega será via API entre dois sistemas independentes — não é multi-tenant, não muda a arquitetura de dados local. Ver `VISAO.md` seção 2.
- [x] **Empacotador desktop:** Tauri.
- [x] **Numeração de versão:** `V0.x` até o núcleo fechar, vira `V1.0` de verdade só quando os itens desta seção estiverem todos `[x]`.
- [x] **Plant.percentual_disponivel:** ⚠️ nota desatualizada até 2026-08-19 dizia "continua manual" -- na prática, `percentual_disponivel_efetivo()` (`models/plant.py`) já calcula automaticamente (`100 - reserva_percentual`) sempre que a usina tem produção mensal cadastrada, e só cai no campo manual quando não há produção. `PlantCard.ts` ainda mostra o campo "Disponível para rateio (%)" como editável mesmo quando ele é ignorado pela API nesse caso (a API já devolve `percentualManual: false/true` pra distinguir) -- **TODO:** esconder/desabilitar esse campo no formulário quando `percentualManual === false`. Registrado como tarefa pendente, não decisão em aberto.
- [x] **CPF/CNPJ da UC:** UC tem campo `documento` próprio (pode diferir do CPF do Cliente — ex.: casa no CPF pessoal, empresa no CNPJ do mesmo titular). Sem validação rígida contra o cliente, é campo livre.
- [x] **Código ANEEL:** UC tem `codigo` (atual/legado) e `codigoAneel` (novo padrão nacional de 15 dígitos, REN ANEEL 1.095/2024) como campos separados.
- [x] **Deploy completo (Fase 1):** HUB roda 100% na nuvem — Postgres (Neon, projetos separados dev/produção), backend (Render Web Service), frontend (Render Static Site), documentos no Google Drive. Não depende mais do `python hub.py iniciar` pra existir, só pra desenvolver/testar.
- [x] **Autenticação e papéis (Fase 1 de Segurança):** cookie HttpOnly + CSRF + rate limit + headers de segurança + roles `admin`/`viewer`, todos com teste automatizado antes de entregar. Auto-cadastro condicionado a `SIGNUP_CODE` (ver `.env.production.example`).
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
- [x] **Tela de Usuários** (`UsersPage.ts`) — tabela com Nome/Email/Senha (toggle mostrar/ocultar)/Papel/Status/Ações. Modal para criar e editar usuário. Botões de editar e excluir funcionais. Backend com `updateUser` e `deleteUser` no `userService.ts`.

### Documentação viva
- [x] **`API_CONTRACTS.md` criado** — todo endpoint ativo documentado.
- [x] `API_CONTRACTS.md` atualizado com as rotas de `/pendencias` (CRUD, resolver/cancelar/reabrir/comentarios, resumo, verificar, regras) e o filtro novo de `/logs`.

### Deploy
- [x] **Backend rodando na nuvem (Render) com Postgres**, saindo do SQLite local. `config.py` normaliza `postgres://` → `postgresql://`. `psycopg2-binary` e `gunicorn` adicionados ao `requirements.txt`. Start Command: `gunicorn -w 2 -b 0.0.0.0:$PORT app:app`.
- [ ] Start Command ainda não roda a migration sozinho a cada deploy (sugestão: `flask db upgrade && gunicorn ...`) — hoje precisa rodar `flask db upgrade` manualmente do PC local apontando `DATABASE_URL` pra URL externa do Postgres do Render.
- [x] **Histórico Alembic validado em SQLite vazio:** `backend/tests/test_sqlite_migrations.py` executa `flask db upgrade` até a head e confere `api_credentials`. Em 2026-08-31, passou após tornar as migrations legadas `e5f9a3b2c7d4` (conversão numérica) e `d1e5f8a2b4c7` (unicidade de GoogleAccount) compatíveis com SQLite, preservando os caminhos PostgreSQL. O teste também cobre valores legados válidos/malformados, precisão/overflow `NUMERIC(p,2)` e bloqueia downgrade quando emails duplicados entre tenants perderiam a unicidade global.
- [x] Frontend confirmado publicado no Render. `VITE_API_BASE_URL` apontando pro backend do Render em produção.

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
- [x] **Pendências — Sprint 2**: motor de automação implementado (`automacao_service.py` + `GET /pendencias/verificar` + `GET /pendencias/regras`). Regras automáticas implementadas:
  - UC sem usina vinculada há 7+ dias (cria alerta)
  - Cliente sem UC cadastrada (cria pendência)
  - Campos obrigatórios faltando no cliente (cria pendência)
  - Documentos obrigatórios faltando (cria pendência)
  - Resolução automática quando situação é corrigida
  - Sem duplicação de pendências existentes
  - Verificação automática ao abrir a tela de Pendências
  - Botão "Verificar agora" na toolbar
- [x] **Formulário Copel de Rateio (Associações) — geração completa** (`RATEIO.md` seções 8-10). 4 sprints: (1) documentos fixos da empresa (CNPJ/Estatuto, reaproveitando `Document`/Drive), (2) tabela de revisão + checagem automática de Termo de Adesão (bloqueia geração e cria `Pendencia` crítica se faltar), (3) aba nova em `/rateio` ("Gerar Formulário Copel") com tabela editável de conferência antes de gerar, (4) geração real dos PDFs — overlay de texto sobre o template oficial em branco (`backend/assets/formulario_copel_associacao.pdf`, calibrado via `pdfplumber`) + merge dos Termos de Adesão em PDF único. Entrega final: 4 arquivos pro envio à Copel (formulário preenchido + termos mesclados + CNPJ + estatuto). **Pendente de validação visual em produção** — ver seção de decisões em aberto abaixo.
- [x] **Dashboard operacional:** `GET /dashboard/resumo` entrega, em tempo real e no tenant ativo, fila de pendências abertas (priorizada), abertas/vencidas/vencendo em 7 dias/resolvidas no mês, totais e status de Clientes/Usinas, totais de UCs e documentos por categoria. A tela `/dashboard` consome esse contrato, é a página inicial e apresenta métricas, fila operacional e estados de carregamento/erro/vazio. O payload respeita RBAC: métricas de um domínio sem permissão de leitura são omitidas (`disponivel: false`), sem vazamento indireto. Build do frontend validado em 2026-08-31.
- [x] **Hardening OAuth de transporte:** `OAUTHLIB_INSECURE_TRANSPORT` não é mais habilitado no import e `OAUTHLIB_RELAX_TOKEN_SCOPE` foi removido, preservando a validação padrão de escopos. HTTP é aceito apenas em desenvolvimento local explicitamente configurado (`FLASK_DEBUG=true`, `OAUTH_ALLOW_INSECURE_TRANSPORT=true`, callback/frontend loopback); qualquer outro ambiente exige callback e frontend HTTPS absolutos, sem credenciais/fragmentos, e remove a exceção herdada do processo.
- [x] **Credenciais de API por empresa:** `ApiCredential` armazena segredo somente criptografado (`SECRET_ENCRYPTION_KEY`) para Resend, WhatsApp, ASAAS e concessionárias. CRUD em `/api-credentials` é tenant-scoped, não serializa segredo e registra auditoria sem valores sensíveis. O endpoint de teste é dry-run local, sem chamadas externas.
- [x] **Agenda operacional (fonte Pendências)** — `GET /agenda` entrega a fila de pendências abertas com `prazo`, tenant-scoped e protegida por `pendencias.read`, com filtros de intervalo (máximo 93 dias-calendário) e visões dia/semana/mês (mês atual por padrão). Não há tabela de evento nem duplicação de estado: edição de prazo ou reabertura aparece imediatamente; conclusão/cancelamento remove o item na próxima consulta. Financeiro e Rateio continuam como fontes futuras.
- [x] **Dados cadastrais da empresa atual:** `GET`/`PUT /empresas/atual` expõem e atualizam somente nome, razão social, CNPJ, e-mail e telefone da empresa autenticada. Escrita é limitada a owner/admin; slug, status e IDs são protegidos e o contrato/testes cobrem isolamento e validação.
- [x] **Importação em massa de Cliente/UC/Usina:** rota e tela de preview + confirmação para CSV UTF-8 ou XLSX (abas Clientes/UCs/Usinas), somente criação e sem conexões UC–usina. O plano fica temporariamente no servidor, tenant/user-scoped; confirmação é atômica e protegida contra replay. Parsing tem limites, bloqueio de fórmulas e resposta controlada para arquivos inválidos. Previews com PII expiram e são removidos por comando operacional `flask purge-import-previews`; auditoria guarda apenas hash, contagens e resultado. CPF agora é único por empresa. Em 2026-08-31: 13 testes de importação/migration, 36 testes de regressão e build do frontend aprovados; revisão de segurança aprovada.
- [x] **Templates de mensagem V1.5-C:** tela `/templates` e API tenant-scoped para criar, editar, remover, restaurar e pré-visualizar templates de e-mail/WhatsApp sem qualquer envio. Templates globais legados foram copiados por empresa na migration e estão somente em leitura por compatibilidade; provisionamento de empresa cria seus padrões na mesma transação. Prévia usa texto seguro, corpo/variáveis são validados, links exigem HTTPS e a auditoria é redigida. Em 2026-08-31: 43 testes de regressão e build do frontend passaram; revisão de segurança aprovada.
- [x] **Isolamento do estado OAuth:** a limpeza de estados OAuth expirados executada durante uma requisição agora é limitada explicitamente à empresa atual; teste de regressão confirma que iniciar OAuth em uma empresa não remove estado de outra. O build do frontend também está sem aviso de import dinâmico/estático do cliente HTTP.
- [x] **Lookups de domínio tenant-scoped:** autenticação, Cliente, UC, Usina, Pendência e Documento deixaram de usar `Query.get()` para modelos de domínio; buscas e referências agora filtram explicitamente a empresa atual. Regressão A/B cobre criação/edição de UC aninhada, update/delete de entidades estrangeiras, vínculo de pendência e conexão de usina entre empresas.

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
