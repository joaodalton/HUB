# HUB — Task Contract e gates nativos do Paperclip

Este é o template operacional canônico para tarefas novas do HUB. O Paperclip
preenche e classifica o contrato antes da execução. Os gates ficam na própria
tarefa, em `executionPolicy.stages`; não devem ser representados por subtarefas
de revisão ou por comentários sem autoridade de decisão.

## Template

```text
# TASK CONTRACT

Task:
Base revision:
Deliverable revision: pending
Approval required: YES | NO
Approval owner: none | <user/board responsável>
Agent:
Objective:
Context:
Files expected:
Files prohibited:
File ownership:
Depends-on:
Must preserve:
- existing functionality
- API compatibility
- tenant isolation
- RBAC
- current architecture
Acceptance:
Validation:
Security-sensitive: YES | NO
Security triggers: none | <gatilhos objetivos>
Database: YES | NO
Documentation affected:
Required reviewers:
Code Reviewer required: YES | NO
Review rationale:
Handoff-to:
```

`Base revision` é imutável durante o ciclo de correção. `Deliverable revision`
identifica exatamente a entrega revisada e deve ser preenchida antes do primeiro
gate. Qualquer alteração posterior gera nova revisão e invalida todos os
pareceres anteriores. Quando `Approval required: YES`, a aprovação também deve
referenciar a revisão final.

`Files expected` orienta o escopo. Uma dependência tecnicamente necessária fora
da lista deve ser registrada antes da edição. `Files prohibited` é uma fronteira
forte. `File ownership` declara um único escritor por arquivo; trabalhos
paralelos só podem escrever conjuntos disjuntos. O Paperclip é o único dono da
integração e da atualização final de `PROGRESS.md`.

## Classificação proporcional dos gates

| Mudança | Gates nativos obrigatórios |
|---|---|
| Backend, migration ou contrato de API | Backend Reviewer |
| Frontend | Frontend Reviewer |
| Autenticação, autorização, RBAC, tenant, endpoint, upload, documento, integração, webhook, cobrança, token, segredo, cookie, CSRF ou CORS | Security Reviewer, depois do reviewer especializado |
| Cruza camadas, altera contrato/migration com consumidores, apresenta risco relevante ou o contrato exige | Code Reviewer, por último |
| Pequena, localizada e de uma única camada | Apenas o reviewer especializado pertinente |
| Somente documentação/configuração de control plane | Sem reviewer técnico; aprovação humana apenas se o contrato marcar `Approval required: YES` |

Backend e frontend podem executar em paralelo somente quando o ownership for
disjunto e não houver dependência de contrato. Quando o frontend depende de
contrato novo ou alterado, o backend e seu gate terminam antes do frontend.

## Configuração nativa

Cada participante é o agente especializado real, e não o implementador. Exemplo
mínimo para uma mudança backend sensível e transversal:

```json
{
  "executionPolicy": {
    "mode": "normal",
    "commentRequired": true,
    "stages": [
      {
        "type": "review",
        "participants": [
          { "type": "agent", "agentId": "<backend-reviewer-id>" }
        ]
      },
      {
        "type": "review",
        "participants": [
          { "type": "agent", "agentId": "<security-reviewer-id>" }
        ]
      },
      {
        "type": "review",
        "participants": [
          { "type": "agent", "agentId": "<code-reviewer-id>" }
        ]
      }
    ]
  }
}
```

Ao terminar, o implementador envia a tarefa original para `in_review`. O
Paperclip atribui cada stage ao participante correto e registra a decisão.

- `PASS` ou `PASS_WITH_NOTES`: o reviewer atual atualiza a tarefa para `done`
  com parecer vinculado à `Deliverable revision`. O Paperclip avança para o
  próximo stage ou encerra a tarefa.
- `BLOCK`: o reviewer atual atualiza a tarefa para `in_progress`, com os achados
  bloqueantes. O Paperclip registra `changes_requested` e devolve a tarefa ao
  `returnAssignee`, preservando contrato, revisão ativa e trilha de auditoria.
- Após a correção, uma nova `Deliverable revision` volta ao mesmo stage. O
  implementador nunca aprova a própria entrega e um reviewer não decide uma
  etapa atribuída a outro participante.

`PASS_WITH_NOTES` não expande o escopo. A nota é registrada como observação ou
vira tarefa futura somente quando houver valor concreto. Após dois `BLOCK` pelo
mesmo problema, o Paperclip reavalia contrato e escopo antes de novo ciclo; o
limite nunca transforma falha em aprovação.

## Evidência e encerramento

O parecer deve declarar a `Deliverable revision`, o resultado e as verificações
realmente executadas. Uma tarefa só pode chegar a `done` quando, cumulativamente:

1. os critérios de aceite foram atendidos;
2. a validação prevista foi executada e registrada;
3. a documentação afetada foi atualizada;
4. todos os gates aplicáveis aprovaram a revisão final;
5. a aprovação humana exigida, quando houver, referencia essa mesma revisão.

O ensaio do pipeline deve registrar na tarefa original: configuração de stages,
entrada em `in_review`, `BLOCK` com retorno ao implementador, nova revisão e
`PASS` final. A evidência inclui os estados `executionState.currentParticipant`,
`returnAssignee` e `lastDecisionOutcome` observados em cada transição.
