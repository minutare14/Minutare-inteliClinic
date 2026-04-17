# CLAUDE.md

## Objetivo

- Memoria viva tecnica do projeto IntelliClinic / Minutare Med.
- Registrar descobertas reais da auditoria com separacao clara entre `Evidencia`, `Inferencia` e `Plano`.
- Servir como referencia padrao para futuras varreduras tecnicas, refactors e onboarding.

## Historico de Alteracoes

### 2026-04-17 - Correcao do Bug de Auth + Admin via Env Vars

**Bug reportado:** Login com `emanoelmcedo@gmail.com` falhava com "E-mail ou senha incorretos".

**Causa raiz 1 (Dokploy):** `.env` no servidor VPS tinha `DOCKER_CONFIG=/root/.dockerADMIN_SYNC=true` — duas variaveis concatenadas na mesma linha sem separador. Pydantic_settings leu como uma unica variavel `DOCKER_CONFIG=/root/.dockerADMIN_SYNC=true`. `ADMIN_SYNC` nunca era definido.

**Causa raiz 2 (local):** `seed_default_admin()` usava SQLAlchemy ORM com `UserRole.admin.value` — PostgreSQL tentava converter para tipo enum `userrole` que nao existe na base, gerando `UndefinedObjectError`. Função была envolta em try/except silencioso que logava "FALHA" sem expor o erro real.

**Correcao 1 (VPS):** Adicionada linha separada `ADMIN_SYNC=true` no `.env` da VPS. Container recreation necessaria para Docker recolher a variavel.

**Correcao 2 (codigo):** `seed_default_admin()` reescrito com raw SQL via `text()` para ignorar o tipo enum. Logica: verifica se email configurado existe na DB → se admin, sincroniza senha; se diferente email e `ADMIN_SYNC=true`, deleta admin antigo e cria novo.

**Observacao:** `admin_sync` nao estava no container em execucao porque a imagem Docker была buildada ANTES da adicao do campo em `config.py`. O container so le `admin_sync` corretamente apos rebuild da imagem.

**Estado atual:**
- Login funciona: `emanoelmcedo@gmail.com` / `Asd142000`
- `ADMIN_SYNC=true` registrado no .env da VPS
- `seed_default_admin()` reescrito com raw SQL

**Arquivos alterados:**
- `apps/api/app/core/auth.py` — rewrite completo do seed com raw SQL
- `apps/api/app/core/config.py` — campo `admin_sync` adicionado

**Nota para deploy futuro:** Após mudar `ADMIN_DEFAULT_EMAIL` ou adicionar `ADMIN_SYNC=true` no .env, é necessário rebuild da imagem Docker para que o campo `admin_sync` funcione (pydantic_settings lê do binario, não do .env em runtime para campos novos).

### 2026-04-17 - Step 3 - Analise Real do AIAnytime/LangGraph-Agentic-RAG

**Fonte:** codigo lido diretamente de raw.githubusercontent.com — arquivos `nodes.py`, `edges.py`, `graph.py`, `retriever.py`, `main.py`.

**GraphState confirmado no codigo:**

- `Evidencia`: `GraphState` tem apenas `messages: Annotated[list, add_messages]` — um unico campo. Sem `question`, `documents`, `attempts`, `clinic_id`, `grade_score`. Estado circula serializado como lista de mensagens.

**Nodes confirmados:**

- `Evidencia`: `agent` — LLM com tools bound; decide se chama `retrieve_documents` via `tool_calls`
- `Evidencia`: `retrieve` — `ToolNode(tools)`; executa FAISS
- `Evidencia`: `rewrite` — LLM reescreve `messages[0].content` (primeira mensagem hardcoded)
- `Evidencia`: `generate` — LLM gera resposta; extrai contexto por `if "Document" in msg.content` (string matching fragil)
- `Evidencia`: `grade_documents` NAO e um node — e uma funcao de edge condicional

**Edges confirmadas:**

- `Evidencia`: `route_after_agent` — se `last_message.tool_calls` existe → `retrieve`; senao → `END`
- `Evidencia`: `grade_documents` — LLM com `structured_output(GradeDocuments)` avalia `last_message.content[:500]`; retorna `binary_score: "yes"/"no"`; "yes" → `generate`, "no" → `rewrite`
- `Evidencia`: `rewrite → agent` — edge fixa, sem limite de tentativas; loop potencialmente infinito confirmado

**Problemas confirmados no codigo:**

