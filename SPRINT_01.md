# SPRINT 01 — Identidade Multi-Tenant: Empresa, Usuários, Roles e Permissões

## Status: ✅ COMPLETA

## Objetivo

Transformar **Empresa** como unidade primária (tenant) do HUB e consolidar o núcleo de identidade do SaaS.

Transformar **Empresa** como unidade primária (tenant) do HUB e consolidar o núcleo de identidade do SaaS.

---

## Regra Central

```
Pessoa
  ↓
cria Empresa
  ↓
sistema cria Empresa + User (owner)
  ↓
User.empresa_id = Empresa.id
  ↓
User.role = owner
```

**Nenhum usuário escolhe ou altera `empresa_id` pelo frontend.**

---

## 1. Modelos Existentes (Aproveitar)

### Empresa (`backend/models/empresa.py`)
```python
Empresa
├── id
├── nome
├── razao_social
├── cnpj
├── email
├── telefone
├── slug
├── status
├── created_at
└── updated_at
```

### User (`backend/models/user.py`)
```python
User
├── id
├── empresa_id → Empresa.id
├── nome
├── email
├── password_hash
├── role (owner|admin|operator|financial|viewer)
├── status (ativo|inativo)
├── email_verified
├── must_change_password
├── created_at
└── updated_at
```

### Invitation (`backend/models/invitation.py`)
```python
Invitation
├── id
├── empresa_id → Empresa.id
├── email
├── role
├── token_hash (SHA-256)
├── expires_at
├── invited_by → User.id
├── accepted_at
├── status (pending|accepted|expired|revoked)
├── created_at
└── updated_at
```

---

## 2. Roles

| Role | Descrição |
|------|-----------|
| `owner` | Dono da empresa. Controle total. |
| `admin` | Administrador operacional. Gerencia usuários. |
| `operator` | Operador. Sem acesso a usuários. |
| `financial` | Financeiro. Sem acesso a usuários. |
| `viewer` | Somente leitura. |

**Não criar tabela `roles` no banco — definição em código.**

---

## 3. Permissões (Sprint 01)

### Matriz de Permissões

| Permissão | Owner | Admin | Operator | Financial | Viewer |
|-----------|-------|-------|----------|-----------|--------|
| `empresa.read` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `empresa.update` | ✓ | ✓ | — | — | — |
| `users.read` | ✓ | ✓ | — | — | — |
| `users.invite` | ✓ | ✓ | — | — | — |
| `users.create` | ✓ | ✓ | — | — | — |
| `users.update` | ✓ | ✓ | — | — | — |
| `users.change_role` | ✓ | ✓* | — | — | — |
| `users.deactivate` | ✓ | ✓* | — | — | — |
| `users.reactivate` | ✓ | ✓* | — | — | — |
| `invitations.read` | ✓ | ✓ | — | — | — |
| `invitations.create` | ✓ | ✓ | — | — | — |
| `invitations.revoke` | ✓ | ✓ | — | — | — |

*Admin com restrições: não pode promover a owner, não pode alterar owner.

---

## 4. Contexto Autenticado

O middleware define após login:

```python
g.current_user      # User
g.current_empresa    # Empresa
g.current_empresa_id # int
g.current_role      # str
```

Fluxo:
```
cookie → user_id → User → empresa_id → Empresa → contexto
```

**Nunca confiar em `empresa_id` enviado pelo frontend.**

---

## 5. Criação de Usuário

### Caminho A — Convite
```
Owner/Admin
  → email + role
  → Invitation (token hasheado, TTL 7 dias)
  → link
  → usuário aceita
  → define senha
  → User ativo
```

### Caminho B — Criação Direta
```
Owner/Admin
  → nome + email + senha + role
  → User ativo
  → must_change_password = true
```

**Senha criada pelo admin é temporária.**

---

## 6. Regras de Segurança

1. `User` sempre pertence a uma `Empresa`.
2. `empresa_id` nunca vem do frontend.
3. Owner/Admin só gerenciam usuários da própria empresa.
4. **Não permitir remover/desativar o último owner.**
5. Admin não pode se promover a owner.
6. Usuário inativo não autentica.
7. Convite é single-use.
8. Token de convite é hasheado (nunca em texto puro).

