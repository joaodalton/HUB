# HUB — Documento de Visão (Norte do Projeto)

> **Para qualquer IA trabalhando neste repositório (Claude, Codex, etc.):** leia este arquivo INTEIRO antes de começar qualquer tarefa. Ele não muda com frequência — é a meta fixa do projeto. O que muda a cada sessão é o `PROGRESS.md`, que diz exatamente em qual tarefa você está agora.
>
> **Documentos relacionados:** `PROGRESS.md` · `API_CONTRACTS.md` · `DEPLOY.md` · `RATEIO.md` · `PENDENCIAS.md` · `SPRINT_01.md` · `SPRINT_02.md` · `CONTRIBUTING.md`
>
> Se este arquivo e uma instrução dada em um prompt específico entrarem em conflito, este arquivo vence, a menos que o usuário diga explicitamente "isso substitui a visão do projeto".

---

## 1. O que é o HUB

O HUB organiza clientes, UCs (unidades consumidoras), usinas, documentos, rateio de energia, pendências operacionais, financeiro e comunicação (WhatsApp/email) de empresas de energia solar — hoje espalhados em Google Drive, planilhas e processos manuais — numa única interface.

Não é um site institucional. Não é um dashboard interno de uso ocasional. É pra ser o **programa de trabalho diário** de quem opera o negócio.

**Motivação original (2026-07-19):** substituir o sistema antigo (GDASH), considerado ruim, reduzindo o trabalho manual do próprio João.

**Motivação atual (evoluída em 2026-08-17):** o HUB deixou de ser só uma ferramenta interna da Selec Energy e virou **produto vendável pra outras empresas de geração distribuída** — daí a decisão de multi-tenancy (seção 2). Isso não muda o critério de priorização: **valor visível e usável no dia a dia continua batendo arquitetura perfeita**. Prioridade favorece o que reduz dor real de operação primeiro, não o que é "mais correto" em teoria.

---

## 2. Arquitetura e infraestrutura atual

O HUB é uma **API REST em Flask + SQLAlchemy** (backend) consumida via HTTP por um frontend em **TypeScript vanilla + Vite** (sem framework). Essa separação sempre existiu e continua sendo o contrato entre as duas camadas.

### 2.1 Onde roda hoje (produção)

- **Backend:** Render (Web Service, Gunicorn).
- **Frontend:** Render (Static Site).
- **Banco:** PostgreSQL via Neon — projeto de produção separado do projeto de dev, nunca misturar (ver `DEPLOY.md`).
- **Armazenamento de documentos:** Google Drive (upload real via API, não é mais disco local — filesystem do Render é efêmero). O caminho local antigo (`backend/uploads/`) só existe pra servir documento legado enviado antes da migração.
- **Observabilidade:** Sentry (backend + frontend), `send_default_pii=False` fixado nos dois lados.

Empacotamento desktop (Tauri/.exe) **foi avaliado e descartado como direção principal** (decisão registrada em `PROGRESS.md`, 2026-08-06). O plano de deploy é 100% cloud; não há trabalho planejado ou pendente de `.exe`/instalador local. Se isso mudar um dia, é decisão nova, não retomada de plano antigo.

### 2.2 Multi-tenant (decisão de 2026-08-17)

O HUB é **multi-tenant de verdade** — um banco só, `empresa_id` em praticamente todo model de domínio — em vez de instalação isolada por cliente. Motivo: instalação isolada não escala em custo/operação pro modelo de venda atual (cada empresa nova exigiria Render + Neon pagos próprios e migration manual por banco).

**Como o vazamento de dado entre empresas é mitigado:** não é convenção que alguém pode esquecer de seguir — é estrutural. Um listener do SQLAlchemy (`do_orm_execute` em `backend/extensions.py`) injeta `WHERE empresa_id = <empresa da sessão atual>` automaticamente em toda query feita contra qualquer model que herde de `TenantMixin`. Isso já está implementado e em produção — não é mais item de roadmap.

**Modelos com `TenantMixin`:** `Client`, `Plant`, `ConsumerUnit`, `PlantConnection`, `Document`, `Pendencia`, `PendenciaComentario`, `GoogleAccount`.

**Modelos sem `TenantMixin`, de propósito:**
- `User` — login precisa localizar o usuário pelo email antes de existir uma "empresa atual" na sessão.
- `Invitation` — o fluxo de aceitar convite roda sem sessão autenticada.

**Cadastro de empresa nova:** manual, via `backend/scripts/criar_empresa.py` (cria a Empresa + convite de owner, roda direto no servidor depois do pagamento confirmado). Self-signup público não é prioridade agora — mas ver seção 5 (V1.5-B) pra evolução planejada de todo o fluxo de cadastro/onboarding.

### 2.3 Identidade, RBAC e convites

Implementado nas Sprints 01/02 (ver `SPRINT_01.md`, `SPRINT_02.md`):

- **Empresa** é a unidade primária (tenant). `User.empresa_id` nunca vem do frontend — sempre resolvido a partir do usuário autenticado no middleware (`utils/auth.py`).
- **Roles:** `owner`, `admin`, `operator`, `financial`, `viewer` — matriz de permissões centralizada em `backend/services/permission_service.py` (`ROLE_PERMISSIONS`), não espalhada em `if` por rota.
- **Criação de usuário:** por convite (`Invitation`, token hasheado SHA-256, TTL 7 dias, single-use) ou criação direta por owner/admin (senha temporária, força troca no primeiro acesso).
- Owner nunca é criado por auto-cadastro nem por convite comum — só nasce junto com a Empresa (`criar_empresa.py`).

Este núcleo funciona, mas é o alvo direto da evolução descrita na seção 5, V1.5-B — hoje falta e-mail transacional de verdade para convite/redefinição de senha em produção estável, e a tela de Usuários/Empresas ainda não expõe tudo que o multi-tenant já suporta no banco (ex.: dados cadastrais da própria Empresa, troca de plano, limites de uso).

