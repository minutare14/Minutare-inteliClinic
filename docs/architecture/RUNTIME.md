# IntelliClinic — Runtime Architecture

**Last updated:** 2026-04-16
**Status:** Current and authoritative

---

## 1. Runtime oficial

O runtime operacional real do IntelliClinic é:

| Camada     | Localização              | Tecnologia         |
|------------|--------------------------|--------------------|
| Backend    | `apps/api/app/`          | FastAPI + SQLModel |
| Frontend   | `frontend/src/`          | Next.js 16 + React |
| Database   | PostgreSQL 16 + pgvector | Alembic migrations |
| Embeddings | sentence-transformers    | local / OpenAI / Gemini |
| Vector DB  | pgvector (embutido no PG)| Pronto para Qdrant |
| Canal      | Telegram Webhook         | bot via HTTPS      |

**`src/inteliclinic/`** é a camada de evolução arquitetural futura (LangGraph, Instructor, Qdrant, LlamaIndex). Não está no caminho principal da API hoje.

---

## 2. Estratégia de deploy

```
1 clínica = 1 VPS = 1 banco = 1 deploy = 1 configuração
```

Trocar de clínica significa trocar:
- `.env` (CLINIC_ID, CLINIC_NAME, TELEGRAM_BOT_TOKEN, etc.)
- assets / branding (via Admin UI)
- KB (RAG documents — via Admin UI ou script)
- dados iniciais (seed_data.py usa CLINIC_NAME do env)

**Nunca exige alteração de código.**

---

## 3. Pipeline conversacional (runtime atual)

```
Telegram msg
  ↓
webhook_handler.py
  ↓
AIOrchestrator.process_message()
  │
  ├─ NODE 1: load_runtime_context
  │    ClinicSettings + PromptRegistry + InsuranceCatalog + ClinicSpecialty
  │
  ├─ NODE 2: resolve_conversation_state
  │    pending_action (multi-turn state)
  │
  ├─ NODE 3: analyze_intent_and_entities (FARO)
  │    Intent classification + entity extraction
  │
  ├─ NODE 4: build_context
  │    ConversationContext + patient history
  │
  ├─ NODE 5: policy_guardrails (pre)
  │    injection / consent / urgency
  │
  ├─ NODE 6: decision_router
  │    │
  │    ├─ Priority 1: structured_data_lookup
  │    │    professionals / insurance / address / phone
  │    │    → source_of_truth: professionals | insurance_catalog | clinic_settings
  │    │
  │    ├─ Priority 2: schedule_flow
  │    │    AGENDAR / CANCELAR / REMARCAR
  │    │    → source_of_truth: schedule_db
  │    │
  │    ├─ Priority 3: rag_retrieval + response_composer
  │    │    DUVIDA_OPERACIONAL / POLITICAS
  │    │    Stage 1: pgvector (top_k_initial)
  │    │    Stage 2: lexical boost
  │    │    Stage 3: cross-encoder rerank (if enabled)
  │    │    Stage 4: top_k_final → LLM
  │    │    → source_of_truth: rag
  │    │
  │    ├─ clarification_flow
  │    │    DESCONHECIDA / missing entities
  │    │
  │    └─ handoff_flow
  │         FALAR_COM_HUMANO / urgency / clinical
  │
  ├─ NODE 7: response_composer
  │    UnifiedResponseComposer centraliza toda resposta final
  │
  ├─ NODE 8: post_guardrails
  │    urgency / clinical / confidence
  │
  ├─ NODE 9: persist_and_audit
  │    AuditEvent com trace completo do pipeline
  │
  └─ NODE 10: emit_response
       EngineResponse → webhook handler → Telegram
```

---

## 4. Governança da clínica em runtime

Todo comportamento da IA é governado por:

| Fonte              | O que controla                                          |
|--------------------|---------------------------------------------------------|
| `ClinicSettings`   | nome, bot name, horário, endereço, config de IA, RAG   |
| `PromptRegistry`   | prompts por agente (response_builder, guardrails, etc.) |
| `InsuranceCatalog` | convênios aceitos (injetados no contexto da IA)         |
| `ClinicSpecialty`  | especialidades ativas (sobrepõe lista hardcoded do FARO)|
| `.env`             | fallback quando banco não tem config                    |

