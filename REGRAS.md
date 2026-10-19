# REGRAS — Time de agentes HUB

Seis papéis especializados, versionados em `.claude/agents/hub-*.md` e
descritos em detalhe em `.paperclip-agent-bundles/`: `hub-backend-developer`,
`hub-frontend-developer` (implementação), `hub-backend-reviewer`,
`hub-frontend-reviewer`, `hub-code-reviewer`, `hub-security-reviewer`
(revisão, somente leitura).

## Regra central

- Um implementador nunca aprova a própria entrega.
- Um revisor nunca edita, formata, aplica patch, comita, faz deploy ou
  atualiza documentação — os quatro `hub-*-reviewer` têm `Write`/`Edit`
  removidos do `tools` da própria definição, não é só instrução de prompt.
- Toda tarefa roda dentro de um Task Contract (`docs/TASK_CONTRACT.md`):
  `Files expected` define o escopo, `Files prohibited` é fronteira dura,
  `File ownership` garante um único escritor por arquivo.
- O parecer de um revisor (`PASS` / `PASS_WITH_NOTES` / `BLOCK`) vale só para
  a `Deliverable revision` exata revisada — qualquer mudança depois invalida
  o parecer.

## Gate por tipo de mudança

| Mudança | Gate obrigatório |
|---|---|
| Backend, migration ou contrato de API | `hub-backend-reviewer` |
| Frontend | `hub-frontend-reviewer` |
| Autenticação, RBAC, tenant, endpoint, upload, webhook, cobrança, token, segredo | `hub-security-reviewer`, depois do reviewer especializado |
| Cruza camadas, contrato com consumidores, risco relevante | `hub-code-reviewer`, por último |
| Pequena, localizada, uma única camada | só o reviewer especializado |

Backend e frontend podem rodar em paralelo só com `File ownership` disjunto e
sem dependência de contrato novo.

## Convenção de nome

Os 6 agentes usam o prefixo `hub-` de propósito — o diretório
`.claude/agents/{browser,consensus,core,sparc,swarm,testing}/` é de outro
framework de agentes já presente no projeto (não confundir nem apagar). Rode
`/agents` depois de qualquer mudança nesta pasta e confirme que nenhum nome
colide antes de delegar uma tarefa.

Detalhe completo de cada papel: `.paperclip-agent-bundles/README.md` e
`docs/TASK_CONTRACT.md`.