### 2.4 Autenticação

Cookie `HttpOnly` (não é JWT — token assinado via `itsdangerous`) + cookie CSRF duplo + rate limit no login + headers de segurança (`HSTS`, `X-Frame-Options`, etc.). Auto-cadastro público condicionado a `SIGNUP_CODE` (vazio = desligado); quando ligado, sempre cria `viewer`, nunca aceita `admin` vindo do formulário.

Fluxo de **redefinição de senha por e-mail já existe** (`ForgotPasswordPage.ts`/`ResetPasswordPage.ts`, token SHA-256, TTL 1h, single-use, editável via `EmailTemplate`) — mas depende de e-mail transacional configurado (Resend, no-op sem chave). Ver seção 5, V1.5-B, pra padronizar isso junto do resto do fluxo de cadastro.

### 2.5 Integração planejada com o SunHub

Integração futura com o **SunHub** (sistema comercial que a Selec Energy já usa) via API — dois sistemas independentes, cada um com seu próprio banco. Não é fusão de dados nem o HUB assumindo o papel do SunHub.

---

## 3. Regras não-negociáveis

- Nunca remover funcionalidade existente sem necessidade clara.
- Nunca mudar comportamento já implementado só por "achar melhor" — se for mudar, explicar antes.
- Sempre reaproveitar componente/serviço existente antes de criar um novo ("reuse before create").
- Seguir a arquitetura de pastas já definida (seção 4).
- Código limpo, modular. Comentário só quando agrega valor de verdade.
- Zero duplicação de código.
- Toda credencial, URL ou porta vem de variável de ambiente — nunca hardcoded. Ver seção 5 (V1.5-A) pra centralização de chaves de API gerenciáveis pela interface, que não substitui essa regra: chave de API por empresa fica no banco (criptografada, como já é feito hoje com `GoogleAccount.refresh_token_encrypted`), segredo de infraestrutura (banco, assinatura de sessão) continua em variável de ambiente.
- Toda API e componente novo deve nascer pensando em expansão futura.
- Documentação (`README.md`, este arquivo, `PROGRESS.md`, `API_CONTRACTS.md`) é atualizada **no mesmo commit** da mudança, não depois.
- Se uma mudança pode impactar algo que já existe, explicar o impacto antes de aplicar — nunca aplicar silenciosamente.
- Toda funcionalidade nova deve ser utilizável pela interface: não criar endpoint que ainda não será consumido pelo frontend na mesma tarefa/sessão; não criar tela sem o backend correspondente já ligado.
- **Arquitetura cliente-servidor:**
  - O frontend nunca é responsável pela persistência de dados permanentes — isso é papel exclusivo do backend via API REST.
  - `localStorage` só guarda preferência temporária de interface (ex.: aba selecionada), nunca dado de negócio. Essa dívida já foi eliminada do projeto inteiro (`localStorage` zerado, confirmado em `PROGRESS.md`) — não reintroduzir.
- **Multi-tenant:**
  - Todo model de domínio novo herda `TenantMixin`, salvo justificativa explícita documentada (mesmo padrão de `User`/`Invitation`).
  - Toda query sensível em massa (ex.: `UPDATE`/`DELETE` que afeta várias linhas) filtra `empresa_id` explicitamente no service, não confia só no filtro automático — ver exemplos em `oauth_service.py`.
  - Toda automação nova (robôs da seção 5-V6, envio de mensagem, sincronização de agenda) roda sempre no escopo de uma empresa por vez — nunca processa lote misturando empresas diferentes na mesma execução, mesmo em job em background.
- **Sessões paralelas de IA (Codex/Hermes rodando junto com Claude):** sempre inspecionar o estado real dos arquivos antes de corrigir algo — nunca assumir que o arquivo está como a última sessão deixou. GitHub Issues complementam o `PROGRESS.md` pra rastrear item pendente entre sessões paralelas sem exigir branch-per-issue.

---

## 4. Arquitetura de pastas

```text
backend/
  app.py              # entrypoint Flask (app factory, registro de blueprints)
  config.py
  extensions.py        # db, migrate, limiter, TenantMixin + listener multi-tenant
  routes/              # um blueprint por domínio
  services/            # regra de negócio, um serviço por domínio
  models/              # entidades SQLAlchemy
  migrations/           # Alembic
  scripts/              # utilitários pontuais (criar_empresa.py, migrate_sqlite_to_postgres.py)
  utils/
  assets/               # ex.: template PDF do formulário Copel (rateio)
  requirements.txt
  .env

frontend/
  src/
    pages/
    components/
    layouts/
    hooks/
    services/          # chamadas HTTP ao backend
    styles/
  package.json
  .env
```

Sem pasta `desktop/` — empacotamento nativo não é plano ativo (ver seção 2.1).

> **Reorganização por módulo (`modules/clientes/`, `modules/ucs/` etc.) e camada Repository** foram avaliadas e adiadas deliberadamente. Com a expansão de escopo prevista na seção 5 (financeiro, comunicação, robôs), o gatilho pra revisitar essa decisão fica mais próximo — reavaliar quando `services/`/`routes/` passarem de ~25 arquivos cada.

---

## 5. Roadmap consolidado por versão

> Numeração alinhada com o histórico real de commits, com sub-fases (A, B, C...) adicionadas onde o escopo de uma versão cresceu o suficiente pra precisar de ordem interna. Consulte sempre `PROGRESS.md` pro status granular e mais atualizado — esta seção é a visão de alto nível.

### V1.0 — Núcleo funcional — **fechado**
CRUD completo de Cliente/UC/Usina (com todos os campos de negócio), autenticação, RBAC multi-tenant, Google Drive OAuth com múltiplas contas, upload/organização de documentos, deploy 100% cloud (Render + Neon), `localStorage` eliminado como fonte de dado.

