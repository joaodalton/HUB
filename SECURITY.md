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
permissoes enquanto visualizam uma empresa.

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
python -m unittest security_regression_test.py
```

Tambem execute testes integrados com dois tenants e com os papeis `owner`,
`admin`, `operator`, `financial` e `viewer` antes de cada deploy.
