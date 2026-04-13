# AUDITORIA TÉCNICA — INTELLICLINIC

**Data da auditoria:** 10/04/2026 | **Branch auditada:** `claude/intelliclinic-tech-audit-fpUfk`

---

## 1. RESUMO EXECUTIVO DO ESTADO ATUAL

**Classificação geral: MVP PARCIAL → FUNCIONAL BÁSICO**

O IntelliClinic existe em dois planos simultâneos e desconexos:

* **`apps/api/`** — MVP real, funcional, testado (backend FastAPI + frontend Next.js 16). Telegram chatbot com agendamento ponta a ponta funciona. 86 testes passando.
* **`src/inteliclinic/`** — Arquitetura Phase 2 (LangGraph, LlamaIndex, Qdrant, Docling, Guardrails). Definida com rigor, mas praticamente  **tudo é stub** . Não está integrado ao fluxo real em produção.

O produto sabe o que quer ser. A arquitetura de destino foi projetada. Mas há uma lacuna crítica entre o que foi desenhado e o que está operando de verdade.

| Dimensão                        | Classificação                          |
| -------------------------------- | ---------------------------------------- |
| Estrutura de projeto             | FUNCIONAL BÁSICO                        |
| Backend (MVP)                    | FUNCIONAL BÁSICO                        |
| Frontend                         | FUNCIONAL BÁSICO                        |
| IA de atendimento externo        | PARCIAL                                  |
| IA cérebro interna              | NÃO INICIADO                            |
| CRM / Pipeline de leads          | NÃO INICIADO                            |
| ERP clínico (estoque, produtos) | NÃO INICIADO                            |
| Autenticação / RBAC            | NÃO INICIADO                            |
| Observabilidade                  | NÃO INICIADO                            |
| Integração Google Calendar     | NÃO INICIADO                            |
| LangGraph ativo                  | NÃO INICIADO (definido, não integrado) |
| Multi-clínica                   | EM ESTRUTURAÇÃO                        |

**Principais riscos hoje:**

1. Todas as rotas API são públicas — nenhum JWT/RBAC implementado
2. LangGraph definido mas não ativo — o MVP usa orquestrador regex; a migração é uma reescrita
3. CRM, ERP, estoque, convênios, relatórios, alertas e follow-up: **zero linhas implementadas**
4. O frontend não tem login/auth, qualquer pessoa com a URL tem acesso total
5. Observabilidade inexistente além de logs básicos

**Principais bloqueios:**

1. Sem auth, o projeto não pode ir a produção real com dados de pacientes
2. Sem CRM/ERP, metade do escopo do produto não existe
3. A divisão `apps/api/` vs `src/inteliclinic/` cria duas bases de código que precisam ser reconciliadas antes de qualquer SDD sério

---

## 2. O QUE JÁ EXISTE DE FATO

### 2.1 Estrutura de projeto

| Item             | Status                   | Detalhe                                                                                           |
| ---------------- | ------------------------ | ------------------------------------------------------------------------------------------------- |
| Monorepo         | Sim, informal            | Sem Nx/Turborepo. Convivem `apps/api/`,`src/`,`frontend/`,`docs/`,`scripts/`,`infra/` |
| Backend          | Existe e funciona        | FastAPI, async SQLAlchemy, Python 3.11+ em `apps/api/`                                          |
| Frontend         | Existe e funciona        | Next.js 16.2.2, React 19, Tailwind 4 em `frontend/`                                             |
| Banco            | PostgreSQL 16 + pgvector | Schema real, migrations Alembic (2 versões)                                                      |
| Auth             | **Não existe**    | Nenhum JWT, session, OAuth ou RBAC                                                                |
| Filas / Workers  | **Não existe**    | Sem Celery, RQ, ou qualquer task queue                                                            |
| Docker           | Existe                   | `docker-compose.yml`na raiz + cópia em `infra/docker/`. Stack: db, qdrant, api, frontend     |
| Deploy           | Documentado              | Dokploy + Traefik + VPS. Guia em `docs/deployment/dedicated-deploy.md`                          |
| Observabilidade  | Mínima                  | Logs estruturados básicos. Sem OpenTelemetry, sem Prometheus, sem Sentry                         |
| `.env.example` | Completo                 | Cobre todas as variáveis necessárias (60+ variáveis)                                           |
| Migrations       | 2 versões Alembic       | `001_initial_schema.py`,`002_add_pending_action.py`                                           |
| Documentação   | Robusta                  | README.md (30KB), RUNBOOK, API_MAP, DB_SCHEMA, PRD_MVP, guia de onboarding                        |

### 2.2 Módulos já implementados

