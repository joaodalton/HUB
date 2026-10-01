# Handoffs: Platform Billing e Object Storage

Estado: plano revisado em 2026-09-29; nenhuma das três sprints está implementada por este documento.

Execute na ordem ARCH-PLATFORM-1 → STORAGE-1 → STORAGE-2. Cada sprint tem seu próprio ciclo: implementação, regressão, revisão independente de arquitetura/segurança, correções, nova validação e registro da evidência em `PROGRESS.md`. Libere a próxima somente após o gate anterior. Compatibilidade com dados e rotas legadas faz parte do aceite, não é tarefa opcional posterior. Preserve as alterações já existentes no workspace.

## ARCH-PLATFORM-1 — ASAAS plataforma × ASAAS das empresas

**Objetivo.** Criar uma fronteira explícita entre o HUB cobrando empresas pelo SaaS e cada empresa cobrando seus clientes, sem alterar o funcionamento tenant B0–B3. Esta sprint estabelece e valida a separação. Só declare cobrança SaaS operacional se plano, preço, ciclo, criação, conciliação e ativação estiverem definidos e testados de ponta a ponta; não use `READY` para uma estrutura apenas preparada.

**Mapa atual a preservar.** `AsaasClient(empresa_id)` em `backend/services/asaas_client.py` resolve chave cifrada de `ApiCredential` por empresa e contém transporte HTTP e métodos do provedor. `fatura_service.py` usa esse cliente para `Fatura` e mantém reserva/reconciliação de emissão. `POST /api/v1/webhooks/asaas` autentica pelo token da empresa após identificar uma `Fatura`; `PaymentWebhookEvent` registra idempotência tenant. `external_reference` tenant já existe no formato `hub-<uuid>`. `Empresa` não é uma assinatura; `backend/planos/catalogo.py` é catálogo de franquias e contém apenas `starter`. `RESEND_API_KEY` e `EMAIL_FROM` já são variáveis globais do backend.

**Implementação.** Extraia do cliente atual apenas transporte ASAAS reutilizável, com URL-base e credencial injetadas. Preserve a interface tenant ou crie adaptador de compatibilidade para seus consumidores. Crie um serviço de plataforma separado, que use exclusivamente `PLATFORM_ASAAS_*`, e um serviço tenant que use exclusivamente `ApiCredential` da empresa. Não faça o transporte conhecer `Empresa`, `Fatura` ou assinatura.

Modele plano/assinatura/customer/pagamento da plataforma somente conforme o fluxo SaaS efetivamente definido; não reutilize `Fatura`, `PaymentWebhookEvent` tenant nem `Client.asaas_customer_id` para o SaaS. Persistências e referências externas devem distinguir contextos; mantenha leitura e conciliação das referências tenant antigas. Registre separadamente eventos de webhook da plataforma com unicidade/idempotência própria.

**Rotas.** Mantenha `POST /api/v1/webhooks/asaas` como entrada tenant compatível. Adicione uma entrada nova e inequívoca para a plataforma, por exemplo `/api/v1/webhooks/asaas/platform`; não renomeie a rota tenant nesta sprint. O webhook plataforma valida seu token global antes de qualquer alteração e só alcança registros plataforma. O webhook tenant conserva o lookup atual, valida o token tenant e só alcança registros tenant. Identificador da URL não substitui autenticação.

**E-mail.** Formalize Resend existente como infraestrutura global do HUB, preservando `RESEND_API_KEY` e `EMAIL_FROM` para evitar renomeação desnecessária. Não trate a credencial `resend` por empresa na UI como substituta da chave global do sistema; documente a diferença antes de qualquer alteração dessa UI.

**Gate 1.** Testes com pelo menos duas empresas provam separação de credenciais, pagamentos, webhooks e idempotência; B0–B3 e contratos existentes continuam verdes. Revisão independente inspeciona segredos/logs, falhas parciais de pagamento, concorrência, migration e referências antigas. Atualize `API_CONTRACTS.md`, `ARCHITECTURE.md`, documentação de billing e `PROGRESS.md`. Registre separadamente `BOUNDARY_READY` e `SAAS_BILLING_READY` conforme o que foi realmente implementado.

