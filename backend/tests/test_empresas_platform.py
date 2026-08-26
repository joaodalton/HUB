"""
Testes do Sistema A — rotas de empresa protegidas por
@require_platform_admin().

API real:
- POST /empresas: {"empresa": {...}, "owner": {...}}
- DELETE /empresas/<id>: {"confirmacao": "CONFIRMAR"}
- /sair-plataforma: /api/v1/empresas/sair-plataforma (blueprint prefix)
"""
import uuid

import pytest
from werkzeug.security import generate_password_hash

from models.empresa import Empresa
from models.user import User


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _login(client, email: str, senha: str):
    """Faz login. Retorna (client, csrf_token). O client já tem cookies."""
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "senha": senha},
    )
    assert resp.status_code == 200, f"Login falhou: {resp.get_data(as_text=True)}"
    csrf = None
    for cookie in resp.headers.getlist("Set-Cookie"):
        if "hub_csrf=" in cookie:
            csrf = cookie.split("hub_csrf=")[-1].split(";")[0]
            break
    assert csrf is not None, "CSRF token não encontrado no login"
    return client, csrf


def _email_unico():
    """Gera um email de owner único para evitar conflito de unique no banco
    de teste (scope=session, persiste entre os testes)."""
    return f"owner-{uuid.uuid4().hex[:8]}@teste.com"


