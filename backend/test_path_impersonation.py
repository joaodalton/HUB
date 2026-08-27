#!/usr/bin/env python3
"""
test_path_impersonation.py — testa o fluxo de impersonação via path explícito.

Este é o teste que comprova que o bug original ("clicar no nome de uma
empresa e os dados não trocarem") está resolvido de verdade: o platform
admin acessa /empresa/<slug-B>/clients e vê só os clientes de B, não os
da própria empresa de origem ou da plataforma.

Uso:
    python test_path_impersonation.py

Pre-requisitos:
    - backend/.env com SECRET_KEY, CSRF_SECRET_KEY, DATABASE_URL (sqlite
      para teste), etc.
    - Extensões Flask-Carilot, SQLAlchemy e as demais deps do projeto
      instaladas.
"""

import os
import sys
import json
import secrets

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from werkzeug.security import generate_password_hash


def _make_token() -> str:
    return secrets.token_urlsafe(32)


def _hash(password: str) -> str:
    return generate_password_hash(password)


def _login(client, email: str, senha: str) -> str | None:
    """Faz login e retorna o token de sessão (cookie hub_token)."""
    resp = client.post(
        '/api/v1/auth/login',
        data=json.dumps({'email': email, 'senha': senha}),
        content_type='application/json',
    )
    data = json.loads(resp.data)
    if not data.get('success'):
        return None
    # O cookie de sessão vem na resposta; para testes com test_client,
    # o cookie é mantido automaticamente entre chamadas.
    return data.get('token')


