# CLAUDE.md

## Objetivo
- Memoria viva tecnica do projeto IntelliClinic / Minutare Med.
- Registrar descobertas reais da auditoria com separacao clara entre `Evidencia`, `Inferencia` e `Plano`.
- Servir como referencia padrao para futuras varreduras tecnicas, refactors e onboarding.

## Convencoes
- `Evidencia`: confirmado em codigo, migrations, scripts, tests, rotas, schemas ou frontend conectado.
- `Inferencia`: conclusao derivada do conjunto de evidencias, mas nao declarada literalmente.
- `Plano`: aparece em docs, TODOs, placeholders, stubs ou arquitetura-alvo sem integracao operacional completa.

## Snapshot Atual da Auditoria

### Visao geral do projeto
- `Evidencia`: o runtime operacional atual esta concentrado em `apps/api/app/` (backend FastAPI) e `frontend/src/` (painel Next.js).
- `Evidencia`: existe uma segunda camada em `src/inteliclinic/` com uma arquitetura mais ampla, cobrindo LangGraph, Instructor, Qdrant, LlamaIndex, analytics e avaliacao de RAG.
- `Inferencia`: o repositorio esta em estado hibrido. O MVP funcional esta em `apps/api`, enquanto `src/inteliclinic` representa a direcao arquitetural desejada.

### Stack real encontrada
- `Evidencia`: backend runtime usa FastAPI, SQLModel/SQLAlchemy async, Alembic, PostgreSQL/pgvector e SQLite em testes (`apps/api/app/main.py`, `apps/api/app/core/db.py`, `apps/api/pyproject.toml`).
- `Evidencia`: frontend usa Next.js 16, React 19, TypeScript e Tailwind 4 (`frontend/package.json`).
- `Evidencia`: integracao operacional implementada hoje e Telegram webhook (`apps/api/app/api/routes/telegram.py`, `apps/api/app/integrations/telegram/webhook_handler.py`).
- `Evidencia`: o RAG realmente usado no MVP esta em PostgreSQL com `rag_documents` + `rag_chunks` e busca vetorial via pgvector (`apps/api/app/services/rag_service.py`, `apps/api/app/repositories/rag_repository.py`).
- `Plano`: Qdrant, LlamaIndex, Docling, GraphRAG, LangGraph completo e configuracao por clinica aparecem em `src/inteliclinic`, mas nao sao o fluxo operacional atual.

### Arquitetura encontrada
- `Evidencia`: `apps/api/app/main.py` monta a API publica. `/health` fica fora de `/api/v1`, o restante fica majoritariamente sob `/api/v1`.
- `Evidencia`: o frontend consome a API diretamente, sem token, sem middleware de sessao e sem RBAC efetivo (`frontend/src/lib/api.ts`, `frontend/src/app/*`).
- `Evidencia`: o atendimento principal segue `telegram webhook -> paciente -> conversa -> mensagem inbound -> AIOrchestrator -> Telegram -> mensagem outbound -> auditoria`.
- `Plano`: `src/inteliclinic/core/ai_engine/graphs/main_graph.py` define outra arquitetura de orquestracao baseada em LangGraph, ainda nao conectada ao backend MVP.

### Servicos existentes
- `Evidencia`: `PatientService`
- `Evidencia`: `ConversationService`
- `Evidencia`: `ScheduleService`
- `Evidencia`: `HandoffService`
- `Evidencia`: `RagService`
- `Evidencia`: `TelegramService`
- `Evidencia`: `AuditService`

### Pipelines existentes
- `Evidencia`: bootstrap da API com migracao + seed a cada start (`apps/api/entrypoint.sh`).
- `Evidencia`: ingestao de mensagem Telegram ponta a ponta (`apps/api/app/integrations/telegram/webhook_handler.py`).
- `Evidencia`: pipeline de agendamento via `AIOrchestrator` + `ScheduleActions`.
- `Evidencia`: pipeline de cancelamento via `AIOrchestrator` + `ScheduleActions`.
- `Evidencia`: pipeline de handoff humano por baixa confianca, falta de consentimento, urgencia ou pedido explicito.
- `Evidencia`: pipeline de auditoria minima por evento.
- `Evidencia`: pipeline de ingestao de RAG via API (`POST /api/v1/rag/ingest`) e via script (`scripts/ingest_docs.py`).
- `Plano`: pipeline de LangGraph, pipeline de NLU via Instructor, pipeline de Qdrant/LlamaIndex, pipeline de glosa/anomalia e onboarding por clinica.

### Rotas existentes
- `Evidencia`: backend exposto hoje cobre `health`, `patients`, `professionals`, `schedules`, `conversations`, `handoff`, `rag`, `telegram`, `audit` e `dashboard`.
- `Evidencia`: nao existem rotas reais de auth, Google, CRM, follow-up, leads, estoque, produtos, salas, funcionarios, procedimentos ou admin RBAC.
- `Evidencia`: o frontend possui paginas para dashboard, conversas, pacientes, profissionais, agenda, handoffs, RAG, integracoes, auditoria e settings.
- `Evidencia`: todas as paginas do frontend estao publicas do ponto de vista do codigo.

