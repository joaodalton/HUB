# APP HUB — Progresso

> Leia `VISAO.md` primeiro. Este arquivo é o estado atual, atualizado a cada tarefa concluída.
> Regra: pegue a primeira tarefa `[ ]` de cima pra baixo. Não pule.

Última atualização: 2026-07-22 — reescrito do zero pra bater com o estado real do repositório (a versão anterior, de 12/07, estava desatualizada e ainda falava de um bloqueador já resolvido há semanas). Tudo abaixo foi verificado rodando de verdade (migration, testes de API via HTTP), não só lido no código.

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
- [x] Migrations aplicadas em cadeia, testadas inclusive contra banco com dado pré-existente: `45f056e2a73d` (schema inicial) → `cbc335adce4f` (Categoria/Documento/Configuração/GoogleAccount/Log) → `061e810abc38` (users) → `c4b5632aaedd` (campos de negócio extras em Cliente/UC/Usina).
- [x] Models completos: `Client`, `Plant`, `ConsumerUnit`, `PlantConnection`, `Category`, `Document`, `Setting`, `GoogleAccount`, `LogEntry`, `User`.
- [x] Campos de negócio em Cliente: nome, cpf, email, telefone, concessionaria, status.
- [x] Campos de negócio em UC: codigo, codigoAneel, apelido, documento, endereco, cep, concessionaria, geracaoPropria, diaEmissaoFatura, consumo, baseTarifaria, desconto, tipoLigacao, inicioContrato, terminoContrato, carenciaMeses, percentualDescontoCarencia.
- [x] Campos de negócio em Usina: nome, uc, kwPico, status, percentualDisponivel, marcaInversor, telefoneProprietario, emailProprietario.
- [x] `GoogleAccount.refresh_token` criptografado de verdade via `utils/crypto.py` (Fernet, chave em `SECRET_ENCRYPTION_KEY`) — nunca aparece em `to_dict()`.

### Backend — API
- [x] `POST /auth/bootstrap` (cria o admin uma única vez), `POST /auth/login` (retorna token assinado via `itsdangerous`, expira em 7 dias).
- [x] Middleware (`utils/auth.py`) protege toda rota exceto `/`, `/auth/login`, `/auth/bootstrap` — testado: sem token dá 401, token forjado dá 401, token válido passa.
- [x] `GET/POST/PUT/DELETE /clients` — inclui sincronização de UCs aninhadas.
- [x] `GET/POST/PUT/DELETE /ucs` — CRUD avulso, além de aninhado dentro de `/clients`. Lógica de conexão UC-Usina (`sync_connections`, por `plantId`) compartilhada entre os dois, sem duplicação.
- [x] `GET/POST/PUT/DELETE /plants`.
- [x] `GET/POST /categories`.
- [x] `GET/POST/PUT/DELETE /documents` + `GET /documents/<id>/download` — upload/download de arquivo real em disco (`backend/uploads/`, fora do git), testado byte a byte.
- [x] `GET/PUT /settings` — configuração chave/valor (hoje usado só por Aparência).
- [x] `drive_routes.py` não derruba mais o backend se `credentials.json` não existir — erro controlado (503) em vez de crash.

### Frontend
- [x] Login (tela + guarda de rota — sem token, qualquer página redireciona pra `/login`).
- [x] Clientes: 100% via API real (`clientsService.ts`), zero `localStorage`.
- [x] Usinas: 100% via API real (`plantService.ts`).
- [x] Aparência (cor, logo): via API real (`/settings`), zero `localStorage`.
- [x] `localStorage` eliminado do projeto inteiro — confirmado por busca no código, não sobrou nenhum uso.
- [ ] **Tela de UCs** — rota `/ucs` ainda é o placeholder estático original. A API já existe e já foi testada; falta só a tela consumir.
- [ ] **Tela de Documentos** — API pronta e testada; zero UI ainda. Decidido ficar pra quando entrar a reforma geral do frontend.
- [ ] Formulário de Cliente/UC/Usina ainda não expõe os campos de negócio novos (telefone, endereço, CEP, concessionária por UC, geração própria, código ANEEL, contrato, carência, marca do inversor, contato do proprietário) — dado já tem onde morar no banco, só falta aparecer no formulário.

### Google Drive
- [ ] Ainda no modelo antigo (`credentials.json` fixo, uma conta só). OAuth 2.0 real (múltiplas contas, refresh token no banco) não foi iniciado.