Pendente dentro desse escopo original:
- [ ] Importação em massa de Cliente/UC/Usina via planilha Excel — nunca foi implementada, segue como dívida.

### V1.5-A — Refinamento operacional (pendências + agenda + configurações de API)
- [x] Pendências — Sprint 1 (model, CRUD, comentários, timeline) e Sprint 2 (motor de automação: UC sem usina, cliente sem UC, campos obrigatórios, documentos obrigatórios, resolução automática).
- [ ] **Regras automáticas adicionais de pendência** — boleto vencido, lembrete de vencimento (ver `PENDENCIAS.md` 11.3/11.4), protocolo de rateio parado.
- [x] Dashboard com métricas reais (fila de pendências, vencidas, vencendo em 7 dias, concluídas no mês e indicadores operacionais por empresa).
- [ ] **Agenda operacional com backend próprio, sincronizada com Pendências e Financeiro** — hoje a Agenda só lê de `Pendencia.prazo`; precisa virar fonte única de verdade pra prazo de qualquer entidade (pendência, boleto a vencer, protocolo de rateio), sem duplicar estado. Todo evento com prazo em qualquer domínio aparece na Agenda automaticamente, e resolver/pagar/concluir o item de origem atualiza a Agenda sem passo manual extra.
- [ ] **Configurações → APIs e Integrações** vira o local único pra gerenciar toda credencial de serviço externo por empresa: Google OAuth (já existe, só muda de aba), Resend (e-mail), provedor de WhatsApp, ASAAS, e qualquer chave de robô/scraper (seção V6). Cada credencial fica guardada criptografada (mesmo padrão Fernet de `GoogleAccount.refresh_token_encrypted`), nunca em texto puro, com teste de conexão por integração — reaproveita e generaliza a rota `POST /config/database/test` que já existe.

### V1.5-B — Usuários, Empresas, e-mail e cadastro (fundação de SaaS de verdade)
Núcleo de identidade multi-tenant (seção 2.3) existe, mas foi construído pra "funcionar" — esta fase é pra deixar pronto pra operar com clientes pagantes de verdade.

- [ ] **Envio de e-mail transacional configurado e testado em produção** (Resend já integrado no código, falta ficar ativo/validado de ponta a ponta): convite de usuário, redefinição de senha, boas-vindas de empresa nova, aviso de boleto (ver V2.0). Sem isso, convite e redefinição de senha continuam existindo só como link copiado manualmente.
- [ ] **Cadastro de empresa + owner via `/empresas/registro` revisado** — hoje é público-porém-travado por `SIGNUP_CODE`; decidir com o João se o fluxo de vendas continua sendo manual (`criar_empresa.py`) ou se abre self-signup de verdade, e nesse caso conectar a um passo de cobrança/plano.
- [ ] **Tela de Empresa (dados cadastrais)** — hoje só existe o model (`nome`, `razao_social`, `cnpj`, `email`, `telefone`, `status`, `slug`); falta tela pra owner/admin editar isso, hoje só dá pra ver via API.
- [ ] **Tela de Usuários mais completa**: hoje já lista, cria, ativa/desativa; falta reenvio de convite, revogação de convite pendente, e trocar de forma amigável entre "criar direto" vs. "convidar por link" (os dois já existem no backend, a UI não deixa claro qual está sendo usado).
- [ ] **Aceite de Termos de Uso e Política de Privacidade** — obrigatório antes do primeiro acesso de qualquer usuário novo (owner na criação da empresa, demais no aceite do convite) e sempre que o texto for revisado (nova versão numerada, reaceite forçado no próximo login se a versão aceita for anterior à vigente). Registra `usuarioId`, versão do documento, data/hora e IP — vira parte do histórico de auditoria, não só um checkbox que desaparece depois de marcado.
- [ ] **Tiers de funcionalidade + volume de recurso contratável à la carte** (usuários, clientes, UCs, usinas) — ver seção 6 pro modelo completo, incluindo a tela de autosserviço pro owner ajustar volume livremente.

### V1.5-C — Comunicação: templates e WhatsApp
- [ ] **Item "Templates" na sidebar** (hoje desabilitado, "Em breve") vira tela real: lista os templates existentes (e-mail e WhatsApp juntos, com um seletor de canal), permite editar um template existente ou criar um novo, com pré-visualização. Generaliza o `EmailTemplate` (hoje só e-mail, armazenado no banco, `{{link}}` → botão estilizado) pra um model único de template com `canal` (`email` | `whatsapp`) — reaproveitar a lógica de variável/placeholder já existente, não recriar do zero.
- [ ] **Tela de WhatsApp** — inbox real dentro do HUB: ver conversas por cliente/UC, enviar mensagem usando os templates acima ou texto livre, histórico. Depende de decidir o provedor de API de WhatsApp (avaliar oficial via Meta Business API vs. serviço terceirizado — decisão de custo/estabilidade a ser tomada com o João antes de codar, mesmo padrão de cautela já usado pra ASAAS).
- [ ] Disparo automático de mensagem a partir de evento da Agenda (boas-vindas, aviso de boleto, rateio concluído) usando os templates da própria tela — isso é o que fecha o ciclo Agenda → Pendência → Notificação → Mensagem.

### V2.0 — Financeiro completo, cobrança e notificações
Financeiro deixa de ser só "geração de boleto" e vira módulo com histórico, importação e visão por cliente — sempre integrado com Pendências (que geram alertas de vencimento/atraso) e a Agenda (que mostra os prazos).