**Ordem de precedência:** `db_registry > clinic_settings > .env > hardcoded default`

---

## 5. Reranker RAG (dois estágios)

```
query ──→ pgvector (top_k_initial=20) ──→ lexical boost
                                              ↓
                              [RAG_RERANKER_ENABLED=true]
                                              ↓
                              cross-encoder scoring (mMARCO multilíngue)
                                              ↓
                              top_k_final=5 ──→ LLM
```

**Modelo padrão:** `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`
- Multilíngue, treinado em mMARCO (PT-BR incluído)
- Ref: https://huggingface.co/cross-encoder/mmarco-mMiniLMv2-L12-H384-v1

**O reranker NÃO é chamado para:**
- `structured_data_lookup` (profissionais, convênios, endereço, telefone)
- `schedule_flow` (AGENDAR, CANCELAR, REMARCAR)
- bloqueios de guardrails
- handoff flows

---

## 6. Auth e RBAC

| Rota             | Proteção                                  |
|------------------|-------------------------------------------|
| `POST /auth/login` | pública (gera token)                    |
| `GET /auth/me`   | Bearer token obrigatório                  |
| `/admin/*`       | Bearer + role: admin ou manager           |
| `/crm/*`         | Bearer + role: qualquer autenticado       |
| `/patients/*`    | Bearer + qualquer autenticado             |
| `/professionals/*`| Bearer + qualquer autenticado            |
| `/telegram/webhook` | HMAC secret (sem JWT — chamado pelo Telegram) |

**Perfis:**
- `admin` — acesso total
- `manager` — gestão operacional, sem exclusão destrutiva
- `reception` — agendamento, pacientes, conversas
- `handoff_operator` — fila de handoff

---

## 7. O que é `src/inteliclinic/` hoje

| Componente            | Status                     | Plano                         |
|-----------------------|----------------------------|-------------------------------|
| `core/ai_engine/`     | Arquitetura LangGraph      | Substituir orchestrator.py    |
| `core/nlu/`           | Extrator Instructor        | Substituir FARO heurístico    |
| `core/rag/`           | Pipeline Qdrant/LlamaIndex | Upgrade do RAG pgvector       |
| `core/analytics/`     | Detecção de anomalias      | Monitoramento de qualidade    |
| `clinic/`             | Config por clínica         | Wiring com ClinicSettings     |

**Regra:** não importar de `src/inteliclinic/` no runtime `apps/api/`. Evoluir em camadas, migrar por módulo.

---

## 8. Módulos futuros — encaixe arquitetural

| Módulo             | Onde entra                              | Dependência         |
|--------------------|-----------------------------------------|---------------------|
| CRM / follow-up    | `CrmService` + `/api/v1/crm/*`          | ✅ Criado (básico)  |
| Google Calendar    | `integrations/google/calendar_client.py`| OAuth2 + env keys   |
| Jobs / worker      | `models/jobs.py` + ARQ ou asyncio       | ✅ Estrutura criada |
| Alertas            | `models/jobs.py` + `CrmService.alerts`  | ✅ Estrutura criada |
| IA cérebro interno | `src/inteliclinic/core/ai_engine/`      | LangGraph migration |
| WhatsApp           | `integrations/whatsapp/`                | Meta API keys       |
| Voz/telefonia      | `integrations/voice/` (LiveKit)         | Phase 2             |

---

## 9. Referências técnicas

- **LangGraph:** https://langchain-ai.github.io/langgraph/
- **LangSmith:** https://smith.langchain.com/
- **pgvector (Python):** https://github.com/pgvector/pgvector-python
- **Qdrant FastEmbed Rerankers:** https://qdrant.github.io/fastembed/examples/Reranking/
- **sentence-transformers CrossEncoder:** https://sbert.net/docs/cross_encoder/pretrained_models.html
- **mMARCO cross-encoder:** https://huggingface.co/cross-encoder/mmarco-mMiniLMv2-L12-H384-v1
- **Pinecone reranking (referência comparativa):** https://docs.pinecone.io/guides/inference/rerank
- **FastAPI security:** https://fastapi.tiangolo.com/tutorial/security/