| Módulo                          | Existe?        | Funcional? | Completude | Rotas                                             | Telas                           | Modelos                                                       | Lacunas principais                                                  |
| -------------------------------- | -------------- | ---------- | ---------- | ------------------------------------------------- | ------------------------------- | ------------------------------------------------------------- | ------------------------------------------------------------------- |
| **Pacientes**              | Sim            | Sim        | ~70%       | POST/GET/PATCH `/patients`, lookup por Telegram | Lista + detalhe + modal create  | `patients`table completa (CPF, convênio, consentimento IA) | Sem histórico completo, sem documentos, sem prontuário            |
| **Médicos/Profissionais** | Sim            | Sim        | ~65%       | GET/POST/PATCH/DELETE `/professionals`          | Lista + modal create/edit       | `professionals`(CRM, especialidade)                         | Sem agenda própria, sem configuração de disponibilidade          |
| **Funcionários**          | **Não** | —         | 0%         | —                                                | —                              | —                                                            | Não existe                                                         |
| **Salas**                  | **Não** | —         | 0%         | —                                                | —                              | —                                                            | Não existe                                                         |
| **Consultas**              | Parcial        | Parcial    | ~40%       | Dentro de schedules                               | Dentro de schedules             | `schedule_slots`                                            | Sem prontuário, sem status clínico                                |
| **Agenda**                 | Sim            | Sim        | ~60%       | POST/GET/book/cancel `/schedules`               | Lista com filtros, cancelamento | `schedule_slots`com status enum                             | Sem visão calendário visual, sem disponibilidade por profissional |
| **Convênios**             | Parcial        | Não       | ~10%       | Ausente                                           | Ausente                         | Campo `convenio_name`em `patients`                        | Sem tabela própria, sem regras, sem validação TISS               |
| **Procedimentos**          | **Não** | —         | 0%         | —                                                | —                              | —                                                            | Não existe                                                         |
| **Produtos**               | **Não** | —         | 0%         | —                                                | —                              | —                                                            | Não existe                                                         |
| **Estoque**                | **Não** | —         | 0%         | —                                                | —                              | —                                                            | Não existe                                                         |
| **Leads**                  | **Não** | —         | 0%         | —                                                | —                              | —                                                            | Não existe                                                         |
| **Pipeline CRM**           | **Não** | —         | 0%         | —                                                | —                              | —                                                            | Não existe                                                         |
| **Follow-up**              | **Não** | —         | 0%         | —                                                | —                              | —                                                            | Não existe                                                         |
| **Relatórios**            | **Não** | —         | 0%         | Apenas `/dashboard/summary`(7 KPIs)             | KPI cards no dashboard          | —                                                            | Sem exportação, sem filtros temporais, sem financeiro             |
| **Alertas**                | **Não** | —         | 0%         | —                                                | —                              | —                                                            | Não existe                                                         |
| **Trilha de auditoria**    | Sim            | Sim        | ~70%       | GET `/audit`                                    | Tabela com filtros              | `audit_events`(actor_type, action, resource_type, payload)  | Sem interface avançada, sem filtro por período                    |
| **Centro de pendências**  | **Não** | —         | 0%         | —                                                | —                              | —                                                            | Existe tela de handoffs, mas não é "centro de pendências"        |
| **Handoff humano**         | Sim            | Sim        | ~65%       | GET/POST/PATCH `/handoff`                       | Lista + update de status        | `handoffs`(reason, priority, context_summary)               | Sem notificação, sem assignment automático                       |

### 2.3 IA já implementada

**IA de atendimento externo (Telegram)**

| Item                            | Existe?        | Funciona?       | Observação                                                                                                      |
| ------------------------------- | -------------- | --------------- | ----------------------------------------------------------------------------------------------------------------- |
| Recepção via Telegram         | Sim            | Sim, de verdade | Webhook handler em `integrations/telegram/webhook_handler.py`                                                   |
| Identificação de paciente     | Sim            | Sim             | Por `telegram_user_id`, cria paciente se não existe                                                            |
| Análise de intenção (FARO)   | Sim            | Sim (regex)     | `ai_engine/intent_router.py`— intents: AGENDAR, CANCELAR, REMARCAR, DUVIDA_OPERACIONAL, FALAR_COM_HUMANO, etc. |
| Extração de entidades         | Sim            | Parcial         | Data/hora relativa + absoluta, nome de médico via regex.**Não usa LLM estruturado**                       |
| Guardrails                      | Sim            | Sim             | `ai_engine/guardrails.py`— urgência, questões clínicas, prompt injection, baixa confiança                  |
| Actions reais (agendar)         | Sim            | Sim             | `ai_engine/actions.py`— search_slots, book_slot, cancel_slot, list_appointments                                |
| Multi-turn state                | Sim            | Sim             | Via `conversation.pending_action`(JSON) — fluxo de seleção de slot, confirmação de cancelamento            |
| Geração de resposta via LLM   | Sim            | Sim             | `response_builder.py`+`clients/llm_client.py`— suporta OpenAI/Anthropic/Gemini                               |
| RAG no atendimento              | Parcial        | Parcial         | `rag_service.py`— vector search (pgvector) + text fallback.**Docling não ativo**                        |
| Classificação de lead         | **Não** | —              | Não existe                                                                                                       |
| Agendamento por IA completo     | Parcial        | Parcial         | Funciona para slots existentes. Sem criação de slot novo, sem múltiplos médicos em paralelo                   |
| Geração de relatório por IA  | **Não** | —              | Não existe                                                                                                       |
| Alertas por IA                  | **Não** | —              | Não existe                                                                                                       |
| Supervisão humana (handoff)    | Sim            | Sim             | Auto-escalation por baixa confiança/urgência + handoff manual via API                                           |
| Logs/auditoria de ações da IA | Sim            | Sim             | `audit_service.py`registra todas as ações da IA                                                               |