def _criar_empresa(client, nome: str, csrf: str):
    """Cria uma empresa via POST /empresas. Retorna o ID."""
    resp = client.post(
        "/api/v1/empresas",
        json={
            "empresa": {"nome": nome},
            "owner": {"nome": "Admin", "email": _email_unico(), "senha": "admin123"},
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code in (200, 201), \
        f"Falha ao criar empresa '{nome}': {resp.status_code} {resp.get_data(as_text=True)}"
    data = resp.get_json()
    return data.get("data", data).get("empresa", data).get("id")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestEmpresasPlatformAdmin:
    """Todas as rotas de empresa exigem platform admin."""

    def test_listar_retorna_403_para_nao_admin(self, client, db_session):
        """listar() sem platform admin deve retornar 403."""
        with client.application.app_context():
            empresa = Empresa(nome="Empresa bait", cnpj="12345678901234")
            empresa.slug = "empresa-bait"
            db_session.add(empresa)
            db_session.flush()
            empresa_id = empresa.id

            user = User(
                email="nao_admin@test.com",
                password_hash=generate_password_hash("senha123"),
                role="member",
                is_platform_admin=False,
                empresa_id=empresa_id,
            )
            db_session.add(user)
            db_session.commit()

        _login(client, "nao_admin@test.com", "senha123")
        resp = client.get("/api/v1/empresas")
        assert resp.status_code == 403, f"Esperado 403, obtido {resp.status_code}"

    def test_listar_retorna_200_para_admin(self, client):
        """listar() com platform admin deve retornar 200 com lista de empresas."""
        _login(client, "admin@example.com", "admin123")
        resp = client.get("/api/v1/empresas")
        assert resp.status_code == 200
        data = resp.get_json()
        lista = data.get("data", [])
        assert isinstance(lista, list)
        assert len(lista) >= 1  # pelo menos a empresa de teste do conftest

    def test_criar_empresa_sucessado_retorna_201(self, client):
        """criar() com platform admin deve retornar 201."""
        _, csrf = _login(client, "admin@example.com", "admin123")

        resp = client.post(
            "/api/v1/empresas",
            json={
                "empresa": {"nome": "Nova Empresa Teste"},
                "owner": {"nome": "Admin", "email": _email_unico(), "senha": "admin123"},
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code in (200, 201), \
            f"{resp.status_code} {resp.get_data(as_text=True)}"

        data = resp.get_json()
        empresa_data = data.get("data", data).get("empresa", data)
        assert empresa_data.get("id") is not None
        assert empresa_data.get("nome") == "Nova Empresa Teste"

    def test_criar_empresa_falha_para_nao_admin(self, client, db_session):
        """criar() sem platform admin deve retornar 403."""
        with client.application.app_context():
            empresa = Empresa(nome="Empresa bait", cnpj="12345678901234")
            empresa.slug = f"empresa-bait-{uuid.uuid4().hex[:8]}"
            db_session.add(empresa)
            db_session.flush()
            empresa_id = empresa.id

            user = User(
                email="cria_nao_admin@test.com",
                password_hash=generate_password_hash("senha123"),
                role="member",
                is_platform_admin=False,
                empresa_id=empresa_id,
            )
            db_session.add(user)
            db_session.commit()

        _, csrf = _login(client, "cria_nao_admin@test.com", "senha123")
        resp = client.post(
            "/api/v1/empresas",
            json={
                "empresa": {"nome": "Tentativa de criar"},
                "owner": {"nome": "Tento", "email": _email_unico(), "senha": "123456"},
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 403, \
            f"Esperado 403, obtido {resp.status_code}"

    def test_detalhe_empresa_sucesso(self, client):
        """detalhe() com platform admin deve retornar 200."""
        _, csrf = _login(client, "admin@example.com", "admin123")
        empresa_id = _criar_empresa(client, "Empresa para detalhe", csrf)

        resp = client.get(f"/api/v1/empresas/{empresa_id}")
        assert resp.status_code == 200
        data = resp.get_json()
        empresa = data.get("data", data)
        assert empresa.get("id") == empresa_id
        assert empresa.get("nome") == "Empresa para detalhe"

    def test_detalhe_empresa_nao_admin_retorna_403(self, client, db_session):
        """detalhe() sem platform admin deve retornar 403."""
        with client.application.app_context():
            empresa = Empresa(nome="Empresa para acessar", cnpj="12345678901234")
            empresa.slug = "empresa-para-acessar"
            db_session.add(empresa)
            db_session.flush()
            empresa_id = empresa.id

            user = User(
                email="detalhe_nao_admin@test.com",
                password_hash=generate_password_hash("senha123"),
                role="member",
                is_platform_admin=False,
                empresa_id=empresa_id,
            )
            db_session.add(user)
            db_session.commit()

        _login(client, "detalhe_nao_admin@test.com", "senha123")
        resp = client.get(f"/api/v1/empresas/{empresa_id}")
        assert resp.status_code == 403, \
            f"Esperado 403, obtido {resp.status_code}"

    def test_atualizar_empresa_sucesso(self, client):
        """atualizar() com platform admin deve retornar 200."""
        _, csrf = _login(client, "admin@example.com", "admin123")
        empresa_id = _criar_empresa(client, "Empresa para atualizar", csrf)

        resp = client.put(
            f"/api/v1/empresas/{empresa_id}",
            json={"nome": "Nome Atualizado"},
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 200, \
            f"{resp.status_code} {resp.get_data(as_text=True)}"

    def test_excluir_empresa_sucesso(self, client):
        """excluir() com platform admin deve deletar a empresa."""
        _, csrf = _login(client, "admin@example.com", "admin123")
        empresa_id = _criar_empresa(client, "Empresa para excluir", csrf)

        resp = client.delete(
            f"/api/v1/empresas/{empresa_id}",
            json={"confirmacao": "CONFIRMAR"},
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 200, \
            f"{resp.status_code} {resp.get_data(as_text=True)}"

        resp = client.get(f"/api/v1/empresas/{empresa_id}")
        assert resp.status_code == 404

    def test_entrar_empresa_sucesso(self, client):
        """entrar() com platform admin deve funcionar."""
        _, csrf = _login(client, "admin@example.com", "admin123")
        empresa_id = _criar_empresa(client, "Empresa para entrar", csrf)

        resp = client.post(
            f"/api/v1/empresas/{empresa_id}/entrar",
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code in (200, 201), \
            f"{resp.status_code} {resp.get_data(as_text=True)}"

    def test_sair_plataforma_sucesso(self, client):
        """sair_plataforma() com platform admin deve funcionar."""
        _, csrf = _login(client, "admin@example.com", "admin123")

        # Blueprint prefix: /api/v1/empresas/sair-plataforma
        resp = client.post(
            "/api/v1/empresas/sair-plataforma",
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 200, \
            f"{resp.status_code} {resp.get_data(as_text=True)}"
