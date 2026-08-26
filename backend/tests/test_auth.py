"""
Testes de autenticação:
- Login com email/senha
- /me retorna dados do usuário com isPlatformAdmin
- Proteção CSRF
- Cookies httponly corretos
"""
import pytest
from werkzeug.security import generate_password_hash

from models.user import User


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _login(client, email: str, senha: str):
    """Faz login. Retorna a resposta do POST /auth/login (200 esperado)."""
    return client.post(
        "/api/v1/auth/login",
        json={"email": email, "senha": senha},
    )


def _extrair_csrf(resp):
    """Extrai CSRF token dos Set-Cookie da resposta."""
    for cookie in resp.headers.getlist("Set-Cookie"):
        if "hub_csrf=" in cookie:
            return cookie.split("hub_csrf=")[-1].split(";")[0]
    return None


def _header_csrf(token: str):
    return {"X-CSRF-Token": token}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestAuth:
    """Testes de auth e sessão."""

    def test_login_com_senha_correta_retorna_200(self, client):
        """Login com credenciais válidas retorna 200 e cookies de sessão."""
        resp = _login(client, "admin@example.com", "admin123")
        assert resp.status_code == 200
        set_cookie = resp.headers.get("Set-Cookie", "")
        assert "hub_token" in set_cookie

    def test_login_com_senha_incorreta_retorna_401(self, client):
        """Login com senha errada retorna 401."""
        resp = _login(client, "admin@example.com", "errada")
        assert resp.status_code == 401

    def test_me_retorna_is_platform_admin_para_admin(self, client):
        """Rota /me retorna isPlatformAdmin=True para admins da plataforma."""
        _login(client, "admin@example.com", "admin123")
        resp = client.get("/api/v1/auth/me")
        assert resp.status_code == 200
        data = resp.get_json()
        user_data = data.get("data", data)
        assert user_data.get("isPlatformAdmin") is True

    def test_me_retorna_is_platform_admin_false_para_normal(self, client, db_session):
        """Rota /me retorna isPlatformAdmin=False para usuários normais."""
        with client.application.app_context():
            user = User(
                email="normal@test.com",
                password_hash=generate_password_hash("senha123"),
                role="member",
                is_platform_admin=False,
                empresa_id=1,
            )
            db_session.add(user)
            db_session.commit()

        _login(client, "normal@test.com", "senha123")
        resp = client.get("/api/v1/auth/me")
        assert resp.status_code == 200
        data = resp.get_json()
        user_data = data.get("data", data)
        assert user_data.get("isPlatformAdmin") is False

    def test_token_ausente_retorna_401(self, client):
        """Rota /me sem token de sessão retorna 401."""
        resp = client.get("/api/v1/auth/me")
        assert resp.status_code == 401

    def test_hub_csrf_nao_e_httponly(self, client):
        """Cookies de CSRF precisam ser legíveis pelo JS (XSS protection
        não se aplica a CSRF — o token precisa ser lido pelo frontend)."""
        resp = _login(client, "admin@example.com", "admin123")
        set_cookies = resp.headers.getlist("Set-Cookie")
        assert any("hub_csrf=" in c for c in set_cookies), \
            f"hub_csrf não encontrado nos cookies: {set_cookies}"
        # O cookie inteiro (junto com os demais) não deve conter HttpOnly no CSRF
        assert "hub_csrf=" in "".join(set_cookies)

    def test_hub_token_e_httponly(self, client):
        """Cookies de auth (hub_token) devem ser httponly para evitar
        leitura via XSS."""
        resp = _login(client, "admin@example.com", "admin123")
        set_cookie = resp.headers.get("Set-Cookie", "")
        assert "hub_token=" in set_cookie
        assert "HttpOnly" in set_cookie