**IA cérebro interna**

| Item                               | Existe?        | Status                                                                                              |
| ---------------------------------- | -------------- | --------------------------------------------------------------------------------------------------- |
| IA observando recepção           | **Não** | —                                                                                                  |
| IA observando estoque              | **Não** | —                                                                                                  |
| IA observando CRM                  | **Não** | —                                                                                                  |
| IA observando gestão              | **Não** | —                                                                                                  |
| Recepcionista cadastrando via chat | **Não** | —                                                                                                  |
| IA gerando alertas operacionais    | **Não** | —                                                                                                  |
| Memória/contexto persistente      | Parcial        | Apenas dentro da conversa Telegram. Sem memória cross-session, sem embeddings de contexto clínico |

**LangGraph (Phase 2)**

| Item                               | Status                                                |
| ---------------------------------- | ----------------------------------------------------- |
| Grafo definido (`main_graph.py`) | Código existe, 8 nós mapeados                       |
| State (`clinic_state.py`)        | TypedDict definido                                    |
| Nós (reception, scheduling, etc.) | **Stubs**— estrutura existe, lógica não      |
| Builder (`langgraph/builder.py`) | Stub                                                  |
| Integração ao fluxo real         | **Não existe**— MVP usa orquestrador separado |

---

## 3. MATRIZ DE ADERÊNCIA AO PRD

| Requisito / Bloco do PRD        | Status Atual        | Evidência no Projeto                                         | Gap para Fechar                                                               |
| ------------------------------- | ------------------- | ------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| Interface tradicional forte     | PARCIAL             | Frontend Next.js funcional, 8 páginas operacionais           | Faltam: visão calendário, módulos ERP/CRM, relatórios, módulo financeiro |
| IA de atendimento externo       | FUNCIONAL BÁSICO   | Telegram ponta a ponta, actions reais                         | Sem WhatsApp, sem voz, NLU regex (não LLM), sem classificação de lead      |
| IA cérebro interna             | NÃO INICIADO       | `src/`tem esboços, mas nada ativo                          | Requer LangGraph ativo, tools de observação, acesso a dados internos        |
| CRM vivo                        | NÃO INICIADO       | Campo `convenio_name`em paciente; zero CRM                  | Tabelas, pipeline, funil, lead scoring, source tracking: tudo por fazer       |
| Agenda + Google Calendar        | PARCIAL             | Agenda existe (slots, book, cancel)                           | Sem Google OAuth, sem sync bilateral, sem visão calendário no frontend      |
| Follow-up                       | NÃO INICIADO       | Não existe                                                   | Fila de follow-up, triggers, envio automático: tudo por fazer                |
| Alertas                         | NÃO INICIADO       | Não existe                                                   | Sem motor de alertas, sem triggers, sem notificações                        |
| Relatórios                     | NÃO INICIADO       | `/dashboard/summary`com 7 KPIs estáticos                   | Sem financeiro, sem exportação, sem filtros, sem geração por IA           |
| Auditoria                       | FUNCIONAL BÁSICO   | `audit_events`table + rota + tela                           | Sem filtro por período na UI, sem exportação, sem diferencial IA vs humano |
| Permissões / RBAC              | NÃO INICIADO       | Nada existe                                                   | JWT + roles (recepcionista, médico, gerente, admin) tudo por fazer           |
| Observabilidade                 | NÃO INICIADO       | Logs básicos                                                 | Sem OpenTelemetry, sem Prometheus, sem dashboards de infra                    |
| Handoff humano                  | FUNCIONAL BÁSICO   | `handoffs`table, API, tela                                  | Sem notificação push, sem assignment automático, sem SLA tracking          |
| Operação híbrida tela + chat | PARCIAL             | Tela existe; chat Telegram existe                             | Sem chat interno no dashboard, sem interface unificada tela+chat              |
| Documentação de deploy        | FUNCIONAL AVANÇADO | `docs/deployment/`, RUNBOOK, docker-compose                 | Bem documentado para MVP. Falta para ERP/CRM/autenticação                   |
| Guia nova clínica              | FUNCIONAL BÁSICO   | `docs/clinic-onboarding/new-clinic.md`, checklist 10 passos | Funcional para MVP. Incompleto para produto final                             |
| Auth / Google OAuth             | NÃO INICIADO       | `.env.example`tem vars de Google (inativas)                 | Implementação completa pendente                                             |
| ERP clínico                    | NÃO INICIADO       | Sem funcionários, salas, procedimentos, estoque              | Módulos inteiros por criar                                                   |
| Estoque                         | NÃO INICIADO       | Não existe                                                   | —                                                                            |
| Financeiro                      | NÃO INICIADO       | Não existe                                                   | —                                                                            |