### Documentação viva
- [ ] `API_CONTRACTS.md` nunca foi criado — regra definida faz tempo, ainda pendente. Listar todo endpoint ativo (método, payload, resposta) antes de esquecer o formato de algum.

---

## Transversal — Empacotamento (.exe)
Nada disso foi tocado ainda. Continua valendo tudo que já foi levantado:
- [ ] Trocar Werkzeug por `waitress` no build de produção.
- [ ] Path do SQLite não pode ser relativo ao `backend/` no `.exe` — precisa ir pra `%APPDATA%` (ou equivalente) antes do empacotamento.
- [ ] `FLASK_DEBUG` forçado `false` no build, independente do `.env` de dev (debug ligado expõe o debugger interativo do Werkzeug).
- [ ] Ciclo de vida do processo via sidecar do Tauri (`comandos/iniciar.py`/`parar.py` já corrigidos localmente pro dev — isso é só o launcher manual, não é o empacotamento final).
- [ ] Porta fixa sem fallback (`API_PORT=8000`) — checar disponibilidade antes de subir.
- [ ] Backend empacotado com PyInstaller, testado isolado.
- [ ] Projeto Tauri criado em `desktop/`.
- [ ] Instalador testado em máquina limpa.

---

## V1.5 — Refinamento operacional
- [ ] Pendências.
- [ ] Dashboard inteligente com métricas reais.
- [ ] **Agenda operacional real** — hoje é grade estática com 3 itens de exemplo, sem backend. Eventos definidos com o João: boas-vindas, verificação AVA, início/conclusão de rateio, primeiro desconto, fatura com desconto aplicado — cada um com opção de disparo de mensagem (provável API de WhatsApp, ver V2.0).
- [ ] Importação em massa de Cliente/UC/Usina via planilha Excel.

## V2.0 — Cobrança e automação de mensagens
- [ ] Integração ASAAS (boleto).
- [ ] Integração WhatsApp pra disparo automático dos eventos da Agenda.
- [ ] Cobranças automáticas.

## V3.0 — Financeiro / Rateios
- [ ] **Regra de cálculo do rateio automático ainda não definida** — é decisão de negócio, precisa de conversa com o João (como o GDASH calcula hoje) antes de qualquer linha de código.
- [ ] Botão de rateio automático por Usina, calculando % de consumo de cada UC conectada.
- [ ] Importação de fatura e planilha de rateio.
- [ ] Relatórios + exportação Excel/PDF.
- [ ] Histórico de competências.

## V4.0 — Monitoramento
- [ ] Integração com APIs de inversores (viabilidade depende da marca — levantar com o João antes de estimar).
- [ ] Leitura automatizada de fatura das concessionárias (robô/ML) — alta incerteza, validar com prova de conceito pequena antes de comprometer prazo.
- [ ] Alertas automáticos de produção/falha.

## V5.0 — Automação
- [ ] Motor de automações.
- [ ] Portal do cliente.
- [ ] Integração com SunHub via API (se o comercial não for absorvido pelo HUB).

---

## Log de decisões tomadas durante o desenvolvimento

- 2026-07-08 a 2026-07-12: fundação inicial (SQLAlchemy, migrations, models Cliente/UC/Usina, revisão arquitetural que achou o bug dos 5 models faltando).
- 2026-07-19: resolvida a dúvida de single-user vs multi-máquina (ver seção de decisões resolvidas). Vindo do GDASH, levantada lista extensa de campos de negócio pra Cliente/UC/Usina — triada entre "adota agora" (dado estático) e "ignora por enquanto" (tudo que é calculado ou depende de integração ainda não construída: economia total, saldo de crédito, gráficos de geração em tempo real, etc.).
- 2026-07-20/21: sessão focada destravou em sequência — bug de duas instâncias `SQLAlchemy()` brigando (client_routes 500), blueprint de cliente nunca registrado, os 5 models faltando (criados e testados), autenticação completa (bootstrap/login/middleware, chave vazada no `.env.example` detectada e trocada), CRUD de UC avulso, backend de Documentos + Categorias, `localStorage` eliminado do frontend inteiro (Clientes, Usinas, Aparência), `iniciar.py` corrigido (venv apontava pra pasta errada, PID errado).
- 2026-07-22: campos de negócio completos adicionados a Cliente/UC/Usina a partir de comparação com o GDASH; migration testada especificamente contra banco com dado pré-existente (achado e corrigido: `geracao_propria NOT NULL` sem default quebraria em banco real). `PROGRESS.md` reescrito do zero pra parar de arrastar informação desatualizada.