- `Evidencia`: sem `max_retries` em nenhum arquivo — loop `rewrite → agent → retrieve → grade → rewrite` e infinito
- `Evidencia`: grading avalia truncamento de 500 chars da ultima mensagem — nao por chunk individual
- `Evidencia`: contexto extraido por `if "Document" in msg.content` — se string nao bater, `context = ""` e LLM gera sem contexto
- `Evidencia`: retrieval nao e garantido — depende do LLM agent decidir usar a ferramenta
- `Evidencia`: FAISS in-memory, URLs hardcoded em `main.py` (lilianweng.github.io)
- `Evidencia`: observabilidade via `print()` com emojis — sem logger, sem trace estruturado

**O que vale absorver (padrao, nao codigo):**

- `Evidencia`: separacao `nodes.py / edges.py / graph.py` e arquiteturalmente correta
- `Evidencia`: grading como gate condicional antes de gerar e o padrao correto
- `Evidencia`: `GradeDocuments(BaseModel)` com `binary_score` e `reasoning` via `with_structured_output` e pratica valida

**O que NAO sera aproveitado:**

- `Evidencia`: FAISS — pgvector permanece
- `Evidencia`: state como lista de mensagens — IntelliClinic usa `DocumentGraphState` com 30+ campos tipados
- `Evidencia`: retrieval via decisao do LLM — IntelliClinic chama retrieval deterministicamente
- `Evidencia`: ausencia de retry limit — IntelliClinic tem `RAG_QUERY_REWRITE_MAX_RETRIES`
- `Evidencia`: grading em string truncada — IntelliClinic grada por chunk com score numerico heuristico

**Impacto arquitetural no IntelliClinic:**

- `Evidencia`: todos os padroes validos do repo ja estao implementados em `document_runtime_graph.py` com qualidade superior
- `Inferencia`: o repo confirma que o padrao de grafo com grading condicional e a direcao certa — nao e overengineering
- `Evidencia`: o IntelliClinic supera o repo em: estado tipado, retry controlado, grading heuristico, retrieval deterministico, audit log, governanca por clinica, structured lookup prioritario

### 2026-04-17 - Step 2 - Fechamento do Pipeline LangGraph + LangSmith + Composer

**O que foi concluido neste step:**

- `Evidencia`: `orchestrator.py` agora passa `prompt_source` e `clinic_cfg` para `ResponseComposer.compose()`, corrigindo lacuna que deixava esses parametros sem efeito no grafo documental.
- `Evidencia`: `orchestrator.py` propaga todos os campos LangGraph do `ComposedResponse` para `ConversationState` — `langgraph_used`, `document_grading_*`, `query_rewrite_*`, `retrieval_attempts`, `initial_candidate_count`, `final_candidate_count`, `selected_chunks`, `composer_audit_payload`.
- `Evidencia`: `orchestrator._audit()` agora inclui todos os campos do pipeline documental no log estruturado persistido — antes somente reranker era logado; agora o trace completo do grafo vai para `audit_events`.
- `Evidencia`: `llm_client.call_llm()` agora wrapping com `trace_step("llm_call", run_type="llm")` — todo chamado LLM fica visivel no LangSmith quando `LANGSMITH_TRACING=true` e `LANGSMITH_API_KEY` configurada, sem quebrar o runtime quando nao configurada.
- `Evidencia`: todos os 5 arquivos modificados validados com `ast.parse()` sem erros de sintaxe.

**Runtime do pipeline documental (fechado):**

1. `load_runtime_context` — carrega prompts do PromptRegistry ou defaults
2. `decision_router` — roteia por intent
3. `structured_data_lookup` / `schedule_flow` / `handoff_flow` / `clarification_flow` — fluxos diretos
4. `rag_retrieval` — busca vetorial ou textual via pgvector
5. `document_grading` — heuristico + opcional LLM (se prompt ativo no PromptRegistry)
6. `query_rewrite` / `retry_retrieval` — rewrite deterministico + opcional LLM, ate max_retries
7. `reranker` — cross-encoder multilingual (lazy, noop se desabilitado)
8. `response_composer` — gera resposta final via LLM ou template
9. `persist_and_audit` — payload completo logado estruturado

**Tracing LangSmith (funcionando quando env presente):**

- `trace_step` usado em todos os nodes do grafo documental
- `call_llm` instrumentado com span `llm_call` (provider, latencia, tamanho da resposta)
- Fallback silencioso quando LangSmith nao esta configurado — runtime saudavel sem env

**Impacto no deploy:**