## STORAGE-1 — R2 privado para novas faturas

**Objetivo.** Guardar novos PDFs de faturas em R2 em produção e localmente em desenvolvimento, preservando todos os PDFs antigos no Google Drive ou no storage local legado. PostgreSQL/Neon continua com metadados e relacionamentos; não armazene bytes permanentes no banco.

**Mapa atual a preservar.** `FaturaConcessionaria.document_id` aponta obrigatoriamente para `Document`, cujo `storage_provider/storage_ref` hoje é `google_drive` ou `local`. `upload_invoice()` chama `prepare_document()` e tem compensação em falha de commit. A listagem marca `documentoDisponivel` somente para Drive; o download genérico de Document redireciona para a visualização no Drive. O limite de PDF de fatura é `FATURA_CONCESSIONARIA_MAX_BYTES`, default **10 MiB**, e 10 páginas. Não confunda esse limite com os 100 MiB da importação regulatória.

**Implementação.** Introduza uma interface pequena de armazenamento de objetos e implementação local/S3 compatível, configurada por ambiente. Cloudflare R2 usa o endpoint S3; credenciais do bucket ficam em env, nunca no banco nem no frontend. Preserve `Document` como referência da fatura: novos documentos de fatura podem ter `storage_provider='s3'` e `storage_ref` opaca, mais metadados ausentes adicionados por migration reversível. Não crie uma segunda referência de arquivo concorrente em `FaturaConcessionaria`. Mantenha acesso às referências `google_drive`/`local` existentes e ajuste todos os consumidores de `storage_provider`, inclusive `documentoDisponivel` e processamento posterior.

Configure `STORAGE_PROVIDER=local|s3`, `OBJECT_STORAGE_ENDPOINT`, `OBJECT_STORAGE_BUCKET`, `OBJECT_STORAGE_ACCESS_KEY_ID`, `OBJECT_STORAGE_SECRET_ACCESS_KEY` e `OBJECT_STORAGE_REGION` por ambiente. O diretório local é exclusivo de desenvolvimento; produção exige R2. Defina o provider padrão de modo que configuração ausente em produção falhe explicitamente, sem gravar no disco efêmero do Render.

