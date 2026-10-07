# Retenção e expiração de dados — estado técnico conhecido

Data de levantamento: 2026-10-05. Os prazos abaixo são apenas os que podem ser confirmados tecnicamente pelo código atual. Onde não há expiração implementada e comprovada, o estado é `PENDING_REVIEW`; não se estabelece prazo legal ou operacional por inferência.

| Categoria | Dados | Local | Retenção técnica atual | Base/finalidade | Retenção jurídica | Status |
|---|---|---|---|---|---|---|
| PERSONAL / SECRET | Convite: e-mail/endereço de destino e token hash | Banco da aplicação (`Invitation`) | Token válido por 7 dias e uso único; purga do registro não confirmada | PENDING_REVIEW — código implementa convite/autenticação; finalidade jurídica não inferida | PENDING_REVIEW | PARCIAL — expiração do token confirmada; retenção do registro pendente |
| SECRET | Token de redefinição de senha | Banco da aplicação (`PasswordResetToken` ou modelo associado) | Token válido por 1 hora e uso único; purga do registro não confirmada | PENDING_REVIEW — código implementa recuperação de acesso; finalidade jurídica não inferida | PENDING_REVIEW | PARCIAL — expiração do token confirmada; retenção do registro pendente |
| PERSONAL / INTERNAL | Clientes, UCs, usinas, documentos, faturas, snapshots, logs e dados de empresa | Banco da aplicação e armazenamento de documentos conforme provider configurado | Prazo técnico geral ou rotina de purga não confirmados | PENDING_REVIEW | PENDING_REVIEW | PENDING_REVIEW |
| PERSONAL / INTERNAL | Arquivos em Google Drive, storage local ou R2 | Provedor de arquivos, conforme configuração/legado | Regra temporal automática uniforme não confirmada | PENDING_REVIEW | PENDING_REVIEW | PENDING_REVIEW |
| INTERNAL / PERSONAL | Logs e telemetria em Sentry, Render, Neon e provedores externos | Serviços externos | Configuração de retenção não determinada pelo código inspecionado | PENDING_REVIEW | PENDING_REVIEW | PENDING_REVIEW |

## Aviso jurídico

Este documento não constitui definição jurídica de prazo de retenção. Prazos dependentes de obrigação legal, contratual ou orientação do controlador devem ser definidos após revisão jurídica.

## Próximas confirmações

- Definir e aprovar prazos por categoria, incluindo suspensão/cancelamento, backups, documentos legados, logs e obrigações de preservação.
- Identificar rotinas e evidências operacionais de exclusão/anonimização; este documento não afirma que exista purga automática.
- Validar a política com assessoria responsável antes de apresentá-la como política LGPD ou prazo legal.