- `Evidencia`: sem alteracao no caminho critico do boot — lazy load de embeddings preservado
- `Evidencia`: `LANGSMITH_TRACING=false` por padrao — nao afeta deploy sem configuracao LangSmith
- `Evidencia`: `LANGGRAPH_RUNTIME_ENABLED=true` por padrao — grafo ativo; fallback linear disponivel se LangGraph nao instalado

**Pendencias:**

- `Plano`: validar boot real do compose assim que houver engine Docker acessivel
- `Plano`: testes unitarios para `document_runtime_graph.py` e `response_composer.py`

### 2026-04-17 - Step 4 - Correcao do Unhealthy de Deploy (lifespan timeout)

**Causa raiz identificada por auditoria de codigo (evidencia):**

- `Evidencia`: `apps/api/app/main.py` lifespan executava `admin_svc.get_clinic_settings()` e `seed_default_admin()` sem nenhum timeout — se a conexao com o banco fosse lenta no boot, o `yield` nunca chegava, o uvicorn nunca recebia conexoes, e o healthcheck sempre falhava.
- `Evidencia`: `docker-compose.yml` usava `start_period: 150s` e `curl -sf` sem `--max-time` — curl podia bloquear ate o timeout do OS (padrão ilimitado), consumindo toda a janela de start_period com uma unica verificacao travada.
- `Evidencia`: `Dockerfile HEALTHCHECK` usava `start_period=120s` — abaixo dos 150s do compose e muito abaixo do tempo real de boot (Python heavy packages + DB seed).
- `Inferencia`: soma de `sentence-transformers` + `langgraph` + `langchain-core` + `langsmith` na importacao (~10-30s em VPS fria) + webhook Telegram (~30s) + seed DB sem timeout = ultrapassagem sistematica da janela de health.

**O que foi corrigido neste step:**

- `Evidencia`: `apps/api/app/main.py`: ambas as operacoes DB agora usam `asyncio.wait_for(..., timeout=15.0)`. `asyncio.TimeoutError` capturado com log de erro; boot nao e mais bloqueado indefinidamente.
- `Evidencia`: timing logs adicionados ao lifespan — `_time.monotonic()` marca inicio total, inicio de cada operacao DB, e log final mostra tempo total de startup em segundos.
- `Evidencia`: `docker-compose.yml`: `start_period` aumentado de `150s` para `300s`; `curl --max-time 8` adicionado ao comando healthcheck.
- `Evidencia`: `apps/api/Dockerfile`: `HEALTHCHECK start_period` aumentado de `120s` para `300s`; `--max-time 8` adicionado ao curl; `timeout` do HEALTHCHECK aumentado de `5s` para `10s`.

**Garantias pos-correcao:**

- `Evidencia`: lifespan nao bloqueia mais de 30s total nas operacoes DB (2x 15s timeout).
- `Evidencia`: curl do healthcheck tem limite de 8s por verificacao — nao consome janela inteira em uma verificacao travada.
- `Evidencia`: `start_period: 300s` absorve boot pesado de VPS fria + imports Python + seed + webhook.
- `Inferencia`: risco de unhealthy por boot lento reduzido drasticamente sem alterar comportamento funcional da API.

**Commit:** `fix(deploy): guard lifespan DB ops with timeout + raise start_period to 300s`

### 2026-04-17 - Step 1 - Estabilizacao do Bootstrap de Deploy

**Deploy / causa raiz (evidencia):**

- `Evidencia`: `apps/api/entrypoint.sh` rodava `alembic -> seed_data.py -> register_telegram_webhook.py -> uvicorn` antes de expor HTTP.
- `Evidencia`: `scripts/seed_data.py` chamava `RagService.ingest_document()` no startup.
- `Evidencia`: `RagService.ingest_document()` tentava gerar embeddings no ingest; com `EMBEDDING_PROVIDER=local`, isso entra no caminho de `sentence-transformers` e carrega modelo local antes da API responder.
- `Inferencia`: o container podia ficar `unhealthy` mesmo com `/health` leve porque o processo demorava para chegar ao `uvicorn`, deixando o healthcheck sem endpoint HTTP ativo dentro da janela do compose.

**O que foi feito neste step:**

- `Evidencia`: `apps/api/entrypoint.sh` reescrito para bootstrap limpo com logs por etapa, sem `set -x`, com tempos medidos e seed/webhook opcionais por env.
- `Evidencia`: adicionadas flags reais de startup em `apps/api/app/core/config.py`:
  - `BOOTSTRAP_SEED_ON_STARTUP`
  - `BOOTSTRAP_SEED_WITH_EMBEDDINGS`
  - `BOOTSTRAP_REGISTER_TELEGRAM_WEBHOOK_ON_STARTUP`
