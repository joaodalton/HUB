# APP HUB — Documento de Visão (Norte do Projeto)

> **Para o Codex (ou qualquer IA trabalhando neste repositório):** leia este arquivo INTEIRO antes de começar qualquer tarefa. Ele não muda com frequência — é a meta fixa do projeto. O que muda a cada sessão é o `PROGRESS.md`, que diz exatamente em qual tarefa você está agora.
>
> Se este arquivo e uma instrução dada em um prompt específico entrarem em conflito, este arquivo vence, a menos que o usuário diga explicitamente "isso substitui a visão do projeto".

---

## 1. O que é o APP HUB

O APP HUB organiza clientes, UCs (unidades consumidoras), usinas e documentos de uma operação de energia solar, hoje espalhados em Google Drive, planilhas e processos manuais, numa única interface.

Não é um site. Não é um dashboard interno de uso ocasional. É pra ser o **programa de trabalho diário** de quem opera o negócio.

## 2. Formato final obrigatório

O produto final é um **executável instalável (.exe no Windows)**. O usuário:
- abre um ícone, não um navegador;
- não roda comando nenhum;
- não sabe (nem precisa saber) que por trás existe um backend Flask e um frontend Vite.

**Decisão de arquitetura já tomada pra viabilizar isso** (mude se tiver motivo forte, mas não deixe implícito):
- O backend Flask é empacotado como um `.exe` standalone via **PyInstaller**.
- O frontend (Vite/TS) e o empacotador desktop (**Tauri**, preferido por ser mais leve que Electron para esse tipo de app de gestão; pode trocar por Electron se precisar de algo mais maduro/testado) sobem esse `.exe` do backend como subprocesso local ao abrir o app.
- Comunicação entre frontend e backend continua via HTTP local (`localhost:8000`), como já é hoje — isso não muda, só passa a rodar dentro do pacote instalado em vez de dois terminais abertos manualmente.

**Pergunta em aberto pro usuário responder (isso decide a Fase 2 e a Fase 7 em diante):**
Este app vai rodar **local, uma máquina, um usuário por vez** (aí SQLite local resolve tudo e o executável fica 100% autocontido), ou em algum momento vai precisar de **múltiplos usuários/máquinas vendo os mesmos dados** (aí precisa de banco em servidor, e o "executável" vira um cliente que depende de rede — isso muda a arquitetura de forma relevante)? Até essa resposta vir, o Codex deve seguir com SQLite local como padrão, porque é o que sustenta a promessa de "executável instalável" sem infraestrutura extra.

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

> **Nota importante de estado atual:** foi identificado que os arquivos deste Project (Claude) estão com nome e conteúdo trocados entre si (ex.: `app.py` continha texto do README, `package.json` continha código Python). Isso é um problema de sincronização deste espaço de arquivos, não necessariamente do seu repositório real. **Antes do Codex confiar em qualquer leitura de arquivo aqui, confirme contra o repositório local de verdade.**

## 5. Roadmap consolidado por versão

Esta é a **única** ordem de execução válida. Numeração alinhada com o histórico real de commits do repositório:

- **`V0.x`** = fase atual, núcleo ainda instável/incompleto (é onde o projeto está agora — commits como `V0.5`, `V0.6.5 "não está acabada"`). Continue incrementando `V0.x` enquanto o núcleo funcional abaixo não estiver 100% de pé.
- **`V1.0`** = o momento em que tudo que está listado abaixo como núcleo funcional estiver pronto, testado e estável. É aí que a versão "vira" 1.0 de verdade.
- Os marcos seguintes (`V1.5`, `V2.0`, `V3.0`, `V4.0`, `V5.0`) mantêm o mesmo escopo que já estava definido, só ajustando o rótulo.

### V0.x → V1.0 — Núcleo funcional
- [ ] Estrutura de pastas backend/frontend batendo com a seção 4 (verificar o que já existe e completar o que falta: `models/`, `database/`).
- [ ] Banco de dados local (SQLite) com tabelas: Cliente, UC, Usina, Documento, Categoria, Configuração, GoogleAccount, Log.
- [ ] CRUD completo (API + tela) de Cliente, UC, Usina — mantendo tudo que já funciona hoje (popup de cadastro, acordeão de UC, conexão UC↔Usina, etc.).
- [ ] Google Drive com OAuth 2.0 (substitui `credentials.json`), permitindo conectar mais de uma conta.
- [ ] Módulo de Documentos ligado ao banco (não mais só Drive solto): upload, busca, categoria, vínculo com Cliente/UC.
- [ ] Configurações consolidadas (banco de dados + aparência, como já existe).

### V1.5 — Refinamento operacional
- [ ] Pendências (o que está faltando resolver por cliente/UC).
- [ ] Dashboard inteligente (métricas reais, não só cards estáticos).
- [ ] Agenda operacional funcional (hoje é rascunho estático).

### V2.0 — Cobrança
- [ ] Integração ASAAS.
- [ ] WhatsApp (notificações).
- [ ] Cobranças automáticas.

### V3.0 — Financeiro / Rateios
- [ ] Importação de fatura e planilha de rateio.
- [ ] Cálculo automático de rateio por UC/Usina.
- [ ] Relatórios, exportação Excel/PDF.
- [ ] Histórico de competências.

### V4.0 — Monitoramento
- [ ] Integração com APIs de inversores.
- [ ] Alertas automáticos de produção/falha.

### V5.0 — Automação
- [ ] Motor de automações.
- [ ] Portal do cliente (acesso externo, fora do escopo do executável desktop — provavelmente vira um serviço web à parte).

### Transversal — Empacotamento (.exe)
Não é uma "fase no final" — deve ser validada já no v1.0, mesmo que de forma simples, pra garantir que a arquitetura escolhida (PyInstaller + Tauri) realmente funciona antes de o projeto crescer em cima dela.
- [ ] Backend empacotado com PyInstaller rodando como `.exe` isolado (testar fora do ambiente de dev).
- [ ] Projeto Tauri criado em `desktop/`, subindo o `.exe` do backend como subprocesso e carregando o frontend buildado.
- [ ] Instalador gerado e testado numa máquina limpa (sem Python/Node instalado).

## 6. Como o Codex deve trabalhar (o "loop")

1. No início de qualquer sessão: ler este arquivo (`VISAO.md`) e depois o `PROGRESS.md`.
2. Pegar a **primeira tarefa não marcada** do `PROGRESS.md`, na ordem em que aparece. Não pular pra frente, não fazer duas de uma vez.
3. Antes de codar: escrever, na própria tarefa do `PROGRESS.md`, qual é o critério de "pronto" (ex.: "rota testada com curl retornando 200 e persistindo no banco").
4. Implementar só o necessário pra essa tarefa — sem refatorar coisas não relacionadas "por estar ali".
5. Validar (rodar teste, rodar o app, testar a rota) antes de marcar como concluído.
6. Marcar a tarefa como `[x]` no `PROGRESS.md`, com uma linha curta do que foi feito e se algo ficou pendente/decisão foi tomada no meio do caminho.
7. Se a tarefa esbarrar numa decisão de arquitetura não coberta por este documento (ex.: qual biblioteca usar), o Codex registra a dúvida no `PROGRESS.md` em vez de decidir sozinho por algo que é difícil de reverter depois.
8. Nunca marcar uma tarefa como concluída se ela quebrou algo que funcionava antes.
