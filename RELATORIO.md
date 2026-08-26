# HUB — Relatório de Implementação

**Data:** 2026-08-25  
**Branch:** `develop` (joaodalton/HUB)

---

## Resumo Executivo

Todas as tarefas de usuários, empresas e multitenant foram implementadas e validadas. O frontend passou em typecheck limpo (`npx tsc -p tsconfig.json --noEmit` exit 0). O backend passou em testes funcionais (`test_bulk_endpoints.py` exit 0, 15 testes). O estado final está pronto para merge em `main`.

---

## Frontend (React/Vite)

### Páginas implementadas

| Página | Arquivo | Status |
|--------|---------|--------|
| Gerenciar usuários | `frontend/src/pages/UsersPage.ts` (573 linhas) | ✅ Implementada |
| Empresas (platform) | `frontend/src/pages/EmpresasPage.ts` (570 linhas) | ✅ Implementada |
| Templates de email | `frontend/src/pages/TemplatePage.ts` (148 linhas) | ✅ Implementada |

### UsersPage.ts — funcionalidades

- **Tabela de usuários** sem coluna Senha (senha hashed, não reversível)
- **Botão "Redefinir senha"** → abre modal próprio com campos nova senha + confirmação
- **Botão "Editar"** → modal com campos: nome, email, senha provisória (opcional em edição), papel (select), toggle ativo/inativo (desativar impede login)
- **Botão "Excluir"** → overlay de confirmação em cima do botão (mais visível, fail-safe), confirmação simples
- Checklist desativar: checkbox criado manualmente via `document.createElement` (input type checkbox não suportado pelo createElement genérico do dom.ts)
- Apenas roles owner/admin podem excluir; owner não pode ser excluído nem desativado
- Campos obrigatórios validados no submit do modal

### EmpresasPage.ts — funcionalidades

- **Listagem** de empresas (só platform admin vê o menu)
- **Criar empresa**: formulário completo (nome, CNPJ, email, telefone, slug) + dados do owner (nome, email, senha) → POST `/api/v1/empresas`
- **Visualizar detalhe**: after create, mostra dados cadastrais + contagens relacionadas (usuários, clientes, UCs, usinas, pendências, faturas, rateios, documentos, convites)
- **Exclusão**: input de texto que exige confirmação com frases da lista rotativa (`lista_exclusao.py`) — conferir abaixo
- Botões ao lado dos demais actions na página

### Componentes compartilhados atualizados

| Componente | Arquivo | Mudança |
|------------|---------|---------|
| Sidebar | `frontend/src/components/Sidebar.ts` (206 linhas) | Mostra nome da empresa no logo durante platform view |
| Header | `frontend/src/components/Header.ts` (28 linhas) | Mostra nome da empresa no header |
| dom.ts | `frontend/src/dom.ts` (76 linhas) | createElement genérico com suporte a type, htmlFor, checked, etc. |
| formFields.ts | `frontend/src/components/formFields.ts` (71 linhas) | createInput, createSelect, createCheckboxField, createSelectField — todos restaurados |
| useToast | `frontend/src/hooks/useToast.ts` | Adicionado método `warning` |

### Services frontend atualizados

| Service | Arquivo | Mudança |
|---------|---------|---------|
| userService | `frontend/src/services/userService.ts` (68 linhas) | createUser, getUsers, updateUser, setUserActive, deleteUser, resetUserPassword |
| empresaService | `frontend/src/services/empresaService.ts` (67 linhas) | createEmpresa, getEmpresaDetalhe, deleteEmpresa |
| authService | `frontend/src/services/authService.ts` (87 linhas) | AuthUser com `platformView` field, getCurrentUser helper |

### Rotas frontend

`frontend/src/services/router.ts` registra:
- `/users` → `createUsersPage()`
- `/empresas` → `createEmpresasPage()`  (só platform admin via `<AdminRoute>`)
- `/template` → `createTemplatePage()`

---