### Agentes / IAs encontradas
- `Evidencia`: `AIOrchestrator` e a camada de IA realmente usada no runtime (`apps/api/app/ai_engine/orchestrator.py`).
- `Evidencia`: o roteamento de intencao do MVP e `FaroIntentRouter`, heuristico e deterministico, sem LLM (`apps/api/app/ai_engine/intent_router.py`).
- `Evidencia`: `response_builder.py` monta o prompt e chama `llm_client.py` se existir API key; caso contrario usa templates.
- `Evidencia`: `apps/api/app/ai_engine/guardrails.py` aplica bloqueio, urgencia, consentimento e handoff.
- `Plano`: `src/inteliclinic/core/ai_engine/` define subagentes/nodes `reception`, `scheduling`, `insurance`, `financial`, `glosa`, `supervisor`, `fallback`, `response`.
- `Plano`: `src/inteliclinic/core/nlu/extractors/message_extractor.py` define extrator estruturado com Instructor + OpenAI/Anthropic.

### Prompts encontrados
- `Evidencia`: prompt principal em camadas no runtime atual em `apps/api/app/ai_engine/response_builder.py`.
- `Evidencia`: templates de fallback do MVP tambem ficam em `apps/api/app/ai_engine/response_builder.py`.
- `Evidencia`: prompt do extrator NLU em `src/inteliclinic/core/nlu/extractors/message_extractor.py`.
- `Evidencia`: prompt do `response_node` do grafo em `src/inteliclinic/core/ai_engine/nodes/response.py`.
- `Plano`: prompts complementares por clinica em `src/inteliclinic/clinic/prompts/base_prompts.py`, sem ligacao operacional observada no MVP.

### Tools encontradas
- `Evidencia`: `ScheduleActions` funciona como tool layer do orquestrador para buscar slots, reservar, cancelar, remarcar e listar especialidades.
- `Evidencia`: `RagService` funciona como tool de conhecimento administrativo.
- `Evidencia`: `ConversationService` e `PatientService` funcionam como camada de estado e memoria persistente.
- `Plano`: no core planejado, os nodes do grafo deveriam cooperar com retrievers, query engine, safety e possivel HITL.

### Integracoes encontradas
- `Evidencia`: Telegram implementado.
- `Plano`: WhatsApp Business aparece no frontend como "Em breve".
- `Plano`: Voz / LiveKit aparece no frontend como "Em breve".
- `Plano`: Google/Calendar aparece em docs e arquitetura, mas nao em rotas reais.

### Reaproveitamento de projetos anteriores
- `Evidencia`: comentarios em varios modulos dizem "Adapted from minutare.ai" e "Adapted from qwen-test".
- `Inferencia`: o motor conversacional atual e parte do core foram derivados de repositorios/prototipos anteriores.

### Componentes open source identificados
- `Evidencia`: FastAPI
- `Evidencia`: SQLModel / SQLAlchemy
- `Evidencia`: Alembic
- `Evidencia`: pgvector
- `Evidencia`: httpx
- `Evidencia`: Next.js
- `Evidencia`: React
- `Evidencia`: Tailwind
- `Plano`: LangGraph
- `Plano`: Instructor
- `Plano`: LlamaIndex
- `Plano`: qdrant-client
- `Plano`: Docling
- `Plano`: Guardrails AI
- `Plano`: PyOD
- `Plano`: RAGAS

## Pontos Fracos Ja Confirmados
- `Evidencia`: o projeto nao tem autenticacao nem RBAC no runtime atual.
- `Evidencia`: nao existe `clinic_id` ou `tenant_id` nas tabelas operacionais principais (`patients`, `professionals`, `schedule_slots`, `conversations`, `rag_documents`).
- `Evidencia`: o frontend e o backend discordam em algumas integracoes:
  - `POST /api/v1/telegram/set-webhook` espera `url` em query param, mas `frontend/src/lib/api.ts` envia JSON body.
  - `GET /api/v1/telegram/webhook-info` retorna `{"info": ...}`, mas o frontend espera o objeto plano.
  - `RagQueryResult` do frontend espera `document_id` e `title`, mas o backend retorna `document_title` e nao retorna `document_id`.