- [ ] **Model `Boleto`/`Fatura`** (nome final a definir com o João) — competência, mês de referência, mês de vencimento, valor, status (a pagar / pago / vencido), concessionária de origem, UC e cliente vinculados, arquivo do boleto (mesmo padrão de storage do `Document`, Google Drive).
- [ ] **Importação de boleto/fatura** — dois caminhos: (1) importação em lote (planilha, já previsto desde `VISAO.md` original), e (2) **upload direto dentro da página do cliente**, sem precisar passar pela tela de importação em massa — o cliente já teria uma aba/seção "Financeiro" análoga à de "Documentos" que já existe hoje em `ClientDetailView.ts`.
- [ ] **Página financeira do cliente** — histórico completo de boletos daquele cliente, com gráfico (evolução de valor pago/pendente ao longo dos meses), lista separada de "pagos" vs. "a pagar", sempre cruzando concessionária + mês de referência + mês de vencimento (os 3 já são campos do model, é questão de expor bem na UI).
- [ ] Integração ASAAS (geração de boleto de cobrança da própria Selec Energy pro cliente — não confundir com o boleto da concessionária, que é importado).
- [ ] **Notificações** ligadas ao ciclo de pendência financeira: lembrete de vencimento (N dias antes, configurável — já previsto em `PENDENCIAS.md` 11.3), boleto vencido (11.4), primeiro boleto com desconto (11.2). Cada uma dessas já tem especificação de gatilho em `PENDENCIAS.md`, falta implementar como regra automática do motor que já existe (mesmo padrão de `automacao_service.py`).
- [ ] Cobranças automáticas recorrentes (depende da integração ASAAS acima).

### V3.0 — Rateio automático multi-concessionária
O motor de cálculo (`backend/services/rateio_service.py`) já existe e está em produção pra Copel: preview por porcentagem, funil de qualificação, confirmação de seleção (wizard de 4 telas), edição de distribuição, histórico por competência, geração do formulário oficial Copel (`rateio_formulario_service.py` + `rateio_pdf_service.py`). Ver `RATEIO.md` pra especificação completa do fluxo atual.

- [ ] **Suporte às 8 maiores concessionárias do Brasil** (além de Copel — lista final a confirmar com o João, mas referência de mercado: CPFL, Enel, Light, Cemig, Coelba/Neoenergia, Celesc, Equatorial, Energisa). Isso significa generalizar o que hoje é específico da Copel:
  - `rateio_formulario_service.py`/`rateio_pdf_service.py` viram estratégia por concessionária (cada uma tem seu próprio layout de formulário e regras de anexo) — provável introduzir um "adapter" por concessionária em vez de um service monolítico.
  - Template de PDF por concessionária (hoje só existe `formulario_copel_associacao.pdf` em `backend/assets/`) — cada concessionária nova precisa do próprio arquivo oficial versionado.
  - Regras de qualificação/janela de leitura (`_checar_qualificacao`) podem variar por concessionária, não só por usina/UC como hoje.
  - `ConsumerUnit.concessionaria` e `Plant.concessionaria` já existem como campo livre — vira enum fechado alinhado à lista suportada, mantendo compatibilidade com dado já cadastrado.
- [ ] Modelo "por prioridade" (hoje só "por porcentagem" está implementado — decisão de negócio já tomada de focar em porcentagem primeiro; prioridade pode não valer a pena generalizar por concessionária ao mesmo tempo — avaliar depois da V3.0-A).
- [ ] Importação de fatura e planilha de rateio legada (por concessionária).
- [ ] Relatórios e exportação Excel/PDF do rateio.
- [ ] Estimativa automática de produção via CEP + irradiação solar (CRESESB) — hoje é 100% manual (produção mensal ou média cadastrada à mão).

### V4.0 — Monitoramento
- [ ] Integração com APIs de inversores (viabilidade depende da marca usada).
- [ ] Alertas automáticos de produção/falha.

### V5.0 — Portal do cliente
- [ ] Portal do cliente (acesso externo, somente leitura do próprio financeiro/rateio).

### V5.5 — API pública do HUB e Connectors (SunHub e outros CRMs)
Duas frentes relacionadas mas distintas — não confundir uma com a outra na implementação.

**API pública** (sistemas de fora consumindo o HUB):
- [ ] **API Key por empresa** — autenticação separada do cookie de sessão que a própria SPA usa hoje. Cada chave tem escopo (leitura / leitura+escrita) e rate limit próprio, gerenciada em Configurações → APIs (seção V1.5-A), aba "Minha API".
- [ ] Endpoints públicos versionados (`/api/public/v1/...`), documentação gerada automaticamente (OpenAPI/Swagger a partir das rotas — não escrever documentação de API à mão, ela desatualiza rápido).
- [ ] **Webhooks** — sem isso a API pública só serve pra polling. Eventos mínimos: `rateio.confirmado`, `boleto.pago`, `pendencia.criada`, `cliente.criado`. Reaproveita o padrão de log/evento que já existe em `LogService`.

**Connectors** (o HUB puxando/enviando dado de CRMs externos, incluindo SunHub):
- [ ] **Camada `Connector` genérica** — generaliza o que hoje já existe só pra Google (`oauth_service.py`, `GoogleAccount`): um registro de provedores suportados, cada um com seu fluxo de autenticação ("logar na conta" — OAuth2 quando o provedor suportar, API key simples quando não), sem reescrever o fluxo de autorização do zero a cada CRM novo.
- [ ] **Adapter por provedor** — tradução campo-a-campo entre a entidade do HUB (Cliente, UC) e a entidade equivalente do CRM externo. SunHub é o primeiro adapter real; a arquitetura já nasce pensando em RD Station, Pipedrive, HubSpot como próximos, não como caso especial do SunHub.
- [ ] **Regra de sincronização explícita por connector** — direção (HUB→CRM, CRM→HUB, bidirecional), o que fazer em conflito de dado, e log de sincronização visível pro usuário (pra responder "por que esse dado mudou/sumiu" sem precisar abrir o banco).
- [ ] SunHub como primeiro connector implementado (ver seção 2.5 — decisão de produto de manter os dois sistemas independentes continua valendo, o connector só troca dado, não funde base).

