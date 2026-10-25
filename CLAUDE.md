# HUB — Claude Code Configuration

Sistema de operação solar (clientes, UCs, usinas, documentos), multi-tenant.
Stack: backend Flask + SQLAlchemy + PostgreSQL (Neon); frontend TypeScript
vanilla + Vite (sem framework). Deploy no Render. Documentos no Google
Drive e/ou S3-compatible na Backblaze B2 (provedor de armazenamento é
configurável por tenant).

**Antes de qualquer tarefa, leia `AGENTS.md`** — é a fonte de verdade sobre
ordem de leitura, papéis de agente, prioridade de entrega e os 6 agentes
reais em `.claude/agents/hub-*.md` (backend-developer, backend-reviewer,
frontend-developer, frontend-reviewer, security-reviewer, code-reviewer).
Este arquivo não repete aquelas regras — só cobre o que falta.

## Rules

- Do what has been asked; nothing more, nothing less
- NEVER create files unless absolutely necessary — prefer editing existing files
- NEVER create documentation files unless explicitly requested
- NEVER save working files or tests to root — use `backend/tests`, `docs/`, `scripts/`
- ALWAYS read a file before editing it
- NEVER commit secrets, credentials, or .env files
- NEVER add a `Co-Authored-By` trailer (no attribution configurado em `.claude/settings.json`)
- Keep files under 500 lines
- Validate input at system boundaries — toda rota recebe dado de fora

## Build & Test

Backend:
```bash
cd backend && venv\Scripts\activate
pytest                      # suíte completa
flask db upgrade            # aplica migrations
```

Frontend:
```bash
cd frontend
npm run build                # tsc + vite build
npm test                     # vitest run
npm run lint                 # eslint
```

ALWAYS rodar os dois antes de considerar qualquer entrega pronta.

## Armazenamento de documentos

Dois provedores possíveis por tenant: Google Drive (OAuth) ou bucket
S3-compatible na Backblaze B2. Mudança em `services/` ou `routes/` que toca
upload/download de documento precisa cobrir os dois caminhos, não só o
provedor padrão — não assuma Google Drive como único destino.

## Segurança / multi-tenancy

Isolamento por `empresa_id` é requisito crítico, não feature — qualquer
mudança em `models/`, `extensions.py` (Session/Query) ou rotas que leem
dado por tenant passa obrigatoriamente por `hub-security-reviewer`, nunca
auto-aprovada. Ver `SECURITY.md`.