---

## 4. REUTILIZAÇÃO DE PROJETOS ANTERIORES

### 4.1 Reaproveitamento já realizado

Com base na evidência no código, houve reaproveitamento  **conceitual e estrutural** , não direto de código copiado:

| Origem                      | O que foi aproveitado                                                          | Como aparece no projeto                                                                            |
| --------------------------- | ------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------- |
| `ai_engine`anterior       | Padrão de orquestrador com pipeline FARO → guardrails → actions → response | `apps/api/app/ai_engine/orchestrator.py`— estrutura idêntica ao padrão de projetos anteriores |
| Projetos FastAPI anteriores | Padrão repository/service layer, schemas Pydantic, async SQLAlchemy           | Toda a camada `models/ → repositories/ → services/ → api/routes/`                             |
| Minutare.ai                 | Conceito de chatbot clínico + FARO + identificação de paciente por Telegram | Estrutura de `webhook_handler.py`e `intent_router.py`                                          |
| Projetos com LangGraph      | Definição dos grafos em `src/`— os nós, o StateGraph, o builder          | `src/inteliclinic/core/ai_engine/graphs/main_graph.py`                                           |
| Projetos de CRM/Dashboard   | Layout de AppShell + Sidebar + Topbar no frontend                              | `frontend/src/components/layout/`                                                                |
| Boilerplates de RAG         | Estrutura ingestion/chunking/retriever/store                                   | `src/inteliclinic/core/rag/`                                                                     |

### 4.2 Reaproveitamento recomendado mas ainda não feito

| Projeto/Fonte                     | O que deveria ser aproveitado                                                      | Impacto                                        |
| --------------------------------- | ---------------------------------------------------------------------------------- | ---------------------------------------------- |
| `qwen-test`/ projetos de NLU    | Pipeline de extração estruturada com Instructor (já está no `src/`como stub) | Alto — substituiria o FARO regex por NLU real |
| Projetos anteriores com Celery/RQ | Padrão de task queue para follow-up e alertas                                     | Alto — sem fila não há follow-up            |
| Projetos de auth FastAPI          | JWT + RBAC (middleware, deps, models)                                              | Crítico — sem isso não há produção real  |
| Projetos de observabilidade       | Structured logging com contexto de request                                         | Médio                                         |
| Pipelines de RAG com Qdrant       | `rag_repository.py`usa pgvector; Qdrant está no docker-compose mas não wired   | Médio                                         |

### 4.3 Reaproveitamento que NÃO vale a pena fazer

| Item                                        | Motivo                                                                                                     |
| ------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| Projetos de ERP genérico open source       | Acoplamento alto, customização médica complexa demais; melhor construir do zero com o domínio clínico |
| Qualquer boilerplate de dashboard genérico | Frontend atual está adequado para o domínio; reescrever custaria mais do que continuar                   |
| Migrar infra atual para Kubernetes agora    | Prematura; Dokploy + VPS é suficiente para fase atual                                                     |

---

## 5. OPEN SOURCE: O QUE JÁ FOI APROVEITADO E O QUE DEVERIA SER

### 5.1 Já incorporado (evidência real no código/deps)

| Projeto                     | Versão   | Como incorporado               |
| --------------------------- | --------- | ------------------------------ |
| **FastAPI**           | ≥0.115.0 | Framework principal do backend |
| **SQLAlchemy 2.0**    | ≥2.0.35  | ORM async completo             |
| **SQLModel**          | ≥0.0.22  | Models Pydantic+SQLAlchemy     |
| **Alembic**           | ≥1.14.0  | Migrations                     |
| **pgvector**          | ≥0.3.6   | Embeddings em PostgreSQL       |
| **Next.js 16**        | 16.2.2    | Framework frontend             |
| **Tailwind CSS 4**    | 4.x       | Styling                        |
| **Pydantic Settings** | ≥2.6.0   | Configuração via env vars    |
| **pytest-asyncio**    | ≥0.24    | Testes assíncronos            |
| **Ruff**              | ≥0.8.0   | Linter                         |
| **Docker Compose v2** | —        | Orquestração local/prod      |