- `Evidencia`: `AIOrchestrator` salva pending action `select_slot_to_cancel`, mas `_handle_pending_action` nao trata esse tipo; cancelamento com varias consultas fica incompleto.
- `Evidencia`: o fluxo de remarcacao reaproveita `entities.get("date")` para data antiga e nova; o runtime nao separa claramente as duas datas.
- `Evidencia`: prompts, seeds, nome da aplicacao e branding estao hardcoded em "Minutare Med" no backend, frontend e scripts.
- `Evidencia`: `src/inteliclinic/core/rag/ingestion/pipelines/ingest_pipeline.py` ainda nao faz embed nem upsert no store; ha TODO explicito.
- `Evidencia`: o seed de dados e executado no startup da API e injeta conhecimento e profissionais da propria Minutare Med.

## Lacunas
- `Evidencia`: nao ha rotas de auth, refresh token, sessao, usuario ou permissao.
- `Evidencia`: nao ha rotas reais para CRM, follow-up, leads, alertas, Google, salas, funcionarios, estoque, produtos ou procedimentos.
- `Evidencia`: nao ha separacao por clinica na base operacional nem nos filtros do RAG do MVP.
- `Evidencia`: nao ha governanca de prompt, versionamento de prompt ou repositorio de prompts externo.
- `Evidencia`: nao ha politica de versionamento/atualizacao de knowledge base operacional alem de `version` fixo nos documentos.

## Decisoes Arquiteturais Percebidas
- `Inferencia`: a equipe preferiu manter um MVP simples e funcional em FastAPI/pgvector enquanto construi um core mais ambicioso em paralelo.
- `Evidencia`: o dominio "clinic-specific" ja foi pensado para ser injetado por configuracao, nao por `if/else`, em `src/inteliclinic/clinic/*`.
- `Evidencia`: o canal principal escolhido para o MVP e Telegram.
- `Inferencia`: o produto tenta convergir para um core reutilizavel por clinica, mas ainda nao completou o desacoplamento da primeira implantacao.

## O que ja existe de verdade
- `Evidencia`: webhook Telegram funcional.
- `Evidencia`: CRUD de pacientes, profissionais e agenda.
- `Evidencia`: listagem de conversas, mensagens, handoffs, auditoria e dashboard.
- `Evidencia`: RAG simples via ingestao textual + pgvector + fallback textual.
- `Evidencia`: testes do backend para orquestrador, RAG, webhook, router e actions.

## O que existe parcial
- `Evidencia`: cancelamento multi-turn com mais de uma consulta.
- `Evidencia`: remarcacao.
- `Evidencia`: multi-clinic via `ClinicSettings` e `ClinicPrompts`, mas sem wiring no runtime.
- `Evidencia`: arquitetura LangGraph montada, mas fora do caminho principal da API.
- `Evidencia`: retriever hibrido, mas com componente sparse placeholder.

## O que esta so em plano
- `Plano`: GraphRAG.
- `Plano`: Google Calendar / Google integrations.
- `Plano`: WhatsApp e voz/LiveKit.
- `Plano`: RBAC/JWT.
- `Plano`: follow-up, CRM e leads.
- `Plano`: pipeline de onboarding completo por clinica usando `CLINIC_*`.

## Duvidas em Aberto
- `Inferencia`: pode existir algum deploy externo usando `src/inteliclinic/` diretamente, mas isso nao aparece neste repositorio.
- `Inferencia`: pode haver uma camada de auth externa ao frontend, mas nao existe evidencia no codigo local.
- `Inferencia`: o uso de Qdrant em algum ambiente manual e possivel, mas nao esta refletido no runtime principal do repositorio.

## Recomendacoes Futuras
- Extrair `clinic_id` para todas as entidades operacionais relevantes e filtrar tudo por tenant.
- Trocar todos os hardcodes de Minutare Med por configuracao de clinica ou branding injetado.
- Unificar o caminho principal de IA: ou promover `src/inteliclinic` para runtime real, ou simplificar docs/arquitetura para o que realmente roda.
- Corrigir os contratos frontend/backend de Telegram e RAG.
- Implementar auth minima antes de qualquer deploy publico do painel.
- Definir governanca de prompts e KB por clinica com versionamento.

## Referencias Principais desta Varredura
- `apps/api/app/main.py`
- `apps/api/app/core/config.py`
- `apps/api/app/ai_engine/*`
- `apps/api/app/api/routes/*`
- `apps/api/app/services/*`
- `apps/api/app/repositories/*`
- `apps/api/app/models/*`
- `apps/api/app/integrations/telegram/*`
- `frontend/src/app/*`
- `frontend/src/lib/*`
- `frontend/src/components/layout/sidebar.tsx`
- `src/inteliclinic/clinic/*`
- `src/inteliclinic/core/ai_engine/*`
- `src/inteliclinic/core/nlu/*`
- `src/inteliclinic/core/rag/*`
- `src/inteliclinic/core/analytics/*`
- `scripts/seed_data.py`
- `scripts/ingest_docs.py`
- `scripts/evaluate_rag.py`
- `docs/architecture/core-vs-clinic.md`
- `docs/clinic-onboarding/new-clinic.md`
