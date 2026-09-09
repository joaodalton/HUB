# HUB — Regras de execução para agentes

## Fonte de verdade e ordem de leitura

1. Leia `VISAO.md` inteiro antes de iniciar uma tarefa. Ele é a visão canônica.
2. Leia `PROGRESS.md` para saber o estado comprovado e a próxima entrega.
3. Consulte `API_CONTRACTS.md`, `PENDENCIAS.md`, `RATEIO.md`, `SECURITY.md` e `DEPLOY.md` quando a mudança tocar seus domínios.
4. Inspecione os contratos e o código existente relacionado à tarefa antes de implementar.

Em caso de conflito, siga esta ordem de precedência:

1. instrução explícita do usuário na tarefa atual;
2. `VISAO.md`;
3. documentação específica do domínio;
4. contratos e código existente.

Se documentação e implementação divergirem de forma relevante para a tarefa, não escolha silenciosamente. Identifique a divergência e determine se ela exige decisão do usuário conforme as regras de autonomia deste arquivo.

---

## Prioridade de entrega

1. Segurança, isolamento por empresa, recuperação de regressões e migrations.
2. Fluxos operacionais usáveis de ponta a ponta, incluindo backend, frontend e documentação na mesma entrega.
3. V1.5 conforme `VISAO.md`, depois V2 financeiro e os itens posteriores na ordem definida pela visão.

Não declarar uma tarefa concluída sem evidência de validação registrada em `PROGRESS.md`.

---

## Papel do agente

O agente atua principalmente como **implementador técnico do HUB**.

A arquitetura de produto, as regras de negócio e o comportamento esperado são definidos pela fonte de verdade descrita neste arquivo.

O agente é responsável por descobrir **como e onde implementar** a mudança dentro da arquitetura existente.

Antes de modificar código:

1. leia a especificação completa da tarefa;
2. siga a ordem de leitura definida neste arquivo;
3. investigue a implementação atual;
4. localize dependências e consumidores;
5. reutilize estruturas existentes;
6. implemente a menor mudança completa capaz de atender ao objetivo;
7. valide a implementação;
8. revise o diff;
9. atualize a documentação necessária.

**Investigue amplamente, altere somente o necessário.**

Quando houver acesso ao repositório e autorização para executar a tarefa, não responda apenas com instruções de implementação. Implemente a mudança.

---

## Orquestração em ondas

Use os perfis em `.codex/agents/` conforme o domínio:

* backend;
* frontend;
* revisão de backend;
* revisão de frontend;
* revisão geral;
* segurança.

Só paralelize tarefas quando elas não dependerem umas das outras e os conjuntos de arquivos forem disjuntos.

Para cada tarefa, declare:

```text
Files:
Depends-on:
```

Se houver dúvida sobre dependência ou sobreposição de arquivos, execute em série.

Implementadores não fazem commit em paralelo. O orquestrador integra e valida uma tarefa por vez.

Revisões somente de leitura podem ocorrer em paralelo quando forem independentes.

---

## Autonomia e pontos que exigem decisão do usuário

O agente pode decidir autonomamente:

* padrões técnicos de implementação;
* detalhes de UX que não alterem regra de negócio;
* textos de interface;
* organização interna compatível com a arquitetura existente;
* testes;
* migrations reversíveis;
* correções técnicas necessárias para completar a tarefa dentro do escopo.

Solicite decisão do usuário antes de:

* alterar regras de negócio;
* alterar comportamento de produto não definido na especificação;
* disparar automações com efeito externo;
* utilizar credenciais ou dados reais;
* integrar pagamentos ou novos terceiros;
* enviar mensagens reais;
* executar deploy;
* realizar migration destrutiva ou transformação irreversível de dados.

Não solicitar ao usuário decisões que possam ser determinadas com segurança pela especificação, documentação ou código existente.

---

## Regras técnicas obrigatórias