### 5.2 Parcialmente incorporado (declarado no pyproject.toml, mas não integrado ao fluxo real)

| Projeto                         | Status real                                                                                |
| ------------------------------- | ------------------------------------------------------------------------------------------ |
| **LangGraph**≥0.2.0      | Dependency declarada, código em `src/`como stubs.**Não ativo em produção**     |
| **LlamaIndex**≥0.11.0    | Declarado,`llamaindex_store.py`é stub. MVP usa pgvector direto                          |
| **Qdrant client**≥1.11.0 | No docker-compose, cliente instanciado, mas `qdrant_store.py`é stub. MVP usa pgvector   |
| **Docling**≥2.0.0        | Declarado,`docling_parser.py`é stub. MVP recebe texto direto                            |
| **Guardrails AI**≥0.5.0  | Declarado,`output_guards.py`parcialmente implementado. MVP usa guardrails custom simples |
| **Instructor**≥1.4.0     | Declarado,`message_extractor.py`é stub. MVP usa FARO regex                              |
| **PyOD**≥2.0.0           | Declarado,`anomaly/`é stub                                                              |
| **RAGAS**≥0.1.0          | Declarado, evaluator é stub                                                               |

### 5.3 Ainda não incorporado

| Projeto                               | Caso de uso                                           |
| ------------------------------------- | ----------------------------------------------------- |
| **OpenTelemetry**               | Tracing distribuído, spans por request               |
| **Prometheus + Grafana**        | Métricas de infra e negócio                         |
| **Celery ou RQ**                | Task queue para follow-up, alertas, jobs assíncronos |
| **python-jose / FastAPI-Users** | JWT auth + RBAC                                       |
| **Google Auth / OAuth2**        | Login social + Calendar integration                   |
| **medspaCy**                    | NLP clínico (entidades médicas em português)       |
| **GraphRAG**                    | RAG baseado em grafo para relacionamentos clínicos   |
| **Sentry**                      | Error tracking em produção                          |

### 5.4 Recomendação objetiva de adoção ou descarte

| Projeto                               | Recomendação                      | Justificativa                                                                                                 |
| ------------------------------------- | ----------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| **LangGraph**                   | **ADOTAR — prioridade alta** | Já declarado, arquitetura Phase 2 foi desenhada para ele. Integrar ao fluxo real é o próximo passo lógico |
| **Instructor**                  | **ADOTAR**                    | Substitui FARO regex por extração estruturada real. Melhora confiabilidade do NLU significativamente        |
| **LlamaIndex + Qdrant**         | **ADOTAR**                    | Já no docker-compose. Migrar de pgvector para Qdrant melhora escalabilidade de RAG                           |
| **Docling**                     | **ADOTAR**                    | Necessário para ingestão real de PDFs clínicos (protocolos, convênios)                                    |
| **Celery + Redis**              | **ADOTAR**                    | Sem fila não há follow-up ou alertas. Bloqueia 30% das features do produto                                  |
| **python-jose / FastAPI-Users** | **ADOTAR — crítico**        | Sem auth não vai a produção                                                                                |
| **RAGAS**                       | **ADOTAR**                    | Já declarado. Conectar ao pipeline de avaliação de RAG                                                     |
| **medspaCy**                    | **AVALIAR**                   | Útil para Phase 2, mas dependência pesada. Checar se há modelo PT-BR adequado                              |
| **GraphRAG**                    | **ADIAR**                     | Interface definida mas prematura. Priorizar RAG básico funcionando primeiro                                  |
| **OpenTelemetry**               | **ADOTAR a médio prazo**     | Necessário antes de escalar para múltiplas clínicas                                                        |
| **Guardrails AI**               | **COMPLETAR**                 | Já declarado. A implementação parcial em `output_guards.py`precisa ser finalizada                        |
| **PyOD**                        | **ADIAR**                     | Útil para detecção de glosa, mas não é bloqueador para MVP+                                              |
| **LiveKit**                     | **ADIAR**                     | Voice é Phase 3, não bloqueia nada atual                                                                    |

---

## 6. NOVAS EXIGÊNCIAS: JÁ FORAM IMPLANTADAS?

