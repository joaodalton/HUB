# APP HUB — Documento de Visão (Norte do Projeto)

> **Para o Codex (ou qualquer IA trabalhando neste repositório):** leia este arquivo INTEIRO antes de começar qualquer tarefa. Ele não muda com frequência — é a meta fixa do projeto. O que muda a cada sessão é o `PROGRESS.md`, que diz exatamente em qual tarefa você está agora.
>
> Se este arquivo e uma instrução dada em um prompt específico entrarem em conflito, este arquivo vence, a menos que o usuário diga explicitamente "isso substitui a visão do projeto".

---

## 1. O que é o APP HUB

O APP HUB organiza clientes, UCs (unidades consumidoras), usinas e documentos de uma operação de energia solar, hoje espalhados em Google Drive, planilhas e processos manuais, numa única interface.

Não é um site. Não é um dashboard interno de uso ocasional. É pra ser o **programa de trabalho diário** de quem opera o negócio.

**Motivação real (registrado 2026-07-19):** o objetivo é substituir o sistema atual (GDASH), considerado ruim, primeiro pra reduzir o trabalho manual do próprio João. A meta concreta: por volta de meados de 2027, apresentar resultado pro chefe (o que foi facilitado, o que reduziu de retrabalho) e negociar reconhecimento. Isso significa que **valor visível e usável no dia a dia bate arquitetura perfeita** — prioridade favorece o que reduz dor real primeiro, não o que é "mais correto" em teoria.

## 2. Formato final e modo de uso

**Decisão resolvida (2026-07-19, substitui a pergunta em aberto anterior):**

- **Hoje:** uso local, um usuário (o João), SQLite local, rodando como `.exe` instalável com o backend Flask empacotado via PyInstaller e subido como subprocesso pelo Tauri — exatamente como já estava desenhado.
- **Futuro (não é multi-tenant):** o HUB deve poder subir num servidor da própria Select pra outros funcionários acessarem os mesmos dados. Isso NÃO significa hospedar várias empresas diferentes no mesmo banco/servidor — se um dia isso for vendido pra outra empresa, o modelo é uma instalação separada por cliente (banco e servidor próprios cada uma), não multi-tenant.
- **Por que os dois cabem na mesma arquitetura:** o backend já é (e deve continuar sendo) uma API REST em Flask + SQLAlchemy consumida via HTTP pelo frontend. Rodar "embutido no `.exe` de um usuário só" ou "como servidor pra vários usuários" é a mesma API, mudando apenas: (1) onde o SQLite mora (arquivo local vs. caminho compartilhado — e possivelmente Postgres só quando o volume justificar, não antes), (2) se existe autenticação (não precisa enquanto for só o João local; precisa existir ANTES de qualquer segunda pessoa acessar pela rede), (3) o valor de `VITE_API_BASE_URL` (localhost vs. endereço real do servidor). Nenhuma dessas mudanças exige reescrever a lógica de negócio.
- Integração futura com o **SunHub** (sistema comercial que a Select já usa) via API — é integração entre dois sistemas independentes, cada um com seu próprio banco, não fusão de dados nem HUB assumindo o papel do SunHub.

**Regra prática pro Codex:** continuar construindo a API REST normalmente (é isso que já vinha sendo feito). Autenticação (mesmo que simples, sem tela de permissões ainda) entra **antes** de qualquer deploy em rede compartilhada — não depois. Não implementar Docker, múltiplos usuários reais ou PostgreSQL de forma especulativa antes disso ser necessário de verdade.

## 3. Regras não-negociáveis

- Nunca remover funcionalidade existente sem necessidade clara.
- Nunca mudar comportamento já implementado só por "achar melhor" — se for mudar, explicar antes.
- Sempre reaproveitar componente/serviço existente antes de criar um novo.
- Seguir a arquitetura de pastas já definida (seção 4).
- Código limpo, modular. Comentário só quando agrega valor de verdade.
- Zero duplicação de código.
- Toda credencial, URL ou porta vem de variável de ambiente — nunca hardcoded.
- Toda API e componente novo deve nascer pensando em expansão futura (não é pra jogar rápido e sujo).
- Documentação (`README.md`, este arquivo, `PROGRESS.md`) é atualizada ao final de cada tarefa, não "depois".
- Se uma mudança pode impactar algo que já existe, o Codex explica antes de aplicar — não aplica silenciosamente.
- Toda funcionalidade nova deve ser utilizável pela interface: não criar endpoint que ainda não será consumido pelo frontend na mesma tarefa/sessão; não criar tela sem o backend correspondente já ligado.
- **Arquitetura cliente-servidor (adicionado 2026-07-19):**
  - O frontend nunca é responsável pela persistência de dados permanentes — isso é papel exclusivo do backend via API REST.
  - `localStorage` só pode guardar preferência temporária de interface (ex.: aba selecionada), nunca dado de negócio (cliente, UC, usina, documento). Hoje `operationsService.ts` ainda guarda tudo em `localStorage` — isso é dívida a ser eliminada (ver seção 5), não o padrão a seguir daqui pra frente.
  - O banco permanece abstraído via SQLAlchemy pra permitir troca de SQLite por Postgres no futuro sem reescrever a lógica de negócio — mas SQLite continua sendo a escolha ativa até o volume de uso justificar trocar (ver seção 2).