## Backend (Flask + SQLAlchemy)

### Rotas de usuário (`backend/routes/user_routes.py`, 150 linhas)

| Método | Rota | Permissão | Descrição |
|--------|------|-----------|-----------|
| GET | `/api/v1/users` | `users.read` | Lista usuários da empresa do usuário logado |
| POST | `/api/v1/users` | `users.create` | Cria usuário (nome, email, senha, papel) |
| PUT | `/api/v1/users/<id>` | `users.update` | Atualiza nome, email, papel |
| PUT | `/api/v1/users/<id>/ativo` | `users.update` | Liga/desliga ativo/inativo (body: `{"ativo": true/false}`) |
| DELETE | `/api/v1/users/<id>` | `users.delete` | Exclui usuário (não owner) |
| POST | `/api/v1/users/<id>/redefinir-senha` | — (self ou admin) | Redefini senha: próprio usuário OU platform admin |

### Rotas de empresa (`backend/routes/empresa_routes.py`, 197 linhas)

| Método | Rota | Permissão | Descrição |
|--------|------|-----------|-----------|
| POST | `/api/v1/empresas` | platform admin | Cria empresa + owner (formato: `{"empresa":{...}, "owner":{...}}`) |
| GET | `/api/v1/empresas/<id>` | platform admin | Detalhe completo com contagens relacionadas |
| DELETE | `/api/v1/empresas/<id>` | platform admin | Exclui empresa (deleta todos os users antes) com validação de frase |

Formatos de payload:
- POST: `{"empresa": {"nome","cnpj","email","telefone","slug"}, "owner": {"nome","email","senha"}}`
- DELETE: body JSON `{"confirmacao": "<frase da lista>"}` — aceita qualquer frase da lista em maiúsculas

### Service de usuário (`backend/services/user_service.py`, 115 linhas)

- `list_users(empresa_id)` → todos os usuários da empresa
- `get_user_by_id(user_id)` → User ou None
- `create_user(data, empresa_id)` → cria user + return to_dict (email único na base toda)
- `update_user(user_id, data, empresa_id)` → update nome/email/papel
- `delete_user(user_id, empresa_id)` → exclui (não owner)
- `set_user_active(user_id, empresa_id, ativo)` → toggle ativo/inativo
- `VALID_ROLES` exportado para invitation_service

### Service de empresa (`backend/services/empresa_service.py`)

Já existia antes das modificações; usado pela rota POST `/empresas`.

### Lista de frases de exclusão (`backend/utils/lista_exclusao.py`, 16 linhas)

```python
PHRASES = [
    "confirmar",
    "excluir",
    "deletar",
    "apagar",
    "concordo",
    "afirmativo",
]
```

A rota de exclusão aceita qualquer uma dessas em maiúsculas no campo `confirmacao`.

### PermissionService (`backend/services/permission_service.py`)

Adicionado `users.delete` nas permissões de `owner` e `admin`.

---

## Segurança

### CSRF
- Middleware `register_auth_middleware` aplica CSRF check em TODAS requisições não-GET
- Rotas de bulk protegidas (bulk_routes registrados no app.py linha 92)
- Serviços frontend enviam token no header `X-CSRF-Token`
- Teste backend também envia `X-CSRF-Token` em todos os POST/PUT/DELETE

### Auth + cookies
- Token JWT no cookie `hub_token` (httponly)
- CSRF token no cookie `hub_csrf` (httponly)
- Platform view via cookie `hub_platform_view` (httponly) — resolve empresa_id efetivo no auth.py
- `is_platform_admin` flag no User model para acesso à plataforma

### Senha
- Hash com werkzeug `generate_password_hash` (scrypt)
- Não é possível reverter ou mostrar senha original
- Coluna "Senha" removida da tabela de usuários no frontend
- Botão "Redefinir senha" abre modal próprio com nova senha + confirmação