* Preservar identificadores técnicos, tenants, slugs, URLs e dados persistidos, salvo decisão explícita.
* Toda consulta, agregação e mutação de domínio deve respeitar a empresa autenticada.
* IDs pertencentes a outro tenant devem responder como recursos inexistentes.
* Nunca confiar em `empresa_id` enviado pelo frontend como mecanismo de autorização.
* Nunca registrar, retornar ou expor segredos.
* Segredos de infraestrutura devem permanecer em variáveis de ambiente.
* Credenciais específicas por empresa devem utilizar armazenamento cifrado.
* Não introduzir persistência de dados de negócio no frontend ou em `localStorage`.
* Não remover funcionalidades existentes.
* Não alterar comportamentos fora do objetivo da tarefa sem necessidade.
* Não criar arquitetura paralela quando já existir padrão equivalente no HUB.
* Não introduzir dependências novas sem necessidade.
* Uma funcionalidade só está pronta quando interface e API correspondentes estiverem conectadas, quando ambas fizerem parte do fluxo.
* Atualizar `API_CONTRACTS.md` no mesmo commit de qualquer alteração de contrato ou endpoint.
* Atualizar `PROGRESS.md` no mesmo commit de qualquer entrega.
* Atualizar também a documentação operacional ou de domínio afetada.

---

## Preservação e escopo

Antes de criar novo model, service, route, componente, hook, helper, utilitário ou abstração, procure implementação existente que possa ser reutilizada ou estendida.

Evite:

* refatorações não relacionadas;
* abstrações prematuras;
* duplicação de regras de negócio;
* dependências novas sem necessidade;
* mudanças estéticas fora do escopo;
* renomeações sem benefício funcional;
* alterações de contratos não solicitadas;
* reescrita de módulos funcionando apenas por preferência técnica.

Quando encontrar um problema fora do escopo, registre-o como observação em vez de corrigi-lo automaticamente.

Pode corrigi-lo diretamente somente quando o problema:

* impedir a implementação;
* causar regressão direta na tarefa;
* representar vulnerabilidade crítica relacionada à alteração.

**Menor mudança correta e completa > grande refatoração.**

---

## Contratos e dependências

Antes de alterar comportamento existente, localize seus consumidores.

Preserve sempre que possível:

* endpoints;
* métodos HTTP;
* nomes de campos;
* tipos;
* formatos de request e response;
* códigos HTTP;
* identificadores persistidos;
* contratos utilizados pelo frontend;
* compatibilidade com dados existentes.

Quando a tarefa exigir mudança de contrato:

1. identifique todos os consumidores relevantes;
2. atualize os consumidores afetados;
3. atualize `API_CONTRACTS.md`;
4. valide o fluxo completo.

Não assuma nomes de arquivos, funções, campos, endpoints ou models. Verifique o repositório.

---

## Banco de dados

Antes de alterar um model persistente:

1. verifique o schema atual;
2. verifique migrations relacionadas;
3. considere os dados existentes;
4. determine se uma migration Alembic é necessária;
5. avalie compatibilidade de upgrade.

Evite migrations destrutivas.

Mudanças devem preservar dados existentes, salvo instrução explícita em contrário.

Nunca considere uma alteração de model concluída quando uma migration necessária estiver ausente.

Quando schema ou dados anteriores forem afetados, valide tanto:

* criação/upgrade a partir de banco vazio;
* upgrade de banco representando o estado anterior.

---

## Implementação de tarefas

A especificação da tarefa informa principalmente **o que deve ser construído**.

O agente deve determinar **onde e como implementar** analisando o repositório.

Arquivos mencionados na tarefa são referências de escopo, não necessariamente a lista completa de arquivos necessários.

O agente pode modificar dependências adicionais quando forem necessárias para completar corretamente a implementação, desde que permaneçam dentro do objetivo da tarefa.

Não transforme lacunas da especificação em novas regras de produto.

Quando houver várias soluções tecnicamente válidas, priorize:

