# APP HUB — Como contribuir (humanos e agentes de IA)

> Leia isso depois de `VISAO.md` e `PROGRESS.md`. Este arquivo é sobre **processo** — como o trabalho é registrado e entregue. `VISAO.md` continua sendo o norte do produto; `PROGRESS.md`, o estado atual.

---

## 1. Fluxo de trabalho

Não usamos branch-por-tarefa nem PR obrigatório — o MCP do GitHub não está funcional neste projeto hoje, então esse fluxo viraria burocracia sem automação por trás. O padrão real é mais simples:

1. Trabalho no dia a dia acontece direto (aqui no chat, ou como commit direto quando aplicável). Não precisa de Issue pra tudo.
2. **Vira Issue** quando algo é identificado mas fica pra depois: bug conhecido não resolvido na hora, decisão de produto adiada, TODO técnico, campo/funcionalidade faltando que não é a tarefa atual.
3. Se o trabalho resolve uma Issue existente, a mensagem de commit inclui `Closes #N` (ou `Fixes #N`) — o GitHub fecha a Issue sozinho ao chegar na `main`.
4. `PROGRESS.md` continua sendo a fonte de verdade principal do que foi feito — é o que qualquer sessão nova (humano ou IA) lê primeiro. Issues são complemento pra itens pequenos e pontuais que não merecem virar uma linha do roadmap principal.

**Regra pra qualquer agente de IA (Claude, Codex, Cursor, etc.) trabalhando neste repositório:** ao identificar algo que fica pendente e não vai ser resolvido na tarefa atual, sinalize ao usuário que aquilo é candidato a Issue, em vez de deixar como comentário solto no código ou esquecer. Não crie Issue automaticamente sem o usuário confirmar — quem decide o que vale rastrear é ele.

---

## 2. Duas frentes em paralelo

Este projeto às vezes é trabalhado em mais de uma sessão/conta ao mesmo tempo (ex.: uma frente cuidando do núcleo, outra de uma feature grande isolada, como o Rateio). Nesse cenário:

- Issues e `PROGRESS.md` são o ponto de sincronia entre as frentes — qualquer decisão que afete a outra frente (nome de campo, formato de dado, contrato de API) deve ser registrada em um dos dois, não só combinada verbalmente numa sessão.
- Antes de tomar uma decisão que a outra frente vai depender (ex.: nome de status, categoria, formato de payload), prefira registrar a decisão em `PROGRESS.md` ou numa Issue antes de implementar, não depois.

---

## 3. Observabilidade

Erros de produção (backend e frontend) são reportados ao Sentry (ver `SENTRY_DSN` em `.env`). Isso significa:

- Não é preciso testar tudo manualmente pra descobrir que algo quebrou em produção — olhe o Sentry primeiro quando desconfiar de um bug.
- `send_default_pii=False` está fixado de propósito nos dois lados (backend e frontend) — nenhum dado pessoal de cliente vai automaticamente pro Sentry. Não mude isso sem decisão explícita.

---

## 4. Qualidade mínima antes de entregar

Sem suíte de testes automatizados configurada ainda (decisão deliberada — ver `VISAO.md`, prioriza valor visível sobre arquitetura perfeita neste estágio). Até lá, todo trabalho de frontend passa por:

```powershell
cd frontend
npx tsc --noEmit
npm run build
```

Quando o Rateio (ou qualquer lógica que envolva cálculo financeiro) for implementado, **isso muda**: teste automatizado deixa de ser opcional para essa área específica, mesmo sem suíte geral configurada — erro em cálculo financeiro tem custo real pro cliente.

---

## 5. Documentação viva

Sempre que uma tarefa mexe em contrato de API, `API_CONTRACTS.md` é atualizado no mesmo commit — não depois. Mesma regra para `PROGRESS.md` quando a tarefa fecha algo do roadmap.