### V6.0 — Robôs de automação (visão de longo prazo, alta incerteza)
Esta fase é explicitamente **"BEM no futuro"** — não estimar prazo, não comprometer estimativa até existir prova de conceito pequena e escopada pra cada robô individualmente. Todos os três dependem de automação de navegador contra sites de terceiros (concessionárias), que quebram sem aviso quando o site muda — trate cada um como projeto de manutenção contínua, não entrega única.

- [ ] **Robô de leitura de AVA/boletos** — acessa o site da concessionária (Copel primeiro, depois as demais da V3.0), entra no AVA do cliente e baixa os boletos automaticamente, alimentando o model `Boleto` da V2.0 sem upload manual.
- [ ] **Robô de envio de rateio** — acessa o site da concessionária, preenche as informações do formulário de rateio e sobe os arquivos necessários automaticamente (hoje esse envio é manual: gerar o PDF no HUB, depois submeter à mão no site da concessionária).
- [ ] **Robô de verificação de protocolo** — consulta periodicamente o status de um protocolo já submetido (rateio, AVA, etc.) e atualiza o HUB sozinho, disparando pendência/notificação se o status mudar ou travar.

Pré-requisitos antes de começar qualquer um dos três:
- Escopo de credencial de acesso ao site da concessionária por empresa (fica em Configurações → APIs, seção V1.5-A, nunca hardcoded).
- Isolamento de execução — automação de navegador headless roda fora do processo principal do Flask, mesmo racional de isolamento já aplicado à ideia do Hermes (seção 10).
- Estratégia de fallback manual sempre disponível — o robô nunca pode ser o único caminho pra uma ação crítica (submeter rateio, por exemplo), sempre precisa dar pra fazer manual se o robô falhar.

---

## 6. Cobrança do próprio HUB — modelo detalhado

Não confundir com o financeiro da V2.0: aquele é a Selec Energy (ou qualquer empresa-tenant) cobrando **o cliente final dela** via ASAAS. Esta seção é sobre cobrar **a empresa-tenant pelo uso do HUB** — a assinatura do próprio produto. As duas coisas podem reaproveitar a mesma integração ASAAS (um único adapter de pagamento, dois contextos de cobrança diferentes), mas são fluxos de negócio separados e nunca devem se misturar no código nem na UI.

Este desenho é ponto de partida pra validar com o João — os nomes de tier e valores abaixo são exemplo, não decisão fechada.

### 6.1 Duas dimensões de cobrança, independentes uma da outra

Modelo inspirado no que o próprio GDASH já faz (o João confirmou que acha prático) — separar **o que a empresa pode fazer** de **quanto ela usa**, pra não forçar upgrade de tier só porque a empresa cresceu em quantidade de UC:

- **Tier (`Plano`)** — desbloqueia **funcionalidade**, não quantidade. A empresa escolhe o tier pelo que precisa operar, não pelo tamanho da base de clientes.
- **Volume (`LimiteContratado`)** — à la carte, por tipo de recurso (usuários, clientes, UCs, usinas). Independente do tier: uma empresa no Starter pode ter 5 usuários e 10.000 UCs se for esse o perfil dela; outra pode ter 40 usuários e 300 UCs. Cada recurso tem preço unitário próprio, e a empresa ajusta pra cima ou pra baixo quando quiser, self-service, sem depender de suporte.

### 6.2 Tiers propostos (funcionalidade, não quantidade)

Cada tier já vem com uma **quantidade incluída de graça** no preço-base — só o que passar dessa franquia é cobrado por unidade (seção 6.3). Exemplo de referência pro Starter (valores pra validar com o João, não fechados):

| Tier | O que desbloqueia | Franquia incluída (exemplo) |
|---|---|---|
| **Starter** | Núcleo completo: Cliente/UC/Usina/Documentos, Google Drive, ASAAS, WhatsApp, E-mail (templates), Pendências, Agenda, **Rateio semi-automático** (motor de cálculo + geração do formulário oficial, submissão continua manual no site da concessionária). | 10 usinas, 1.000 clientes, 1.000 UCs incluídos no preço-base. |
| **Avançado** | Starter + **Robô de leitura de AVA/boletos** (V6.0). | Franquia própria a definir (provavelmente maior que Starter). |
| **Enterprise** *(nome sujeito a ajuste)* | Avançado + **Robô de envio de rateio** + **Robô de verificação de protocolo** — ou seja, todos os robôs de automação da V6.0. | Franquia própria a definir. |

Cada tier também pode ter preço-base diferente independente do volume contratado (ex.: Enterprise custa mais só pelo acesso aos robôs, mesmo com poucos usuários) — isso é o preço do `Plano`; o preço do volume **acima da franquia** é calculado à parte (seção 6.3).

### 6.3 Estrutura de dados

- **`Plano`** — catálogo de tiers: nome, preço-base, ciclo (mensal/anual), flags de funcionalidade (`robo_ava: bool`, `robo_envio_rateio: bool`, `robo_protocolo: bool`, `acesso_api_publica: bool`, `acesso_connectors: bool` — reaproveitando os flags já previstos na V5.5), e a **franquia incluída** por recurso (`franquia_usuarios`, `franquia_clientes`, `franquia_ucs`, `franquia_usinas`) — quantidade coberta pelo preço-base, sem custo extra. Não é `TenantMixin` — catálogo global, igual `Category` hoje.
- **`PrecoRecurso`** — catálogo de preço unitário por tipo de recurso (`usuario`, `cliente`, `uc`, `usina`), cobrado só sobre o que exceder a franquia do tier — podendo ter faixa degressiva no futuro (ex.: 1–100 UCs excedentes a um preço, 101–500 a outro); no desenho inicial, preço fixo por unidade é suficiente pra validar o modelo.
- **`Assinatura`** — liga uma `Empresa` a um `Plano` (tier): `status` (`trial`, `ativa`, `atrasada`, `suspensa`, `cancelada`), `inicio_periodo_atual`, `fim_periodo_atual`, `proxima_cobranca`, `asaas_subscription_id`.
- **`LimiteContratado`** — por `Empresa`, por tipo de recurso: quantidade contratada **total** (franquia do tier + excedente pago), preço unitário vigente **no momento da contratação** do excedente (snapshot — não muda retroativamente se o preço de tabela for reajustado depois), histórico de alteração (quando aumentou/diminuiu e por quem).
- **`FaturaHub`** (nome pra não colidir com `Boleto`/`Fatura` do cliente final na V2.0) — cobrança consolidada do ciclo: preço-base do tier + soma do excedente de cada `LimiteContratado` acima da franquia, com status espelhando o webhook do ASAAS.

