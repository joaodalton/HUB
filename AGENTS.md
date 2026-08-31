# HUB — regras de execução para agentes

## Fonte de verdade e ordem de leitura

1. Leia `VISAO.md` inteiro antes de iniciar uma tarefa. Ele é a visão canônica.
2. Leia `PROGRESS.md` para saber o estado comprovado e a próxima entrega.
3. Consulte `API_CONTRACTS.md`, `PENDENCIAS.md`, `RATEIO.md`, `SECURITY.md` e `DEPLOY.md` quando a mudança tocar seus domínios.

Em conflito, a instrução explícita do usuário prevalece; caso contrário, `VISAO.md` prevalece sobre os demais documentos.

## Prioridade de entrega

1. Segurança, isolamento por empresa, recuperação de regressões e migrations.
2. Fluxos operacionais usáveis de ponta a ponta (backend, frontend e documentação no mesmo commit).
3. V1.5 conforme `VISAO.md`, depois V2 financeiro e os itens posteriores na ordem definida pela visão.

Não declarar uma tarefa concluída sem evidência de validação em `PROGRESS.md`.

## Autonomia e pontos que exigem decisão do usuário

O agente decide padrões técnicos, UX, textos, testes e migrations reversíveis.

Pedir decisão antes de alterar regras de negócio, disparar automações com efeito externo, usar credenciais ou dados reais, integrar pagamentos/terceiros, enviar mensagens, ou fazer deploy.

## Regras técnicas obrigatórias

- Preservar identificadores técnicos, tenants, slugs, URLs e dados persistidos, salvo decisão explícita.
- Toda consulta, agregação e mutação de domínio deve respeitar a empresa autenticada; IDs de outro tenant devem responder como inexistentes.
- Nunca registrar, retornar ou expor segredos. Segredos de infraestrutura ficam em variáveis de ambiente; credenciais por empresa usam armazenamento cifrado.
- Não introduzir persistência de dado de negócio no frontend ou `localStorage`.
- Uma funcionalidade só está pronta quando a interface e a API correspondente estiverem conectadas.
- Atualizar `API_CONTRACTS.md` e `PROGRESS.md` no mesmo commit de qualquer alteração de endpoint ou entrega; atualizar também a documentação de operação afetada.

## Validação mínima

Execute a validação proporcional ao risco antes de entregar:

```powershell
# Backend: suíte de regressão disponível
.\.venv\Scripts\python.exe -m unittest discover -s backend\tests

# Histórico Alembic em SQLite vazio
.\.venv\Scripts\python.exe -m unittest backend.tests.test_sqlite_migrations

# Frontend de produção
npm --prefix frontend run build
```

Para alterações de tenancy/RBAC, acrescente teste com duas empresas. Para alterações financeiras, acrescente testes de cálculo e cenários de erro. Para migrations, validar banco vazio e upgrade de banco existente quando o schema/dados anteriores forem tocados.
