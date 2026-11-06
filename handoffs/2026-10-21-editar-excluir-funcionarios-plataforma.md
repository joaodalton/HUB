# Handoff — Editar/Excluir Funcionários da Plataforma

Data: 2026-10-21
Branch: hub-develop-corrigido

## Pedido do usuário

Na página "Funcionários" (Platform admin, `/platform/funcionarios`), adicionar:
1. Botão de editar as informações do funcionário, incluindo a senha.
2. Botão de excluir o usuário.

## Investigação (já feita)

- `frontend/src/pages/PlatformFuncionariosPage.ts` hoje só tem **criar** (`openForm`) e **revogar** (`createRevokeButton`, chama `DELETE /platform/funcionarios/:id`). Não existe edição.
- `backend/routes/platform_worker_routes.py` só tem `GET`, `POST ''`, `DELETE /<id>` (que é soft-delete: `revoke_platform_worker` seta `is_platform_worker=False`, `status='inativo'`, incrementa `session_version` — não apaga a linha do banco). Falta `PUT`/`PATCH /<id>`.
- `backend/services/platform_worker_service.py` tem `create_platform_worker`/`revoke_platform_worker`, falta `update_platform_worker`.
- Para comparação, `frontend/src/pages/UsersPage.ts` (usuários normais de empresa, não platform worker) **já tem** edição completa com senha opcional (`createUserEditModal`, linha ~166-189) — usar como referência de padrão de UI/UX (campo "Nova senha (opcional)", só envia se preenchido).
- Botão de excluir: o "Revogar" existente já cumpre a função (soft-delete), decisão: reaproveitar o mesmo endpoint/ação, só renomear o label do botão pra "Excluir" (o termo que o usuário usou), sem mudar o comportamento (manter soft-delete, que é o padrão já estabelecido no projeto — nunca apagar linha do banco de usuário).

## Plano de implementação

### Backend
1. `backend/services/platform_worker_service.py`: nova função `update_platform_worker(user_id, data) -> dict | None`.
   - Busca `User.query.filter_by(id=user_id, is_platform_worker=True).first()`; `None` se não achar.
   - Campos aceitos: `nome`, `email`, `senha` (todos opcionais — só atualiza o que vier).
   - Mesmas validações de `create_platform_worker`: email não vazio se enviado, formato minimo (reaproveitar a checagem já usada), unicidade de email (excluindo o próprio `user_id`), senha com pelo menos 6 caracteres se enviada.
   - Bloquear mudança de `is_platform_admin`/`isPlatformAdmin`/`is_platform_worker`/`isPlatformWorker` (mesma regra do create).
   - Se `senha` vier, hash via `hash_password` e também incrementar `session_version` (importante: troca de senha deve invalidar sessões antigas, mesmo padrão de outros fluxos de troca de senha no projeto — CONFIRMAR lendo `user_service.py`/`auth_routes.py` como esse incremento é feito noutros lugares antes de implementar, pra manter consistência).
   - `LogService.info(acao='update', ...)` igual ao padrão de create/revoke.
2. `backend/routes/platform_worker_routes.py`: nova rota `PUT /<int:user_id>`, `@require_platform_admin()`, chama `update_platform_worker`, trata `ValueError` como 400, `None` como 404 (mesmo padrão do `destroy`).

### Frontend
1. `frontend/src/services/platformWorkerService.ts`: `updatePlatformWorker(id, data: { nome?: string; email?: string; senha?: string }): Promise<PlatformWorker>`.
2. `frontend/src/pages/PlatformFuncionariosPage.ts`:
   - Novo botão "Editar" por linha (coluna de ação, ao lado do de excluir), abre modal/form pré-preenchido com nome/email, campo "Nova senha (opcional)" (`minLength 6`, só envia se preenchido) — seguir o padrão visual de `createUserEditModal` em UsersPage.ts.
   - Renomear o botão/texto "Revogar" pra "Excluir" (mesmo `revokePlatformWorker`, sem mudar comportamento).

## Testes
- Backend: teste novo (ou atualizar `backend/tests/test_platform_worker_management.py`) cobrindo: update de nome/email funciona, update de senha funciona e invalida sessão antiga (`session_version` incrementado), email duplicado de outro usuário é rejeitado, tentar mudar `is_platform_admin` é rejeitado, `require_platform_admin()` continua obrigatório.
- Rodar suíte backend relevante + `npm run build` no frontend.

## Gate de revisão
- `hub-backend-reviewer` (rota exclusiva de platform_admin, hash de senha, invalidação de sessão).
- `hub-security-reviewer` (troca de senha e exclusão de usuário são superfície sensível — confirmar RBAC e que senha nunca é logada/retornada em texto puro).
- `hub-frontend-reviewer` (modal de edição, build).
