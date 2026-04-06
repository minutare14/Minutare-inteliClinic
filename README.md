# Minutare inteliClinic

Plataforma operacional para clinica medica com IA nativa. Sistema de agendamento, atendimento via Telegram e painel administrativo.

## Stack

| Camada | Tecnologia |
|--------|-----------|
| Backend | FastAPI, SQLAlchemy (async), PostgreSQL 16, pgvector |
| AI Engine | FARO Intent Router, RAG, Guardrails CFM, LLM (OpenAI/Gemini/Anthropic) |
| Frontend | Next.js 16, TypeScript, Tailwind CSS |
| Integracao | Telegram Bot API (webhook) |
| Infra | Docker Compose, Alembic migrations |

## Estrutura

```
apps/api/          Backend FastAPI
  app/
    ai_engine/     Motor de IA (intent, orchestrator, guardrails, actions, RAG)
    api/routes/    Endpoints REST
    models/        SQLModel/SQLAlchemy models
    schemas/       Pydantic schemas
    services/      Business logic
    repositories/  Data access
  tests/           86 testes automatizados
  alembic/         Migrations
frontend/          Painel operacional Next.js
  src/app/         Paginas (App Router)
  src/components/  Componentes React
  src/hooks/       Data fetching hooks
  src/lib/         API client, tipos, formatters
infra/docker/      Docker Compose (PostgreSQL + API)
scripts/           Seed data, RAG ingest
docs/              Documentacao
```

## Como rodar

### Backend

```bash
# Com Docker (recomendado)
cd infra/docker
docker compose up -d

# Ou localmente
cd apps/api
pip install -e ".[dev]"
alembic upgrade head
python ../../scripts/seed_data.py --mode db
uvicorn app.main:app --port 8001 --reload
```

### Frontend

```bash
cd frontend
npm install
# Ajustar NEXT_PUBLIC_API_URL em .env.local se necessario
npm run dev
```

Painel abre em http://localhost:3000

### Testes

```bash
cd apps/api
python -m pytest tests/ -v
```

## Funcionalidades do MVP

- Webhook Telegram com processamento de mensagens por IA
- Intent Router (FARO): 10 intencoes, extracao de entidades
- Agendamento real: busca, reserva, cancelamento, remarcacao
- Fluxo multi-turno: selecao de slot, confirmacao de cancelamento
- RAG: base de conhecimento com busca textual e embeddings
- Guardrails CFM 2.454: sem diagnostico, deteccao de urgencia, bloqueio de injection
- Painel operacional: dashboard, conversas, pacientes, agenda, handoffs, RAG, auditoria
- Seed de producao: 8 profissionais, 3 pacientes, 880 slots, 8 documentos RAG

## Status

MVP funcional — 86 testes passando, backend + frontend integrados.