| Exigência                                           | Status            | Evidência                                                           | O que falta                                                                         | Prioridade |
| ---------------------------------------------------- | ----------------- | -------------------------------------------------------------------- | ----------------------------------------------------------------------------------- | ---------- |
| Documentação separando novo vs herdado             | PARCIAL           | `docs/architecture/core-vs-clinic.md`existe                        | Não há linha clara no código indicando o que veio de projetos anteriores vs novo | Baixa      |
| Projeto pronto para deploy                           | PARCIAL           | Docker-compose funcional, RUNBOOK existe                             | Sem auth, sem backup, sem monitoramento — não é deploy de produção real        | Alta       |
| Pipelines construídas e documentadas                | PARCIAL           | Pipeline de chat: documentada e funcional                            | Pipelines de follow-up, alertas, relatórios: não existem                          | Alta       |
| CRM funcional com classificação de leads           | **NÃO**    | —                                                                   | Tabelas, lógica, scoring, fonte de lead: tudo por criar                            | Alta       |
| ERP clínico e estoque                               | **NÃO**    | —                                                                   | Módulos inteiros                                                                   | Alta       |
| Gestão de pacientes, funcionários, salas, produtos | PARCIAL           | Pacientes: ~70%. Funcionários/salas/produtos: 0%                    | 3 de 4 módulos não existem                                                        | Alta       |
| Rotas seguras por env/auth                           | **NÃO**    | `.env.example`tem secrets, mas sem autenticação nas rotas        | JWT middleware + RBAC + API key management                                          | Crítico   |
| IA de atendimento com classificação de lead        | PARCIAL           | Atendimento funciona; classificação não existe                    | Lead scoring, source tracking, pipeline CRM                                         | Alta       |
| Tools da IA feitas e funcionais                      | PARCIAL           | `actions.py`tem tools de agenda                                    | Tools de CRM, estoque, relatório, follow-up: não existem                          | Alta       |
| Google OAuth pronto para Calendar                    | **NÃO**    | Vars no `.env.example`(inativas)                                   | Implementação completa OAuth2 + sync Calendar                                     | Média     |
| IA interna observando recepção/estoque/CRM/gestão | **NÃO**    | Esboços em `src/`como stubs                                       | LangGraph ativo + tools de observação + dados internos                            | Alta       |
| Recepção cadastrar via chat pela IA cérebro       | **NÃO**    | —                                                                   | IA interna + interface de chat interna                                              | Média     |
| Relatórios financeiro/CRM/operação                | **NÃO**    | 7 KPIs estáticos                                                    | Motor de relatórios, exportação, filtros                                         | Média     |
| Follow-up com IA                                     | **NÃO**    | —                                                                   | Fila de follow-up, triggers, envio automático                                      | Alta       |
| Alertas e avisos inteligentes                        | **NÃO**    | —                                                                   | Motor de alertas, regras, notificações                                            | Alta       |
| Observabilidade                                      | **NÃO**    | Logs básicos                                                        | OpenTelemetry, Prometheus, dashboards                                               | Média     |
| Human-in-the-loop                                    | FUNCIONAL BÁSICO | Handoff table + API + tela                                           | Sem notificação, sem SLA, sem assignment                                          | Média     |
| Memória/contexto persistente                        | PARCIAL           | `pending_action`JSON por conversa                                  | Sem memória cross-session, sem embeddings de histórico                            | Alta       |
| Separação core global vs core clínica             | PARCIAL           | `src/inteliclinic/core/`vs `src/inteliclinic/clinic/`documentado | Separação no código ainda não respeitada em `apps/api/`(mistura tudo)         | Média     |
| Guia de onboarding nova clínica                     | FUNCIONAL BÁSICO | `docs/clinic-onboarding/new-clinic.md`                             | Incompleto para produto final (sem ERP, sem auth)                                   | Baixa      |

---

## 7. ARQUITETURA ATUAL AGUENTA O PRODUTO?

**Resposta direta:** Para o MVP de chat + agenda + painel básico, aguenta. Para o produto final descrito, **não aguenta sem refatoração em blocos centrais.**

### Partes sólidas

| Componente                         | Por quê é sólido                                                           |
| ---------------------------------- | ----------------------------------------------------------------------------- |
| Camada de dados (models/repos)     | Schema normalizado, async correto, pgvector integrado, migrations versionadas |
| Pipeline de chat Telegram          | Funciona ponta a ponta, testado, auditado                                     |
| Separação core/clinic (conceito) | Bem documentada, estrutura de pastas correta                                  |
| Frontend layout                    | Componentizado, hooks separados, API client tipado                            |
| Testes                             | 86 testes com banco real (SQLite async) — base confiável                    |
| Documentação                     | Acima da média para um projeto neste estágio                                |

### Partes frágeis

| Componente                                      | Problema                                                                                                                                                                                                       |
| ----------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Orquestrador MVP vs LangGraph Phase 2** | Duas implementações paralelas.`apps/api/ai_engine/`(real) e `src/core/ai_engine/`(stub). Precisam ser unificadas ou haverá divergência permanente                                                      |
| **FARO (regex NLU)**                      | Frágil para linguagem natural variada. Falha silenciosa em inputs inesperados. Não escala                                                                                                                    |
| **RAG em pgvector**                       | Funciona, mas Qdrant já está no docker-compose e a arquitetura Phase 2 foi projetada para ele. Manter dois sistemas é custo técnico                                                                        |
| **`pending_action`como JSON em coluna** | Multi-turn state gravado como JSON bruto em `conversations.pending_action`. Funciona para fluxos simples, mas não escala para conversas complexas — sem schema, sem validação, sem histórico de estados |
| **Sem auth em nada**                      | Risco crítico. Não é fragilidade arquitetural, é ausência de componente                                                                                                                                   |

