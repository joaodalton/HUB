# HUB — próximos passos (handoff de continuidade)

> Gerado em 2026-10-17 pra iniciar sessão nova com contexto limpo. Branch atual: `feat/b2-object-storage-endpoint`. HEAD: `cc3b489`.

## O que já está pronto e mesclado

- **Feature Relatórios (Google Docs/Sheets/Slides)** — completa, revisada (backend, frontend, segurança, review final de branch) e mesclada local em `feat/b2-object-storage-endpoint`. Detalhes completos em `handoffs/2026-10-16-relatorios-google.md`.
- **Storage B2/Backblaze** — mesclado antes, handoff em `handoffs/2026-10-15-storage-b2-backblaze.md`.

## Riscos abertos da feature de Relatórios (ainda não validados)

Copiados do handoff `2026-10-16` — nenhum foi ainda testado com credencial Google real:

1. **Pasta de destino pode falhar sob escopo `drive.file`** — a pasta raiz configurada do tenant não foi criada pelo próprio app, então `files.create` pode ser rejeitado. Precisa testar com conta Google real; se falhar, criar subpasta própria do HUB ou cair pro `My Drive` raiz.
2. **Contas conectadas antes da redução de escopo** mantêm o escopo antigo até reconectar/revogar manualmente — não há migração automática.
3. **Verificação do app pelo Google** — `drive.readonly` é escopo "restricted", exige avaliação de segurança (CASA) pra uso em produção com conta de terceiro; `drive.file` é "non-sensitive". Ação externa, fora do controle do time.
4. **`backend/.env.example`** documenta escopo `drive` completo como exemplo — checar contra a env var real de produção antes de ir ao ar.
5. **Arquivos órfãos no Drive** se a geração falhar no meio (Doc/Sheet/Slide criado mas conteúdo não escrito) — sem limpeza automática, aceito como débito operacional (dado é do próprio tenant).
6. **Geração síncrona, sem fila de job** — relatório grande pode dar timeout do request. Parcialmente mitigado pelo filtro de competência adicionado no fix final, mas não resolvido de raiz.

## Pendências de teste (não cobertas por mock)

- **Nenhum teste rodou contra a API Google real** — toda a suíte de testes da feature de Relatórios usa mocks. Precisa validar manualmente, com conta Google de teste:
  - Criar Doc/Sheet/Slide de verdade na pasta configurada (valida o risco #1 acima).
  - Reconexão de conta com scope antigo → fluxo de aviso + botão "Reconectar" end-to-end no browser.
  - Geração de relatório Financeiro/Rateio/Cadastro com dados reais de uma empresa de teste, abrindo o `webViewLink` retornado.
- **`backend/tests/test_delete_user_physical.py`** — arquivo untracked, não commitado em nenhuma branch, com 5 falhas conhecidas. Pré-existente, não relacionado a nenhuma feature recente. Decidir: commitar e corrigir, ou descartar.
- Build frontend e suíte backend passam limpos fora desse arquivo (733 backend / 34 frontend na branch mesclada).

## Melhorias de polimento ainda não planejadas/implementadas

Da conversa sobre "o que falta pro HUB funcionar 100%" (nenhuma dessas tem spec ou plano escrito ainda — precisam de brainstorming antes de implementar):

- Fila assíncrona de job para relatórios grandes (explicitamente fora de escopo na entrega atual).
- Exportação em `.docx`/`.xlsx`/`.pptx` (hoje só gera Google nativo).
- Relatórios adicionais além dos 3 atuais (Financeiro, Rateio, Cadastro) — ex. estimativa de produção.
- Revisão geral de performance/otimização de alguma etapa do fluxo (não detalhado, mencionado em aberto).
- Outras melhorias gerais de polimento do HUB mencionadas em conversa anterior, mas nunca reduzidas a uma lista concreta — próxima sessão deve perguntar ao usuário quais áreas priorizar (ex.: revisar `VISAO.md`/`PROGRESS.md` de novo com o estado atual) antes de propor plano.

## Estado do working tree (não commitado)

Mudanças não commitadas presentes na árvore no momento deste handoff — revisar antes de continuar:

```
M .claude/settings.json
M .claudian/claudian-settings.json
M .mcp.json
M ARCHITECTURE.md
M PROGRESS.md
M README.md
M backend/.env.example
?? REGRAS.md
?? Response
?? backend/Status
?? backend/grande
?? backend/somente
?? backend/tests/test_delete_user_physical.py
?? void
?? {,+
```

Os arquivos `Response`, `backend/Status`, `backend/grande`, `backend/somente`, `void`, `{,+` têm nomes suspeitos/não convencionais — checar conteúdo antes de decidir se são lixo, scratch, ou algo a commitar.

## Regras globais ativas (lembrar na próxima sessão)

- Orquestrador, não implementador — toda implementação delegada a subagentes especialistas (`hub-backend-developer`, `hub-frontend-developer`, etc.), nunca escrever código de feature diretamente.
- Brainstorm antes de delegar — usar skill `superpowers:brainstorming` antes de qualquer dispatch de subagente de implementação.
- Subagentes sempre em Sonnet 5, não Opus.
- `git push`/`git merge` exigem confirmação explícita (modo "ask" no `.claude/settings.json`).
- Nada foi enviado pro remoto ainda — merge da feature de Relatórios é só local.
