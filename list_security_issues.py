#!/usr/bin/env python3
"""List issues by label from GitHub API using token from backend/.env"""
import os
import json
import ssl
import urllib.request
import urllib.error

REPO_OWNER = "joaodalton"
REPO_NAME = "HUB"
LABELS = "security"
STATE = "open"

def get_token():
    env_path = os.path.join(os.path.dirname(__file__), "backend", ".env")
    if not os.path.exists(env_path):
        env_path = os.path.join(os.path.dirname(__file__), "..", "HUB", "backend", ".env")
    with open(env_path, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            if line.startswith('GITHUB_CLIENT_TOKEN_KEY='):
                return line.split('=', 1)[1].strip().strip('"').strip("'")
    return None

def fetch_issues(token, labels=LABELS, state=STATE):
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/issues?state={state}&labels={labels}&per_page=50"
    req = urllib.request.Request(url, headers={
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "HermesAgent/1.0"
    })
    # Create SSL context that doesn't verify certs (for Windows env issues)
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
            data = json.load(resp)
            return data
    except urllib.error.HTTPError as e:
        print(f"HTTP Error {e.code}: {e.reason}")
        print(f"Response: {e.read().decode()[:500]}")
        return []
    except Exception as e:
        print(f"Error: {e}")
        return []

def main():
    token = get_token()
    if not token:
        print("ERROR: Token not found in backend/.env")
        print("Looking for GITHUB_CLIENT_TOKEN_KEY")
        # Try the HUB directory
        alt_path = os.path.join("C:/Users/deadj/Desktop/Vscode/HUB", "backend", ".env")
        if os.path.exists(alt_path):
            with open(alt_path, 'r', encoding='utf-8', errors='replace') as f:
                for line in f:
                    if 'GITHUB_CLIENT_TOKEN_KEY' in line:
                        print(f"Found line: {line.strip()[:80]}")
        return
    
    print(f"Token found, length={len(token)}, prefix={token[:8]}...")
    
    issues = fetch_issues(token)
    print(f"\n=== ISSUES DE SEGURANÇA (abertos) ===")
    print(f"Total: {len(issues)} issues\n")
    
    if not issues:
        print("NENHUM ISSUE DE SEGURANÇA ENCONTRADO")
        return
    
    for issue in issues:
        if 'pull_request' in issue:
            continue  # Skip PRs that appear in issues endpoint
        num = issue['number']
        title = issue['title']
        labels = [l['name'] for l in issue['labels']]
        body = issue.get('body', '') or '(sem descrição)'
        state = issue['state']
        created = issue['created_at'][:10]
        user = issue['user']['login']
        
        print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print(f"#{num} | {state} | criado: {created} | por: {user}")
        print(f"Título: {title}")
        print(f"Labels: {', '.join(labels)}")
        print(f"Descrição:\n{body[:500]}")
        print()
    
    # Also fetch closed issues for completeness
    closed = fetch_issues(token, state="closed")
    closed_real = [i for i in closed if 'pull_request' not in i]
    if closed_real:
        print(f"\n=== ISSUES DE SEGURANÇA (fechados) - {len(closed_real)} ===")
        for issue in closed_real[:20]:
            print(f"#{issue['number']}: {issue['title']} [{issue['state']}]")

if __name__ == "__main__":
    main()