## 4. Arquitetura alvo

```text
backend/
  app.py              # entrypoint Flask
  config.py
  routes/              # um blueprint por domínio
  services/            # regra de negócio, um serviço por domínio
  database/            # conexão, migrations
  models/              # entidades (SQLAlchemy ou equivalente)
  utils/
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

desktop/               # (nova, a criar na fase de empacotamento)
  # projeto Tauri (ou Electron) que embala frontend + chama o .exe do backend
```

> **Reorganização por módulo (`modules/clientes/`, `modules/ucs/` etc.) e camada Repository foram avaliadas e adiadas deliberadamente** — ver `PROGRESS.md`, seção "Decisões em aberto". Vale a pena quando `services/`/`routes/` começarem a ficar difíceis de navegar (gatilho provável: chegada do módulo de Documentos ou Financeiro), não antes.

## 5. Roadmap consolidado por versão

Esta é a **única** ordem de execução válida. Numeração alinhada com o histórico real de commits do repositório:

- **`V0.x`** = fase atual, núcleo ainda instável/incompleto. Continue incrementando `V0.x` enquanto o núcleo funcional abaixo não estiver 100% de pé.
- **`V1.0`** = o momento em que tudo que está listado abaixo como núcleo funcional estiver pronto, testado e estável.
- Os marcos seguintes (`V1.5`, `V2.0`, `V3.0`, `V4.0`, `V5.0`) mantêm o mesmo escopo, ajustado com o detalhamento da seção 7.

### V0.x → V1.0 — Núcleo funcional
- [ ] Estrutura de pastas backend/frontend batendo com a seção 4.
- [ ] Banco de dados local (SQLite) com tabelas: Cliente, UC, Usina, Documento, Categoria, Configuração, GoogleAccount, Log.
- [ ] CRUD completo (API + tela) de Cliente, UC, Usina.
- [ ] Frontend eliminando `localStorage` como fonte de dados, consumindo a API REST de verdade (ver seção 3).
- [ ] Documento por Cliente: adicionar, renomear e excluir arquivo com facilidade (ver seção 7).
- [ ] Importação em massa de Cliente/UC/Usina via planilha Excel (ver seção 7).
- [ ] Google Drive com OAuth 2.0, permitindo conectar mais de uma conta.
- [ ] Configurações consolidadas (banco de dados + aparência).
- [ ] Autenticação simples (usuário/senha ou token) — obrigatória antes de qualquer deploy fora do `localhost`, mesmo que ainda não haja tela de permissões por papel.

### V1.5 — Refinamento operacional
- [ ] Pendências (o que está faltando resolver por cliente/UC).
- [ ] Dashboard inteligente (métricas reais).
- [ ] Agenda operacional funcional com os eventos definidos na seção 7 (boas-vindas, verificação AVA, início/conclusão de rateio, primeiro desconto, fatura com desconto aplicado).

### V2.0 — Cobrança e automação de mensagens
- [ ] Integração ASAAS (geração de boleto).
- [ ] Integração com serviço de WhatsApp pra disparo automático dos eventos da Agenda.
- [ ] Cobranças automáticas.

### V3.0 — Financeiro / Rateios
- [ ] Botão de rateio automático por Usina (calcula % de consumo de cada UC conectada) — **regra de cálculo ainda não definida, precisa ser especificada com o João antes de implementar** (ver seção 7).
- [ ] Importação de fatura e planilha de rateio.
- [ ] Relatórios, exportação Excel/PDF.
- [ ] Histórico de competências.