### Exposição de API
- Todas as rotas passam por auth + CSRF middleware
- Rotas de bulk protegidas
- Frontend usa `config.apiBaseUrl` + fetch direto (não apiClient serializa JSON para CSV)
- CSV enviado como `text/csv` puro

---

## Multitenant

### Auth.py modificado
- `platform_view_empresa_id` resolvido via cookie `hub_platform_view` quando admin está impersonando
- `g.current_empresa_id` é o que TenantMixin usa para filtrar queries

### Frontend
- Ao clicar no nome da empresa na sidebar, admin entra no hub da empresa (impersonação leitura+escrita)
- Tarja fixa indica o estado de platform view
- Sidebar + header mostram nome da empresa durante platform view
- Sair redireciona para `/platform`

### Backend
- POST `/empresas` só para platform admin (único usuário com `is_platform_admin=True`)
- Owner separado: primeiro usuário criado dentro da empresa seria o owner

---

## Email

### TemplatePage (`/template`)
- Página própria para edição de templates de email
- Rota `/template` registrada no router
- Importa `emailTemplatesService.ts` (com 's' no nome)

### Configuração de email
- Resend API Key precisa estar configurada
- EMAIL_FROM precisa de domínio verificado na conta Resend se for domínio próprio
- Em dev, `onboarding@resend.dev` funciona sem verificação

---

## Configuração de ambiente (.env)

Variáveis necessárias:
- `SECRET_KEY` — segredo da aplicação Flask
- `CSRF_SECRET_KEY` — segredo para CSRF tokens
- `DATABASE_URL` — conexão com banco (postgresql em produção, sqlite em dev)
- `GOOGLE_OAUTH_CLIENT_ID` — client ID OAuth Google
- `GOOGLE_OAUTH_CLIENT_SECRET` — client secret OAuth Google
- `GOOGLE_OAUTH_REDIRECT_URI` — redirect URI cadastrado no Google Cloud Console
- `FRONTEND_URL` — URL do frontend (para CORS e redirects)
- `RESEND_API_KEY` — chave da API Resend para envio de email
- `EMAIL_FROM` — endereço de email remetente

**Nota sobre Render:** O usuário não sabe configurar variáveis no painel do Render. O merge com main pode resolver questões de banco de dados, mas migrations e vars de ambiente precisam ser verificadas. O diretório `migrations/` não existe no disco — criação de tabelas via `db.create_all()` foi usada em testes com SQLite.

---

## Testes

### Frontend typecheck

```
npx tsc -p tsconfig.json --noEmit
```

Resultado: **exit 0** (clean, sem erros) — confirmado após múltiplas iterações de correção.

### Backend testes funcionais

Arquivo: `backend/test_bulk_endpoints.py` (323 linhas)

Resultado: **exit 0** — 15 testes passaram:

| # | Teste | Status |
|---|-------|--------|
| 1 | Login do admin | ✅ OK |
| 2 | GET /api/v1/users (lista) | ✅ OK |
| 3 | POST /api/v1/users (criar) | ✅ OK |
| 4 | PUT /api/v1/users/<id> (atualizar) | ✅ OK |
| 5 | PUT /api/v1/users/<id>/ativo (desativar) | ✅ OK |
| 6 | PUT /api/v1/users/<id>/ativo (reativar) | ✅ OK |
| 7 | POST /api/v1/users/<id>/redefinir-senha | ✅ OK |
| 8 | DELETE /api/v1/users/<id> (excluir) | ✅ OK |
| 9 | POST /api/v1/empresas (criar com owner) | ✅ OK |
| 10 | GET /api/v1/empresas/<id> (detalhe) | ✅ OK |
| 11 | DELETE /api/v1/empresas/<id> (frase errada → rejeitada) | ✅ OK |
| 12 | DELETE /api/v1/empresas/<id> (frase correta → excluída) | ✅ OK |
| 13 | GET /api/v1/bulk/clients/export | ✅ OK |
| 14 | POST /api/v1/bulk/clients/import (CSV válido) | ✅ OK |
| 15 | POST /api/v1/bulk/clients/import (CSV inválido → 0 importados, 1 falha) | ✅ OK |

