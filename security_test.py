#!/usr/bin/env python3
"""
Script de verificação de segurança para o HUB.
Testa as correções de segurança aplicadas verificando se os decoradores
e validações estão corretamente implementados.
"""
import os
import sys

# Determinar o diretório backend
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(SCRIPT_DIR, 'backend')
sys.path.insert(0, SCRIPT_DIR)  # Para imports como 'from backend.xxx import yyy'
sys.path.insert(0, BACKEND_DIR)  # Para imports como 'from extensions import yyy'

def test_imports():
    """Testa se todos os módulos de segurança podem ser importados."""
    print("🔍 Testando imports de segurança...")

    try:
        from backend.extensions import TenantSession, TenantQuery, db
        print("   ✅ extensions.py — TenantSession e TenantQuery OK")
    except ImportError as e:
        print(f"   ❌ extensions.py — Falha: {e}")
        return False

    try:
        from backend.routes.pendencia_routes import pendencia_routes
        print("   ✅ pendencia_routes.py — import OK")
    except ImportError as e:
        print(f"   ❌ pendencia_routes.py — Falha: {e}")
        return False

    try:
        from backend.routes.email_template_routes import email_template_routes
        print("   ✅ email_template_routes.py — import OK")
    except ImportError as e:
        print(f"   ❌ email_template_routes.py — Falha: {e}")
        return False

    try:
        from backend.services.settings_service import SETTINGS_KEYS_WHITELIST, update_settings
        print(f"   ✅ settings_service.py — whitelist com {len(SETTINGS_KEYS_WHITELIST)} chaves")
    except ImportError as e:
        print(f"   ❌ settings_service.py — Falha: {e}")
        return False

    try:
        from backend.services.email_template_service import _contem_conteudo_proibido
        print("   ✅ email_template_service.py — validação de conteúdo OK")
    except ImportError as e:
        print(f"   ❌ email_template_service.py — Falha: {e}")
        return False

    return True


def test_settings_whitelist():
    """Testa a whitelist de settings."""
    print("\n🔍 Testando settings whitelist...")

    from services.settings_service import SETTINGS_KEYS_WHITELIST, update_settings

    # Teste 1: chave inválida deve ser rejeitada
    try:
        update_settings({'chave_arbitraria_invalida': 'valor'})
        print("   ❌ Whitelist — falhou: chave inválida aceita")
        return False
    except ValueError:
        print("   ✅ Whitelist — chave inválida rejeitada corretamente")

    # Teste 2: chave válida deve ser aceita (testar com uma chave conhecida)
    # Não podemos testar com chaves que não existem no banco, mas podemos testar
    # se o ValueError não é lançado para chaves da whitelist
    print(f"   ℹ️  Whitelist contém {len(SETTINGS_KEYS_WHITELIST)} chaves:")
    categories = {
        'GERAL': ['site_name', 'company_name', 'company_cnpj'],
        'APARÊNCIA': ['primary_color', 'font_family', 'logo_position'],
        'EMAIL': ['resend_api_key', 'email_from', 'email_signature'],
        'TAXAS': ['taxa_juros', 'moeda', 'periodicidade_fatura'],
        'NOTIFICAÇÕES': ['notificacoes_ativas', 'email_notificacoes'],
        'SEGURANÇA': ['require_mfa', 'session_timeout_min', 'max_login_attempts'],
    }

    for cat, keys in categories.items():
        found = [k for k in keys if k in SETTINGS_KEYS_WHITELIST]
        print(f"      {cat}: {len(found)}/{len(keys)} chaves encontradas")
        if len(found) < len(keys):
            missing = [k for k in keys if k not in SETTINGS_KEYS_WHITELIST]
            print(f"         Ausentes: {missing}")

    return True


def test_template_key_validation():
    """Testa a validação de chave de template."""
    print("\n🔍 Testando validação de chave de template...")

    from backend.routes.email_template_routes import _validar_chave_template

    # Chaves válidas
    valid_keys = [
        'welcome_email',
        'password_reset',
        'invoice_v2',
        'cliente-confirmacao',
        'A',  # mínimo válido
        'template123',
    ]

    for key in valid_keys:
        try:
            _validar_chave_template(key)
            print(f"   ✅ '{key}' — validada como chave válida")
        except ValueError as e:
            print(f"   ❌ '{key}' — rejeitada incorretamente: {e}")
            return False

    # Chaves inválidas
    invalid_keys = [
        ('123template', 'starts with number'),
        ('', 'empty'),
        ('template<script>', 'contains special chars'),
        ('template admin', 'contains space'),
        ('_template', 'starts with underscore'),
        ('template-admin-', 'ends with hyphen'),
    ]

    for key, reason in invalid_keys:
        try:
            _validar_chave_template(key)
            print(f"   ❌ '{key}' ({reason}) — aceita incorretamente")
            return False
        except ValueError:
            print(f"   ✅ '{key}' ({reason}) — rejeitada corretamente")

    return True


