# Arquitetura do HUB — Tenant Isolation

Data: 2026-10-07. Refeito do SPRINT USERS, LOGS E CONVITES TENANT-ISOLATION.

## Regras arquiteturais

1. **Usuários, logs e convites são recursos tenant-scoped.** `empresa_id` é parte da
   fronteira de segurança: o frontend não pode usá-lo para decidir *quem pode ler
   ou modificar* o recurso. A origem do tenant é sempre o contexto autenticado do
   usuário (modelo `User.empresa_id`), never o id de uma empresa selecionada no
   navegador/cookie.

2. **E-mail globalmente único.** `User.email` é `UNIQUE` na base. Uma empresa não pode
   conter o mesmo e-mail de outro tenant e não pode "ter" um e-mail já cadastrado em
   outra empresa. Convite para e-mail já pertencente a outra empresa é rejeitado no
   `POST /convites`.

3. **Verdade do tenant.** O backend define o tenant; o frontend não manda
   `empresa_id` como mecanismo de autorização nas rotas `users`, `logs` e
   `convites`. As rotas usam `g.current_empresa_id` já resolvido pelo middleware de
   autenticação, e os serviços aplicam o filtro `empresa_id` nas consultas e nas
   restrições de negócio.

4. **Gravação de logs com tenant obrigatória.** `LogService.info/warning/error` vai
   gravar o `empresa_id` do contexto Flask (ou o `empresa_id` explícito passado por
   um consumo administrativo). Sem tenant, o log é descartado, não persistido como
   global. Rotas de auditoria obrigatória usam `strict=True` e falham fechado.

## Mecanismos aplicados

- Middleware de autenticação (`utils/auth.py`, `register_auth_middleware`):
  instala `g.current_user`, `g.current_empresa_id = user.empresa_id`, e só o cookie
  de platform admin altera o contexto depois de validar `is_platform_admin`.
- Filtro ORM por tenant (`extensions.py`, listener `do_orm_execute`): todas as SELECTs
  contra `TenantMixin` são filtradas por `empresa_id` da sessão atual.
- `User` e `Invitation` não usam `TenantMixin` por desenho (login/convite rodem sem
  sessão autenticada); o filtro `empresa_id` é aplicado explicitamente no service e
  na rota.
- Serviço de convites (`services/invitation_service.py`): verifica duplicidade de
  e-mail com usuário existente, convite pendente em outra empresa, e revoga o
  convite pendente anterior do mesmo `empresa_id + email`.
- Serviço de usuários (`services/user_service.py`): `PUT /users/<id>` verifica
  `id + empresa_id`, campos permitidos, e-mail único por outro usuário, role
  imutável `owner`, e invalidação de sessão ao mudar senha.
- Logs (`services/log_service.py`): `empresa_id` opcional; `strict` para auditorias
  obrigatórias de platform (entrada/saída).

## Arquivos de referência

- `backend/services/user_service.py` — edição/validações/crítica de senha.
- `backend/services/invitation_service.py` — isolamento e regras de convite.
- `backend/services/log_service.py` — escrita/log com `empresa_id`.
- `backend/services/auth_service.py` — login, `session_version`, audit.
- `backend/routes/user_routes.py`, `invitation_routes.py`, `log_routes.py`.
- `backend/models/user.py`, `invitation.py` — modelos não TenantMixin por desenho.
- `backend/extensions.py` — listener ORM de filtro por tenant.
- `backend/utils/auth.py` — resolução de `g.current_empresa_id`.
- `backend/tests/test_user_activation_security.py`,
  `test_invitation_service.py`, `test_log_tenant_isolation.py`,
  `test_platform_boundary.py` — cobertura de isolamento.

## Limitações registradas

- A fase arquitetural `ARCH-TENANT-1` não concluiu o controle global de identity map;
  apenas contenção impeditiva foi entregue. A regra de "empresa_id não é
  autorização do frontend" permanece aplicada sempre que o tenant é resolvido no
  backend.