def main():
    app = create_app()
    app.config['TESTING'] = True
    client = app.test_client()

    print("=== Teste de Impersonação via Path ===\n")

    with app.app_context():
        from extensions import db
        from models.empresa import Empresa
        from models.user import User
        from models.client import Client

        # ------------------------------------------------------------------
        # Setup: duas empresas com clientes diferentes + platform admin
        # ------------------------------------------------------------------

        # Empresa A
        empresa_a = Empresa.query.filter_by(slug='empresa-a-test').first()
        if not empresa_a:
            empresa_a = Empresa(
                slug='empresa-a-test',
                nome='Empresa A',
                cnpj='11.111.111/0001-11',
                email='contato@a.com',
                telefone='(11) 1111-1111',
            )
            db.session.add(empresa_a)
            db.session.flush()
            print(f"Empresa A criada: id={empresa_a.id}")

        # Empresa B
        empresa_b = Empresa.query.filter_by(slug='empresa-b-test').first()
        if not empresa_b:
            empresa_b = Empresa(
                slug='empresa-b-test',
                nome='Empresa B',
                cnpj='22.222.222/0002-22',
                email='contato@b.com',
                telefone='(22) 2222-2222',
            )
            db.session.add(empresa_b)
            db.session.flush()
            print(f"Empresa B criada: id={empresa_b.id}")

        # Platform admin — empresa de casa = nenhuma das duas
        platform_admin = User.query.filter_by(
            email='platform@example.com'
        ).first()
        if not platform_admin:
            platform_admin = User(
                empresa_id=None,
                email='platform@example.com',
                password_hash=_hash('platform123'),
                nome='Platform Admin',
                role='admin',
                is_platform_admin=True,
                status='ativo',
            )
            db.session.add(platform_admin)
            db.session.commit()
            print(f"Platform admin criado: id={platform_admin.id}")
        else:
            print(f"Platform admin já existe: id={platform_admin.id}")

        # Cliente de A
        cliente_a = Client.query.filter_by(
            empresa_id=empresa_a.id, nome='Cliente A-1'
        ).first()
        if not cliente_a:
            cliente_a = Client(
                empresa_id=empresa_a.id,
                nome='Cliente A-1',
                cpf='11111111111',
                email='a1@teste.com',
                telefone='(11) 1111-1111',
            )
            db.session.add(cliente_a)
            db.session.flush()
            print(f"Cliente A-1 criado: id={cliente_a.id}")

        # Cliente de B
        cliente_b = Client.query.filter_by(
            empresa_id=empresa_b.id, nome='Cliente B-1'
        ).first()
        if not cliente_b:
            cliente_b = Client(
                empresa_id=empresa_b.id,
                nome='Cliente B-1',
                cpf='22222222222',
                email='b1@teste.com',
                telefone='(22) 2222-2222',
            )
            db.session.add(cliente_b)
            db.session.flush()
            print(f"Cliente B-1 criado: id={cliente_b.id}")

        db.session.commit()
        print()

    # ------------------------------------------------------------------
    # Teste 1: login como platform admin
    # ------------------------------------------------------------------
    print("Teste 1: login como platform admin...")
    token = _login(client, 'platform@example.com', 'platform123')
    if not token:
        print("  FAIL — não foi possível fazer login")
        return
    print("  OK — logado como platform admin")

    # ------------------------------------------------------------------
    # Teste 2: GET /empresa/<slug-B>/clients → só clientes de B
    # ------------------------------------------------------------------
    print(
        f"\nTeste 2: GET /empresa/{empresa_b.slug}/clients "
        "→ deve trazer só cliente de B"
    )
    resp = client.get(f'/api/v1/empresas/{empresa_b.slug}/clients')
    data = json.loads(resp.data)
    if not data.get('success'):
        print(f"  FAIL — resposta: {data}")
        return
    clientes_b = data.get('data', [])
    # Deve ter exatamente 1 cliente (Cliente B-1) e não o Cliente A-1
    nomes_b = {c['nome'] for c in clientes_b}
    if 'Cliente B-1' not in nomes_b:
        print(f"  FAIL — não encontrou Cliente B-1. Clientes: {nomes_b}")
        return
    if 'Cliente A-1' in nomes_b:
        print(f"  FAIL — encontrou Cliente A-1 (de outra empresa)! Clientes: {nomes_b}")
        return
    if len(clientes_b) != 1:
        print(f"  FAIL — esperado 1 cliente, encontrados {len(clientes_b)}: {nomes_b}")
        return
    print(f"  OK — {len(clientes_b)} cliente(s) de B, sem vazamento de A: {nomes_b}")

    # ------------------------------------------------------------------
    # Teste 3: GET /empresa/<slug-A>/clients → só clientes de A
    # ------------------------------------------------------------------
    print(
        f"\nTeste 3: GET /empresa/{empresa_a.slug}/clients "
        "→ deve trazer só cliente de A"
    )
    resp = client.get(f'/api/v1/empresas/{empresa_a.slug}/clients')
    data = json.loads(resp.data)
    if not data.get('success'):
        print(f"  FAIL — resposta: {data}")
        return
    clientes_a = data.get('data', [])
    nomes_a = {c['nome'] for c in clientes_a}
    if 'Cliente A-1' not in nomes_a:
        print(f"  FAIL — não encontrou Cliente A-1. Clientes: {nomes_a}")
        return
    if 'Cliente B-1' in nomes_a:
        print(f"  FAIL — encontrou Cliente B-1 (de outra empresa)! Clientes: {nomes_a}")
        return
    if len(clientes_a) != 1:
        print(f"  FAIL — esperado 1 cliente, encontrados {len(clientes_a)}: {nomes_a}")
        return
    print(f"  OK — {len(clientes_a)} cliente(s) de A, sem vazamento de B: {nomes_a}")

    # ------------------------------------------------------------------
    # Teste 4: GET /empresa/<slug-B>/plants → só plants de B
    # ------------------------------------------------------------------
    print(
        f"\nTeste 4: GET /empresa/{empresa_b.slug}/plants "
        "→ deve trazer só plants de B (vazio, se não houver)"
    )
    resp = client.get(f'/api/v1/empresas/{empresa_b.slug}/plants')
    data = json.loads(resp.data)
    if not data.get('success'):
        print(f"  FAIL — resposta: {data}")
        return
    plants_b = data.get('data', [])
    print(f"  OK — {len(plants_b)} plant(s) de B (esperado 0): {plants_b}")

    # ------------------------------------------------------------------
    # Teste 5: POST /empresa/<slug-B>/pendencias com cliente de A → rejeita
    # ------------------------------------------------------------------
    print(
        f"\nTeste 5: POST /empresa/{empresa_b.slug}/pendencias "
        "com clienteId de A → deve rejeitar"
    )
    resp = client.post(
        f'/api/v1/empresas/{empresa_b.slug}/pendencias',
        data=json.dumps({
            'titulo': 'Teste de proteção cruzada',
            'categoria': 'Teste',
            'clienteId': cliente_a.id,
            'prioridade': 'media',
        }),
        content_type='application/json',
    )
    data = json.loads(resp.data)
    if data.get('success'):
        print(f"  FAIL — aceitou pendência com cliente de outra empresa!")
        return
    msg = data.get('message', '').lower()
    if 'outra empresa' not in msg and 'cliente' not in msg:
        print(f"  FAIL — mensagem inesperada: {data}")
        return
    print(f"  OK — rejeitada com mensagem: {data.get('message')}")

    # ------------------------------------------------------------------
    # Teste 6: usuario normal de A tenta acessar /empresa/<slug-B>/clients
    # ------------------------------------------------------------------
    print(
        f"\nTeste 6: usuario normal de A tenta GET "
        f"/empresa/{empresa_b.slug}/clients → deve dar 403"
    )
    # Criar usuário normal de A
    user_a = User.query.filter_by(
        email='user_a@example.com'
    ).first()
    if not user_a:
        user_a = User(
            empresa_id=empresa_a.id,
            email='user_a@example.com',
            password_hash=_hash('user_a_123'),
            nome='Usuário A',
            role='operator',
            is_platform_admin=False,
            status='ativo',
        )
        db.session.add(user_a)
        db.session.commit()
        print(f"  Usuário A criado: id={user_a.id}")

    # Login como usuário A
    client_a_session = app.test_client()
    token_a = _login(client_a_session, 'user_a@example.com', 'user_a_123')
    if not token_a:
        print("  FAIL — não foi possível fazer login como usuário A")
        return

    resp = client_a_session.get(
        f'/api/v1/empresas/{empresa_b.slug}/clients'
    )
    # Espera 403 (Acesso negado à empresa)
    if resp.status_code != 403:
        print(f"  FAIL — esperado 403, recebido {resp.status_code}")
        return
    print(f"  OK — usuário de A recebeu 403 ao tentar acessar empresa B")

    # ------------------------------------------------------------------
    # Teste 7: usuario normal de A acessa /empresa/<slug-A>/clients → OK
    # ------------------------------------------------------------------
    print(
        f"\nTeste 7: usuario normal de A acessa "
        f"/empresa/{empresa_a.slug}/clients → deve funcionar"
    )
    resp = client_a_session.get(
        f'/api/v1/empresas/{empresa_a.slug}/clients'
    )
    data = json.loads(resp.data)
    if not data.get('success'):
        print(f"  FAIL — resposta: {data}")
        return
    clientes_a2 = data.get('data', [])
    nomes_a2 = {c['nome'] for c in clientes_a2}
    if 'Cliente A-1' not in nomes_a2:
        print(f"  FAIL — não encontrou Cliente A-1. Clientes: {nomes_a2}")
        return
    print(f"  OK — usuário de A acessou sua própria empresa: {nomes_a2}")

    # ------------------------------------------------------------------
    # Teste 8: platform admin acessa /empresas (listagem global)
    # ------------------------------------------------------------------
    print("\nTeste 8: GET /empresas → lista todas as empresas (platform admin)")
    resp = client.get('/api/v1/empresas')
    data = json.loads(resp.data)
    if not data.get('success'):
        print(f"  FAIL — resposta: {data}")
        return
    empresas = data.get('data', [])
    nomes_empresas = {e['nome'] for e in empresas}
    if 'Empresa A' not in nomes_empresas or 'Empresa B' not in nomes_empresas:
        print(f"  FAIL — não encontrou ambas as empresas. Encontradas: {nomes_empresas}")
        return
    print(f"  OK — listagem global com {len(empresas)} empresa(s): {nomes_empresas}")

    # ------------------------------------------------------------------
    # Resumo
    # ------------------------------------------------------------------
    print("\n" + "=" * 60)
    print("TODOS OS TESTES PASSARAM")
    print("=" * 60)
    print(
        "\nConclusão: o fluxo de impersonação via path (/empresa/<slug>/...) "
        "está funcionando corretamente. O platform admin visualiza apenas os "
        "dados da empresa escolhida, e usuários de outras empresas são "
        "barrados. A validação de referências cruzadas em pendências também "
        "está ativa.\n"
    )


if __name__ == '__main__':
    main()