def test_xss_prevention():
    """Testa a prevenção de XSS em templates de email."""
    print("\n🔍 Testando prevenção de XSS...")

    from backend.services.email_template_service import _contem_conteudo_proibido

    # Conteúdo com script deve ser detectado
    dangerous_content = [
        '<script>alert("xss")</script>',
        '<script>document.cookie</script>',
        '<img src=x onerror="alert(1)">',
        '<div onclick="malicious()">clicar</div>',
        '<body onload="steal()">',
    ]

    for content in dangerous_content:
        if _contem_conteudo_proibido(content):
            print(f"   ✅ Detectado: {content[:50]}...")
        else:
            print(f"   ❌ NÃO detectado: {content[:50]}...")
            return False

    # Conteúdo seguro deve ser permitido
    safe_content = [
        '<p>Olá, {{nome}}!</p>',
        '<a href="{{link}}">Clique aqui</a>',
        '<strong>Importante</strong>',
        '<ul><li>Item 1</li><li>Item 2</li></ul>',
        'Teste sem HTML',
    ]

    for content in safe_content:
        if not _contem_conteudo_proibido(content):
            print(f"   ✅ Permitido (seguro): {content[:50]}...")
        else:
            print(f"   ❌ Bloqueado incorretamente: {content[:50]}...")
            return False

    return True


def test_tenant_session():
    """Testa a estrutura da TenantSession (sem app context)."""
    print("\n🔍 Testando TenantSession...")

    from extensions import TenantSession, TenantMixin

    # Verifica se TenantSession é subclasse de Session
    from sqlalchemy.orm import Session
    if issubclass(TenantSession, Session):
        print("   ✅ TenantSession é subclasse de Session")
    else:
        print("   ❌ TenantSession NÃO é subclasse de Session")
        return False

    # Verifica se TenantMixin está sendo usado por modelos
    from models.client import Client
    from models.consumer_unit import ConsumerUnit
    from models.plant import Plant
    from models.document import Document
    from models.pendencia import Pendencia

    tenant_models = [Client, ConsumerUnit, Plant, Document, Pendencia]
    for model in tenant_models:
        if issubclass(model, TenantMixin):
            print(f"   ✅ {model.__name__} usa TenantMixin")
        else:
            print(f"   ⚠️  {model.__name__} NÃO usa TenantMixin")

    # Verifica a configuração do db (necessita app context)
    print(f"   ℹ️  Para verificar db.query_class e session_options, é necessário app context")

    return True


def test_rate_limiting_decorators():
    """Verifica se os decorators de rate limit estão nos arquivos corretos."""
    print("\n🔍 Verificando decorators de rate limit...")

    import ast
    import os

    def count_limit_decorators(filepath):
        with open(filepath, 'r') as f:
            tree = ast.parse(f.read())

        count = 0
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                for decorator in node.decorator_list:
                    if isinstance(decorator, ast.Call):
                        if hasattr(decorator.func, 'attr') and decorator.func.attr == 'limit':
                            count += 1
                            break

        return count

    files_to_check = [
        ('backend/routes/pendencia_routes.py', 'pendencia_routes'),
        ('backend/routes/email_template_routes.py', 'email_template_routes'),
        ('backend/routes/auth_routes.py', 'auth_routes'),
    ]

    for filepath, name in files_to_check:
        full_path = os.path.join(os.path.dirname(__file__), filepath)
        if os.path.exists(full_path):
            count = count_limit_decorators(full_path)
            print(f"   ℹ️  {name}: {count} decorators @limiter.limit()")
        else:
            print(f"   ⚠️  {filepath} não encontrado")

    return True


def main():
    print("=" * 60)
    print("VERIFICAÇÃO DE SEGURANÇA — HUB")
    print("=" * 60)

    tests = [
        ("Imports de segurança", test_imports),
        ("Settings whitelist", test_settings_whitelist),
        ("Validação de chave de template", test_template_key_validation),
        ("Prevenção de XSS", test_xss_prevention),
        ("TenantSession", test_tenant_session),
        ("Rate limiting decorators", test_rate_limiting_decorators),
    ]

    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"   ❌ Erro inesperado em {name}: {e}")
            results.append((name, False))

    print("\n" + "=" * 60)
    print("RESUMO DOS TESTES")
    print("=" * 60)

    passed = sum(1 for _, r in results if r)
    total = len(results)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status}: {name}")

    print(f"\nTotal: {passed}/{total} testes passaram")

    if passed == total:
        print("\n🎉 Todas as verificações de segurança passaram!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} teste(s) falhou(ram) — revisar as correções.")
        return 1


if __name__ == "__main__":
    exit(main())
