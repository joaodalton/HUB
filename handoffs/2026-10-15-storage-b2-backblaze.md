# Handoff — STORAGE-1B: Backblaze B2 como endpoint S3 válido

Data: 2026-10-15

## Task

Habilitar Backblaze B2 como endpoint S3-compatível em `get_object_storage()`
(`backend/services/object_storage.py`), hoje bloqueado por uma validação de
hostname que só aceitava `*.r2.cloudflarestorage.com`. Objetivo: concluir o
caminho de armazenamento das faturas (já usa essa função) e deixar a base
pronta para qualquer upload futuro de PDF/imagem.

## Pipeline executado

Primeira execução real do time de 6 agentes HUB fora do piloto (HUB-12),
orquestrada nesta sessão via Agent tool do Claude Code:

1. `hub-backend-developer` — implementou.
2. `hub-backend-reviewer` — **PASS**.
3. `hub-security-reviewer` — **PASS**.

Nenhum `BLOCK` no ciclo. Task Contract completo e pareceres detalhados estão
registrados em `PROGRESS.md`, entrada `STORAGE-1B`.

## O que foi implementado

- `backend/services/object_storage.py`: `get_object_storage()` aceita agora
  hostname `s3.<regiao>.backblazeb2.com` (regex
  `re.fullmatch(r's3\.[a-z0-9-]+\.backblazeb2\.com', ...)`) em OR com o
  sufixo R2 já existente. Todas as demais validações continuam inalteradas e
  combinadas por `and`: HTTPS obrigatório fora de debug/teste, proibição de
  usuário/senha/query/fragment na URL, path vazio ou `/`. Nenhum hostname
  fora da allowlist passa a ser aceito.
- `backend/tests/test_object_storage.py`: teste novo
  (`test_s3_factory_accepts_backblaze_b2_endpoint`) cobre B2 válido, HTTP
  puro rejeitado e host malicioso com sufixo
  (`s3.us-west-002.backblazeb2.com.attacker.com`) rejeitado.
- `DEPLOY.md`: nota do formato de endpoint B2 ao lado da entrada de R2 já
  existente.
- `PROGRESS.md`: entrada `STORAGE-1B` com evidência completa.
- `S3ObjectStorage` e `fatura_concessionaria_upload_service.py` (upload de
  faturas) **não precisaram mudar** — já são agnósticos ao provider.

## Validação executada

- `backend/venv/Scripts/python.exe -m unittest backend.tests.test_object_storage -v`
  → **6/6 OK**, incluindo os 2 testes novos.
- `backend/venv/Scripts/python.exe -m unittest discover -s backend/tests`
  → 715 testes, 5 falhas isoladas em `backend/tests/test_delete_user_physical.py`
  (arquivo não versionado, pré-existente, fora do escopo desta entrega).

## Revisão independente

- **Backend** (`hub-backend-reviewer`): confirmou que `fullmatch` bloqueia
  bypass de sufixo/prefixo, que `urlparse` normaliza maiúsculas, que R2 não
  regrediu e que o escopo de arquivos foi respeitado.
- **Segurança** (`hub-security-reviewer`): testou ativamente SSRF via
  userinfo embutido na URL (`https://s3...@attacker.com/` — já bloqueado
  pela checagem pré-existente de `username`/`password`), confirmou ausência
  de vazamento de credencial em mensagens de erro e que o isolamento por
  `empresa_id` nos caminhos de objeto (`_key()`) não foi tocado. Nenhum
  bypass de SSRF encontrado apesar de busca ativa. Único ponto citado foi
  operacional, não de segurança: região errada configurada para B2 falharia
  em runtime no boto3/B2, não é uma falha de validação.

## Fora de escopo (decisão explícita)

Migrar `document_service.py` (documentos genéricos de cliente/UC, hoje no
Google Drive) para object storage **não entrou nesta entrega** — é trabalho
maior (dedup por MD5 equivalente ao `find_duplicate` do Drive, migração de
arquivo existente, mudança de contrato de `create_drive_document`). Já está
especificado como `STORAGE-2` em `HANDOFFS_PLATFORM_STORAGE.md` e fica para
sprint própria.

## Estado do commit

- Branch: `feat/b2-object-storage-endpoint`, criada a partir de `develop`.
- Commit local feito (`feat(storage): habilita Backblaze B2 como endpoint S3
  valido (STORAGE-1B)`), **push ainda não realizado** — o dono do projeto
  decidiu dar o push manualmente.

## Pendente, fora desta entrega

- Ativação operacional real da conta Backblaze B2: bucket privado, chave de
  acesso restrita ao bucket, variáveis `OBJECT_STORAGE_*` em
  `backend/.env`/Render. Nenhuma credencial real foi usada ou solicitada
  nesta sprint — o agente desenvolvedor trabalhou só com `boto3.client`
  mockado, igual aos testes já existentes para R2.
- `STORAGE-2` (documentos genéricos) conforme especificado em
  `HANDOFFS_PLATFORM_STORAGE.md`.