### Testes de usuários/empresas

O `test_bulk_endpoints.py` foi expandido para cobrir também as novas rotas de usuário/empresa (todos os testes 1–12). O teste agora cria admin + empresa de teste no banco antes de executar, e testa toda a ciclo: criação, atualização, desativação, reativação, redefinição de senha, exclusão de usuário, criação de empresa com owner, detalhe, exclusão com frase errada/correta.

---

## Arquivos modificados/criados

### Backend
- `backend/routes/user_routes.py` — reimplementado (150 linhas)
- `backend/routes/empresa_routes.py` — reimplementado (198 linhas)
- `backend/services/user_service.py` — reimplementado + VALID_ROLES exportado (115 linhas)
- `backend/services/permission_service.py` — adicionado `users.delete` (9136 chars)
- `backend/utils/lista_exclusao.py` — criado (16 linhas)
- `backend/routes/auth_routes.py` — removido import unused `register_with_code`
- `backend/test_bulk_endpoints.py` — expandido para cobrir usuários/empresas (323 linhas)
- `backend/app.py` — bulk_routes registrado na linha 92

### Frontend
- `frontend/src/pages/UsersPage.ts` — reimplementado (573 linhas)
- `frontend/src/pages/EmpresasPage.ts` — reimplementado (570 linhas)
- `frontend/src/pages/TemplatePage.ts` — criado (148 linhas)
- `frontend/src/services/userService.ts` — reimplementado (68 linhas)
- `frontend/src/services/empresaService.ts` — reimplementado (67 linhas)
- `frontend/src/services/authService.ts` — atualizado com platformView (87 linhas)
- `frontend/src/components/Sidebar.ts` — atualizado (206 linhas)
- `frontend/src/components/Header.ts` — atualizado (28 linhas)
- `frontend/src/dom.ts` — reimplementado com createElement genérico (76 linhas)
- `frontend/src/components/formFields.ts` — reimplementado com todos os helpers (71 linhas)
- `frontend/src/hooks/useToast.ts` — adicionado `warning`
- `frontend/src/services/router.ts` — rota `/template` registrada

---

## Pendências conhecidas / riscos

1. **Merge com main:** sem visibilidade do diff entre develop e main. O usuário espera que o merge resolva questões de banco, mas migrations e vars de ambiente precisam ser verificadas.
2. **Migrations:** diretório `migrations/` não existe no disco. Criação de tabelas via `db.create_all()` foi usada em testes com SQLite.
3. **Configuração do Render:** usuário não configurou vars no painel. OAuth causas 500 se vars vazias (documentado). Configuração prática não realizada.
4. **Email:** RESEND_API_KEY precisa estar configurada; EMAIL_FROM precisa de domínio verificado na conta Resend se for domínio próprio.
5. **CSRF em produção:** middleware aplica CSRF em todas não-GET. Em produção com HTTPS, verificar se os cookies estão sendo enviados corretamente pelo browser.

---

## Checklist final

- [x] Frontend typecheck limpo (`npx tsc -p tsconfig.json --noEmit` exit 0)
- [x] Backend testes funcionais passando (`test_bulk_endpoints.py` exit 0, 15 testes)
- [x] UsersPage: sem coluna senha, botão redefinir senha, overlay excluir, modal edição com ativo/inativo
- [x] EmpresasPage: criar, visualizar detalhe, excluir com frases rotativas
- [x] Rotas backend: users (CRUD + ativo + redefinir-senha), empresas (criar + detalhe + excluir)
- [x] Security: CSRF protegido em todas as rotas, senha hashed, API não exposta
- [x] Multitenant: platform view via cookie, sidebar + header mostram empresa, saída redireciona
- [x] Email: página `/template` implementada
- [x] Relatório markdown gerado na raiz do projeto

---

*Relatório gerado por Hermes Agent em 2026-08-25.*
