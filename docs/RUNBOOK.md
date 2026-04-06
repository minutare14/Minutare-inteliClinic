# Runbook — Minutare Med

## Pré-requisitos
- Docker e Docker Compose instalados
- Git
- (Opcional) Python 3.12+ para execução local sem Docker
- (Opcional) ngrok para desenvolvimento com Telegram

## Subir o Sistema

### 1. Clonar e configurar

```bash
cd "MINUTARE MED"

# Copiar e configurar variáveis de ambiente
cp infra/docker/.env.example infra/docker/.env
# Edite infra/docker/.env com seus valores reais
```

### 2. Subir com Docker Compose

```bash
cd infra/docker
docker-compose up -d --build
```

Isso irá:
- Subir PostgreSQL 16 com pgvector
- Rodar migrations (Alembic)
- Subir a API FastAPI na porta 8000

### 3. Verificar

```bash
# Health check
curl http://localhost:8000/health

# Database health
curl http://localhost:8000/health/db

# Docs interativos
# Abra http://localhost:8000/docs no navegador
```

### 4. Popular dados iniciais

```bash
# Instalar httpx se não tiver
pip install httpx

# Seed de dados (pacientes + FAQ RAG)
python scripts/seed_data.py --api-url http://localhost:8000

# Ingerir documentos GUIAS-DEV
python scripts/ingest_docs.py --docs-dir GUIAS-DEV --api-url http://localhost:8000
```

### 5. Configurar Telegram

Veja [TELEGRAM_SETUP.md](TELEGRAM_SETUP.md) para detalhes completos.

Resumo rápido:
```bash
# 1. Configure TELEGRAM_BOT_TOKEN no .env
# 2. Exponha com ngrok
ngrok http 8000

# 3. Registre o webhook
curl -X POST "http://localhost:8000/api/v1/telegram/set-webhook?url=https://SEU-NGROK.ngrok-free.app/api/v1/telegram/webhook"
```

## Desenvolvimento Local (sem Docker)

```bash
cd apps/api

# Criar virtualenv
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# Instalar dependências
pip install -e ".[dev]"

# Configurar .env
cp ../../infra/docker/.env.example .env
# Edite .env (DATABASE_URL apontando para seu Postgres local)

# Rodar migrations
alembic upgrade head

# Iniciar servidor
uvicorn app.main:app --reload --port 8000
```

## Comandos Úteis

```bash
# Logs
docker-compose -f infra/docker/docker-compose.yml logs -f api

# Restart
docker-compose -f infra/docker/docker-compose.yml restart api

# Nova migration
cd apps/api && alembic revision --autogenerate -m "description"

# Aplicar migrations
cd apps/api && alembic upgrade head

# Rollback migration
cd apps/api && alembic downgrade -1

# Abrir psql
docker exec -it minutare-db psql -U minutare -d minutare_med
```

## Estrutura do Projeto

```
minutare-med/
├── apps/api/                 # Backend FastAPI
│   ├── app/
│   │   ├── main.py           # Entry point
│   │   ├── core/             # Config, DB, logging, security
│   │   ├── models/           # SQLModel entities
│   │   ├── schemas/          # Pydantic request/response models
│   │   ├── repositories/     # Data access layer
│   │   ├── services/         # Business logic
│   │   ├── ai/               # Intent router, orchestrator, guardrails
│   │   ├── integrations/     # Telegram client + webhook handler
│   │   └── api/routes/       # FastAPI route handlers
│   ├── alembic/              # Database migrations
���   ├── Dockerfile
│   └── pyproject.toml
├── scripts/
│   ├─�� ingest_docs.py        # Ingerir GUIAS-DEV no RAG
│   └── seed_data.py          # Popular dados de teste
├── infra/docker/
│   ├── docker-compose.yml
│   └── .env.example
├── docs/                     # Documentação técnica
└── GUIAS-DEV/                # Documentos de referência do produto
```

## O que foi implementado

- [x] API FastAPI com 11+ endpoints reais
- [x] 9 tabelas no banco (migration real com Alembic)
- [x] pgvector para busca vetorial RAG
- [x] Integração Telegram via webhook (recebe, processa, responde)
- [x] Roteador de intenção (regras + keywords em pt-BR)
- [x] Orquestrador de resposta (RAG, agendamento, handoff)
- [x] Guardrails (sem diagnóstico, detecção de urgência, disclaimers)
- [x] Pipeline RAG (ingestão, chunking, embeddings, busca)
- [x] Trilha de auditoria em todas as operações
- [x] Docker Compose funcional (API + PostgreSQL/pgvector)
- [x] Scripts de seed e ingestão de documentos

## Pendências para Continuidade

- [ ] Autenticação/autorização (JWT + RBAC)
- [ ] Fluxo transacional real de agendamento (booking end-to-end no Telegram)
- [ ] Classificador de intenção com LLM (substituir regras)
- [ ] Geração de resposta com LLM (RAG + prompt engineering)
- [ ] Painel web da recepção (handoff UI)
- [ ] CRUD de profissionais via API
- [ ] Follow-up e lembretes (T-24h)
- [ ] Consentimento LGPD no primeiro contato
- [ ] Testes automatizados
- [ ] CI/CD pipeline
- [ ] Deploy em produção (HTTPS, domínio real)