---

## 7. Arquivos Implementados

### Backend
```
backend/
├── models/
│   ├── empresa.py      ✅
│   ├── user.py        ✅
│   └── invitation.py  ✅
├── services/
│   ├── permission_service.py  ✅ (NOVO)
│   ├── empresa_service.py      ✅ (NOVO)
│   ├── user_service.py         ✅
│   ├── invitation_service.py  ✅
│   └── auth_service.py        ✅
├── routes/
│   ├── empresa_routes.py      ✅ (NOVO)
│   ├── user_routes.py         ✅
│   ├── invitation_routes.py   ✅
│   └── auth_routes.py         ✅
├── utils/
│   └── auth.py                ✅
├── extensions.py              ✅
└── app.py                     ✅
```

### Frontend (a implementar em Sprint 01-FRONT)
```
frontend/
├── src/
│   ├── pages/
│   │   ├── RegisterPage.tsx    (NOVO - criar empresa)
│   │   ├── LoginPage.tsx       (atualizar)
│   │   └── UsersPage.tsx       (atualizar)
│   └── services/
│       ├── empresaService.ts    (NOVO)
│       └── userService.ts      (atualizar)
```

---

## 8. Endpoints

### Públicos
| Método | Path | Descrição |
|--------|------|-----------|
| POST | `/api/v1/auth/login` | Login |
| POST | `/api/v1/auth/logout` | Logout |
| POST | `/api/v1/auth/aceitar-convite` | Aceitar convite |
| GET | `/api/v1/convites/verificar?token=` | Verificar convite |
| POST | `/api/v1/empresas/registro` | Criar empresa + owner |
| GET | `/api/v1/empresas/<slug>` | Buscar empresa por slug |

### Autenticados
| Método | Path | Permissão |
|--------|------|-----------|
| GET | `/api/v1/auth/me` | — |
| GET | `/api/v1/users` | `users.read` |
| POST | `/api/v1/users` | `users.create` |
| PUT | `/api/v1/users/<id>/ativo` | `users.deactivate` / `users.reactivate` |
| GET | `/api/v1/convites` | `invitations.read` |
| POST | `/api/v1/convites` | `invitations.create` |

---

## 9. Migrations

A migração `e2f6a9c3d5b8_rbac_empresa_user_fields.py` já implementa:
- Adiciona `nome`, `role`, `status`, `email_verified`, `must_change_password` ao User
- Adiciona `razao_social`, `cnpj`, `email`, `telefone`, `status` à Empresa
- Migra `papel` → `role` (admin → owner, viewer → viewer)
- Migra `ativo` → `status`
- Extrai `nome` do prefixo do email

A migração `f4a7b2c6d9e1_add_invitations_table.py` já cria a tabela de convites.

**Não criar novas migrations — as existentes cobrem o schema.**

---

## 10. O que NÃO Implementar na Sprint 01

- ❌ Tenantização de Client, UC, Plant, Document, Pendencia, Category, Setting, LogEntry, RateioHistorico
- ❌ RLS (Row Level Security)
- ❌ Supabase Auth
- ❌ JWT
- ❌ Membership N:N (usuário em múltiplas empresas)
- ❌ Billing/Subscription
- ❌ Refatoração profunda do Google OAuth (apenas preservar compatibilidade)

---

## 11. Critério de Conclusão

A Sprint está completa quando:

```
Empresa A
├── João — owner
├── Maria — admin
├── Carlos — operator
├── Ana — financial
└── Pedro — viewer

Empresa B
├── Lucas — owner
└── Julia — financial
```

E:
- João ✅ administra Empresa A
- João ❌ não acessa usuários B
- Maria ❌ não vira owner sozinha
- Carlos ❌ não administra usuários
- Pedro ❌ não escreve

---

## 12. Próximos Passos

Após Sprint 01 completa:
1. Migrar TenantMixin para todos os modelos (Client, UC, Plant, etc.)
2. Adicionar permissões de domínio (clients.*, plants.*, etc.)
3. Google OAuth: adicionar empresa_id ao state, criar usuário com role correta
4. Billing/Subscription

---

*Última atualização: Sprint 01 concluída*
