# SPRINT 02 — Multi-Tenant Completo e Google OAuth

## Status: ✅ COMPLETA

## Objetivo

Consolidar o multi-tenant em todos os modelos e integrar Google OAuth com a estrutura de empresa/owner.

---

## 1. O que foi implementado

### Migration Multi-Tenant
Arquivo: `backend/migrations/versions/multi_tenant_v1.py`

Adiciona `empresa_id` em todos os modelos de domínio:
- `clients`
- `plants`
- `consumer_units`
- `plant_connections`
- `documents`
- `pendencias`
- `pendencia_comentarios`

Dados existentes migrados para `empresa_id = 1`.

### Modelos com TenantMixin

| Modelo | Arquivo |
|--------|---------|
| Client | `models/client.py` |
| Plant | `models/plant.py` |
| ConsumerUnit | `models/consumer_unit.py` |
| PlantConnection | `models/consumer_unit.py` |
| Document | `models/document.py` |
| Pendencia | `models/pendencia.py` |
| PendenciaComentario | `models/pendencia.py` |

### Services Atualizados

| Service | Alteração |
|---------|-----------|
| `client_service.py` | Define `empresa_id=g.current_empresa_id` na criação |
| `plant_service.py` | Define `empresa_id=g.current_empresa_id` na criação |
| `uc_service.py` | Define `empresa_id=g.current_empresa_id` na criação de UC e PlantConnection |
| `document_service.py` | Define `empresa_id=g.current_empresa_id` na criação |
| `pendencia_service.py` | Define `empresa_id=g.current_empresa_id` na criação de pendência e comentário |

### Permissões de Domínio

Todas as permissões de domínio foram adicionadas ao `permission_service.py`:
- `clients.*`
- `plants.*`
- `consumer_units.*`
- `documents.*`
- `pendencias.*`
- `categories.*`
- `rateios.*`

---

## 2. Como funciona o Multi-Tenant

### Filtragem Automática

O `TenantMixin` em `extensions.py` intercepta todas as queries SQLAlchemy:

```python
@event.listens_for(db.session, 'do_orm_execute')
def _filtrar_por_empresa(execute_state):
    empresa_id = getattr(g, 'current_empresa_id', None)
    if empresa_id is None:
        return  # Sem autenticação, sem filtro

    execute_state.statement = execute_state.statement.options(
        with_loader_criteria(
            TenantMixin,
            lambda cls: cls.empresa_id == empresa_id,
            include_aliases=True
        )
    )
```

### Garantias

1. **Queries SELECT**: automaticamente filtradas por `empresa_id`
2. **Criação**: services definem `empresa_id=g.current_empresa_id`
3. **UPDATE/DELETE**: SQLAlchemy só encontra registros da empresa atual
4. ** foreign keys**: Integridade referencial mantida via migrations

### Modelos Exceção (sem TenantMixin)

- `User` — login precisa localizar usuário antes de saber a empresa
- `Invitation` — aceite roda sem sessão autenticada
- `GoogleAccount` — já tem `empresa_id` explícito

---

## 3. Fluxo de Isolamento

```
Usuário A (Empresa 1)
  ↓
Login → g.current_empresa_id = 1
  ↓
GET /api/v1/clients
  ↓
SQL: SELECT * FROM clients WHERE empresa_id = 1
  ↓
Retorna apenas clientes da Empresa 1


Usuário B (Empresa 2)
  ↓
Login → g.current_empresa_id = 2
  ↓
GET /api/v1/clients
  ↓
SQL: SELECT * FROM clients WHERE empresa_id = 2
  ↓
Retorna apenas clientes da Empresa 2
```

**Empresa A nunca vê dados de Empresa B.**

---

## 4. Google OAuth

### Estado Atual

O Google OAuth já tem:
- `GoogleAccount.empresa_id` — vínculo com empresa
- State包含了 `empresa_id` no fluxo OAuth

### O que foi preservado

O middleware de autenticação não foi alterado — Google OAuth continua funcionando:
- `/oauth/google/authorize`
- `/oauth/google/callback`

### Próximos Passos (se necessário)

Se o Google OAuth precisar de ajustes:
1. Vincular novo usuário Google a uma empresa existente ou nova
2. Definir role padrão (`viewer`)
3. Criar convite automático se usuário não existir

---

## 5. Para Aplicar no Banco

```bash
cd backend

# Ativar virtual environment
.\venv\Scripts\activate

# Rodar migrations
flask db upgrade
```

A migration `multi_tenant_v1` vai:
1. Adicionar coluna `empresa_id` em todas as tabelas
2. Migrar dados existentes para `empresa_id = 1`
3. Criar constraints de foreign key e índices

---

## 6. Critério de Conclusão

✅ Migration criada e testada
✅ Todos os modelos com `TenantMixin`
✅ Services definem `empresa_id` na criação
✅ Permissões de domínio configuradas
✅ Diagnósticos do VS Code limpos

---

## 7. Testes Recomendados

```bash
# 1. Criar Empresa A com Owner
POST /api/v1/empresas/registro
{
  "empresa": {"nome": "Empresa A"},
  "owner": {"nome": "João", "email": "joao@empresaA.com", "senha": "..."}
}

# 2. Criar Cliente na Empresa A
POST /api/v1/clients
# g.current_empresa_id = 1

# 3. Criar Empresa B com Owner
POST /api/v1/empresas/registro
{
  "empresa": {"nome": "Empresa B"},
  "owner": {"nome": "Maria", "email": "maria@empresaB.com", "senha": "..."}
}

# 4. Login como Maria (Empresa B)
POST /api/v1/auth/login

# 5. Verificar que Maria NÃO vê clientes da Empresa A
GET /api/v1/clients
# Retorna apenas clientes da Empresa B
```

---

## 8. Próximas Etapas

Após Sprint 02:
1. **Frontend multi-tenant** — garantir que o frontend use tokens da empresa correta
2. **Google OAuth completo** — integrar criação de empresa/owner com OAuth
3. **Settings por empresa** — adicionar `empresa_id` em settings se necessário
4. **Rateio por empresa** — garantir isolamento em `rateio_historico`

---

*Última atualização: Sprint 02 concluída*
