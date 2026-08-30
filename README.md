# APP HUB — Sistema de Operação Solar

Consulte [SECURITY.md](SECURITY.md) para os controles de multi-tenancy, RBAC,
sessões, Google Drive e o procedimento de migração de segurança.

> **Programa de trabalho diário** para organizar clientes, UCs (unidades consumidoras), usinas e documentos de uma operação de energia solar.
> **Documentos relacionados:** [[VISAO]] · [[ARCHITECTURE]] · [[PROGRESS]] · [[API_CONTRACTS]]

[![Status](https://img.shields.io/badge/versão-V0.x-blue)](VISAO.md)
[![Backend](https://img.shields.io/badge/backend-Flask%20%2B%20SQLAlchemy-green)](backend/)
[![Frontend](https://img.shields.io/badge/frontend-React%20%2B%20TypeScript-blue)](frontend/)

---

## 📋 Índice

- [Visão Geral](#visão-geral)
- [Arquitetura](#arquitetura)
- [Pré-requisitos](#pré-requisitos)
- [Instalação e Configuração](#instalação-e-configuração)
- [Como Rodar](#como-rodar)
- [Funcionalidades Atuais](#funcionalidades-atuais)
- [API REST](#api-rest)
- [Próximos Passos](#próximos-passos)
- [Documentação Complementar](#documentação-complementar)

---

## Visão Geral

O APP HUB substitui planilhas, Google Drive fragmentado e processos manuais por uma interface única que centraliza:

- **Clientes**: CPF/CNPJ, contatos, concessionárias, status operacional
- **UCs**: código ANEEL, consumo, base tarifária, conexões com usinas
- **Usinas**: capacidade, inversores, percentual disponível para rateio
- **Documentos**: upload, organização por categorias, download em lote
- **Configurações**: provedor de dados (Google Drive ou SQL), aparência, contas OAuth

**Público-alvo**: operação single-user local (atualmente), com arquitetura preparada para deploy em servidor multi-usuário futuro.

**Empacotamento futuro**: `.exe` instalável via Tauri + PyInstaller (ver [VISAO.md](VISAO.md)).

---

## Arquitetura

```
workspace/
├── backend/                 # API REST Flask + SQLAlchemy
│   ├── app.py              # Entry point da aplicação
│   ├── config.py           # Configurações e variáveis de ambiente
│   ├── extensions.py       # Instâncias centralizadas (db, migrate)
│   ├── routes/             # Blueprints por domínio (auth, clients, ucs, plants...)
│   ├── services/           # Regra de negócio (client_service, uc_service, oauth_service...)
│   ├── models/             # Entities SQLAlchemy (Client, Plant, ConsumerUnit...)
│   ├── database/           # Conexão e migrations
│   ├── utils/              # Helpers (auth, crypto, api_response)
│   └── uploads/            # Arquivos de documentos (fora do git)
│
├── frontend/               # React + TypeScript + Vite
│   ├── src/
│   │   ├── pages/         # Telas: Login, Clients, Ucs, Plants, Documents, Settings...
│   │   ├── components/    # Componentes reutilizáveis (DataTable, Cards, Forms...)
│   │   ├── services/      # Chamadas HTTP à API (clientsService, ucsService...)
│   │   ├── hooks/         # Hooks customizados
│   │   └── styles/        # Estilos globais
│   └── package.json
│
├── comandos/              # Scripts auxiliares (iniciar, parar, status)
├── logs/                  # Logs da aplicação
│
├── VISAO.md               # Documento de visão (norte do projeto)
├── PROGRESS.md            # Status atual e tarefas pendentes
└── API_CONTRACTS.md       # Contratos completos de todos os endpoints
```

---

## Pré-requisitos

- **Python 3.9+** (backend)
- **Node.js 18+** (frontend)
- **Git** (controle de versão)

Opcional para produção:
- **Tauri CLI** (empacotamento desktop)
- **PyInstaller** (build do backend)

---

## Instalação e Configuração

### 1. Clone o repositório

```bash
git clone <url-do-repositorio>
cd workspace
```

### 2. Backend

```bash
cd backend

# Criar ambiente virtual
python -m venv venv

# Ativar (Windows)
venv\Scripts\activate

# Ativar (Linux/Mac)
source venv/bin/activate

# Instalar dependências
pip install -r requirements.txt

# Copiar modelo de .env e configurar
cp .env.example .env
```

Edite `backend/.env`:

```env
FLASK_APP=app.py
FLASK_DEBUG=true
SECRET_KEY=<sua-chave-secreta-aleatoria>
SECRET_ENCRYPTION_KEY=<chave-fernet-32-bytes>
DATABASE_URL=sqlite:///hub.db
FRONTEND_URL=http://localhost:5173
API_PORT=8000
```

**Google Drive (opcional)**: coloque `credentials.json` da Service Account na pasta `backend/` (não commitar).

### 3. Frontend

```bash
cd frontend

# Instalar dependências
npm install

# Copiar modelo de .env
cp .env.example .env
```

Edite `frontend/.env`:

```env
VITE_API_BASE_URL=http://localhost:8000
```

---

## Como Rodar

### Desenvolvimento

**Terminal 1 — Backend:**

```bash
cd backend
venv\Scripts\activate   # Windows
# ou source venv/bin/activate  # Linux/Mac
python app.py
```

Backend roda em: **http://localhost:8000**

**Terminal 2 — Frontend:**

```bash
cd frontend
npm run dev
```

Frontend roda em: **http://localhost:5173**

### Primeiro Acesso

1. Acesse `http://localhost:5173/login`
2. Use o endpoint `POST /auth/bootstrap` (via Insomnia/cURL) para criar o admin:

```bash
curl -X POST http://localhost:8000/auth/bootstrap \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@hub.com", "senha": "123456"}'
```

3. Faça login com as credenciais criadas.

---

## Funcionalidades Atuais

### ✅ Núcleo Funcional (V0.9)

#### Autenticação
- Bootstrap de usuário admin (único, primeira execução)
- Login com token JWT-like (7 dias de expiração)
- Middleware protegendo todas as rotas exceto públicas

#### Clientes
- CRUD completo (criar, ler, atualizar, excluir)
- Status automático baseado em conexões com usinas
- UCs aninhadas no cadastro do cliente
- Concessionárias configuráveis (Copel, CPFL, Enel, Energisa...)

#### UCs (Unidades Consumidoras)
- CRUD avulso e aninhado em Clientes
- Campos completos: código, código ANEEL, consumo, base tarifária (A1-B4), tipo de ligação, contrato, carência
- Conexões múltiplas com usinas (percentual de rateio)
- Vínculo com cliente (movimentação entre clientes suportada)

#### Usinas
- CRUD completo
- Campos: nome, UC associada, kW pico, marca do inversor, contatos do proprietário
- Percentual disponível manual (rateio automático previsto para V3.0)
- Cascade nas conexões ao excluir

#### Documentos
- Upload de arquivos (multipart/form-data)
- Organização por categorias (Termo de Adesão, RG, Contrato...)
- Renomear, baixar, excluir
- Filtro por cliente e/ou UC
- Armazenamento local em `backend/uploads/`

#### Categorias
- CRUD de categorias de documentos
- Tipos classificatórios (documento pessoal, técnico, jurídico...)

#### Configurações
- **Aparência**: cor primária, logotipo (persistido no banco)
- **Banco de Dados**: escolha de provedor (Google Drive ou SQL)
  - Google Drive: service account (`credentials.json`) ou OAuth 2.0 PKCE
  - SQL: cadastro de credenciais (driver ainda não plugado)
  - Teste de configuração integrado

#### OAuth Google
- Fluxo completo PKCE (Authorization Code + PKCE)
- Múltiplas contas salvas (`GoogleAccount`)
- Refresh token criptografado (Fernet, nunca exposto)
- Conta ativa única (priorizada pelo `drive_service`)
- Fallback para `credentials.json` se não houver OAuth

#### Google Drive (Legado)
- Busca de arquivos e pastas (`GET /search?q=`)
- Download em lote (`POST /download-zip`)
- Integração transparente via conta OAuth ativa ou service account

#### Health Check
- `GET /` retorna status do servidor

---

## API REST

A API segue padrão RESTful com envelope de resposta consistente:

**Sucesso:**
```json
{ "success": true, "message": "texto", "data": {} }
```

**Erro:**
```json
{ "error": "texto", "details": {} }
```

**Autenticação:** header `Authorization: Bearer <token>` em todas as rotas protegidas.

### Endpoints Principais

| Método | Rota | Descrição |
|--------|------|-----------|
| POST | `/auth/bootstrap` | Cria admin (uma única vez) |
| POST | `/auth/login` | Login, retorna token |
| GET/POST/PUT/DELETE | `/clients` | CRUD de clientes |
| GET/POST/PUT/DELETE | `/ucs` | CRUD de UCs |
| GET/POST/PUT/DELETE | `/plants` | CRUD de usinas |
| GET/POST | `/categories` | Listar/criar categorias |
| GET/POST/PUT/DELETE | `/documents` | CRUD de documentos |
| GET | `/documents/:id/download` | Baixar arquivo |
| GET/PUT | `/settings` | Configurações de aparência |
| GET/POST | `/config/database/*` | Configuração de provedor de dados |
| GET/POST/DELETE | `/oauth/google/*` | Contas Google OAuth |
| GET | `/search` | Busca no Google Drive |
| POST | `/download-zip` | Download em lote do Drive |

📄 **Contrato completo em**: [API_CONTRACTS.md](API_CONTRACTS.md)

---

## Próximos Passos

### V1.0 — Fechamento do Núcleo
- [ ] Formulários expondo campos de negócio completos (telefone, endereço, CEP, contrato, marca do inversor...)
- [ ] Empacotamento Tauri + PyInstaller (.exe instalável)
- [ ] Migração completa para SQLite com path correto para produção

### V1.5 — Refinamento Operacional
- [ ] Módulo de Pendências
- [ ] Dashboard com métricas reais
- [ ] Agenda operacional funcional (boas-vindas, AVA, rateio, faturas)

### V2.0 — Cobrança e Automação
- [ ] Integração ASAAS (boletos)
- [ ] Disparo automático de mensagens (WhatsApp API)

### V3.0 — Rateio Automático
- [ ] Regra de cálculo definida com usuário
- [ ] Botão de rateio automático por usina
- [ ] Importação de fatura e planilha de rateio

### V4.0+ — Monitoramento e Automação
- [ ] APIs de inversores (marca a definir)
- [ ] Leitura automatizada de faturas (ML/robô)
- [ ] Portal do cliente

📋 **Roadmap detalhado em**: [PROGRESS.md](PROGRESS.md)

---

## Documentação Complementar

| Arquivo | Descrição |
|---------|-----------|
| [VISAO.md](VISAO.md) | Documento de visão — norte estratégico do projeto |
| [PROGRESS.md](PROGRESS.md) | Status atual, tarefas concluídas e pendentes |
| [API_CONTRACTS.md](API_CONTRACTS.md) | Contratos completos de todos os endpoints |

---

## Decisões de Arquitetura

- **Single-user hoje, multi-usuário amanhã**: mesma API, muda apenas autenticação e path do banco.
- **SQLite agora, Postgres depois**: SQLAlchemy abstrai a troca quando o volume justificar.
- **Zero localStorage para dado de negócio**: tudo via API REST, `localStorage` só para preferências de UI.
- **OAuth prioritário, service account como fallback**: segurança e flexibilidade para múltiplas contas.
- **Tauri > Electron**: menor footprint, melhor performance, Rust sob o capô.

---

## Contribuição

Este é um projeto focado em uso interno. Se encontrar bugs ou tiver sugestões:

1. Verifique se já existe uma issue relacionada
2. Descreva o problema com detalhes (passos para reproduzir, comportamento esperado)
3. Para features, discuta primeiro no `PROGRESS.md` antes de implementar

---

## Licença

Uso interno — Select Energia Solar.

---

**Versão atual**: V0.x (núcleo em desenvolvimento)
**Última atualização**: 2026-07-27
**Mantenedor**: João