- `Evidencia`: `scripts/seed_data.py` agora aceita `--skip-embeddings`.
- `Evidencia`: `RagService.ingest_document()` agora aceita `skip_embeddings=True`, permitindo seed documental sem carregar modelo local no boot.
- `Evidencia`: adicionados endpoints `/health/live` e `/health/ready` em `apps/api/app/api/routes/health.py`.
- `Evidencia`: `docker-compose.yml` passou a usar `/health/live`, `timeout` maior e `start_period` maior, com defaults seguros para bootstrap.
- `Evidencia`: `apps/api/Dockerfile` passou a instalar `torch` via indice CPU-only antes de `sentence-transformers`, reduzindo risco de stack CUDA desnecessaria no deploy Linux.
- `Evidencia`: `docker compose config` executado com sucesso apos as mudancas, validando sintaxe do compose com as novas envs/defaults.

**Runtime real / impacto:**

- `Evidencia`: o boot critico da API deixa de depender de seed com embeddings por default.
- `Evidencia`: o healthcheck passa a medir liveness HTTP real, separado de readiness com banco.
- `Inferencia`: isso reduz risco de timeout de startup, modelo carregado cedo demais e falha em VPS comum.

**Decisao arquitetural:**

- `Evidencia`: embeddings e reranker continuam lazy/on-demand; nao entram mais no caminho critico do deploy.
- `Evidencia`: seed de demo passa a ser comportamento opt-in, nao requisito implicito do boot.

**Riscos / limitacoes / pendencias:**

- `Evidencia`: sem daemon Docker local ativo nesta thread, ainda nao foi possivel executar `docker compose up -d --build` e observar container health em runtime real local.
- `Plano`: validar boot real do compose assim que houver engine Docker acessivel ou no proximo ambiente de deploy.
- `Plano`: integrar LangGraph real ao fluxo documental/roteamento, com LangSmith, grading, rewrite e retry controlado.

**Impacto em atendimento / RAG / LangGraph / LangSmith:**

- `Evidencia`: seed documental pode existir sem embeddings iniciais; o runtime preserva fallback textual do RAG.
- `Inferencia`: isso melhora deploy sem remover a possibilidade de reindex posterior ou reranker lazy.
- `Plano`: proximos steps vao ligar esse runtime a um subgrafo LangGraph real com observabilidade LangSmith.

### 2026-04-15 — Integridade Operacional & Visualização de Pipeline (Stage 8 & 9)

**Integridade Operacional & Reconciliação (Stage 8):**

- `Evidencia`: `ReconciliationService` implementado para lidar com desativação de profissionais.
- `Evidencia`: `ScheduleRepository` agora possui `find_future_booked_by_professional` e `cancel_slot`.
- `Evidencia`: `ConversationRepository` possui `find_active_with_pending_action` para limpar estados órfãos.
- `Evidencia`: `AIOrchestrator` agora valida integridade em tempo real (check de profissional ativo) e dispara fluxos de contingência.
- `Evidencia`: `IntentRouter` corrigido para não forçar agendamento em perguntas informativas sobre especialidades.
- `Evidencia`: Rota `DELETE /professionals/{id}` integrada ao `ReconciliationService` para automação total.

**Visualização de Pipeline / IA Trace (Stage 9):**

- `Evidencia`: `AuditRepository.list_by_resource` implementado para filtragem de logs por conversa.
- `Evidencia`: Rota `GET /api/v1/audit/pipeline/{id}` reconstrói o rastro da IA a partir dos eventos `pipeline.completed`.
- `Evidencia`: Componente `PipelineViewer` (Frontend) criado para exibir fluxo de Intenção -> Faro -> Guardrails -> Ferramentas.
- `Evidencia`: Integração no `ConversationDetail` com toggle "Ver IA Trace" para depuração administrativa.

### 2026-04-13 — Correcoes de bugs + infraestrutura de deploy

**Bugs corrigidos (evidencias confirmadas na auditoria anterior):**

