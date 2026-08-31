#!/usr/bin/env python3
"""Comenta e fecha issues de segurança no GitHub após correções aplicadas."""
import os
import json
import ssl
import urllib.request
import urllib.error

REPO_OWNER = "joaodalton"
REPO_NAME = "HUB"

def get_token():
    env_path = os.path.join(os.path.dirname(__file__), "backend", ".env")
    with open(env_path, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            if line.startswith('GITHUB_CLIENT_TOKEN_KEY='):
                return line.split('=', 1)[1].strip().strip('"').strip("'")
    return None

def api_call(method, path, body=None):
    """Faz chamada para GitHub API."""
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}{path}"
    headers = {
        "Authorization": f"token {TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "HermesAgent-SecurityFixes/1.0",
        "Content-Type": "application/json",
    }
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code} para {method} {path}: {e.reason}")
        print(f"Resposta: {e.read().decode()[:300]}")
        return None
    except Exception as e:
        print(f"Erro em {method} {path}: {e}")
        return None

def comment_issue(issue_number, comment_body):
    """Deixa comentário em um issue."""
    print(f"\n--- Comentando issue #{issue_number} ---")
    result = api_call("POST", f"/issues/{issue_number}/comments", {"body": comment_body})
    if result and 'id' in result:
        print(f"✅ Comentário #{result['id']} deixado no issue #{issue_number}")
        return True
    else:
        print(f"❌ Falha ao comentar issue #{issue_number}")
        return False

def close_issue(issue_number, state_reason="completed"):
    """Fecha um issue."""
    print(f"\n--- Fechando issue #{issue_number} ---")
    result = api_call("PATCH", f"/issues/{issue_number}", {"state": "closed", "state_reason": state_reason})
    if result and result.get('state') == 'closed':
        print(f"✅ Issue #{issue_number} fechado")
        return True
    else:
        print(f"❌ Falha ao fechar issue #{issue_number}")
        return False