**Chaves e downloads.** Use objeto privado `tenants/<empresa_id>/invoices/<ano>/<mes>/<uuid>.pdf`; não inclua nome, CPF, CNPJ ou UC na chave. Na resposta de download, use nome amigável sanitizado: `<cliente>_<competencia>_Vencimento_<data>.pdf`, com fallback sem metadados. Prefira streaming pelo backend na primeira entrega para que autorização, nome do arquivo e suporte ao legado tenham um único caminho; uma URL assinada curta pode ser adotada se seus limites e exposição forem validados. URL assinada é um bearer token reutilizável até expirar e não deve ir para logs ou banco. [Cloudflare: URLs assinadas](https://developers.cloudflare.com/r2/api/s3/presigned-urls/).

**Upload e consistência.** Preserve a ordem de validação atual: tipo, tamanho, integridade PDF, páginas, hash SHA-256, identificação de UC/tenant e deduplicação. Novo objeto é criado só depois das validações que não exigem storage. Falha de gravação do objeto impede commit; falha de commit tenta apagar somente o objeto criado pela tentativa atual. Nunca apague objeto compartilhado ou legado por uma duplicata. Verifique hash ao ler para reprocessamento quando aplicável. Mantenha os códigos de erro atuais.

**Autorização.** Download da fatura passa por autenticação, permissão `faturas.read`, escopo de empresa e vínculo com `FaturaConcessionaria`; administrador da plataforma usa rota com empresa explícita. Preserve `/documents/<id>/download` para consumidores existentes. O bucket permanece privado, sem `r2.dev` ou domínio público habilitado; R2 é privado por padrão, mas isso deve ser verificado na configuração real. [Cloudflare: buckets privados e acesso público](https://developers.cloudflare.com/r2/buckets/public-buckets/).

**Gate 2.** Testes de upload/download local, S3 compatível mockado, Drive/local legados, duas empresas, admin com empresa explícita, deduplicação, falhas storage/banco, filename, hash, status de disponibilidade e regressão do parser. Migration testada em banco vazio e estado anterior. Revisão independente verifica isolamento, RBAC, segredos e limpeza segura. Atualize `API_CONTRACTS.md`, `FATURAS_E_COBRANCAS.md`, `DEPLOY.md`, `ARCHITECTURE.md` e `PROGRESS.md`. Não marque `R2_READY` sem bucket privado/configuração e leitura real validadas; testes mockados só provam o código.

## STORAGE-2 — Documentos gerais no mesmo storage

**Objetivo.** Reutilizar a interface e o provider da STORAGE-1 para novos uploads de documentos gerais, sem misturar domínio de Document com FaturaConcessionaria.

**Mapa atual a preservar.** `Document` serve documentos de cliente/UC e também arquivos de fatura; há documentos fixos da empresa referenciados por `Empresa`, arquivos vinculados ao Drive por `create_drive_document()` e anexos locais legados. `delete_document()` hoje faz hard delete do registro, apaga arquivo local e não apaga o arquivo no Drive. Há consumidores de Drive fora do módulo de Documentos, inclusive formulários de rateio. Classifique arquivos próprios e apenas vinculados antes de mudar exclusão ou migrar bytes.

**Implementação.** Novos uploads gerais vão para `tenants/<empresa_id>/documents/<contexto>/<uuid>.<ext>` no mesmo serviço de objetos; o contexto deve vir dos relacionamentos reais. Preserve leitura de `google_drive` e `local` e os links já existentes. Não migre ou apague arquivos Drive nesta sprint por padrão: uma migração posterior exige inventário, verificação byte a byte, retomada, rollback e decisão sobre propriedade do arquivo. Reutilize campos de `Document` e acrescente somente metadados necessários, sem duplicar `storage_ref`/`storage_provider`.

**Rotas, segurança e exclusão.** Preserve as rotas e permissões existentes. Para novos objetos privados, baixe via backend autenticado ou URL assinada curta após RBAC e tenant scope; use `Document.nome` ou nome original sanitizado no `Content-Disposition`. Mantenha a semântica de hard delete enquanto não houver decisão de produto para soft delete; antes de apagar bytes, confira se o objeto pertence ao HUB e não é referenciado por fatura, documento fixo ou outro registro. Falhas entre banco e objeto exigem reconciliação/limpeza segura. Audite upload, download e exclusão usando o LogService sem gravar conteúdo, URL assinada ou segredo.

**Gate 3.** Testes de providers local/S3/Drive legado, duas empresas, RBAC, admin, links Drive, documentos fixos, rateio, download amigável, falhas parciais, exclusão e auditoria. Revisão independente de referências e retenção antes de qualquer migração em produção. Atualize `API_CONTRACTS.md`, documentação de Documentos, `DEPLOY.md`, `ARCHITECTURE.md` e `PROGRESS.md`. Distinga `NEW_DOCUMENTS_R2_READY` de `LEGACY_MIGRATED`; o segundo só é verdadeiro após migração real verificada.

## Decisões antes de ativar cobranças ou provisionar produção

- Plataforma: definir preço, periodicidade, trial, status, suspensão/reativação e política de inadimplência antes de cobrar empresas ou conceder acesso automaticamente.
- R2: criar bucket e credenciais restritas; verificar acesso público desabilitado, permissões e configuração no Render. Não registrar valores secretos no handoff.
- Retenção e migração: decidir quando arquivos legados serão copiados e se o Drive continuará como fonte ou será apenas fallback; não apagar o original antes de comparação por hash e janela de rollback.
