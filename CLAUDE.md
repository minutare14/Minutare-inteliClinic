# CLAUDE.md — IntelliClinic / Minutare Med

## Objetivo
Memoria viva tecnica. Registrar descobertas reais com separacao `Evidencia`, `Inferencia`, `Plano`. Atualizar apos cada sprint.

## Historico de Alteracoes

### 2026-04-18 — Bugs Criticos + Correcoes Completas

**Bugs corrigidos (5 bugs):**
- `1.1 CRITICA`: RAG nao filtrava por `clinic_id` → vazamento multi-tenant. Corrigido: `clinic_id` em `RagDocument`/`RagChunk`, migration `011`, todas as 12 methods do `rag_repository` filtram por `clinic_id`.
- `1.2 HIGH`: AI respondia com numero isolado ("1"). Corrigido: NODE 2b `_is_bare_number` no orchestrator + regra no prompt.
- `1.3 CRITICA`: Rotas operacionais sem auth. Corrigido: `Depends(get_current_user)` em todos os 5 arquivos de rota.
- `1.4 HIGH`: StructuredLookup sem cobertura precos/horarios. Corrigido: `_lookup_hours()` e `_lookup_prices()` async.
- `1.5 HIGH`: Prompt usava profissionais hardcoded. Corrigido: `orchestrator._inject_professionals_into_context()` injeta profissionais reais via `faro_brief`.

**Fase 2 — Estabilizacao runtime:**
- CLINIC_ID production guard: `model_validator` em `config.py` — falha se `APP_ENV=production` sem `CLINIC_ID`.
- RagService session leak: `RagService` injetado no `__init__` de `StructuredLookup`.
- Pipeline LangGraph: 14 nodes verificados, fallback linear `_run_without_graph()`, retry finito com `rag_query_rewrite_max_retries`, flag `langgraph_used` propagada ate audit.

**Fase 3 — Audit trail:**
- LLM model + latency: `llm_client._http_call()` inclui `"model"` no metrics; `generate_response()` retorna 3-tuple; `llm_model`/`llm_latency_ms` propagados ate `audit_payload`.

**Arquivos alterados (18 + 1 migration):**
`models/rag.py`, `011_rag_clinic_id.py` (nova), `rag_repository.py`, `rag_service.py`, `document_runtime_graph.py`, `rag.py` (rota), `patients.py`, `conversations.py`, `schedules.py`, `handoff.py`, `structured_lookup.py`, `response_composer.py`, `response_builder.py`, `orchestrator.py`, `llm_client.py`, `config.py`.

**Pendencias:**
Nenhuma — todas as 5 fases concluidas ✅

### 2026-04-17 — Auth Bug + Pipeline LangGraph

**Bug auth:** `seed_default_admin()` com SQLAlchemy ORM quebrava em PostgreSQL (enum `userrole` inexistente). Corrigido com raw SQL via `text()`.

**Pipeline LangGraph** (completado 2026-04-17):
14 nodes: load_runtime_context → decision_router → [structured_data_lookup|schedule_flow|crm_flow|handoff_flow|clarification_flow|rag_retrieval] → document_grading → [query_rewrite→retry_retrieval→rag_retrieval→document_grading]* → reranker → response_composer → persist_and_audit → emit_response.
Retry guard: `query_rewrite_attempts < rag_query_rewrite_max_retries`.
LangSmith tracing via `trace_step()` em todos os nodes.

### 2026-04-15 — Integridade Operacional + Pipeline Viewer

- `ReconciliationService` para desativacao de profissionais.
- `AuditRepository.list_by_resource` + rota `GET /api/v1/audit/pipeline/{id}`.
- Componente `PipelineViewer` no frontend (toggle "Ver IA Trace").

### 2026-04-13 — Bugs + Deploy

- `_handle_slot_to_cancel_selection` em orchestrator.
- Remarcacao com `new_date` separado (nao usava a mesma data para old e new).
- `POST /api/v1/telegram/set-webhook` com JSON body (nao query param).
- `RagQueryResult` com `document_id` e `title`.
- `.env.vps.example`, `docs/deployment/ENV_REFERENCE.md`, `docs/deployment/VPS_DEPLOY_CHECKLIST.md`.

## Convencoes

- `Evidencia`: confirmado em codigo, migrations, scripts, testes ou frontend conectado.
- `Inferencia`: conclusao derivada sem declaracao explicita.
- `Plano`: arquitetura-alvo sem integracao operacional.

## Stack

**Backend:** FastAPI, SQLModel/SQLAlchemy async, Alembic, PostgreSQL/pgvector.
**Frontend:** Next.js 16, React 19, TypeScript, Tailwind 4.
**Canal:** Telegram webhook (operacional). WhatsApp + LiveKit (planejado).
**RAG:** PostgreSQL/pgvector (`rag_documents` + `rag_chunks`). Qdrant + LlamaIndex + Docling (planejado).

## Arquitetura Atual

```
telegram_webhook → AIOrchestrator → [structured_lookup|schedule_flow|handoff_flow|rag_retrieval]
rag_retrieval → document_grading → [query_rewrite + retry]* → reranker → response_composer → persist_and_audit → emit_response
```

**LangGraph:** 14 nodes, condicional edges, fallback linear `_run_without_graph()`.
**Prompts:** `response_builder.py` (camadas) + `PromptRegistry` (DB, ainda nao implementado).
**Auth:** `Depends(get_current_user)` em todas as rotas operacionais.

## Servicos Existentes

`PatientService`, `ConversationService`, `ScheduleService`, `HandoffService`, `RagService`, `TelegramService`, `AuditService`, `AIOrchestrator`.

## Bugs Corrigidos (historico)

- `select_slot_to_cancel` nao tratado → CORRIGIDO 2026-04-13.
- Remarcacao com data duplicada → CORRIGIDO 2026-04-13.
- `set-webhook` JSON body → CORRIGIDO 2026-04-13.
- `webhook-info` wrapper → CORRIGIDO 2026-04-13.
- `RagQueryResult` sem `document_id`/`title` → CORRIGIDO 2026-04-13.
- RAG sem `clinic_id` → CORRIGIDO 2026-04-18.
- AI numero isolado → CORRIGIDO 2026-04-18.
- Rotas sem auth → CORRIGIDO 2026-04-18.
- StructuredLookup sem precos/horarios → CORRIGIDO 2026-04-18.
- Profissionais hardcoded → CORRIGIDO 2026-04-18.
- CLINIC_ID sem guard em production → CORRIGIDO 2026-04-18.
- RagService session leak → CORRIGIDO 2026-04-18.
- LLM sem model/latency no audit → CORRIGIDO 2026-04-18.

## Lacunas Conhecidas

- Sem auth/RBAC no frontend.
- Sem `clinic_id` em `patients`, `professionals`, `schedule_slots`, `conversations` (RAG OK).
- Branding hardcoded em "Minutare Med".
- Sem PromptRegistry/versionamento (em construcao — Fase 3).
- Sem dashboard/analytics (Fase 4 — pendente).
- Sem GraphRAG/LlamaIndex/Docling (Fase 5 — pendente).
- Sem Google Calendar, WhatsApp, voz/LiveKit.

## Referencias

- `apps/api/app/main.py`, `apps/api/app/core/config.py`
- `apps/api/app/ai_engine/orchestrator.py`, `document_runtime_graph.py`, `response_builder.py`, `llm_client.py`
- `apps/api/app/api/routes/`
- `apps/api/app/services/`, `apps/api/app/repositories/`
- `frontend/src/app/`, `frontend/src/lib/api.ts`
- `correction_plan.md` — plano de execucao vivo
