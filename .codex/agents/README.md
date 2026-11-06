# Agentes do HUB no Codex

Cada arquivo TOML deste diretório define um agente personalizado independente.
O campo `name` é o identificador usado pelo Codex para selecioná-lo; `description`
orienta quando usar o perfil e `developer_instructions` define seu comportamento.
`../config.toml` habilita a delegação e permite até cinco subagentes simultâneos.
A configuração do projeto só é aplicada quando o repositório é confiável no Codex.

## Papéis

| Tipo | Arquivo | Responsabilidade |
| --- | --- | --- |
| `backend` | `backend.toml` | Flask, SQLAlchemy, API e integração backend. |
| `frontend` | `frontend.toml` | React, Vite, interface e integração com contratos existentes. |
| `data_migration` | `data-migration.toml` | Schema, Alembic, migrations e transformações de dados. |
| `reviewer` | `reviewer.toml` | Revisão independente de código, segurança, integração e regressões. |
| `tester` | `tester.toml` | Testes focados e evidências de validação. |

## Regras compartilhadas

Todos os agentes devem seguir `AGENTS.md`, ler `VISAO.md` e `PROGRESS.md` e
consultar contratos e documentação do domínio afetados. As instruções globais do
repositório prevalecem sobre estes perfis.

Para delegar, informe objetivo, contexto, critérios de aceite, arquivos relevantes,
dependências e validação esperada. Não permita que dois agentes editem os mesmos
arquivos ao mesmo tempo. Separe implementação, revisão e testes quando a tarefa
permitir.

Implementadores devem concluir com um `HANDOFF` que registre status, arquivos,
contratos, migrations/dados, validações, riscos e pendências. O reviewer não altera
código e retorna `VERDICT: PASS`, `PASS_WITH_NOTES` ou `BLOCK`, com achados concretos
e evidências. O tester não altera comportamento de produção.

Use `reviewer` em alterações não triviais e especialmente quando houver mudanças
de tenancy, autorização, credenciais, pagamentos, migrations ou contratos. Use os
outros agentes conforme o escopo; não é necessário convocar todos em toda tarefa.