### 6.4 Ajuste de volume — tela própria, self-service

Tela dedicada (Configurações → Assinatura, ou seção própria na sidebar) com um controle por recurso — usuários, clientes, UCs, usinas — mostrando lado a lado: franquia incluída no tier, quantidade contratada acima da franquia, quantidade em uso agora, preço unitário do excedente, e o novo total estimado ao alterar, antes de confirmar.

- **Aumentar** — efeito **imediato** no acesso (o recurso é liberado na hora, sem esperar o próximo ciclo) e **imediato também no valor**: o total da assinatura é recalculado na hora (sem cálculo de prorata por dia — mais simples de implementar e é como a maioria dos sistemas parecidos já faz). Se já existir uma `FaturaHub` em aberto pro ciclo atual, ela é atualizada pro novo valor; se não, o valor novo já nasce correto na próxima fatura gerada. Ou seja: o aumento "gira" com o próprio ciclo de cobrança — assim que virar o mês, a fatura que o owner vai pagar já vem com o valor reajustado, sem surpresa nem cobrança avulsa separada.
- **Diminuir** — só permitido até o uso atual (não dá pra contratar menos UC do que já existe cadastrada). Redução só entra em vigor a partir do **próximo ciclo** (não é justo devolver valor já cobrado do mês corrente) — a `FaturaHub` do ciclo atual permanece no valor cheio, a próxima já nasce menor.
- Cada mudança gera uma linha no histórico do `LimiteContratado` — auditável, mesmo padrão da seção 11 (auditoria de ação).

### 6.5 Ciclo de vida da assinatura (tier)

1. **Trial** — empresa nova criada (via `criar_empresa.py` ou self-signup, se a V1.5-B decidir abrir isso) começa em `trial`, tier Starter, com volume inicial modesto pré-definido, sem cobrança, por prazo definido (ex.: 14 dias).
2. **Conversão** — ao fim do trial (ou antes, se o owner escolher upgrade), define-se o `Plano` e os `LimiteContratado` de cada recurso; `Assinatura` vira `ativa`, disparando a primeira cobrança recorrente no ASAAS (base do tier + soma dos recursos contratados).
3. **Cobrança recorrente** — ASAAS gera a fatura no ciclo; webhook de pagamento confirmado atualiza `FaturaHub.status` e mantém `Assinatura.status = ativa`.
4. **Atraso** — pagamento não confirmado até o vencimento → `Assinatura.status = atrasada`. Início de **período de carência** (ex.: 5 dias corridos) — acesso continua normal, mas gera pendência/notificação pro owner (mesmo motor de automação que já existe, reaproveitado, não uma trilha nova).
5. **Suspensão por inadimplência** — carência esgotada sem pagamento → `Assinatura.status = suspensa`. Acesso vira **somente-leitura** (consulta liberada, criação/edição bloqueada) — nunca apaga ou esconde dado da empresa. Mensagem clara na interface explicando o motivo e como regularizar.
6. **Cancelamento** — solicitado pelo owner ou por inadimplência prolongada além de um segundo prazo (ex.: 30 dias suspensa) → `status = cancelada`. Dado da empresa é preservado por um período de retenção antes de qualquer purga (ver LGPD na seção 11) — cancelar não é apagar na hora.

### 6.6 Enforcement de limite — por recurso, não por plano inteiro

- Checagem acontece **na ação que cria o recurso** (criar usuário, criar cliente, criar UC, criar usina), sempre contra a quantidade **total contratada** daquele recurso (franquia do tier + excedente pago via `LimiteContratado`) — resposta imediata pro usuário, não job periódico.
- Ao se aproximar do limite de um recurso (ex.: 90% do total contratado de UCs, franquia + excedente somados) → pendência de aviso automática sugerindo aumentar o volume daquele recurso especificamente, sem bloquear nada ainda.
- Ao estourar → bloqueia só a criação daquele recurso (ex.: botão "Nova UC" desabilitado com link direto pra tela de ajuste de volume da seção 6.4), nunca trava o sistema inteiro nem esconde dado já existente acima do limite.
- Funcionalidade de tier (robôs, API pública) segue lógica separada: não é "quase no limite", é ligado/desligado — ação bloqueada mostra qual tier desbloqueia aquilo, com link pra upgrade de tier (diferente do link de ajuste de volume).

### 6.7 Autosserviço — quem pode ver e ajustar

- **Owner/admin da empresa** — acesso completo à tela de Assinatura: tier atual, volume contratado vs. uso de cada recurso, histórico de faturas (`FaturaHub`), ajuste de volume (seção 6.4), upgrade/downgrade de tier.
- **Administrador geral da plataforma (platform admin)** — mesmo acesso que o owner tem, mas pra **qualquer empresa**, sem precisar de impersonation completa só pra mexer em assinatura. Mesmo padrão que o GDASH já usa e que o João considera prático: suporte consegue ajustar limite ou tier de uma empresa diretamente, sem depender do cliente mexer sozinho ou de simular login como aquele usuário. Essa tela de platform admin é a mesma da seção 11 (painel consolidado), só que com a aba de Assinatura de cada empresa acessível a partir dali.
- Toda alteração feita pelo platform admin em nome de uma empresa fica registrada com `viaPlatformView: true` (mesmo padrão de auditoria que a impersonation já usa hoje pra escrita cross-tenant) — nunca fica ambíguo se foi o próprio owner ou o suporte que mudou.

