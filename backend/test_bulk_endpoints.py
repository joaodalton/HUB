#!/usr/bin/env python3
"""test_bulk_endpoints.py — testa rotas de bulk (import/export CSV) + novas rotas de usuário/empresa.

Uso:
    python test_bulk_endpoints.py

Pre-requisitos:
    - backend/.env com SECRET_KEY, CSRF_SECRET_KEY, DATABASE_URL (sqlite para teste),
      GOOGLE_OAUTH_*, RESEND_API_KEY, etc.
    - Extensões Flask-Carilot, SQLAlchemy e as demais deps do projeto instaladas.
"""

import os
import sys
import json

# Garante que o diretório do backend está no PYTHONPATH para importação das extensões.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import secrets
from werkzeug.security import generate_password_hash

from app import create_app


def _make_token():
    return secrets.token_urlsafe(32)


def main():
    app = create_app()
    app.config["TESTING"] = True
    client = app.test_client()

    print("=== Bulk + Rotas de Usuário/Empresa ===")

    # ------------------------------------------------------------------
    # Criar empresa + admin no banco antes de tudo (para testes funcionais)
    # ------------------------------------------------------------------
    with app.app_context():
        from extensions import db
        from models.empresa import Empresa
        from models.user import User
        from utils.auth import hash_password

        # Criar empresa de teste se não existir
        empresa = Empresa.query.filter_by(slug="empresa-teste-bulk").first()
        if not empresa:
            empresa = Empresa(
                slug="empresa-teste-bulk",
                nome="Empresa Teste Bulk",
                cnpj="12.345.678/0001-99",
                email="contato@empresateste.com",
                telefone="(11) 99999-9999",
            )
            db.session.add(empresa)
            db.session.flush()
            print(f"Empresa creada: id={empresa.id}")

        # Criar admin de teste se não existir
        admin = User.query.filter_by(email="admin@example.com").first()
        if not admin:
            admin = User(
                empresa_id=empresa.id,
                email="admin@example.com",
                password_hash=hash_password("admin123"),
                nome="Admin",
                role="admin",
                is_platform_admin=True,
                status="ativo",
            )
            db.session.add(admin)
            db.session.commit()
            print(f"Admin creado: id={admin.id}")
        else:
            print(f"Admin ja existe: id={admin.id}")

    # ------------------------------------------------------------------
    # Teste 1: login do admin (platform admin)
    # ------------------------------------------------------------------
    print("Teste 1: login do admin...)", end=" ", flush=True)
    resp = client.post(
        "/api/v1/auth/login",
        json={
            "email": "admin@example.com",
            "senha": "admin123",
        },
    )
    body = resp.get_json(silent=True) or {}
    token = body.get("token") or body.get("access_token")
    if resp.status_code != 200 or not token:
        print(f"FAIL (status={resp.status_code}, body={body})")
        sys.exit(1)
    client.set_cookie("hub_token", token, domain="localhost", path="/")
    csrf = _make_token()
    client.set_cookie("hub_csrf", csrf, domain="localhost", path="/")
    print("OK")

    # ------------------------------------------------------------------
    # Teste 2: lista de usuários (GET /api/v1/users)
    # ------------------------------------------------------------------
    print("Teste 2: GET /api/v1/users...)", end=" ", flush=True)
    resp = client.get("/api/v1/users", headers={"X-CSRF-Token": csrf})
    if resp.status_code != 200:
        print(f"FAIL (status={resp.status_code})")
        sys.exit(1)
    print("OK")

    # ------------------------------------------------------------------
    # Teste 3: criação de usuário (POST /api/v1/users)
    # ------------------------------------------------------------------
    print("Teste 3: POST /api/v1/users...)", end=" ", flush=True)
    payload = {
        "nome": "Usuário Teste Bulk",
        "email": f"bulk-{secrets.token_hex(4)}@example.com",
        "senha": "senha123",
        "role": "viewer",
    }
    resp = client.post(
        "/api/v1/users",
        json=payload,
        headers={"X-CSRF-Token": csrf},
    )
    if resp.status_code not in (200, 201):
        print(f"FAIL (status={resp.status_code}, body={resp.get_json(silent=True)})")
        sys.exit(1)
    new_user = resp.get_json(silent=True) or {}
    user_id = new_user.get("data", {}).get("id")
    print(f"OK (id={user_id})")

    # ------------------------------------------------------------------
    # Teste 4: atualização de usuário (PUT /api/v1/users/<id>)
    # ------------------------------------------------------------------
    print("Teste 4: PUT /api/v1/users/<id>...)", end=" ", flush=True)
    resp = client.put(
        f"/api/v1/users/{user_id}",
        json={"nome": "Usuário Atualizado", "role": "operator"},
        headers={"X-CSRF-Token": csrf},
    )
    if resp.status_code != 200:
        print(f"FAIL (status={resp.status_code})")
        sys.exit(1)
    print("OK")

    # ------------------------------------------------------------------
    # Teste 5: desativar usuário (PUT /api/v1/users/<id>/ativo)
    # ------------------------------------------------------------------
    print("Teste 5: PUT /api/v1/users/<id>/ativo (desativar)...)", end=" ", flush=True)
    resp = client.put(
        f"/api/v1/users/{user_id}/ativo",
        json={"ativo": False},
        headers={"X-CSRF-Token": csrf},
    )
    if resp.status_code != 200:
        print(f"FAIL (status={resp.status_code})")
        sys.exit(1)
    print("OK")

    # ------------------------------------------------------------------
    # Teste 6: reativar usuário (PUT /api/v1/users/<id>/ativo)
    # ------------------------------------------------------------------
    print("Teste 6: PUT /api/v1/users/<id>/ativo (reativar)...)", end=" ", flush=True)
    resp = client.put(
        f"/api/v1/users/{user_id}/ativo",
        json={"ativo": True},
        headers={"X-CSRF-Token": csrf},
    )
    if resp.status_code != 200:
        print(f"FAIL (status={resp.status_code})")
        sys.exit(1)
    print("OK")

    # ------------------------------------------------------------------
    # Teste 7: redefinir senha (POST /api/v1/users/<id>/redefinir-senha)
    # ------------------------------------------------------------------
    print("Teste 7: POST /api/v1/users/<id>/redefinir-senha...)", end=" ", flush=True)
    resp = client.post(
        f"/api/v1/users/{user_id}/redefinir-senha",
        json={"nova_senha": "novasenha456", "confirmacao": "novasenha456"},
        headers={"X-CSRF-Token": csrf},
    )
    if resp.status_code != 200:
        print(f"FAIL (status={resp.status_code})")
        sys.exit(1)
    print("OK")

    # ------------------------------------------------------------------
    # Teste 8: exclusão de usuário (DELETE /api/v1/users/<id>)
    # ------------------------------------------------------------------
    print("Teste 8: DELETE /api/v1/users/<id>...)", end=" ", flush=True)
    resp = client.delete(
        f"/api/v1/users/{user_id}",
        headers={"X-CSRF-Token": csrf},
    )
    if resp.status_code != 200:
        print(f"FAIL (status={resp.status_code})")
        sys.exit(1)
    print("OK")

    # ------------------------------------------------------------------
    # Teste 9: criação de empresa (POST /api/v1/empresas) — apenas platform admin
    # ------------------------------------------------------------------
    print("Teste 9: POST /api/v1/empresas...)", end=" ", flush=True)
    payload = {
        "empresa": {
            "nome": "Empresa Teste Bulk 2",
            "cnpj": "98.765.432/0001-00",
            "email": "contato2@empresateste.com",
            "telefone": "(11) 98888-8888",
            "slug": f"empresa-teste-bulk-2-{secrets.token_hex(4)}",
        },
        "owner": {
            "nome": "Dono da Empresa 2",
            "email": f"dono2-{secrets.token_hex(4)}@empresateste.com",
            "senha": "dono123",
        },
    }
    resp = client.post(
        "/api/v1/empresas",
        json=payload,
        headers={"X-CSRF-Token": csrf},
    )
    if resp.status_code not in (200, 201):
        print(f"FAIL (status={resp.status_code}, body={resp.get_json(silent=True)})")
        sys.exit(1)
    new_empresa = resp.get_json(silent=True) or {}
    empresa_id = new_empresa.get("data", {}).get("empresa", {}).get("id")
    print(f"OK (id={empresa_id})")

    # ------------------------------------------------------------------
    # Teste 10: detalhe de empresa (GET /api/v1/empresas/<id>)
    # ------------------------------------------------------------------
    print("Teste 10: GET /api/v1/empresas/<id>...)", end=" ", flush=True)
    resp = client.get(
        f"/api/v1/empresas/{empresa_id}",
        headers={"X-CSRF-Token": csrf},
    )
    if resp.status_code != 200:
        print(f"FAIL (status={resp.status_code})")
        sys.exit(1)
    print("OK")

    # ------------------------------------------------------------------
    # Teste 11: exclusão de empresa com frase errada (DELETE /api/v1/empresas/<id>)
    # ------------------------------------------------------------------
    print("Teste 11: DELETE /api/v1/empresas/<id> (frase errada)...)", end=" ", flush=True)
    resp = client.delete(
        f"/api/v1/empresas/{empresa_id}",
        json={"confirmacao": "frase-incorreta"},
        headers={"X-CSRF-Token": csrf},
    )
    if resp.status_code == 200:
        print("FAIL (deveria ter rejeitado a frase errada)")
        sys.exit(1)
    print("OK (rejeitada)")

    # ------------------------------------------------------------------
    # Teste 12: exclusão de empresa com frase correta
    # ------------------------------------------------------------------
    print("Teste 12: DELETE /api/v1/empresas/<id> (frase correta)...)", end=" ", flush=True)
    resp = client.delete(
        f"/api/v1/empresas/{empresa_id}",
        json={"confirmacao": "confirmar"},
        headers={"X-CSRF-Token": csrf},
    )
    if resp.status_code != 200:
        print(f"FAIL (status={resp.status_code})")
        sys.exit(1)
    print("OK")

    # ------------------------------------------------------------------
    # Teste 13: bulk — exportação de clientes (GET /api/v1/bulk/clients/export)
    # ------------------------------------------------------------------
    print("Teste 13: GET /api/v1/bulk/clients/export...)", end=" ", flush=True)
    resp = client.get("/api/v1/bulk/clients/export")
    if resp.status_code != 200:
        print(f"FAIL (status={resp.status_code})")
        sys.exit(1)
    if not resp.data:
        print("FAIL (resposta vazia)")
        sys.exit(1)
    print("OK")

    # ------------------------------------------------------------------
    # Teste 14: bulk — importação de clientes (POST /api/v1/bulk/clients/import)
    # ------------------------------------------------------------------
    print("Teste 14: POST /api/v1/bulk/clients/import...)", end=" ", flush=True)
    csv_content = (
        "nome|email|telefone|cnpj|empresa_id\n"
        f"_cliente-teste-{secrets.token_hex(4)}|bulk1@example.com|(11) 99999-0001|12.345.678/0001-99|{empresa_id}\n"
    )
    resp = client.post(
        "/api/v1/bulk/clients/import",
        data=csv_content,
        headers={"X-CSRF-Token": csrf, "Content-Type": "text/csv"},
    )
    if resp.status_code not in (200, 201):
        print(f"FAIL (status={resp.status_code}, body={resp.get_json(silent=True)})")
        sys.exit(1)
    print("OK")

    # ------------------------------------------------------------------
    # Teste 15: bulk — importação com CSV inválido (deve falhar graceful)
    # ------------------------------------------------------------------
    print("Teste 15: POST /api/v1/bulk/clients/import (CSV inválido)...)", end=" ", flush=True)
    csv_invalido = "nome,email\nsem separador pipe\n"
    resp = client.post(
        "/api/v1/bulk/clients/import",
        data=csv_invalido,
        headers={"X-CSRF-Token": csrf, "Content-Type": "text/csv"},
    )
    body = resp.get_json(silent=True) or {}
    data = body.get("data", {})
    importados = data.get("importados", -1)
    falhas = data.get("falhas", [])
    if resp.status_code != 200:
        print(f"FAIL (status inesperado={resp.status_code})")
        sys.exit(1)
    if importados != 0 or len(falhas) == 0:
        print(f"FAIL (importados={importados}, falhas={len(falhas)} — deveria importar 0 e ter falhas)")
        sys.exit(1)
    print(f"OK (importados=0, falhas={len(falhas)})")

    print("\nTodos os testes passaram.")
    sys.exit(0)


if __name__ == "__main__":
    main()
