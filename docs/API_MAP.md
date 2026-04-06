# API Map — Minutare Med

Base URL: `http://localhost:8000`

## Health

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Status do serviço |
| GET | `/health/db` | Status da conexão com banco |

## Patients (`/api/v1/patients`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/patients` | Criar paciente |
| GET | `/api/v1/patients/{patient_id}` | Buscar por ID |
| GET | `/api/v1/patients/by-telegram/{telegram_user_id}` | Buscar por Telegram user ID |
| PATCH | `/api/v1/patients/{patient_id}` | Atualizar paciente |

## Schedules (`/api/v1/schedules`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/schedules` | Criar slot de agenda |
| GET | `/api/v1/schedules` | Listar slots (filtros: professional_id, date_from, date_to, status) |
| POST | `/api/v1/schedules/{slot_id}/book` | Reservar slot (query: patient_id, source) |
| POST | `/api/v1/schedules/{slot_id}/cancel` | Cancelar slot |

## Conversations (`/api/v1/conversations`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/conversations/{conversation_id}` | Buscar conversa |
| GET | `/api/v1/conversations/{conversation_id}/messages` | Listar mensagens da conversa |

## Telegram (`/api/v1/telegram`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/telegram/webhook` | Receber update do Telegram (webhook) |
| POST | `/api/v1/telegram/set-webhook` | Configurar webhook URL no Telegram |
| GET | `/api/v1/telegram/webhook-info` | Info do webhook atual |

## RAG (`/api/v1/rag`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/rag/ingest` | Ingerir documento (title, content, category) |
| POST | `/api/v1/rag/query` | Buscar documentos similares (query, top_k, category) |
| GET | `/api/v1/rag/documents` | Listar documentos (filtro: category) |

## Handoff (`/api/v1/handoff`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/handoff` | Criar handoff manual |

## Autenticação
Ainda não implementada no MVP. Próximos passos: JWT + RBAC conforme matriz de permissões do PRD.