### 6.8 Visão de plataforma (você, administrando todas as empresas)

Complementa o painel de platform admin da seção 11: receita total, receita por tier, receita por tipo de recurso (quanto vem de volume de UC vs. usuário vs. usina — útil pra calibrar preço unitário), empresas perto do limite de algum recurso específico (oportunidade de upsell direcionado), empresas atrasadas/suspensas (risco de churn) — tudo derivado de `Assinatura`/`LimiteContratado`/`FaturaHub`, sem precisar de ferramenta de BI externa no primeiro momento.

---

## 7. Como trabalhar (o loop)

1. No início de qualquer sessão: ler este arquivo (`VISAO.md`) e depois o `PROGRESS.md`.
2. Pegar a **primeira tarefa não marcada** do `PROGRESS.md`, na ordem em que aparece. Não pular pra frente, não fazer duas de uma vez.
3. Antes de codar: escrever, na própria tarefa do `PROGRESS.md`, qual é o critério de "pronto".
4. Implementar só o necessário pra essa tarefa — sem refatorar coisas não relacionadas "por estar ali".
5. Validar (rodar teste, rodar o app, testar a rota) antes de marcar como concluído.
6. Marcar a tarefa como `[x]` no `PROGRESS.md`, com uma linha curta do que foi feito e se algo ficou pendente/decisão foi tomada no meio do caminho.
7. Se a tarefa esbarrar numa decisão de arquitetura não coberta por este documento, registrar a dúvida no `PROGRESS.md` em vez de decidir sozinho por algo difícil de reverter depois.
8. Nunca marcar uma tarefa como concluída se ela quebrou algo que funcionava antes.
9. Se estiver rodando em paralelo com outra sessão de IA (Codex, Hermes), conferir o estado real dos arquivos antes de corrigir — ver seção 3.

---

## 8. Domínio de dados — visão geral

Esta seção dá contexto de **por que** cada entidade existe. Para a lista completa e atual de campos, ver os models em `backend/models/` e o contrato de API em `API_CONTRACTS.md` — não duplicar aqui, os campos evoluem rápido demais pra manter dois lugares sincronizados manualmente.

### Já implementado
- **Empresa / User / Invitation** — identidade e RBAC multi-tenant (seção 2.3).
- **Client** — dados cadastrais e de contato; pasta de documentos própria via `Document` (FK opcional a Cliente/UC, FK opcional a Categoria).
- **ConsumerUnit (UC)** — vinculada a exatamente 1 Cliente; conecta-se a uma ou mais Usinas via `PlantConnection` (percentual de rateio, manual ou calculado).
- **Plant (Usina)** — capacidade, produção (manual ou mensal), reserva estratégica, flag de "usina coringa"; pode ter múltiplas UCs conectadas.
- **Pendencia / PendenciaComentario** — fila operacional (`tipo`: pendência/alerta/erro), ver `PENDENCIAS.md` pra especificação completa das regras.
- **RateioHistorico** — snapshot por competência de cada `PlantConnection`, ver `RATEIO.md`.
- **Document / Category** — armazenamento (hoje só Google Drive pra upload novo) e classificação.
- **GoogleAccount** — contas OAuth conectadas, refresh token criptografado (Fernet), uma ativa por vez por empresa.
- **EmailTemplate** — template editável de e-mail transacional, hoje só canal e-mail (ver V1.5-C pra generalizar pra WhatsApp também).

### Planejado (entidades novas previstas no roadmap acima — nomes sujeitos a ajuste na implementação)
- **Boleto/Fatura** (V2.0) — vínculo Cliente + UC + Concessionária, competência/mês de referência, mês de vencimento, status, arquivo.
- **ApiCredential** (V1.5-A) — credencial criptografada por empresa e por integração (Resend, WhatsApp, ASAAS, concessionária), com metadados de teste de conexão.
- **MessageTemplate** (V1.5-C) — generalização de `EmailTemplate` com campo `canal`.
- **WhatsappConversation/WhatsappMessage** (V1.5-C) — histórico de conversa por cliente/UC, ligado ao provedor escolhido.
- **AgendaEvento** ou visão consolidada equivalente (V1.5-A) — fonte única de prazo cruzando Pendência, Boleto e Protocolo de rateio, sem duplicar estado de cada origem.
- **RateioProtocolo** (V3.0/V6.0) — acompanhamento de status de submissão por concessionária, base pro robô de verificação de protocolo.
- **TermoDeUsoAceite** (V1.5-B) — registro de aceite por usuário: versão do termo, data/hora, IP. Nunca é só um `Boolean` solto no `User` — precisa do histórico completo por versão pra valer como aceite de verdade.
- **Plano / PrecoRecurso / Assinatura / LimiteContratado / FaturaHub** (seção 6) — `Plano` é o tier (funcionalidade), `LimiteContratado` é o volume à la carte por recurso (usuário/cliente/UC/usina), independentes um do outro. Ver seção 6 pra detalhamento completo do modelo.
- **ApiKey pública / Webhook** (V5.5) — chave de acesso à API pública por empresa (escopo, rate limit) e registro de webhooks configurados por evento.
- **Connector / ConnectorSync** (V5.5) — provedor externo conectado (SunHub e futuros CRMs), com log de sincronização por execução.

---

## 9. Domínio de dados — regra de concessionárias suportadas