### V4.0 — Monitoramento
- [ ] Integração com APIs de inversores (viabilidade depende da marca usada — levantar com o João antes de estimar).
- [ ] Leitura automatizada de fatura das concessionárias (robô/ML) — meta de longo prazo, alta incerteza técnica. Não estimar prazo até validar com uma prova de conceito pequena e escopada.
- [ ] Alertas automáticos de produção/falha.

### V5.0 — Automação
- [ ] Motor de automações.
- [ ] Portal do cliente (acesso externo).
- [ ] Integração com o SunHub via API, caso o comercial não seja absorvido pelo HUB (ver seção 2).

### Transversal — Empacotamento (.exe) e deploy em servidor
- [ ] Backend empacotado com PyInstaller rodando como `.exe` isolado.
- [ ] Projeto Tauri criado em `desktop/`, subindo o `.exe` do backend como subprocesso.
- [ ] Instalador gerado e testado numa máquina limpa.
- [ ] (Quando for necessário de verdade, não antes) Backend rodando como serviço de servidor comum, apontado por múltiplos clientes na rede da Select — mesma API, sem reescrever lógica de negócio.

## 6. Como o Codex deve trabalhar (o "loop")

1. No início de qualquer sessão: ler este arquivo (`VISAO.md`) e depois o `PROGRESS.md`.
2. Pegar a **primeira tarefa não marcada** do `PROGRESS.md`, na ordem em que aparece. Não pular pra frente, não fazer duas de uma vez.
3. Antes de codar: escrever, na própria tarefa do `PROGRESS.md`, qual é o critério de "pronto".
4. Implementar só o necessário pra essa tarefa — sem refatorar coisas não relacionadas "por estar ali".
5. Validar (rodar teste, rodar o app, testar a rota) antes de marcar como concluído.
6. Marcar a tarefa como `[x]` no `PROGRESS.md`, com uma linha curta do que foi feito e se algo ficou pendente/decisão foi tomada no meio do caminho.
7. Se a tarefa esbarrar numa decisão de arquitetura não coberta por este documento, o Codex registra a dúvida no `PROGRESS.md` em vez de decidir sozinho por algo difícil de reverter depois.
8. Nunca marcar uma tarefa como concluída se ela quebrou algo que funcionava antes.

## 7. Domínio de dados e funcionalidades planejadas (ditado pelo João, registrado 2026-07-19)

Esta seção existe pra não perder o detalhe de negócio que só existe na cabeça do João. Ela dá contexto de **por que** cada campo/tela existe — não é lista de tarefa (isso é a seção 5), é especificação de produto.

### Cliente
- Campos: nome, CPF, telefone, email.
- Pasta de documentos própria por cliente: adicionar, excluir e renomear arquivo precisa ser fácil (mapeia pro model `Document`: FK opcional a Cliente/UC, FK obrigatória a Categoria).

### UC (Unidade Consumidora)
- Vinculada a exatamente 1 Cliente, herda o nome dele na exibição.
- Campos: código da UC, endereço/local, CEP, data de emissão da fatura, % de rateio, tarifa, % de desconto, indicador de geração própria (sim/não), concessionária (lista aberta — pelo menos Copel, CPFL, Enel/Energisa).
- Conecta-se a uma ou mais Usinas via seletor multi-select (já existe como `PlantConnection`).

### Usina
- Tem sua própria UC.
- Campos: quanto produz, marca do inversor, telefone e email do proprietário, quanto libera pro rateio (% ou kWh — unidade ainda não decidida).
- Pode ter múltiplas UCs conectadas.
- Meta de longo prazo: API do inversor pra produção em tempo real — depende da marca usada, viabilidade não confirmada (V4.0).

### Rateio automático
- Botão na tela de Usina que calcula automaticamente a % de consumo de cada UC conectada.
- **Regra de cálculo ainda não definida** — é decisão de negócio, precisa ser especificada com o João antes de qualquer implementação (V3.0).

### Agenda
- Eventos por cliente/UC: boas-vindas, verificação do AVA, início de rateio, rateio concluído, primeiro desconto aplicado, fatura com desconto aplicado.
- Cada evento pode disparar mensagem automática — provável via API de serviço de WhatsApp especializado, em vez de reimplementar do zero (V2.0).

### Importação em massa
- Cliente, UC e Usina devem poder ser importados via planilha Excel.

### Financeiro
- Geração de boleto — integração cogitada: ASAAS (avaliada como a mais simples de integrar).
- Meta de longo prazo, alta incerteza: robô/ML pra ler fatura da concessionária e extrair dados automaticamente. Validar com prova de conceito pequena antes de comprometer prazo.