### Partes acopladas demais

| Componente              | Acoplamento                                                                                           |
| ----------------------- | ----------------------------------------------------------------------------------------------------- |
| `webhook_handler.py`  | Chama diretamente serviços, orquestrador, Telegram client — muito lógica em um arquivo             |
| `orchestrator.py`     | Conhece ScheduleService, RagService, ConversationService, AuditService — acoplamento horizontal alto |
| Frontend `lib/api.ts` | API client monolítico com todos os endpoints em um arquivo — ok agora, problemático quando crescer |

### Módulos que deveriam virar domínios independentes

| Módulo                            | Por quê separar                                                                  |
| ---------------------------------- | --------------------------------------------------------------------------------- |
| **Auth / IAM**               | Precisa ser independente antes de qualquer outra coisa                            |
| **CRM**                      | Domínio próprio, modelo de dados próprio, não deve estar acoplado a pacientes |
| **Financeiro**               | Sensível, auditável independentemente                                           |
| **Notificações / Alertas** | Precisa de fila própria, não deve bloquear o fluxo de chat                      |
| **Relatórios**              | Leitura pesada, não deve competir com o OLTP principal                           |

### Contratos que precisam ser definidos antes de seguir

1. **Contrato de Auth** — Quais roles existem? O que cada role pode fazer?
2. **Contrato LangGraph vs MVP orchestrator** — Qual vai ser o orquestrador em produção?
3. **Contrato de tools da IA** — Quais tools a IA interna tem? Schema de input/output de cada tool?
4. **Contrato multi-clínica** — Tenant ID em todas as tabelas? Banco separado por clínica? Subdomínio?
5. **Contrato de canal** — Telegram agora. WhatsApp depois. A abstração de canal existe? Não de verdade

---

## 8. O QUE FALTA PARA ESCREVER O SDD DEFINITIVO

| Pendência                                                                                                               | Impacto                                            | Bloqueia qual doc        | Pode ser premissa?                                                |
| ------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------- | ------------------------ | ----------------------------------------------------------------- |
| **Decisão: LangGraph ativo ou reescrever MVP orquestrador?**                                                      | Alto — define toda a arquitetura de IA            | DesignDoc + TaskList     | Não. Decide agora                                                |
| **Modelo de Auth/RBAC definido**(roles, permissões, multi-tenant)                                                 | Alto — afeta todas as rotas e modelos             | Requirements + DesignDoc | Não. Decide agora                                                |
| **Escopo do CRM**— o que é lead? Quais estágios do funil? Quais ações de follow-up?                           | Alto — módulo inteiro não definido tecnicamente | Requirements             | Não. Decide antes de escrever requirements                       |
| **Escopo do ERP**— funcionários, salas, procedimentos, produtos, estoque: qual MVP?                              | Alto                                               | Requirements             | Pode ser premissa parcial (listar o que entra no MVP+ vs Phase 2) |
| **Modelo de memória da IA**— cross-session? Por paciente? Por clínica? RAG?                                     | Médio                                             | DesignDoc                | Pode ser premissa com escolha explícita                          |
| **Contrato de canal de comunicação**— Telegram agora, WhatsApp depois, abstração?                             | Médio                                             | DesignDoc                | Pode ser premissa (Telegram agora, interface plugável no futuro) |
| **Definição de "IA cérebro interna"**— Quais dados ela observa? Quais ações pode tomar? Quais são as tools? | Alto                                               | DesignDoc + TaskList     | Não. Sem isso o DesignDoc de IA é impossível                   |
| **Modelo de relatórios**— quais relatórios? por período? exportação? geração por IA?                       | Médio                                             | Requirements             | Pode ser premissa com lista mínima                               |
| **Estratégia de observabilidade**— qual stack? (ELK, Prometheus+Grafana, Datadog?)                               | Baixo                                              | DesignDoc                | Pode ser premissa                                                 |
| **Estrutura de multi-clínica**— VPS por clínica (atual) ou multi-tenant em SaaS?                                | Alto — define schema do banco                     | DesignDoc                | Não. Decisão arquitetural fundamental                           |

---

## 9. MATRIZ FINAL DE STATUS

### 9.1 Já pronto

* Telegram chatbot ponta a ponta (FARO → guardrails → actions → resposta)
* CRUD completo de pacientes e profissionais
* Gestão de slots de agenda (criar, reservar, cancelar)
* Conversa + histórico de mensagens persistidos
* Handoff humano (criação, status)
* Trilha de auditoria de ações
* RAG com pgvector (ingestão texto + busca vetorial + fallback texto)
* Dashboard com 7 KPIs
* Frontend funcional (8 páginas, 20+ componentes)
* Docker-compose de produção
* Documentação técnica (RUNBOOK, API_MAP, DB_SCHEMA, deploy guide, onboarding guide)
* 86 testes automatizados com banco real