Referência única pra "as 8 maiores concessionárias do Brasil" citadas na V3.0 — João confirma/ajusta esta lista antes de começar a implementação, ela vira enum fechado em `ConsumerUnit.concessionaria`/`Plant.concessionaria`:

1. Copel (já suportada — referência de implementação)
2. CPFL
3. Enel
4. Light
5. Cemig
6. Neoenergia (Coelba e demais distribuidoras do grupo)
7. Celesc
8. Equatorial
9. Energisa

(Lista com 9 nomes de propósito — "8 maiores" é estimativa de mercado, a lista final fecha quando o João confirmar quais realmente atendem os clientes do HUB hoje/no curto prazo. Não implementar a nona sem necessidade real.)

---

## 10. Ideias exploratórias (fora do roadmap comprometido)

Itens aqui **não são compromisso de entrega** — são possibilidades sendo avaliadas, registradas pra não se perder, mas que só viram roadmap de verdade (seção 5) quando alguém tomar a decisão explícita de promover.

- **Hermes Agent (Nous Research)** — ferramenta de terceiro sendo avaliada como possível camada de automação, principalmente pra workflows via WhatsApp (ver V1.5-C). Hoje é só ideia/exploração, não integração ativa. **Se algum dia for promovido a uso real em produção, a exigência inegociável é isolamento total**: container próprio, sem acesso direto a nenhum secret do HUB (chaves de API, `SECRET_ENCRYPTION_KEY`, credencial de banco, credencial de concessionária da seção 8). Qualquer proposta de integração real precisa passar por esse desenho de isolamento antes de qualquer linha de código — não é detalhe a resolver depois.

---

## 11. Backlog transversal (plataforma, conformidade, operação)

Itens que não pertencem a uma versão de produto específica (não são feature que o cliente-tenant pede) — são o que sustenta operar o HUB como SaaS de verdade, com múltiplas empresas pagantes. Sem numeração de versão de propósito: promover pra V-algo quando a prioridade ficar clara, mas já registrar aqui pra não perder.

- [ ] **LGPD — exportação e exclusão de dado por empresa.** Com CPF, fatura e documento pessoal real trafegando, isso deixa de ser opcional rapidamente. Precisa de: exportação completa dos dados de uma empresa sob pedido, e exclusão/anonimização quando uma empresa cancela (ver retenção após cancelamento, seção 6.2). Aplica-se tanto ao dado do tenant (Client, ConsumerUnit) quanto, futuramente, ao portal do cliente final (V5.0).
- [ ] **Painel de platform admin consolidado.** A impersonation cross-tenant (cookie `hub_platform_view`) já existe, mas falta uma tela que mostre, de forma agregada: quantas empresas ativas, uso por empresa (usuários, clientes, storage), quem está perto do limite, saúde de cada integração conectada (Drive, WhatsApp, ASAAS por empresa). Inclui a aba de Assinatura por empresa descrita em 6.7/6.8 — o platform admin ajusta tier e volume de qualquer empresa direto dali, sem precisar de impersonation completa só pra isso.
- [ ] **Busca global (Ctrl+K).** Hoje não existe nenhum "digitar nome de cliente/UC/protocolo e achar na hora" em lugar nenhum do frontend — cada tela busca só dentro do próprio domínio. Valor alto em uso diário, custo de implementação relativamente baixo (índice simples por nome/código, sem precisar de motor de busca externo no primeiro momento).
- [ ] **Auditoria de ação exposta na UI.** `LogEntry` já registra evento de sistema bem, mas num contexto multi-usuário por empresa (RBAC das Sprints 01/02), o owner vai querer responder "quem editou esse cliente, e quando" direto na tela do próprio cliente/UC/usina, não cavando em `/logs`. Pode ser o `LogEntry` existente, só exposto de forma mais acessível (ex.: aba "Histórico" já prevista como desabilitada em `ClientDetailView.ts`/`PlantsPage.ts` — na prática só liga o que já é reservado).
- [ ] **Ambiente de staging.** Hoje o caminho é só dev local → produção (Render + Neon de produção). Mudanças de risco maior (ex.: generalização de rateio multi-concessionária da V3.0, ou qualquer coisa que toque em cobrança/pagamento da seção 6) merecem um ambiente intermediário — projeto Neon + serviço Render próprios de staging, mesmo padrão de separação que já existe entre dev e produção (ver `DEPLOY.md`).

---

## 12. Dívidas técnicas conhecidas (não ligadas a uma versão específica)

- **`TenantQuery.get()` / ferramentas de IA externas em paralelo:** já causou pelo menos um bug real em produção (fallback quebrado em `extensions.py`, corrigido). Qualquer alteração em `extensions.py`/autenticação feita por uma sessão de IA diferente precisa ser revisada com atenção redobrada antes de aceitar — não assumir que está correta só porque compilou.
- **Percentual disponível da usina:** `Plant.percentual_disponivel_efetivo()` já resolve automaticamente entre valor manual (campo antigo) e cálculo real (100% − reserva) quando há produção cadastrada — mas o campo manual antigo ainda existe como fallback. Revisar se ainda faz sentido manter os dois caminhos quando o rateio automático (V3.0) estiver mais maduro.
- **`Setting` como storage genérico:** usado hoje pra aparência, buffer de rateio, categorias extras de pendência e state pendente de OAuth. Com a chegada de `ApiCredential` (V1.5-A) e `MessageTemplate` (V1.5-C), a tendência é `Setting` parar de crescer e as credenciais/config específicas ganharem tabela própria — não empurrar mais tipo novo de configuração pra dentro de `Setting` a partir de agora.
- **Testes automatizados:** não existe suíte configurada (decisão deliberada, prioriza valor visível). Exceção: qualquer lógica de cálculo financeiro (rateio, boletos) — erro ali tem custo real pro cliente, então isso deixa de ser opcional assim que uma mudança tocar em `rateio_service.py` ou no futuro `boleto_service.py`.