- `Evidencia`: `AIOrchestrator._handle_pending_action` nao tratava `select_slot_to_cancel` — **CORRIGIDO**: adicionado `_handle_slot_to_cancel_selection` em `orchestrator.py`. O metodo trata selecao numerica, desistencia e erro de indice.
- `Evidencia`: `select_slot_to_cancel` nao persistia textos de exibicao dos slots — **CORRIGIDO**: `slot_displays` adicionado ao dict do pending action em `orchestrator.py`.
- `Evidencia`: remarcacao passava `entities.get("date")` para old_date e new_date ao mesmo tempo — **CORRIGIDO**: `intent_router.py` agora extrai duas datas separadas (`date` e `new_date`) via `re.finditer`; orchestrator usa `entities.get("new_date", entities.get("date"))`.
- `Evidencia`: `POST /api/v1/telegram/set-webhook` esperava `url` via query param mas frontend enviava JSON body — **CORRIGIDO**: rota aceita JSON body com `SetWebhookRequest(url: str | None)` em `telegram.py`.
- `Evidencia`: `GET /api/v1/telegram/webhook-info` retornava `{"info": {...}}` mas frontend esperava objeto plano — **CORRIGIDO**: rota agora retorna o dict de info diretamente em `telegram.py`.
- `Evidencia`: `RagQueryResult` nao retornava `document_id` nem `title` — **CORRIGIDO**: `rag_repository.py` inclui `d.id AS document_id` nas queries SQL; `rag.py` (schemas) adiciona campos `document_id: uuid.UUID` e `title: str`; `rag_service.py` mapeia os campos na construcao do schema.

**Infraestrutura de deploy adicionada:**

- `Evidencia`: `docker-compose.yml` corrigido — healthcheck do Qdrant trocado de `grep 'ok'` (nunca batia) para `wget --spider` (HTTP 200); depends_on do servico `api` sobre `qdrant` trocado de `service_healthy` para `service_started` (Qdrant nao e usado no runtime MVP).
- `Evidencia`: `.env.vps.example` criado na raiz — cobre todas as variaveis do projeto agrupadas por secao com placeholders claros.
- `Evidencia`: `docs/deployment/ENV_REFERENCE.md` criado — referencia completa de cada variavel (nome, onde e usada, obrigatoriedade, impacto, scope LOCAL/VPS/BUILD).
- `Evidencia`: `docs/deployment/VPS_DEPLOY_CHECKLIST.md` criado — checklist passo a passo cobrindo DNS, portas, volumes, TLS, webhook Telegram, RAG, healthchecks e procedimento de atualizacao.
- `Evidencia`: `.gitignore` atualizado para permitir `.env.vps.example` via excecao `!.env.vps.example`.

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
- `Evidencia`: pipeline de cancelamento via `AIOrchestrator` + `ScheduleActions` — selecao de slot em cancelamento multi-consulta CORRIGIDO em 2026-04-13.
- `Evidencia`: pipeline de remarcacao via `AIOrchestrator` + `ScheduleActions` — separacao de datas CORRIGIDA em 2026-04-13.
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

### Abertos (ainda nao corrigidos)

- `Evidencia`: o projeto nao tem autenticacao nem RBAC no runtime atual.
- `Evidencia`: nao existe `clinic_id` ou `tenant_id` nas tabelas operacionais principais (`patients`, `professionals`, `schedule_slots`, `conversations`, `rag_documents`).
- `Evidencia`: prompts, seeds, nome da aplicacao e branding estao hardcoded em "Minutare Med" no backend, frontend e scripts.
- `Evidencia`: `src/inteliclinic/core/rag/ingestion/pipelines/ingest_pipeline.py` ainda nao faz embed nem upsert no store; ha TODO explicito.
- `Evidencia`: o seed de dados e executado no startup da API e injeta conhecimento e profissionais da propria Minutare Med.

### Corrigidos em 2026-04-13

- ~~`POST /api/v1/telegram/set-webhook` espera `url` em query param, mas frontend envia JSON body~~ — CORRIGIDO: rota aceita JSON body.
- ~~`GET /api/v1/telegram/webhook-info` retorna `{"info": ...}`, mas frontend espera objeto plano~~ — CORRIGIDO: retorna objeto direto.
- ~~`RagQueryResult` nao retorna `document_id` nem `title`~~ — CORRIGIDO: campos adicionados em repository, schema e service.
- ~~`AIOrchestrator` salva `select_slot_to_cancel` mas nao trata esse tipo~~ — CORRIGIDO: `_handle_slot_to_cancel_selection` implementado.
- ~~Remarcacao usa `entities.get("date")` para data antiga e nova~~ — CORRIGIDO: intent router extrai `new_date` separado; orchestrator usa `new_date`.

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