### 9.2 Parcial mas aproveitável

* Orquestrador de IA (`apps/api/ai_engine/`) — funciona, mas precisa migrar para LangGraph
* RAG — funciona com pgvector, precisa migrar para Qdrant + LlamaIndex + Docling
* Guardrails — implementação básica funcional, precisa finalizar `output_guards.py`
* Multi-turn state — `pending_action` JSON funciona para fluxos simples, precisa de State Machine real
* Estrutura LangGraph em `src/` — bem projetada, precisa sair dos stubs
* Arquitetura core/clinic — conceito correto, separação no código incompleta

### 9.3 Precisa refatorar

* `webhook_handler.py` — muito acoplado, precisa de injeção de dependência
* `orchestrator.py` — será substituído pelo LangGraph, mas a lógica deve ser migrada
* `intent_router.py` — FARO regex precisa ser substituído por Instructor NLU
* `lib/api.ts` no frontend — API client monolítico vai quebrar quando crescer
* `pending_action` JSON — precisa virar State Machine versionada
* Toda a camada de rotas — adicionar middleware de auth antes de qualquer coisa

### 9.4 Não existe ainda

* Autenticação e autorização (JWT + RBAC)
* CRM (leads, pipeline, funil, scoring)
* ERP (funcionários, salas, procedimentos, produtos)
* Estoque
* Financeiro
* Follow-up automático
* Motor de alertas
* Relatórios avançados
* IA cérebro interna
* Google OAuth + Calendar sync
* Notificações internas
* Observabilidade (OpenTelemetry, Prometheus)
* Task queue (Celery/RQ)
* Interface de chat interno no dashboard
* Admin console (gestão de usuários, roles, API keys)

### 9.5 Riscos de seguir sem ajustar

| Risco                                                      | Severidade         | Consequência                                                                 |
| ---------------------------------------------------------- | ------------------ | ----------------------------------------------------------------------------- |
| Avançar com funcionalidades sem auth                      | **CRÍTICO** | Dados de pacientes expostos, LGPD violada em produção real                  |
| Integrar CRM/ERP sem definir multi-tenant                  | **ALTO**     | Dados de clínicas misturados, reescrita futura obrigatória                  |
| Manter dois orquestradores de IA (MVP + LangGraph)         | **ALTO**     | Divergência de comportamento, manutenção dobrada, bugs de sync             |
| Continuar com FARO regex como NLU                          | **MÉDIO**   | Falha silenciosa em inputs não previstos, experiência do usuário degradada |
| Não ter task queue antes de implementar follow-up         | **MÉDIO**   | Follow-up em requisição HTTP síncrona — timeout, falha silenciosa         |
| `pending_action`JSON sem schema para multi-turn complexo | **MÉDIO**   | Corrupção de estado em fluxos de múltiplos passos                          |

### 9.6 Recomendação de próximos passos antes do SDD

**Passo 1 — Decisões arquiteturais obrigatórias (antes de escrever qualquer doc):**

1. Confirmar: multi-tenant (SaaS) ou VPS-por-clínica? → define schema do banco
2. Confirmar: LangGraph como orquestrador oficial? → define toda arquitetura de IA
3. Definir roles e permissões mínimas do RBAC
4. Definir escopo mínimo do CRM (quais campos de lead, quais estágios)
5. Definir o que a "IA cérebro interna" pode ver e fazer (lista de tools)

**Passo 2 — Refatorações desbloqueadoras (antes de criar features novas):**

1. Implementar JWT auth + middleware → desbloqueia: todas as rotas
2. Ativar LangGraph substituindo MVP orchestrator → desbloqueia: IA cérebro, tools avançadas
3. Migrar NLU de FARO regex para Instructor → desbloqueia: classificação de lead, NLU robusto
4. Adicionar Redis + Celery → desbloqueia: follow-up, alertas, jobs assíncronos

**Passo 3 — Só então escrever o SDD definitivo:**

* `Requirements.md` — com escopo de CRM, ERP, auth e relatórios definidos
* `DesignDoc.md` — com arquitetura de IA (LangGraph), auth, multi-tenant e observabilidade definidas
* `TaskList.md` — com tasks granulares por domínio, em ordem de dependência

---

**Resumo em uma linha:** O IntelliClinic tem uma base técnica honesta e bem documentada, com um MVP de chat+agenda real e funcional — mas está a 40% do produto descrito, com ausência crítica de auth, CRM, ERP, observabilidade e IA interna, e com uma dívida arquitetural específica (dois orquestradores de IA, NLU regex) que precisa ser quitada antes de escalar.
