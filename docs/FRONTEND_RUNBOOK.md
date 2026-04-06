# Minutare Med — Frontend Runbook

## Stack

- Next.js 16 (App Router)
- TypeScript
- Tailwind CSS
- fetch API (sem dependencias extras)

## Requisitos

- Node.js 18+
- Backend rodando em `http://localhost:8000`

## Setup

```bash
cd frontend
npm install
cp .env.example .env.local  # ja vem configurado para localhost:8000
npm run dev
```

O painel abre em **http://localhost:3000**.

## Variavel de Ambiente

| Variavel              | Default                  | Descricao          |
|-----------------------|--------------------------|--------------------|
| NEXT_PUBLIC_API_URL   | http://localhost:8000    | URL da API backend |

## Telas

| Rota                   | Funcao                                        |
|------------------------|-----------------------------------------------|
| /dashboard             | Visao geral — metricas, status do sistema     |
| /conversations         | Lista de conversas do Telegram                |
| /conversations/[id]    | Detalhe — mensagens, intent, guardrails       |
| /patients              | Lista de pacientes com busca                  |
| /patients/[id]         | Detalhe do paciente                           |
| /schedules             | Agenda — filtros por profissional/data/status |
| /handoffs              | Handoffs — assumir, resolver                  |
| /rag                   | Documentos da base de conhecimento            |
| /audit                 | Eventos de auditoria                          |
| /settings              | Status do sistema e configuracoes             |

## Endpoints Utilizados

```
GET  /health
GET  /health/db
GET  /api/v1/dashboard/summary
GET  /api/v1/patients
GET  /api/v1/patients/{id}
GET  /api/v1/conversations
GET  /api/v1/conversations/{id}
GET  /api/v1/conversations/{id}/messages
GET  /api/v1/handoff
PATCH /api/v1/handoff/{id}
GET  /api/v1/schedules
POST /api/v1/schedules/{id}/cancel
GET  /api/v1/professionals
GET  /api/v1/rag/documents
GET  /api/v1/audit
```

## Endpoints Adicionados ao Backend

Os seguintes endpoints foram criados para suportar o frontend:

| Endpoint                       | Metodo | Arquivo                        |
|--------------------------------|--------|--------------------------------|
| /api/v1/patients               | GET    | routes/patients.py             |
| /api/v1/conversations          | GET    | routes/conversations.py        |
| /api/v1/handoff                | GET    | routes/handoff.py              |
| /api/v1/handoff/{id}           | PATCH  | routes/handoff.py              |
| /api/v1/audit                  | GET    | routes/audit.py (novo)         |
| /api/v1/dashboard/summary      | GET    | routes/dashboard.py (novo)     |
| /api/v1/professionals          | GET    | routes/professionals.py (novo) |

## Rodando com Docker

Para rodar o stack completo:

```bash
# Backend + DB
cd infra/docker
docker compose up -d

# Frontend (separado)
cd frontend
npm run dev
```

## Estrutura

```
frontend/src/
  app/          → paginas (App Router)
  components/   → componentes React por dominio
  hooks/        → hooks de data fetching
  lib/          → api client, tipos, formatters, constantes
```