- `Evidencia`: cancelamento multi-turn com mais de uma consulta — fluxo de selecao de slot CORRIGIDO em 2026-04-13; confirmacao de cancelamento ja existia.
- `Evidencia`: remarcacao — separacao de datas CORRIGIDA em 2026-04-13; fluxo completo funcional para casos simples.
- `Evidencia`: multi-clinic via `ClinicSettings` e `ClinicPrompts`, mas sem wiring no runtime.
- `Evidencia`: arquitetura LangGraph montada, mas fora do caminho principal da API.
- `Evidencia`: retriever hibrido, mas com componente sparse placeholder.

## O que esta so em plano

- `Plano`: GraphRAG.
- `Plano`: Google Calendar / Gogle integrations.
- `Plano`: WhatsApp e voz/LiveKit.
- `Plano`: RBAC/JWT.
- `Plano`: follow-up, CRM e leads.
- `Plano`: pipeline de onboarding completo por clinica usando `CLINIC_*`.

## Duvidas em Aberto

- `Inferencia`: pode existir algum deploy externo usando `src/inteliclinic/` diretamente, mas isso nao aparece neste repositorio.
- `Inferencia`: pode haver uma camada de auth externa ao frontend, mas nao existe evidencia no codigo local.
- `Inferencia`: o uso de Qdrant em algum ambiente manual e possivel, mas nao esta refletido no runtime principal do repositorio.

## Infraestrutura de Deploy

### docker-compose.yml (raiz)

- `Evidencia`: compose de producao cobre 4 servicos: `db` (PostgreSQL 16+pgvector), `qdrant`, `api` (FastAPI), `frontend` (Next.js standalone).
- `Evidencia`: servicos `api` e `frontend` expoe via labels Traefik — nao ha ports diretos; proxy gerenciado pelo Dokploy.
- `Evidencia`: Qdrant usa healthcheck via `wget --spider /healthz` (HTTP 200). Dependencia do api sobre qdrant e `service_started`, nao `service_healthy` (Qdrant nao e usado no runtime MVP).
- `Evidencia`: `NEXT_PUBLIC_API_URL` e variavel de BUILD — precisa estar no `.env` antes de `docker compose build`.
- `Evidencia`: `COMPOSE_PROJECT_NAME` controla os nomes dos containers e routers Traefik — dois deploys com o mesmo nome causam conflito no proxy.
- `Inferencia`: o compose atual e adequado para deploy Dokploy single-tenant. Nao possui suporte a multi-replica ou load balancing.

### Arquivos de ambiente

- `Evidencia`: `.env.example` — modelo para ambiente local.
- `Evidencia`: `.env.vps.example` — modelo para VPS/producao; criado em 2026-04-13 com todas as variaveis agrupadas por secao.
- `Evidencia`: `infra/docker/.env.example` — modelo especifico para o compose de desenvolvimento local (`infra/docker/docker-compose.yml`).

### Documentacao de deploy

- `Evidencia`: `docs/deployment/dedicated-deploy.md` — guia de deploy dedicado por clinica.
- `Evidencia`: `docs/deployment/ENV_REFERENCE.md` — referencia completa de cada variavel (criado em 2026-04-13).
- `Evidencia`: `docs/deployment/VPS_DEPLOY_CHECKLIST.md` — checklist passo a passo para Dokploy (criado em 2026-04-13).

### Variaveis obrigatorias na VPS

```
COMPOSE_PROJECT_NAME, FRONTEND_DOMAIN, API_DOMAIN
POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB
APP_ENV=production, APP_SECRET_KEY, CORS_ORIGINS
NEXT_PUBLIC_API_URL  <- antes do build
OPENAI_API_KEY (ou outro LLM)
TELEGRAM_BOT_TOKEN, TELEGRAM_WEBHOOK_URL, TELEGRAM_WEBHOOK_SECRET
CLINIC_ID, CLINIC_NAME
```

### Variaveis injetadas automaticamente pelo compose (nao definir manualmente)

- `DATABASE_URL` -> `postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}`
- `QDRANT_URL` -> `http://qdrant:6333`

## Recomendacoes Futuras

- Extrair `clinic_id` para todas as entidades operacionais relevantes e filtrar tudo por tenant.
- Trocar todos os hardcodes de Minutare Med por configuracao de clinica ou branding injetado.
- Unificar o caminho principal de IA: ou promover `src/inteliclinic` para runtime real, ou simplificar docs/arquitetura para o que realmente roda.
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
- `docs/deployment/ENV_REFERENCE.md`
- `docs/deployment/VPS_DEPLOY_CHECKLIST.md`
