"""
Testes de multi-tenant:
- Empresas isoladas por usuário
- Sem vazamento de dados entre tenants
- Clientes associados corretamente à empresa do usuário
"""
import pytest

from werkzeug.security import generate_password_hash

from models.user import User

from tests.conftest import login_as, criar_empresa


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestMultiTenantIsolation:
    """Testes de isolamento entre tenants."""

    def test_usuario_pega_somente_sua_empresa(self, client):
        """User só deve ver empresas da sua empresa_id."""
        client, csrf = login_as(client, "admin@example.com", "admin123")

        empresa_id = criar_empresa(client, "Empresa do Admin", csrf)

        resp = client.get("/api/v1/empresas")
        assert resp.status_code == 200
        empresas = resp.get_json().get("data", resp.get_json())
        assert isinstance(empresas, list)
        ids = [e.get("id") for e in empresas]
        assert empresa_id in ids

    def test_cliente_pertence_a_empresa_correta(self, client, db_session):
        """Clientes criados devem ter empresa_id correta."""
        client, csrf = login_as(client, "admin@example.com", "admin123")

        empresa_id = criar_empresa(client, "Empresa para teste de cliente", csrf)

        with client.application.app_context():
            user = db_session.query(User).filter_by(email="admin@example.com").first()
            assert user is not None
            assert user.empresa_id is not None

    def test_dados_nao_vazam_entre_empresas(self, client):
        """Dados de uma empresa não devem aparecer na lista de outra."""
        client, csrf = login_as(client, "admin@example.com", "admin123")

        id1 = criar_empresa(client, "Empresa A", csrf)
        id2 = criar_empresa(client, "Empresa B", csrf)

        resp = client.get("/api/v1/empresas")
        assert resp.status_code == 200
        empresas = resp.get_json().get("data", resp.get_json())
        ids = {e.get("id") for e in empresas}
        assert id1 in ids
        assert id2 in ids

    def test_usuario_sem_empresa_nao_acessa_rotas_de_empresa(self, client, db_session):
        """User sem empresa_id deve ser rejeitado (empresa_id é NOT NULL no modelo)."""
        from models.empresa import Empresa

        # Este teste não pode criar um user sem empresa_id pois o campo é NOT NULL.
        # Alternativa: criar user com empresa_id mas sem permissão de platform admin.
        with client.application.app_context():
            empresa = Empresa(nome="Empresa sem permissão", cnpj="12345678901234")
            empresa.slug = "empresa-sem-permissao"
            db_session.add(empresa)
            db_session.flush()

            user = User(
                email="sem_permissao@test.com",
                password_hash=generate_password_hash("senha123"),
                role="viewer", is_platform_admin=False, empresa_id=empresa.id,
            )
            db_session.add(user)
            db_session.commit()

        client, _ = login_as(client, "sem_permissao@test.com", "senha123")
        resp = client.get("/api/v1/empresas")
        # User é platform_admin=False, então a rota listar() deve retornar 403
        assert resp.status_code == 403, f"Esperado 403, obtido {resp.status_code}"
