# Seguranca do HUB

## Isolamento multi-tenant

Os modelos de negocio que pertencem a uma empresa herdam `TenantMixin`. O
listener do SQLAlchemy adiciona o filtro por `g.current_empresa_id` as consultas
ORM. `Setting`, `LogEntry` e `RateioHistorico` tambem sao isolados por empresa.

Modelos globais, como `User`, `Empresa`, `Invitation` e tokens de recuperacao,
devem aplicar `empresa_id` explicitamente em fluxos autenticados.

## Autorizacao

Cada rota de negocio usa `require_permission`; configuracoes de infraestrutura
usam `require_platform_admin`. Administradores da plataforma tem todas as
permissoes somente enquanto visualizam explicitamente uma empresa. Sem o cookie
`hub_platform_view` validado no backend, APIs tenant respondem `403` com
`PLATFORM_TENANT_CONTEXT_REQUIRED`; o `User.empresa_id` do administrador da
plataforma nunca ativa implicitamente um Tenant Context.

Entrar e sair de uma empresa exige `is_platform_admin`, valida a Empresa no
backend, aplica CSRF nas mutacoes autenticadas por cookie e registra auditoria.
Login, logout e a acao de sair removem o contexto anterior. A listagem e a acao
de entrada retornam DTOs minimos, sem documentos, credenciais ou referencias de
storage.

## Contexto de plataforma

O cookie `hub_platform_view` e assinado (`itsdangerous`, salt `platform-view`)
e carrega o `user_id` do administrador que entrou na empresa. Valor cru, assinatura
invalida, cookie de outro usuario ou expirado sao ignorados: o backend responde
`403 PLATFORM_TENANT_CONTEXT_REQUIRED`. Trocar de empresa so acontece pela rota
auditada `POST /platform/empresas/<id>/entrar`.

## OAuth Google

`GET /oauth/google/authorize` grava um nonce em cookie `HttpOnly` restrito ao
path do callback e guarda o SHA-256 dele junto do `state`. O callback exige o
mesmo cookie; um link de consentimento enviado a terceiros nao consegue gravar o
refresh token de outra conta dentro da empresa de quem gerou o link. O `state`
continua de uso unico com TTL curto.

## Rate limit e proxy

Fora do modo debug o app aplica `ProxyFix` (`X-Forwarded-For`/`Proto`), e o
limiter usa `request.remote_addr` -- o IP que o `ProxyFix` corrige para a
origem real, usando apenas os proxies configurados em `TRUSTED_PROXY_COUNT`
(padrao 1, o LB do Render; aumentar se entrar outro proxy na frente, ex.:
Cloudflare). Nunca usar `request.access_route[0]`: e o primeiro IP do
cabecalho `X-Forwarded-For`, escrito pelo proprio cliente -- quem tenta
adivinhar senha trocaria esse valor a cada tentativa e escaparia do limite
de 5 logins por minuto. `RATELIMIT_STORAGE_URI` deve apontar para um storage
compartilhado em producao (ver `DEPLOY.md`).
Corpo de requisicao acima de `MAX_CONTENT_LENGTH` (25 MiB) recebe `413`.

## Usuarios

Somente o proprio owner altera a conta do owner (nome, e-mail, senha); admin
recebe `403 OWNER_PROTECTED`. O owner nao pode ser excluido nem inativado.

## Erros e logs

Toda requisicao recebe `X-Request-ID` (gerado ou ecoado). Excecao nao tratada
responde `500 INTERNAL_ERROR` com `requestId`, sem detalhe interno; traceback vai
para o log JSON (stdout) e para o Sentry. Rotas nunca devolvem `str(exc)` de
integracoes externas ao cliente.

## Sessoes e cookies

O token assinado contem `user_id` e `session_version`. Logout e redefinicao de
senha incrementam a versao, invalidando tokens emitidos anteriormente. O cookie
de autenticacao e `HttpOnly`, `SameSite=Lax` e `Secure` fora do modo de debug.
Mutacoes autenticadas por cookie exigem o cabecalho `X-CSRF-Token`.

## Google Drive

O cache do Google e separado por `empresa_id`. Cada tenant precisa da setting
`google_drive_root_folder_id`; o valor global do ambiente so e usado quando
existe uma unica empresa. Pesquisa, upload e download sao limitados a pasta
raiz autorizada.

A query de busca escapa `\\` e `'` e remove caracteres de controle antes de
montar a expressao `name contains`.

APIs nunca devolvem o valor de uma setting sensivel. Para `resend_api_key`, a
resposta contem apenas `resend_api_key_configured`.

## Migracao

```powershell
cd backend
flask db upgrade
```

A migracao `b1d9e4f7a2c6` replica settings legadas para as empresas existentes,
associa logs antigos a primeira empresa e deriva o tenant do historico de
rateio pela usina. Revise logs legados se o banco ja tinha mais de uma empresa.

## Testes

```powershell
cd backend
python -m pip install -r requirements-dev.txt
python -m pytest -n auto                 # suite completa, paralela (~1-2 min)
python -m pytest tests/security          # so os testes de isolamento de tenant
python -m pytest tests/test_fase1_hardening.py tests/test_owner_protection.py tests/test_platform_boundary.py
```

Tambem execute testes integrados com dois tenants e com os papeis `owner`,
`admin`, `operator`, `financial` e `viewer` antes de cada deploy.