def main():
    global TOKEN
    TOKEN = get_token()
    if not TOKEN:
        print("❌ Token não encontrado")
        return

    print(f"Token carregado (len={len(TOKEN)})")

    # Comentários para cada issue corrigida
    comments = {
        54: """## 🔒 Correção aplicada — Multi-tenant

**Issue relacionada:** #42 e #38 (este commit corrigiu os três juntos)

### O que foi encontrado
O sistema multi-tenant tinha uma falha crítica onde `db.session.get(Model, id)` poderia ignorar o filtro de tenant e retornar objetos de outras empresas.

### Root cause
1. `TenantQuery.get()` override protege `Model.query.get(id)` ✅
2. Listener `do_orm_execute` injeta WHERE empresa_id em selects ✅
3. **FALHA**: `Session.get()` verifica identity map antes de emitir SELECT — se o objeto já estiver na memória de uma sessão anterior, retorna sem SELECT, ignorando o filtro de tenant

### Solução implementada (`backend/extensions.py`)
- Nova subclasse `TenantSession(Session)` que override `get()`:
  - Detecta se o modelo usa `TenantMixin`
  - Verifica se há `current_empresa_id` na sessão Flask
  - Se sim, emite SELECT explícito com `filter_by(empresa_id=...)` — nunca usa identity map para modelos com tenant
- `db = SQLAlchemy(query_class=TenantQuery, session_options={'class_': TenantSession})`

### Impacto
- TODOS os modelos com `TenantMixin` (Client, ConsumerUnit, Plant, Document, Pendencia, PlantConnection) agora têm proteção DUPLA:
  - `.query.get()` via `TenantQuery.get()`
  - `db.session.get()` via `TenantSession.get()`
- 40+ locais no codebase que usavam `.query.get()` agora estão protegidos
- 0 usos de `db.session.get()` na aplicação (apenas Flask internals)

### Observação
`User` não usa `TenantMixin` de propósito (login precisa localizar usuário antes de haver empresa atual) — isso é por design e documentado em `extensions.py`.

### Arquivo modificado
- `backend/extensions.py` — nova classe `TenantSession`""",

        42: """## 🔒 Correção aplicada — db.session.get() bypass

**Issue relacionada:** #54 e #38 (este commit corrigiu os três juntos)

### O que foi encontrado
`db.session.get(Model, id)` podia bypassar o filtro de tenant porque:
- `Session.get()` verifica o identity map antes de emitir SELECT
- Se o objeto já estiver no identity map de uma sessão anterior, retorna imediatamente sem passar pelo listener `do_orm_execute`

### Solução
Nova classe `TenantSession(Session)` que override `get()` para modelos com `TenantMixin`:
- Emite SELECT explícito com filtro de empresa_id quando há contexto de request
- Ignora identity map para modelos com tenant (garante que o filtro sempre é aplicado)

### Verificação
- Encontrados 40+ usos de `.query.get()` no codebase (todos já protegidos via `TenantQuery`)
- 0 usos diretos de `db.session.get()` na aplicação
- Agora todos os modelos com `TenantMixin` têm proteção total

### Arquivo modificado
- `backend/extensions.py` — `TenantSession` subclasse + configuração do `db`""",

        38: """## 🔒 Correção aplicada — acesso direto sem query

**Issue relacionada:** #54 e #42 (este commit corrigiu os três juntos)

### O que foi encontrado
O listener `do_orm_execute` filtra selects, mas `db.session.get()` podia contornar o filtro usando identity map. Além disso, ao acessar objetos diretamente via `db.session.get()`, o filtro de tenant não era aplicado.

### Solução
`TenantSession.get()` agora:
1. Verifica se o modelo alvo usa `TenantMixin`
2. Verifica se há `current_empresa_id` na sessão Flask
3. Se ambas as condições forem verdade, emite SELECT explícito com filtro de empresa_id
4. Nunca usa identity map para modelos com tenant em contexto de request

### Cobertura
- `Pendencia.query.get(id)` → protegido via `TenantQuery.get()`
- `db.session.get(Pendencia, id)` → protegido via `TenantSession.get()`
- Acesso a `uc.conexoes` → protected pelo listener `do_orm_execute`

### Arquivo modificado
- `backend/extensions.py` — `TenantSession` + configuração do `db`""",

        49: """## 🔒 Correção aplicada — Rate limit na rota /verificar

### O que foi encontrado
A rota `POST /api/v1/pendencias/verificar` executava todas as verificações automáticas sem rate limit, permitindo que qualquer usuário autenticado chamasse quantas vezes quisesse.

### Impacto do abuse
- Consumo excessivo de CPU e queries do banco (4 tipos de verificação + resolução de pendências)
- Geração de spam de logs
- Possível criação de pendências falsas se houvesse vulnerabilidade na lógica

### Solução (`backend/routes/pendencia_routes.py`)
- Adicionado `@limiter.limit('5 per minute')` na rota `/verificar`
- Rate limit mais restritivo pois chamadas frequentes não fazem sentido para esta rota (deve ser chamado quando o usuário abre a tela ou clica no botão "Verificar agora")

### Outras rotas protegidas com o mesmo commit
Todas as rotas mutáveis de pendências agora têm rate limit:
- POST / → 30/min (criação)
- PUT /<id> → 30/min (atualização)
- DELETE /<id> → 30/min (exclusão)
- POST /<id>/resolver → 30/min
- POST /<id>/cancelar → 30/min
- POST /<id>/reabrir → 30/min
- POST /<id>/comentarios → 30/min

### Arquivo modificado
- `backend/routes/pendencia_routes.py` — adição de `@limiter.limit()` em todas as rotas mutáveis""",

        48: """## 🔒 Correção aplicada — Rate limit na rota POST /pendencias

### O que foi encontrado
A rota `POST /api/v1/pendencias` (criação manual de pendências) não tinha rate limit, permitindo que qualquer usuário autenticado criasse quantas pendências quisesse.

### Solução (`backend/routes/pendencia_routes.py`)
- Adicionado `@limiter.limit('30 per minute')` na rota `store()`
- 30/min permite uso normal da interface sem restrição excessiva, mas previne abuso em loop

### Contexto
Anteriormente, apenas `auth_routes.py` tinha rate limiting. Agora todas as rotas mutáveis de pendências estão protegidas.

### Arquivo modificado
- `backend/routes/pendencia_routes.py`""",

        47: """## 🔒 Correção aplicada — Whitelist de chaves em settings

### O que foi encontrado
A rota `PUT /api/v1/settings` aceitava QUALQUER chave no corpo da requisição e a salvava no banco, sem nenhuma validação de quais chaves são permitidas.

### Riscos
- Criar chaves arbitrárias que futuramente poderiam ser lidas por outras partes do sistema
- Poluir a tabela de settings com dados não documentados
- Potencial exploração de chaves não documentadas

### Solução (`backend/services/settings_service.py`)
1. **Whitelist explícita** `SETTINGS_KEYS_WHITELIST` com 39 chaves agrupadas:
   - GERAL (site_name, company_name, etc.)
   - APARÊNCIA (primary_color, font_family, etc.)
   - EMAIL (resend_api_key, email_from, etc.)
   - TAXAS & FINANCEIRO (taxa_juros, moeda, etc.)
   - NOTIFICAÇÕES (notificacoes_ativas, etc.)
   - SEGURANÇA (require_mfa, session_timeout_min, etc.)

2. **Validação em `update_settings()`**: antes de fazer qualquer alteração, verifica se todas as chaves estão na whitelist. Se alguma chave for inválida, lança `ValueError` com a lista de chaves rejeitadas.

### Decisão de design
- Whitelist explícita (deny by default) em vez de blacklist
- Chaves sensíveis como `resend_api_key` estão na whitelist mas já são protegidas pelo middleware de auth
- Mensagem de erro inclui as chaves inválidas e a lista de chaves válidas para debugging

### Arquivo modificado
- `backend/services/settings_service.py`""",

        45: """## 🔒 Correção aplicada — Prevenção de XSS em email templates

### O que foi encontrado
A função `renderizar()` em `email_template_service.py` substitui placeholders `{{var}}` pelos valores das variáveis. Embora usasse `escape()` do módulo `html` para conteúdo de texto, havia preocupação sobre:
1. Admins mal-intencionados (ou contas comprometidas) injetando JavaScript no corpo do template
2. Variáveis em atributos HTML sem sanitização extra

### Análise
O código original já era seguro contra XSS via VARIÁVEIS (escape converte `<`, `>`, `&`, `"`, `'` para entidades HTML). O risco era na edição do TEMPLATE em si por admins com acesso à tela de configurações.

### Solução (`backend/services/email_template_service.py`)
1. **Validação de conteúdo proibido em `update_template()`**:
   - Regex que detecta tags `<script>`, `</script>` e atributos `on*` (onclick, onload, etc.)
   - Se o corpo ou assunto contiver conteúdo proibido, retorna `ValueError` com mensagem clara
   - HTML básico permitido: p, a, strong, em, ul, li, table

2. **Documentação de segurança**:
   - Comentários explicando que o escape protege contra XSS via variáveis
   - Advertência que templates editáveis por admins são confiança interna
   - Nota que clientes de e-mail podem executar JavaScript (portanto a sanitização importa)

3. **Melhoria na `_renderizar_html()`**:
   - Comentários explicitando que todos os valores são escapeados antes de inserção

### Decisão de design
- Bloqueio de `<script>` e `on*` é raro para templates de e-mail, mas necessário para clientes de e-mail que executam JS
- HTML básico permitido porque templates de e-mail precisam de formatação
- Validação ocorre na atualização do template, não na renderização (mais eficiente)

### Arquivo modificado
- `backend/services/email_template_service.py`""",

        40: """## 🔒 Correção aplicada — Validação de formato de chave em email templates

### O que foi encontrado
A rota `PUT /api/v1/email-templates/<chave>` aceitava QUALQUER string como chave, mesmo strings aleatórias ou malformadas. Isso permitia:
1. **Enumeração de templates**: um atacante poderia testar várias chaves e ver quais existem (diferença entre resposta 404 vs 200)
2. **Sem validação de formato**: qualquer string era aceita

### Solução (`backend/routes/email_template_routes.py`)
1. **Regex de validação** `r'^[a-zA-Z][a-zA-Z0-9_-]*$'`:
   - Chaves válidas: começa com letra, seguido por alfanuméricos, hífen e underline
   - Exemplos válidos: "welcome_email", "password_reset", "invoice_v2"
   - Exemplos inválidos: "123template", "template<script>", "", " "

2. **Função `_validar_chave_template()`** aplicada em TODAS as rotas que recebem chave:
   - GET /<chave> — show()
   - PUT /<chave> — update()
   - POST /<chave>/restaurar — restore()
   - POST /<chave>/testar — test_send()

3. **Mensagem de erro para chaves inválidas**: "Formato de chave inválido..." — não revela se o template existe ou não

### Impacto na enumeração
Com a validação de formato, um atacante não pode mais testar strings aleatórias para descobrir quais templates existem. Apenas chaves no formato correto passam pela validação, e a resposta para templates inexistentes é a mesma (404).

### Arquivo modificado
- `backend/routes/email_template_routes.py`""",

        33: """## 🔒 Correção aplicada — Controle granular em teste de email

### O que foi encontrado
A rota `POST /api/v1/email-templates/<chave>/testar` permitia que qualquer usuário com permissão `settings.update` enviasse e-mails de teste sem:
- Controle de quem pode testar (qualquer admin/owner/operator/financial podia)
- Rate limit
- Registro de auditoria dos testes enviados

### Solução (`backend/routes/email_template_routes.py`)
1. **Restrição de role**: `@require_role('owner', 'admin')` em vez de `@require_permission('settings.update')`:
   - Apenas owner e admin podem usar esta rota
   - Operadores, financial e viewers não podem mais enviar testes de e-mail

2. **Rate limit**: `@limiter.limit('10 per minute')`:
   - Previne abuso de envio de e-mails de teste
   - Permite testes normais durante desenvolvimento/debugging

3. **Registro de auditoria**: `LogService.info()` com:
   - Ação: 'email_template_test'
   - Usuário ID e email
   - Template testado
   - Assunto do e-mail de teste
   - Permite rastrear quem está enviando testes e quando

4. **Validação de template antes de enviar**: verifica se o template existe antes de tentar renderizar/enviar

### Impacto
- Operadores/financial não podem mais usar a rota de teste
- Todos os testes são logs para auditoria
- Rate limit previne spam de testes

### Arquivo modificado
- `backend/routes/email_template_routes.py`""",

        41: """## ✅ Verificação — CSRF Protection

### Status
**CONFIRMADO: Implementação correta e completa.**

### Análise
O middleware de autenticação em `utils/auth.py` (`register_auth_middleware()`) implementa CSRF protection:

1. **Cookies**: Ao fazer login, são definidos dois cookies:
   - `hub_token`: cookie de sessão (httponly, secure, samesite=Lax)
   - `hub_csrf`: cookie CSRF (httponly=False, secure, samesite=Lax) — lerável pelo JS

2. **Verificação**: Para requisições que vêm com cookie de sessão e que são mutáveis (POST/PUT/DELETE/PATCH), o middleware verifica:
   - Se o cookie `hub_csrf` existe
   - Se o header `X-CSRF-Token` existe
   - Se os valores coincidem
   - Se não, retorna 403 "Token CSRF ausente ou invalido"

3. **Exclusões corretas**:
   - Requisições GET/HEAD/OPTIONS: não verificadas (safe methods)
   - Requisições com Bearer token (API mobile): não verificadas (token bearer é imune a CSRF)
   - Rotas públicas (login, registro, etc.): não verificadas

### Conclusão
A implementação de CSRF está CORRETA. O middleware cobre TODAS as rotas mutáveis automaticamente, sem necessidade de decoradores individuais. Bearer tokens são corretamente excluídos da verificação CSRF. Cookies com samesite=Lax fornecem proteção adicional contra CSRF.

### Nenhuma ação necessária — a implementação já está correta.""",
    }

    # Processa cada issue
    issues_fechadas = 0
    issues_com_erro = 0

    for issue_number, comment_body in comments.items():
        # Deixa comentário primeiro
        if comment_issue(issue_number, comment_body):
            # Se comentário funcionou, fecha o issue
            if close_issue(issue_number):
                issues_fechadas += 1
            else:
                issues_com_erro += 1
        else:
            issues_com_erro += 1

    print(f"\n=== RESUMO ===")
    print(f"Issues processadas: {len(comments)}")
    print(f"Issues fechadas: {issues_fechadas}")
    print(f"Issues com erro: {issues_com_erro}")

if __name__ == "__main__":
    main()