1. arquitetura e padrões existentes no HUB;
2. segurança e isolamento multi-tenant;
3. compatibilidade;
4. reutilização;
5. menor impacto;
6. simplicidade;
7. manutenibilidade.

Somente solicite decisão do usuário nos casos definidos em **Autonomia e pontos que exigem decisão do usuário**.

---

## Implementação completa

Não considere uma tarefa concluída apenas porque a alteração principal foi implementada.

Verifique e atualize, quando necessários, todos os pontos afetados pelo fluxo:

* backend;
* frontend;
* contratos;
* banco e migrations;
* testes;
* documentação.

Não deixe código temporário, mocks, TODOs, fallbacks ou implementações parciais para completar posteriormente, salvo quando a própria especificação da Sprint definir explicitamente uma entrega parcial.

Não utilize mocks ou fallbacks permanentes para mascarar integração incompleta.

Se uma parte necessária não puder ser concluída:

1. informe claramente a limitação;
2. explique o que permanece pendente;
3. não apresente o fluxo como completamente implementado;
4. não registre a funcionalidade como concluída em `PROGRESS.md`.

---

## Validação mínima

Execute validação proporcional ao risco antes de entregar.

### Backend — suíte de regressão

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s backend\tests
```

### Histórico Alembic em SQLite vazio

```powershell
.\.venv\Scripts\python.exe -m unittest backend.tests.test_sqlite_migrations
```

### Frontend — build de produção

```powershell
npm --prefix frontend run build
```

Além da validação mínima:

* alterações de tenancy ou RBAC devem incluir teste com pelo menos duas empresas;
* alterações financeiras devem incluir testes de cálculo e cenários de erro;
* migrations devem ser validadas em banco vazio;
* quando schema ou dados existentes forem tocados, validar também upgrade a partir do estado anterior;
* alterações de contratos devem validar os consumidores afetados;
* correções de regressão devem incluir, quando viável, teste que reproduza o problema corrigido.

Nunca afirmar que teste, build, migration ou validação passou se não foi realmente executado.

---

## Revisão antes da entrega

Antes de considerar uma implementação concluída:

1. revise `git diff`;
2. verifique alterações acidentais;
3. procure duplicação introduzida;
4. verifique imports e código não utilizados;
5. verifique referências quebradas;
6. revise contratos afetados;
7. revise isolamento por empresa;
8. verifique migrations;
9. execute a validação proporcional ao risco;
10. atualize a documentação exigida;
11. registre evidência de validação em `PROGRESS.md`.

Não reverta alterações existentes do usuário que não pertençam à tarefa.

Não execute operações Git destrutivas sem autorização explícita, incluindo:

* `git reset --hard`;
* force push;
* exclusão de branches;
* limpeza destrutiva;
* reescrita de histórico compartilhado.

---

## Formato da entrega do agente

Após implementar uma tarefa, responda de forma objetiva.

### Implementado

Resumo do comportamento entregue.

### Arquivos alterados

Arquivos criados, modificados ou removidos e sua finalidade.

### Validação

Comandos, testes, builds e verificações realmente executados, com seus resultados.

### Impactos

Comportamentos existentes potencialmente afetados e como a compatibilidade foi preservada.

### Observações

Problemas encontrados fora do escopo, limitações ou pontos que mereçam Sprint futura.

### Documentação

Documentos atualizados, incluindo `PROGRESS.md` quando aplicável.

Não reproduza arquivos completos na resposta quando eles já tiverem sido modificados diretamente no repositório.

---

## Regra final

A tarefa informa **o que deve ser construído**.

`VISAO.md` informa **o que o HUB deve ser**.

A documentação de domínio informa **as regras específicas do sistema**.

O repositório informa **como o HUB está implementado atualmente**.

O agente deve determinar **onde e como implementar** respeitando essas fontes e sua ordem de precedência.

**Entenda → investigue → implemente → teste → revise → documente.**
