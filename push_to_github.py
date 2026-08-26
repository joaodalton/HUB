#!/usr/bin/env python3
import os, subprocess, time, sys

env_path = r"C:\Users\deadj\Desktop\Vscode\HUB\backend\.env"
repo_dir = r"C:\Users\deadj\Desktop\Vscode\HUB"

with open(env_path, encoding="utf-8") as f:
    for line in f:
        if line.startswith("GITHUB_CLIENT_TOKEN_KEY="):
            token = line.strip().split("=", 1)[1]
            break

REMOTE = f"https://{token}@github.com/joaodalton/HUB.git"
TAG = "v1.2.0-security-empresa-platform"
TAG_MSG = (
    "Sistema B removido (platform_routes.py + funções mortas authService.ts). "
    "Sistema A com @require_platform_admin() em todas as rotas (listar, criar, detalhe, atualizar, entrar, sair_plataforma, excluir). "
    "refreshAuthMe() agora usa apiRequest('/auth/me') do apiClient.ts. "
    "Suite de testes backend SQLite isolado: 21/21 testes passando. "
    "Hard-refresh validado em produção: sessão sobrevive ao refresh (8/8 checks)."
)

def run(cmd, label, timeout=300):
    print(f"\n>>> {label}")
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=repo_dir, timeout=timeout)
    ok = p.returncode == 0
    st = "OK" if ok else f"ERRO (exit {p.returncode})"
    print(f"    {st}")
    if not ok:
        for line in (p.stderr.splitlines() + p.stdout.splitlines())[:20]:
            print(f"    {line}")
    return ok

print("=== Push develop ===")
ok = False
for i in range(4):
    if run(["git", "push", REMOTE, "develop"], f"Tentativa {i+1}"):
        ok = True
        break
    wait = 15 * (i + 1)
    print(f"    Aguardando {wait}s para retry...")
    time.sleep(wait)

if not ok:
    print("\n!!! PUSH FALHOU")
    sys.exit(1)

print("\n=== Criar tag ===")
run(["git", "tag", "-a", TAG, "-m", TAG_MSG], "criar tag")

print("\n=== Push tag ===")
ok_tag = False
for i in range(4):
    if run(["git", "push", REMOTE, TAG], f"Tentativa {i+1} tag"):
        ok_tag = True
        break
    wait = 15 * (i + 1)
    print(f"    Aguardando {wait}s...")
    time.sleep(wait)

if not ok_tag:
    print("\n!!! PUSH DA TAG FALHOU")
    sys.exit(1)

print("\n=== Verificar ===")
run(["git", "ls-remote", "--tags", REMOTE], "tags remotas")

print("\n=== DONE ===")
