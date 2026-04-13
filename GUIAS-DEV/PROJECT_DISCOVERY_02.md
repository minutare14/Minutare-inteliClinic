# PROJECT_DISCOVERY_02

> **Ultima atualizacao:** 2026-04-13
> Bugs corrigidos desde a discovery original: cancelamento multi-turn, remarcacao de datas, contrato Telegram (set-webhook + webhook-info), RAG (document_id + title).
> Deploy documentado: `.env.vps.example`, `docs/deployment/ENV_REFERENCE.md`, `docs/deployment/VPS_DEPLOY_CHECKLIST.md`.

## Escopo e metodo
- Escopo desta rodada:
  - pipelines
  - rotas
  - configuracoes de IA
  - prompts
  - core de adaptacao para novas clinicas
  - RAG
- Codigo inspecionado:
  - runtime backend em `apps/api/app/`
  - frontend em `frontend/src/`
  - arquitetura paralela em `src/inteliclinic/`
  - scripts em `scripts/`
  - docs e configs em `docs/` e `config/`
- Legenda usada no documento:
  - `Existe no codigo`: implementado e localizado.
  - `Parcial`: existe, mas com buracos de wiring, bugs, placeholders ou cobertura incompleta.
  - `Plano`: aparece em docs/stubs/arquitetura, sem fluxo operacional fechado.

## Snapshot tecnico
- Runtime real hoje:
  - backend: `apps/api/app/`
  - frontend: `frontend/src/`
  - integracao operacional real: Telegram
  - IA operacional real: `AIOrchestrator` + `FaroIntentRouter` + `response_builder`
  - base de conhecimento real: PostgreSQL + pgvector em `rag_documents` / `rag_chunks`
- Arquitetura paralela:
  - `src/inteliclinic/` contem uma plataforma mais ampla com LangGraph, Instructor, Qdrant, LlamaIndex, analytics e avaliacao.
  - Essa camada nao e o caminho principal da API hoje.
- Conclusao estrutural:
  - o repositorio mistura um MVP funcional com uma arquitetura-alvo mais avancada.
  - toda a analise abaixo separa claramente o que ja roda do que ainda esta so desenhado.

---

## 1. Pipelines do projeto

## Visao consolidada

| Pipeline | Status | Onde mora | Observacao curta |
| --- | --- | --- | --- |
| Bootstrap da API | Funcional | `apps/api/entrypoint.sh` | sobe DB, migra, seeda, sobe Uvicorn |
| Atendimento Telegram inbound | Funcional | `apps/api/app/integrations/telegram/webhook_handler.py` | pipeline operacional principal |
| Identificacao / upsert de paciente | Funcional | `PatientService` | cria/recupera paciente por Telegram |
| Memoria de conversa | Funcional simples | `context_manager.py` + DB | perfil + ultimas 6 mensagens |
| Roteamento de intencao FARO | Funcional | `intent_router.py` | heuristico, sem LLM |
| Guardrails + handoff | Funcional | `guardrails.py`, `orchestrator.py` | bloqueio, consentimento, urgencia |
| Agendamento multi-turn | Funcional com limites | `orchestrator.py`, `actions.py` | funciona, mas depende de heuristicas |
| Cancelamento multi-turn | Funcional | `orchestrator.py`, `actions.py` | **CORRIGIDO 2026-04-13**: `_handle_slot_to_cancel_selection` implementado; selecao numerica e desistencia funcionam |
| Remarcacao | Funcional | `orchestrator.py`, `actions.py`, `intent_router.py` | **CORRIGIDO 2026-04-13**: `new_date` extraido separadamente; nao confunde data antiga com nova |
| RAG ingest via API | Funcional limitado | `rag.py`, `rag_service.py` | so texto; sem tenant |
| RAG query runtime | Funcional limitado | `rag_service.py`, `rag_repository.py` | pgvector + fallback textual |
| Ingestao de docs via script | Funcional limitado | `scripts/ingest_docs.py` | usa markdown local, sem embeddings no modo DB |
| Seed operacional | Funcional mas acoplado | `scripts/seed_data.py` | injeta dados Minutare Med |
| Auditoria / observabilidade | Funcional minima | `audit_service.py`, `GET /audit` | sem tracing/metrics |
| Dashboard / relatorios | Funcional minima | `dashboard.py` | agregado de contagens |
| CRUD operacional | Funcional | rotas backend + frontend | pacientes, profissionais, agenda |
| Configuracao de webhook Telegram | Funcional | `telegram.py` + `frontend/src/lib/api.ts` | **CORRIGIDO 2026-04-13**: set-webhook aceita JSON body; webhook-info retorna objeto plano |
| LangGraph clinic graph | Parcial / fora do runtime | `src/inteliclinic/core/ai_engine/*` | grafo existe, sem wiring com API |
| Extraction pipeline com Instructor | Parcial / fora do runtime | `src/inteliclinic/core/nlu/*` | NLU robusta, nao usada pelo MVP |
| RAG Qdrant/LlamaIndex | Parcial | `src/inteliclinic/core/rag/*` | query existe melhor que ingestao |
| Glosa / anomaly | Parcial | `src/inteliclinic/core/analytics/*` | existe como modulo, nao como operacao real |
| RAG evaluation | Funcional dev-only | `scripts/evaluate_rag.py` | nao e pipeline do produto final |
| Auth | Inexistente / prevista | docs apenas | sem JWT, sem sessao, sem login |
| CRM / leads / follow-up / alertas / Google | Inexistente / previstos | docs, placeholders | sem fluxo operacional real |

### P01. Bootstrap da API
- Nome: bootstrap da API
- Objetivo: subir o backend com schema pronto e base minima carregada.
- Onde esta:
  - `apps/api/entrypoint.sh`
  - `scripts/seed_data.py`
- Como funciona:
  1. valida `DATABASE_URL`
  2. testa conectividade com banco
  3. executa `alembic upgrade head`
  4. executa `python scripts/seed_data.py --mode db`
  5. sobe `uvicorn app.main:app`
- Entradas:
  - `DATABASE_URL`
  - `APP_ENV`
  - `APP_LOG_LEVEL`
  - `UVICORN_WORKERS`
- Saidas:
  - schema aplicado
  - dados iniciais criados ou reaproveitados
  - API no ar
- Dependencias:
  - banco
  - Alembic
  - models SQLModel
  - `scripts/seed_data.py`
- Status: `Existe no codigo`
- Modulos tocados:
  - migrations
  - models de paciente, profissional, agenda, RAG
- Gargalos, falhas ou riscos:
  - seed roda em todo startup
  - seed e fortemente hardcoded em Minutare Med
  - mistura preocupacao de bootstrap com dados de primeira clinica

### P02. Atendimento Telegram inbound
- Nome: pipeline de atendimento Telegram inbound
- Objetivo: receber mensagem do paciente e devolver resposta automatica.
- Onde esta:
  - `apps/api/app/api/routes/telegram.py`
  - `apps/api/app/integrations/telegram/webhook_handler.py`
  - `apps/api/app/integrations/telegram/client.py`
- Como funciona:
  1. `POST /api/v1/telegram/webhook` recebe update
  2. valida secret do webhook se header estiver presente
  3. normaliza payload em `TelegramUpdate`
  4. ignora update sem texto
  5. localiza ou cria paciente por `telegram_user_id`
  6. localiza ou cria conversa ativa
  7. grava mensagem inbound
  8. chama `AIOrchestrator.process_message(...)`
  9. envia texto resultante via Telegram
  10. grava mensagem outbound
  11. grava evento de auditoria
- Entradas:
  - payload Telegram
  - header `x-telegram-bot-api-secret-token` opcional
- Saidas:
  - mensagem outbound ao paciente
  - conversa atualizada
  - trilha de auditoria
- Dependencias:
  - `PatientService`
  - `ConversationService`
  - `AIOrchestrator`
  - `AuditService`
  - Telegram Bot API
- Status: `Existe no codigo`
- Modulos tocados:
  - pacientes
  - conversas
  - IA
  - auditoria
  - integracao Telegram
- Gargalos, falhas ou riscos:
  - se nao houver secret configurado, o endpoint aceita chamadas sem verificacao real
  - canal unico; nao existe camada multicanal abstrata pronta no runtime

### P03. Identificacao / upsert de paciente
- Nome: pipeline de identificacao de paciente por Telegram
- Objetivo: associar mensagem ao paciente persistido.
- Onde esta:
  - `apps/api/app/services/patient_service.py`
  - chamado por `webhook_handler.py`
- Como funciona:
  1. recebe `telegram_user_id`, `telegram_chat_id`, `first_name`
  2. procura paciente por Telegram
  3. se nao existir, cria um novo paciente com canal preferido `telegram`
  4. persiste e devolve objeto `Patient`
- Entradas:
  - ids do Telegram
  - nome exibido no Telegram
- Saidas:
  - registro de paciente
- Dependencias:
  - tabela `patients`
- Status: `Existe no codigo`
- Modulos tocados:
  - pacientes
  - conversa subsequente
- Gargalos, falhas ou riscos:
  - nao ha `clinic_id`
  - identificacao depende do Telegram, nao de tenant
  - nao ha resolucao de duplicidade entre canais

### P04. Memoria / contexto conversacional
- Nome: pipeline de memoria curta + perfil persistente
- Objetivo: montar o contexto entregue ao gerador de resposta.
- Onde esta:
  - `apps/api/app/ai_engine/context_manager.py`
- Como funciona:
  1. carrega paciente
  2. carrega conversa
  3. busca mensagens da conversa
  4. corta para `MAX_HISTORY_MESSAGES = 6`
  5. monta `ConversationContext` com perfil, historico recente e FARO
- Entradas:
  - `Patient`
  - `Conversation`
  - FARO brief opcional
- Saidas:
  - `ConversationContext`
- Dependencias:
  - `ConversationRepository`
  - tabelas `patients`, `messages`, `conversations`
- Status: `Existe no codigo`
- Modulos tocados:
  - IA
  - conversa
  - paciente
- Gargalos, falhas ou riscos:
  - nao existe memoria longa semantica por paciente
  - nao ha sumarizacao de historico
  - dados persistentes e sensiveis entram direto no prompt
  - nao ha segregacao por clinica

### P05. Roteamento de intencao + guardrails + resposta
- Nome: pipeline central do `AIOrchestrator`
- Objetivo: transformar a mensagem em acao real, consulta de conhecimento ou resposta.
- Onde esta:
  - `apps/api/app/ai_engine/orchestrator.py`
  - `apps/api/app/ai_engine/intent_router.py`
  - `apps/api/app/ai_engine/guardrails.py`
  - `apps/api/app/ai_engine/response_builder.py`
- Como funciona:
  1. carrega `pending_action` se houver
  2. se existir, tenta resolver multi-turn
  3. roda `intent_router.analyze(user_text)`
  4. salva `conversation.current_intent` e `confidence_score`
  5. monta contexto via `ContextManager`
  6. aplica guardrails de entrada
  7. tenta executar `ScheduleActions` se a intencao for operacional
  8. se for pergunta operacional/politicas, tenta RAG
  9. gera resposta via LLM ou templates
  10. aplica guardrails de saida
  11. cria handoff se necessario
- Entradas:
  - paciente
  - conversa
  - texto do usuario
- Saidas:
  - `EngineResponse`
- Dependencias:
  - FARO router
  - guardrails
  - context manager
  - schedule actions
  - RAG
  - LLM client
- Status: `Existe no codigo`
- Modulos tocados:
  - IA
  - agenda
  - handoff
  - RAG
  - conversa
- Gargalos, falhas ou riscos:
  - orquestrador concentra muitas responsabilidades
  - regra de baixa confianca usa `rag_confidence_threshold`, misturando RAG e handoff
  - nao ha configuracao por agente
  - comportamento fortemente acoplado ao dominio de atendimento administrativo

### P06. Agendamento multi-turn
- Nome: pipeline de agendamento
- Objetivo: buscar slots e reservar horario com confirmacao do paciente.
- Onde esta:
  - `apps/api/app/ai_engine/orchestrator.py`
  - `apps/api/app/ai_engine/actions.py`
- Como funciona:
  1. FARO tenta identificar medico, data e horario
  2. `ScheduleActions.search_slots(...)` procura profissionais e slots
  3. se houver slots, grava `pending_action = {"type": "select_slot", ...}`
  4. paciente responde com numero
  5. `_handle_slot_selection` faz `book_slot`
  6. limpa estado pendente
- Entradas:
  - nome do medico ou data
  - opcionalmente horario
- Saidas:
  - slot reservado
  - mensagem de confirmacao
- Dependencias:
  - `ProfessionalRepository`
  - `ScheduleRepository`
  - `Conversation.pending_action`
- Status: `Existe no codigo`
- Modulos tocados:
  - agenda
  - profissionais
  - conversa
  - IA
- Gargalos, falhas ou riscos:
  - busca por especialidade nao e plenamente explorada no ramo principal do orquestrador
  - confirmacao depende de extracao heuristica do numero
  - sem tenant/clinica, o inventario de agenda e global

### P07. Cancelamento multi-turn
- Nome: pipeline de cancelamento
- Objetivo: localizar consulta e confirmar cancelamento.
- Onde esta:
  - `apps/api/app/ai_engine/orchestrator.py`
  - `apps/api/app/ai_engine/actions.py`
- Como funciona:
  1. lista consultas do paciente
  2. se houver uma, grava `pending_action = {"type": "confirm_cancel", ...}`
  3. se houver varias, grava `pending_action = {"type": "select_slot_to_cancel", ...}`
  4. espera resposta do paciente
  5. no caso simples, `_handle_cancel_confirmation` cancela
- Entradas:
  - paciente
  - data opcional
- Saidas:
  - slot cancelado ou mensagem de confirmacao
- Dependencias:
  - `ScheduleActions.list_patient_appointments`
  - `ScheduleActions.cancel_slot`
- Status: `Parcial`
- Modulos tocados:
  - agenda
  - conversa
  - IA
- Gargalos, falhas ou riscos:
  - `_handle_pending_action` nao trata `select_slot_to_cancel`
  - logo, o caso de varias consultas fica quebrado no runtime

### P08. Remarcacao
- Nome: pipeline de remarcacao
- Objetivo: realocar consulta existente.
- Onde esta:
  - `apps/api/app/ai_engine/orchestrator.py`
  - `apps/api/app/ai_engine/actions.py`
- Como funciona:
  1. FARO classifica como `REMARCAR`
  2. `orchestrator` chama `reschedule_slot`
  3. usa `entities.get("date")` como data antiga e nova
  4. se encontrar opcoes, cai novamente no fluxo `select_slot`
- Entradas:
  - data mencionada
- Saidas:
  - slots sugeridos ou mensagem
- Dependencias:
  - `ScheduleActions.reschedule_slot`
- Status: `Parcial`
- Modulos tocados:
  - agenda
  - conversa
  - IA
- Gargalos, falhas ou riscos:
  - nao existe extracao explicita de `old_date` vs `new_date`
  - comportamento real fica subespecificado

### P09. Handoff humano
- Nome: pipeline de handoff
- Objetivo: transferir conversa para humano quando IA nao deve ou nao consegue continuar.
- Onde esta:
  - `apps/api/app/ai_engine/orchestrator.py`
  - `apps/api/app/services/handoff_service.py`
  - `apps/api/app/repositories/conversation_repository.py`
- Como funciona:
  1. guardrails podem forcar handoff por sem consentimento, baixa confianca, urgencia ou pergunta clinica
  2. usuario pode pedir humano explicitamente
  3. orquestrador cria handoff com prioridade
  4. conversa passa para estado escalado
  5. painel lista em `/handoffs`
- Entradas:
  - conversa
  - motivo
  - prioridade
- Saidas:
  - registro em `handoffs`
  - conversa marcada como escalada
- Dependencias:
  - `Handoff`
  - `Conversation`
- Status: `Existe no codigo`
- Modulos tocados:
  - IA
  - handoff
  - auditoria indireta
- Gargalos, falhas ou riscos:
  - sem RBAC, qualquer consumidor da API pode mexer no estado dos handoffs
  - handoff nao possui fila sofisticada, SLA ou ownership forte

### P10. Auditoria / observabilidade
- Nome: pipeline de auditoria minima
- Objetivo: registrar eventos importantes do sistema.
- Onde esta:
  - `apps/api/app/services/audit_service.py`
  - `apps/api/app/api/routes/audit.py`
  - chamadas em webhook handler e RAG
- Como funciona:
  1. servicos chamam `audit.log_event(...)`
  2. evento vai para `audit_events`
  3. painel consome `GET /api/v1/audit`
- Entradas:
  - actor, action, resource, payload
- Saidas:
  - registro de auditoria
- Dependencias:
  - tabela `audit_events`
- Status: `Existe no codigo`
- Modulos tocados:
  - Telegram
  - RAG
  - IA
- Gargalos, falhas ou riscos:
  - nao ha tracing distribuido
  - nao ha metricas, alerts ou dashboards de runtime
  - auditoria e pontual, nao sistematica em todos os fluxos

### P11. Dashboard / relatorios operacionais
- Nome: pipeline de dashboard agregado
- Objetivo: oferecer contagens para painel operacional.
- Onde esta:
  - `apps/api/app/api/routes/dashboard.py`
  - `frontend/src/app/dashboard/page.tsx`
- Como funciona:
  1. endpoint agrega contagens basicas
  2. frontend exibe cards e tabelas
- Entradas:
  - banco operacional
- Saidas:
  - `DashboardSummary`
- Dependencias:
  - pacientes
  - conversas
  - handoffs
  - slots
  - documentos e chunks de RAG
- Status: `Existe no codigo`
- Modulos tocados:
  - dashboard
  - frontend
- Gargalos, falhas ou riscos:
  - nao ha relatorios historicos nem filtros por periodo
  - nao ha tenant

### P12. RAG ingest via API
- Nome: pipeline de ingestao RAG via API
- Objetivo: receber um documento textual e quebrar em chunks persistidos.
- Onde esta:
  - `apps/api/app/api/routes/rag.py`
  - `apps/api/app/services/rag_service.py`
- Como funciona:
  1. `POST /api/v1/rag/ingest`
  2. cria `RagDocument`
  3. faz `chunk_text` por tamanho de caracteres e overlap
  4. tenta embedding por OpenAI ou Gemini
  5. cria `RagChunk` para cada fragmento
  6. grava evento de auditoria
- Entradas:
  - `title`
  - `content`
  - `category`
  - `source_path`
- Saidas:
  - `document_id`
  - `chunks_created`
- Dependencias:
  - `rag_documents`
  - `rag_chunks`
  - API externa de embedding
- Status: `Existe no codigo`
- Modulos tocados:
  - RAG
  - auditoria
- Gargalos, falhas ou riscos:
  - aceita apenas texto, sem parser de PDF/DOCX no runtime
  - nao existe `clinic_id`
  - `embedding_provider` em config nao governa de fato a escolha

### P13. RAG query runtime
- Nome: pipeline de retrieval do MVP
- Objetivo: recuperar conhecimento administrativo.
- Onde esta:
  - `apps/api/app/services/rag_service.py`
  - `apps/api/app/repositories/rag_repository.py`
  - chamado por `AIOrchestrator`
- Como funciona:
  1. gera embedding da query
  2. faz busca vetorial `pgvector cosine` em `rag_chunks`
  3. filtra opcionalmente por `category`
  4. se nao houver embedding/resultado suficiente, tenta `text_search`
  5. resultado entra no `response_builder`
- Entradas:
  - query do usuario
  - `top_k`
  - `category`
- Saidas:
  - lista de chunks com score e titulo do documento
- Dependencias:
  - Postgres + pgvector
  - OpenAI ou Gemini para embeddings
- Status: `Existe no codigo`
- Modulos tocados:
  - RAG
  - IA
- Gargalos, falhas ou riscos:
  - sem filtro por clinica
  - sem reranking
  - sem citacao robusta
  - resultado de RAG so entra no prompt LLM para `DUVIDA_OPERACIONAL`, nao para `POLITICAS`

### P14. Ingestao de docs via script
- Nome: pipeline offline de ingestao de markdown
- Objetivo: popular a base com markdowns de apoio.
- Onde esta:
  - `scripts/ingest_docs.py`
- Como funciona:
  1. le diretorio `GUIAS-DEV` por padrao
  2. quebra arquivos por secoes `##`
  3. classifica categoria por regex heuristica
  4. no modo DB cria `RagDocument` + `RagChunk`
  5. no modo API chama `POST /api/v1/rag/ingest`
- Entradas:
  - `--docs-dir`
  - `--mode`
  - `--database-url` ou `--api-url`
- Saidas:
  - documentos/chunks
- Dependencias:
  - markdown local
  - API ou banco
- Status: `Existe no codigo`
- Modulos tocados:
  - RAG
  - scripts
- Gargalos, falhas ou riscos:
  - no modo DB nao gera embeddings
  - foco em docs markdown internas, nao em base documental de clinica real
  - sem versionamento por fonte

### P15. Seed operacional
- Nome: pipeline de seed da primeira clinica
- Objetivo: popular profissionais, pacientes, slots e documentos base.
- Onde esta:
  - `scripts/seed_data.py`
- Como funciona:
  1. define arrays hardcoded de profissionais e pacientes
  2. define documentos de KB hardcoded da Minutare Med
  3. gera slots para 14 dias
  4. grava tudo no banco se nao existir
- Entradas:
  - `--mode`
  - `--database-url` ou `--api-url`
- Saidas:
  - base inicial populada
- Dependencias:
  - modelos de dominio
  - banco
- Status: `Existe no codigo`
- Modulos tocados:
  - pacientes
  - profissionais
  - agenda
  - RAG
- Gargalos, falhas ou riscos:
  - fortemente acoplado a uma clinica especifica
  - pode contaminar qualquer ambiente novo com dados errados

### P16. Configuracao de webhook Telegram
- Nome: pipeline de administracao da integracao Telegram
- Objetivo: consultar e atualizar webhook pelo painel.
- Onde esta:
  - backend: `apps/api/app/api/routes/telegram.py`
  - frontend: `frontend/src/lib/api.ts`
  - pagina: `frontend/src/app/integrations/page.tsx`
- Como funciona:
  1. painel consulta `GET /api/v1/telegram/webhook-info`
  2. painel permite enviar URL nova
  3. backend chama `TelegramService`
- Entradas:
  - URL do webhook
- Saidas:
  - status do webhook
- Dependencias:
  - Telegram Bot API
- Status: `Parcial`
- Modulos tocados:
  - integracoes
  - frontend
  - Telegram
- Gargalos, falhas ou riscos:
  - backend espera query param `url`, frontend manda JSON body
  - backend retorna `{"info": info}`, frontend espera objeto plano

### P17. LangGraph clinic graph
- Nome: pipeline do grafo clinic core
- Objetivo: substituir o motor MVP por um fluxo multi-node com supervisor.
- Onde esta:
  - `src/inteliclinic/core/ai_engine/graphs/main_graph.py`
  - `src/inteliclinic/core/ai_engine/langgraph/builder.py`
- Como funciona:
  1. entrada em `reception`
  2. roteia para `scheduling`, `insurance`, `financial`, `glosa`, `fallback` ou `response`
  3. passa por `supervisor`
  4. vai para `response` ou `END` em caso de handoff
  5. pode usar `MemorySaver` e `interrupt_before=["supervisor"]`
- Entradas:
  - `ClinicState`
  - `GraphConfig`
- Saidas:
  - estado atualizado
- Dependencias:
  - LangGraph
  - nodes do core
  - clinic config
- Status: `Parcial`
- Modulos tocados:
  - core/ai_engine
  - clinic config
- Gargalos, falhas ou riscos:
  - nao esta conectado ao backend FastAPI atual
  - alguns nodes ainda usam mocks e chamadas duras a OpenAI

### P18. Extraction pipeline com Instructor
- Nome: pipeline de extracao estruturada
- Objetivo: interpretar mensagem com LLM e retornar schema tipado.
- Onde esta:
  - `src/inteliclinic/core/nlu/extractors/message_extractor.py`
  - `src/inteliclinic/core/nlu/pipelines/extraction_pipeline.py`
- Como funciona:
  1. constroi system prompt conservador
  2. envia mensagem + historico recente
  3. valida em `ExtractedMessage`
  4. em falha, devolve fallback conservador
- Entradas:
  - mensagem
  - historico
  - contexto opcional
- Saidas:
  - `ExtractedMessage`
- Dependencias:
  - Instructor
  - OpenAI ou Anthropic
- Status: `Parcial`
- Modulos tocados:
  - core NLU
  - grafo planejado
- Gargalos, falhas ou riscos:
  - fora do runtime principal
  - mais uma taxonomia de intents paralela ao FARO do MVP

### P19. RAG Qdrant / LlamaIndex
- Nome: pipeline RAG do core futuro
- Objetivo: migrar a KB para colecoes por clinica e query engine mais robusta.
- Onde esta:
  - `src/inteliclinic/core/rag/`
  - `src/inteliclinic/clinic/config/clinic_settings.py`
- Como funciona hoje:
  1. `ClinicSettings` consegue montar config de RAG por clinica
  2. `LlamaIndexStore` e `QdrantStore` conseguem abrir colecoes por `clinic_id`
  3. `ClinicQueryEngine` consulta a store
  4. `HybridRetriever` faz dense + sparse placeholder
  5. `IngestPipeline` parseia e chunka
  6. porem a etapa critica de embed + upsert esta em TODO
- Entradas:
  - config por clinica
  - documentos
- Saidas:
  - atualmente, `IngestResult`; nao a indexacao completa
- Dependencias:
  - Qdrant
  - LlamaIndex
  - OpenAI embeddings
  - parsers Docling e Markdown
- Status: `Parcial`
- Modulos tocados:
  - core/rag
  - clinic config
- Gargalos, falhas ou riscos:
  - ingestao esta incompleta
  - sparse retriever esta placeholder
  - nao alimenta o runtime atual

### P20. Glosa / anomaly
- Nome: pipeline de glosa / anomalia
- Objetivo: detectar risco de glosa em fluxo interno.
- Onde esta:
  - `src/inteliclinic/core/analytics/features/extractor.py`
  - `src/inteliclinic/core/analytics/models/detector.py`
  - `src/inteliclinic/core/analytics/pipelines/anomaly_pipeline.py`
  - `src/inteliclinic/core/ai_engine/nodes/glosa.py`
- Como funciona:
  1. extrai features
  2. calcula score/anomalia
  3. node `glosa` produziria contexto para resposta/supervisor
- Entradas:
  - dados operacionais/financeiros
- Saidas:
  - score de risco
- Dependencias:
  - modulo analytics
- Status: `Parcial`
- Modulos tocados:
  - analytics
  - grafo planejado
- Gargalos, falhas ou riscos:
  - nao esta exposto em rotas
  - node `glosa` faz fallback heuristico

### P21. Pipelines ausentes mas pedidas no escopo

| Familia | Evidencia encontrada | Status real |
| --- | --- | --- |
| CRM | nenhuma rota ou service dedicados | Inexistente |
| leads | nenhuma model/rota dedicada | Inexistente |
| follow-up | apenas `SlotType.follow_up`; sem fluxo | Inexistente |
| alertas | sem engine de alertas | Inexistente |
| onboarding operacional de clinica | docs e config exemplo | Plano |
| autenticacao | nenhuma rota/middleware | Inexistente |
| Google integration | docs e placeholders | Plano |
| memoria semantica por paciente | nao encontrada no runtime | Inexistente |
| observabilidade forte | sem tracing/metrics | Inexistente |

## Consolidado de pipelines
- Pipelines prontas:
  - bootstrap
  - atendimento Telegram inbound
  - identificacao de paciente
  - memoria curta simples
  - FARO + guardrails + geracao de resposta
  - agendamento basico
  - handoff
  - auditoria minima
  - dashboard minimo
  - RAG ingest/query do MVP
  - CRUDs operacionais basicos
- Pipelines parciais:
  - cancelamento com varias consultas
  - remarcacao
  - webhook admin no painel
  - LangGraph core
  - extraction pipeline com Instructor
  - RAG Qdrant/LlamaIndex
  - glosa/anomaly
- Pipelines inexistentes mas previstas:
  - auth
  - CRM
  - leads
  - follow-up
  - alertas
  - Google
  - multicanal de producao

---

## 2. Inventario de rotas

## 2.0. Observacoes gerais
- Prefixo real da API: `API_PREFIX = "/api/v1"` em `apps/api/app/main.py`.
- Excecao: health esta fora do prefixo.
- Nao existe auth em nenhuma rota backend lida.
- Nao existe middleware de pagina protegida no frontend.
- O frontend usa `frontend/src/lib/api.ts` como cliente central.

## 2.1. Backend - health

| Metodo | Caminho | Arquivo | Dominio | O que faz | Quem pode usar | Auth | Role | Implementada | Front conectado | Observacao |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GET | `/health` | `apps/api/app/api/routes/health.py` | health | status do servico | qualquer cliente HTTP | Nao | Nao | Sim | Sim (`getHealth`) | sem prefixo `/api/v1` |
| GET | `/health/db` | `apps/api/app/api/routes/health.py` | health | teste basico de banco | qualquer cliente HTTP | Nao | Nao | Sim | Sim (`getHealthDb`) | sem prefixo `/api/v1` |

## 2.2. Backend - pacientes

| Metodo | Caminho | Arquivo | Dominio | O que faz | Quem pode usar | Auth | Role | Implementada | Front conectado | Observacao |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GET | `/api/v1/patients` | `apps/api/app/api/routes/patients.py` | pacientes | lista pacientes com paginacao | qualquer cliente HTTP | Nao | Nao | Sim | Sim | usado em `/patients` |
| POST | `/api/v1/patients` | `apps/api/app/api/routes/patients.py` | pacientes | cria paciente | qualquer cliente HTTP | Nao | Nao | Sim | Sim | sem validacao de role |
| GET | `/api/v1/patients/{patient_id}` | `apps/api/app/api/routes/patients.py` | pacientes | busca paciente por id | qualquer cliente HTTP | Nao | Nao | Sim | Sim | usado em `/patients/[id]` |
| GET | `/api/v1/patients/by-telegram/{telegram_user_id}` | `apps/api/app/api/routes/patients.py` | pacientes | busca paciente pelo Telegram | integracao interna/cliente HTTP | Nao | Nao | Sim | Nao | rota util para integracao, nao para painel |
| PATCH | `/api/v1/patients/{patient_id}` | `apps/api/app/api/routes/patients.py` | pacientes | atualiza paciente | qualquer cliente HTTP | Nao | Nao | Sim | Sim | sem controle de campos sensiveis |

## 2.3. Backend - profissionais / medicos

| Metodo | Caminho | Arquivo | Dominio | O que faz | Quem pode usar | Auth | Role | Implementada | Front conectado | Observacao |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GET | `/api/v1/professionals` | `apps/api/app/api/routes/professionals.py` | medicos/profissionais | lista ativos, opcional por especialidade | qualquer cliente HTTP | Nao | Nao | Sim | Sim | usado em profissionais e agenda |
| GET | `/api/v1/professionals/all` | `apps/api/app/api/routes/professionals.py` | medicos/profissionais | lista todos, inclusive inativos | qualquer cliente HTTP | Nao | Nao | Sim | Sim | usado no painel |
| POST | `/api/v1/professionals` | `apps/api/app/api/routes/professionals.py` | medicos/profissionais | cria profissional | qualquer cliente HTTP | Nao | Nao | Sim | Sim | CRM unico, sem tenant |
| PATCH | `/api/v1/professionals/{professional_id}` | `apps/api/app/api/routes/professionals.py` | medicos/profissionais | atualiza profissional | qualquer cliente HTTP | Nao | Nao | Sim | Sim | sem role admin |
| DELETE | `/api/v1/professionals/{professional_id}` | `apps/api/app/api/routes/professionals.py` | medicos/profissionais | desativa profissional | qualquer cliente HTTP | Nao | Nao | Sim | Sim | delete logico via `active=false` |

## 2.4. Backend - agenda / consultas

| Metodo | Caminho | Arquivo | Dominio | O que faz | Quem pode usar | Auth | Role | Implementada | Front conectado | Observacao |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| POST | `/api/v1/schedules` | `apps/api/app/api/routes/schedules.py` | agenda | cria slot | qualquer cliente HTTP | Nao | Nao | Sim | Nao direto | usado por API, nao vi form no painel |
| GET | `/api/v1/schedules` | `apps/api/app/api/routes/schedules.py` | agenda | lista slots com filtros | qualquer cliente HTTP | Nao | Nao | Sim | Sim | usado em `/schedules` |
| POST | `/api/v1/schedules/{slot_id}/book` | `apps/api/app/api/routes/schedules.py` | agenda/consultas | reserva slot para paciente | qualquer cliente HTTP | Nao | Nao | Sim | Nao direto | usado internamente por actions |
| POST | `/api/v1/schedules/{slot_id}/cancel` | `apps/api/app/api/routes/schedules.py` | agenda/consultas | cancela slot | qualquer cliente HTTP | Nao | Nao | Sim | Sim | botao do painel usa essa rota |

## 2.5. Backend - conversas

| Metodo | Caminho | Arquivo | Dominio | O que faz | Quem pode usar | Auth | Role | Implementada | Front conectado | Observacao |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GET | `/api/v1/conversations` | `apps/api/app/api/routes/conversations.py` | IA / atendimento | lista conversas | qualquer cliente HTTP | Nao | Nao | Sim | Sim | usado em `/conversations` |
| GET | `/api/v1/conversations/{conversation_id}` | `apps/api/app/api/routes/conversations.py` | IA / atendimento | retorna detalhe da conversa | qualquer cliente HTTP | Nao | Nao | Sim | Sim | usado em `/conversations/[id]` |
| GET | `/api/v1/conversations/{conversation_id}/messages` | `apps/api/app/api/routes/conversations.py` | IA / atendimento | retorna mensagens | qualquer cliente HTTP | Nao | Nao | Sim | Sim | usado no detalhe da conversa |

## 2.6. Backend - handoff

| Metodo | Caminho | Arquivo | Dominio | O que faz | Quem pode usar | Auth | Role | Implementada | Front conectado | Observacao |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GET | `/api/v1/handoff` | `apps/api/app/api/routes/handoff.py` | atendimento humano | lista handoffs | qualquer cliente HTTP | Nao | Nao | Sim | Sim | usado em `/handoffs` |
| POST | `/api/v1/handoff` | `apps/api/app/api/routes/handoff.py` | atendimento humano | cria handoff manual | qualquer cliente HTTP | Nao | Nao | Sim | Nao visivel | pode ser chamado fora do orquestrador |
| PATCH | `/api/v1/handoff/{handoff_id}` | `apps/api/app/api/routes/handoff.py` | atendimento humano | atualiza status | qualquer cliente HTTP | Nao | Nao | Sim | Sim | painel usa para resolver/atribuir |

## 2.7. Backend - auditoria / dashboard / observabilidade

| Metodo | Caminho | Arquivo | Dominio | O que faz | Quem pode usar | Auth | Role | Implementada | Front conectado | Observacao |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GET | `/api/v1/audit` | `apps/api/app/api/routes/audit.py` | observabilidade | lista eventos de auditoria | qualquer cliente HTTP | Nao | Nao | Sim | Sim | usado em `/audit` |
| GET | `/api/v1/dashboard/summary` | `apps/api/app/api/routes/dashboard.py` | dashboard | agrega contagens | qualquer cliente HTTP | Nao | Nao | Sim | Sim | usado em `/dashboard` |

## 2.8. Backend - RAG

| Metodo | Caminho | Arquivo | Dominio | O que faz | Quem pode usar | Auth | Role | Implementada | Front conectado | Observacao |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| POST | `/api/v1/rag/ingest` | `apps/api/app/api/routes/rag.py` | IA / RAG | ingere documento textual | qualquer cliente HTTP | Nao | Nao | Sim | Sim | sem upload de arquivo |
| POST | `/api/v1/rag/query` | `apps/api/app/api/routes/rag.py` | IA / RAG | consulta KB | qualquer cliente HTTP | Nao | Nao | Sim | Sim | tipagem do frontend diverge |
| GET | `/api/v1/rag/documents` | `apps/api/app/api/routes/rag.py` | IA / RAG | lista documentos | qualquer cliente HTTP | Nao | Nao | Sim | Sim | usado em `/rag` |

## 2.9. Backend - Telegram / webhook

| Metodo | Caminho | Arquivo | Dominio | O que faz | Quem pode usar | Auth | Role | Implementada | Front conectado | Observacao |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| POST | `/api/v1/telegram/webhook` | `apps/api/app/api/routes/telegram.py` | webhook / integracao | recebe updates Telegram | Telegram ou qualquer caller com formato correto | Parcial | Nao | Sim | Nao | secret so e validado se header vier |
| POST | `/api/v1/telegram/set-webhook` | `apps/api/app/api/routes/telegram.py` | integracao | seta webhook no bot | qualquer cliente HTTP | Nao | Nao | Sim | Sim, mas quebrado | backend espera query param |
| GET | `/api/v1/telegram/webhook-info` | `apps/api/app/api/routes/telegram.py` | integracao | consulta status do webhook | qualquer cliente HTTP | Nao | Nao | Sim | Sim, mas quebrado | backend retorna `{"info": info}` |

## 2.10. Frontend - paginas e areas

| Caminho | Arquivo | Dominio | O que faz | Protegida | Role | Backend conectado | Status | Observacao |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `/` | `frontend/src/app/page.tsx` | shell | redireciona para dashboard | Nao | Nao | Nao | Sim | redirect simples |
| `/dashboard` | `frontend/src/app/dashboard/page.tsx` | dashboard | visao geral | Nao | Nao | Sim | Sim | consome summary |
| `/conversations` | `frontend/src/app/conversations/page.tsx` | atendimento | lista conversas | Nao | Nao | Sim | Sim | usa API de conversas |
| `/conversations/[id]` | `frontend/src/app/conversations/[id]/page.tsx` | atendimento | detalhe de conversa e mensagens | Nao | Nao | Sim | Sim | sem auth |
| `/patients` | `frontend/src/app/patients/page.tsx` | pacientes | lista pacientes | Nao | Nao | Sim | Sim | CRUD parcial no painel |
| `/patients/[id]` | `frontend/src/app/patients/[id]/page.tsx` | pacientes | detalhe/edicao | Nao | Nao | Sim | Sim | sem controle de permissao |
| `/professionals` | `frontend/src/app/professionals/page.tsx` | profissionais | lista/cria/edita profissionais | Nao | Nao | Sim | Sim | lista de especialidades esta no front |
| `/schedules` | `frontend/src/app/schedules/page.tsx` | agenda | lista slots e cancela | Nao | Nao | Sim | Sim | sem auth |
| `/handoffs` | `frontend/src/app/handoffs/page.tsx` | handoff | fila de handoffs | Nao | Nao | Sim | Sim | qualquer usuario do painel poderia atuar |
| `/rag` | `frontend/src/app/rag/page.tsx` | RAG | lista docs, ingere, consulta | Nao | Nao | Sim | Sim | contrato de query diverge |
| `/integrations` | `frontend/src/app/integrations/page.tsx` | integracoes | mostra Telegram e placeholders futuros | Nao | Nao | Sim | Parcial | mismatch de webhook info/set |
| `/audit` | `frontend/src/app/audit/page.tsx` | observabilidade | lista auditoria | Nao | Nao | Sim | Sim | sem filtros fortes |
| `/settings` | `frontend/src/app/settings/page.tsx` | config | pagina estatica | Nao | Nao | Nao real | Parcial | sem persistencia real |
| `/api/health` | `frontend/src/app/api/health/route.ts` | frontend interno | health do frontend/app | Nao | Nao | Nao | Sim | nao e backend principal |

## 2.11. Dominios pedidos no escopo que nao possuem rotas reais

| Dominio pedido | Backend | Frontend | Estado |
| --- | --- | --- | --- |
| auth | nenhuma rota | nenhuma pagina de login | Ausente |
| admin | nenhuma rota dedicada | apenas `/settings` estatica | Ausente |
| medicos | coberto por `professionals` | sim | Existe sob outro nome |
| funcionarios | nenhuma rota | nenhuma pagina | Ausente |
| salas | nenhuma rota | nenhuma pagina | Ausente |
| consultas | parcialmente sob `schedules` | parcialmente | Parcial |
| convenios | nenhuma rota dedicada | nenhuma pagina | Ausente |
| procedimentos | nenhuma rota | nenhuma pagina | Ausente |
| produtos | nenhuma rota | nenhuma pagina | Ausente |
| estoque | nenhuma rota | nenhuma pagina | Ausente |
| leads | nenhuma rota | nenhuma pagina | Ausente |
| CRM | nenhuma rota | nenhuma pagina | Ausente |
| follow-up | nenhuma rota | nenhuma pagina | Ausente |
| relatorios | apenas `dashboard/summary` | dashboard simples | Parcial |
| alertas | nenhuma rota | nenhuma pagina | Ausente |
| IA interna | nenhuma rota publica dedicada | nenhuma area dedicada | Ausente como API; IA e interna ao webhook |
| Google | nenhuma rota | nenhuma pagina funcional | Ausente |
| webhooks alem do Telegram | nenhuma rota | nenhuma pagina | Ausente |

## 2.12. Rotas prontas, parciais e ausentes
- Rotas prontas:
  - health
  - patients
  - professionals
  - schedules
  - conversations
  - handoff
  - audit
  - dashboard
  - rag
  - telegram webhook
- Rotas parciais:
  - Telegram `set-webhook`
  - Telegram `webhook-info`
  - paginas `integrations`, `settings`, `rag` por mismatch/limites de contrato
- Rotas previstas e ausentes:
  - auth
  - Google
  - CRM
  - leads
  - follow-up
  - alertas
  - admin RBAC
- Conflitos, duplicacoes ou inconsistencias:
  - docs falam em alguns endpoints que o backend real nao expoe
  - frontend e backend discordam nos contratos de Telegram e RAG
  - dominio "medicos" foi modelado como `professionals`; isso esta ok, mas deve ser documentado

---

## 3. Configuracoes de todas as IAs do projeto

## 3.0. Onde ficam as configs

| Escopo | Arquivo | Realmente usado pelo runtime? | Conteudo |
| --- | --- | --- | --- |
| global runtime | `apps/api/app/core/config.py` | Sim | envs gerais, DB, Telegram, API keys, `llm_model`, RAG chunking/threshold |
| por clinica / arquitetura alvo | `src/inteliclinic/clinic/config/clinic_settings.py` | Nao no MVP atual | `CLINIC_*`, branding, horarios, features, LLM, RAG |
| exemplo de deploy por clinica | `config/examples/clinic.example.yaml` | Nao automatico | modelo de configuracao rica por clinica |
| prompts por clinica | `src/inteliclinic/clinic/prompts/base_prompts.py` | Nao no MVP atual | addendum de prompt por clinica |

### Config global real do runtime (`apps/api/app/core/config.py`)
- `database_url`
- `telegram_bot_token`
- `telegram_webhook_url`
- `telegram_webhook_secret`
- `embedding_provider` (declarado, mas nao governa de fato a escolha)
- `openai_api_key`
- `anthropic_api_key`
- `gemini_api_key`
- `llm_model`
- `qdrant_url` (declarado, mas nao usado pelo RAG do MVP)
- `rag_confidence_threshold`
- `rag_top_k`
- `rag_chunk_size`
- `rag_chunk_overlap`

## 3.1. IA operacional real do MVP

### IA-01. `AIOrchestrator`
- Papel: coordenador central do atendimento.
- Onde esta: `apps/api/app/ai_engine/orchestrator.py`
- Modelo usado: nao chama modelo diretamente; delega ao `response_builder`.
- Provider usado: n/a diretamente.
- Temperatura: n/a diretamente.
- Janela de contexto explicita: depende de `ConversationContext` com ultimas 6 mensagens.
- System prompt / instrucoes-base: indiretas, via `response_builder`.
- Ferramentas acessiveis:
  - `ScheduleActions`
  - `RagService`
  - `ContextManager`
  - `guardrails`
  - `HandoffService` / repositorios
- Memoria usada:
  - `Conversation.pending_action`
  - perfil do paciente
  - historico recente
- Como recebe contexto:
  - `ContextManager.build_context(...)`
- Como decide acoes:
  - roteamento FARO + regras condicionais
- Como lida com erros:
  - fallback de resposta
  - handoff
  - limpeza de pending action desconhecida
- Status: `Existe no codigo`
- Limitacoes:
  - muito monolitico
  - sem configuracao por clinica
  - sem separacao de responsabilidades por agente

### IA-02. `FaroIntentRouter`
- Papel: classificador/extrator heuristico de intencao e entidades.
- Onde esta: `apps/api/app/ai_engine/intent_router.py`
- Modelo usado: nenhum.
- Provider usado: nenhum.
- Temperatura / top_p / seed: n/a.
- Context window: n/a.
- Prompt base: nenhum; usa regex e listas de palavras.
- Ferramentas acessiveis: nenhuma.
- Memoria usada: so o texto da mensagem atual.
- Como recebe contexto: mensagem bruta.
- Como decide acoes:
  - palavras-chave
  - regex
  - parser de datas relativas
- Como lida com erros:
  - cai para `Intent.DESCONHECIDA`
- Status: `Existe no codigo`
- Limitacoes:
  - baixa capacidade semantica
  - dificil escalar para intents complexas
  - taxonomia isolada do core LangGraph

### IA-03. `response_builder` + `llm_client`
- Papel: gerador final de resposta do MVP.
- Onde esta:
  - `apps/api/app/ai_engine/response_builder.py`
  - `apps/api/app/ai_engine/clients/llm_client.py`
- Modelo usado:
  - OpenAI: `settings.llm_model or "gpt-4o-mini"`
  - Anthropic: `settings.llm_model or "claude-sonnet-4-20250514"`
  - Gemini: `settings.llm_model or "gemini-2.5-flash"`
- Provider usado:
  - OpenAI se `openai_api_key` existir
  - senao Anthropic se `anthropic_api_key` existir
  - senao Gemini se `gemini_api_key` existir
- Temperatura:
  - `call_llm(... temperature=0.7)` por default
- Top_p / top_k / seed:
  - nao expostos
- Janela de contexto explicita:
  - system prompt
  - historico truncado
  - bloco de perfil
  - bloco de FARO
  - RAG opcional
- System prompt / instrucoes-base:
  - `SYSTEM_BASE`
  - `PERSONA`
  - `SAFETY_RULES`
  - `BEHAVIOR_RULES`
- Ferramentas acessiveis:
  - nenhuma tool calling real; so recebe "acoes sugeridas" como texto
- Memoria usada:
  - perfil do paciente
  - historico curto
  - FARO JSON
  - chunks de RAG
- Como recebe contexto:
  - `_build_messages(...)`
- Como decide acoes:
  - nao decide acoes reais; so redige resposta
- Como lida com erros:
  - se LLM falhar, cai para templates
- Status: `Existe no codigo`
- Limitacoes:
  - hardcoded em Minutare Med
  - sem controle por clinica/agente
  - sem versionamento de prompt

### IA-04. Guardrails do MVP
- Papel: bloqueio e escalonamento de mensagens inseguras.
- Onde esta: `apps/api/app/ai_engine/guardrails.py`
- Modelo usado: nenhum.
- Provider usado: nenhum.
- Temperatura / top_p / seed: n/a.
- Prompt base: nenhum.
- Ferramentas acessiveis: nenhuma.
- Memoria usada: texto atual, resposta atual, consentimento do paciente, score de confianca.
- Como recebe contexto: chamada direta do orquestrador.
- Como decide acoes:
  - regex de prompt injection
  - regex de urgencia
  - regex de pergunta clinica
  - threshold de confianca
- Como lida com erros:
  - devolve `GuardrailResult`
- Status: `Existe no codigo`
- Limitacoes:
  - regras simples
  - usa `rag_confidence_threshold` como threshold geral

### IA-05. `RagService` como componente de embeddings/retrieval
- Papel: gerar embeddings e recuperar contexto.
- Onde esta: `apps/api/app/services/rag_service.py`
- Modelo usado:
  - OpenAI embeddings: `text-embedding-3-small`
  - Gemini embeddings: `text-embedding-004`
- Provider usado:
  - OpenAI ou Gemini
- Temperatura / top_p / seed: n/a.
- Prompt base: nenhum.
- Ferramentas acessiveis: repositorio RAG.
- Memoria usada: base persistente `rag_documents` / `rag_chunks`.
- Como recebe contexto: texto de query/documento.
- Como decide acoes:
  - escolhe provider pela chave disponivel
  - busca vetorial ou textual
- Como lida com erros:
  - loga exception
  - retorna `None` no embedding
  - fallback textual em parte do fluxo
- Status: `Existe no codigo`
- Limitacoes:
  - sem tenant
  - sem reranker
  - sem governanca de fonte

## 3.2. IA / agentes do core planejado

| Nome | Papel | Onde | Modelo / provider | Status | Limite principal |
| --- | --- | --- | --- | --- | --- |
| `InstructorMessageExtractor` | extracao estruturada | `src/inteliclinic/core/nlu/extractors/message_extractor.py` | default `openai/gpt-4o-mini`, suporta Anthropic | Parcial | fora do runtime MVP |
| `ExtractionPipeline` | wrapper com retries/timeouts | `src/inteliclinic/core/nlu/pipelines/extraction_pipeline.py` | usa extractor | Parcial | so no core |
| `reception_node` | entrada do grafo | `src/inteliclinic/core/ai_engine/nodes/reception.py` | depende do extractor | Parcial | nao ligado a FastAPI |
| `scheduling_node` | agenda no grafo | `src/inteliclinic/core/ai_engine/nodes/scheduling.py` | sem modelo proprio | Parcial | usa mocks/heuristicas |
| `insurance_node` | cobertura/convnios | `src/inteliclinic/core/ai_engine/nodes/insurance.py` | sem modelo proprio | Parcial | nao ligado a dados reais |
| `financial_node` | financeiro | `src/inteliclinic/core/ai_engine/nodes/financial.py` | sem modelo proprio | Parcial | fora do runtime |
| `glosa_node` | risco de glosa | `src/inteliclinic/core/ai_engine/nodes/glosa.py` | sem modelo proprio | Parcial | modulo analytics nao totalmente acoplado |
| `supervisor_node` | gate de escalonamento | `src/inteliclinic/core/ai_engine/nodes/supervisor.py` | sem modelo proprio | Parcial | sem uso no runtime |
| `fallback_node` | resposta segura em baixa confianca | `src/inteliclinic/core/ai_engine/nodes/fallback.py` | sem modelo proprio | Parcial | fora do runtime |
| `response_node` | resposta final do grafo | `src/inteliclinic/core/ai_engine/nodes/response.py` | hardcoded `gpt-4o-mini`, OpenAI | Parcial | ignora clinic config |
| `HybridRetriever` | dense + sparse fusion | `src/inteliclinic/core/rag/retrievers/hybrid_retriever.py` | dense implementado, sparse placeholder | Parcial | hibrido incompleto |
| `ClinicQueryEngine` | query engine por clinica | `src/inteliclinic/core/rag/query/query_engine.py` | LlamaIndex/Qdrant | Parcial | depende de store pronta |
| `NotImplementedGraphRAG` | placeholder para GraphRAG | `src/inteliclinic/core/rag/graphrag/interface.py` | n/a | Plano | nao implementado |
| `AnomalyPipeline` | detecao de anomalia | `src/inteliclinic/core/analytics/pipelines/anomaly_pipeline.py` | PyOD/rules | Parcial | fora do produto atual |

## 3.3. O que esta hardcoded
- Nome da clinica:
  - `apps/api/app/main.py`
  - `apps/api/app/ai_engine/response_builder.py`
  - `frontend/src/app/layout.tsx`
  - `frontend/src/components/layout/sidebar.tsx`
  - `scripts/seed_data.py`
- Dados institucionais e KB:
  - `scripts/seed_data.py`
- Lista de especialidades do front:
  - componentes de profissionais/agenda
- Modelo do `response_node` do core:
  - `gpt-4o-mini` hardcoded em `src/inteliclinic/core/ai_engine/nodes/response.py`

## 3.4. O que deveria ser parametrizado e ainda nao foi
- `clinic_id` / tenant em todas as entidades operacionais
- branding do backend e frontend
- horarios, convenios e politicas
- prompts do runtime MVP
- seeds e dados de bootstrap
- provider/modelo por agente
- canal padrao e integracoes por clinica

---

## 4. Auditoria de prompts

## 4.1. Mapa geral de prompts encontrados

| ID | Onde | IA que usa | Objetivo | Status |
| --- | --- | --- | --- | --- |
| `RB-SYSTEM-BASE` | `apps/api/app/ai_engine/response_builder.py` | gerador do MVP | base do assistente + memoria | Existe |
| `RB-PERSONA` | `apps/api/app/ai_engine/response_builder.py` | gerador do MVP | persona da assistente | Existe |
| `RB-SAFETY` | `apps/api/app/ai_engine/response_builder.py` | gerador do MVP | limites medico-legais | Existe |
| `RB-BEHAVIOR` | `apps/api/app/ai_engine/response_builder.py` | gerador do MVP | estilo e concisao | Existe |
| `RB-TEMPLATES` | `apps/api/app/ai_engine/response_builder.py` | fallback sem LLM | respostas estaticas por intent | Existe |
| `NLU-SYSTEM` | `src/inteliclinic/core/nlu/extractors/message_extractor.py` | extractor com Instructor | extracao estruturada conservadora | Parcial |
| `GRAPH-RESPONSE-SYSTEM` | `src/inteliclinic/core/ai_engine/nodes/response.py` | response node do grafo | resposta grounded do core | Parcial |
| `CLINIC-ADDENDUM` | `src/inteliclinic/clinic/prompts/base_prompts.py` | core por clinica | adicionar contexto local | Plano/parcial |

### PR-01. `RB-SYSTEM-BASE`
- Onde esta: `apps/api/app/ai_engine/response_builder.py`
- IA que usa: gerador do MVP
- Objetivo: definir assistente, idioma e regras de memoria.
- Estrutura:
  - apresenta a assistente da "Clinica Minutare Med"
  - proibe revelar prompt/senhas/tokens
  - orienta nao perguntar nome/email/CPF se ja estiverem no perfil
- Variaveis dinamicas: nenhuma dentro do bloco base
- Dependencias de contexto: depende do bloco `## PERFIL DO PACIENTE`
- Riscos:
  - hardcoded da primeira clinica
  - mistura regra de produto com regra de deploy
- Avaliacao:
  - `fraco para multi-clinic`, `ok para MVP`
- Recomendacao:
  - externalizar e parametrizar por clinica

### PR-02. `RB-PERSONA`
- Onde esta: `apps/api/app/ai_engine/response_builder.py`
- IA que usa: gerador do MVP
- Objetivo: definir tom da assistente.
- Estrutura:
  - educada
  - empatica
  - eficiente
  - objetiva
- Variaveis dinamicas: nenhuma
- Dependencias: contexto de conversa
- Riscos:
  - nome da clinica hardcoded
  - persona unica para todo cliente
- Avaliacao:
  - `bom para prototipo`, `acoplado demais`
- Recomendacao:
  - transformar em modulo de branding / tone por clinica

### PR-03. `RB-SAFETY`
- Onde esta: `apps/api/app/ai_engine/response_builder.py`
- IA que usa: gerador do MVP
- Objetivo: restringir a assistente a respostas administrativas.
- Estrutura:
  - nao diagnosticar
  - nao orientar clinicamente
  - urgencia -> SAMU
  - duvida clinica -> humano
  - identificar-se como assistente virtual
- Variaveis dinamicas: nenhuma
- Dependencias: guardrails e politicas reais de negocio
- Riscos:
  - menciona referencia regulatoria inline
  - regras juridicas e de deploy ficam embedadas no codigo
- Avaliacao:
  - `forte em seguranca operacional`, `fraco em governanca`
- Recomendacao:
  - versionar separadamente e alinhar com politicas formais

### PR-04. `RB-BEHAVIOR`
- Onde esta: `apps/api/app/ai_engine/response_builder.py`
- IA que usa: gerador do MVP
- Objetivo: controlar estilo de resposta.
- Estrutura:
  - resposta curta
  - 1-2 emojis
  - nao inventar
  - confirmar antes de agir
- Variaveis dinamicas:
  - `acoes sugeridas`
  - contexto temporal
- Dependencias:
  - FARO brief
- Riscos:
  - regras inline e nao versionadas
- Avaliacao:
  - `ok para MVP`
- Recomendacao:
  - separar regras de estilo de regras de negocio

### PR-05. `RB-TEMPLATES`
- Onde esta: `apps/api/app/ai_engine/response_builder.py`
- IA que usa: fallback sem LLM
- Objetivo: manter atendimento basico quando nao houver provider configurado.
- Estrutura:
  - mapa `Intent -> string`
  - templates para saudacao, agendar, remarcar, cancelar, humano, confirmacao, desconhecida
- Variaveis dinamicas:
  - nome do paciente
  - entidades detectadas pelo FARO
  - melhor resultado RAG
- Dependencias:
  - FARO
  - `ConversationContext`
  - RAG opcional
- Riscos:
  - ainda parecem prompts/teste de MVP
  - linguagem e branding estaticos
- Avaliacao:
  - `parecem prototipo, nao camada final de producao`
- Recomendacao:
  - mover para templates versionados por dominio/canal/clinica

### PR-06. `NLU-SYSTEM`
- Onde esta: `src/inteliclinic/core/nlu/extractors/message_extractor.py`
- IA que usa: `InstructorMessageExtractor`
- Objetivo: extracao estruturada conservadora.
- Estrutura:
  - pede maxima precisao
  - proibe inferencia clinica
  - exige `is_ambiguous`
  - pede normalizacao de data ISO
  - preserva nomes de planos
  - exige `clarification_question` em pt-BR
- Variaveis dinamicas:
  - mensagem do paciente
  - contexto opcional
  - historico
- Dependencias:
  - schema `ExtractedMessage`
- Riscos:
  - taxonomia paralela ao FARO do runtime
  - sem unificacao com o resto do produto
- Avaliacao:
  - `bom tecnicamente`, `nao conectado`
- Recomendacao:
  - escolher se este passa a ser o extrator oficial

### PR-07. `GRAPH-RESPONSE-SYSTEM`
- Onde esta: `src/inteliclinic/core/ai_engine/nodes/response.py`
- IA que usa: `response_node`
- Objetivo: resposta final grounded do grafo.
- Estrutura:
  - assistente de clinica brasileira
  - ajuda em agendamentos, convenios, financeiro e duvidas gerais
  - regras inviolaveis
  - maximo de 200 palavras
  - proximo passo claro
- Variaveis dinamicas:
  - resumo de contexto estruturado
  - excerto de RAG
  - idioma do paciente
- Dependencias:
  - `ClinicState`
  - `rag_results`
  - contexto montado pelos nodes
- Riscos:
  - ignora `ClinicSettings.llm_model`
  - usa OpenAI hardcoded
- Avaliacao:
  - `bom como base arquitetural`, `incompleto como runtime`
- Recomendacao:
  - ler provider/model por configuracao

### PR-08. `CLINIC-ADDENDUM`
- Onde esta: `src/inteliclinic/clinic/prompts/base_prompts.py`
- IA que usa: arquitetura alvo por clinica
- Objetivo: adicionar contexto de especialidades, tom e regras locais.
- Estrutura:
  - `specialty_context`
  - `tone`
  - `additional_rules`
  - `insurance_notes`
  - `proactive_info`
- Variaveis dinamicas:
  - configuracao YAML/env da clinica
- Dependencias:
  - `ClinicPrompts`
- Riscos:
  - existe, mas sem wiring com o runtime real
- Avaliacao:
  - `boa direcao`, `nao operante`
- Recomendacao:
  - acoplar ao gerador real ou remover do marketing arquitetural

## 4.2. Prompts duplicados, contraditorios e frageis
- `response_builder.py` tem um conjunto completo de system prompt no MVP.
- `response.py` do grafo tem outro conjunto completo para o core.
- `ClinicPrompts` tenta ser terceira camada de customizacao.
- Resultado: ha pelo menos tres camadas conceituais de prompt sem uma cadeia unica oficial.
- O MVP fala explicitamente em "Clinica Minutare Med"; o core fala genericamente em "uma clinica medica brasileira".
- O MVP injeta RAG no prompt so para `DUVIDA_OPERACIONAL`; o orquestrador tambem consulta RAG para `POLITICAS`.
- Templates do MVP ainda parecem prototipo.
- `NLU-SYSTEM` e `RB-SAFETY` sao os trechos que mais se aproximam de algo reaproveitavel.

## 4.3. Recomendacao de arquitetura de prompts
- Uma arvore unica:
  1. prompt core de seguranca
  2. prompt de dominio (agendamento, FAQ, handoff, financeiro)
  3. addendum por clinica
  4. contexto dinamico (perfil, historico, RAG)
- Prompts devem sair do codigo hardcoded e ganhar:
  - versionamento
  - ambiente
  - clinica
  - canal
  - testes

---

## 5. Core de mudanca de informacoes para novas clinicas

## 5.1. Diagnostico geral
- Existe uma intencao arquitetural clara de multi-clinic em:
  - `src/inteliclinic/clinic/config/clinic_settings.py`
  - `src/inteliclinic/clinic/branding/brand.py`
  - `src/inteliclinic/clinic/prompts/base_prompts.py`
  - `config/examples/clinic.example.yaml`
  - `docs/clinic-onboarding/new-clinic.md`
- Porem o runtime real do MVP ainda nao consome essa camada.
- Resultado pratico:
  - para subir uma nova clinica hoje, a maior parte da adaptacao ainda seria manual.

## 5.2. O que muda quando uma nova clinica entra

| Item | Como esta hoje | Preparado? | O que teria de mudar |
| --- | --- | --- | --- |
| nome da clinica | hardcoded em backend/frontend/prompts | Nao | editar codigo e assets |
| branding | hardcoded no frontend e parte do backend | Parcial no core | ligar `ClinicBrand` ao runtime |
| especialidades | profissionais seed + lista do front | Nao | trocar seed, forms e KB |
| profissionais | seed hardcoded | Nao | reimportar dados reais |
| salas | nao modelado | Nao | criar dominio novo |
| agenda | global, sem tenant | Nao | adicionar `clinic_id` |
| procedimentos | nao modelado | Nao | criar dominio novo |
| convenios | KB textual e campo em paciente | Parcial | estruturar por clinica |
| produtos / estoque | nao modelado | Nao | criar modulo |
| canais de atendimento | Telegram real; outros placeholders | Parcial | configurar bot/canal novo |
| regras operacionais | prompt + KB hardcoded | Nao | externalizar |
| timezone | existe em `ClinicSettings` apenas | Parcial | ligar ao runtime |
| Google | nao implementado | Nao | criar integracao |
| WhatsApp/Telegram | Telegram apenas | Parcial | abstrair canal/credenciais |
| templates de mensagem | hardcoded | Nao | versionar por clinica |
| politicas de atendimento | prompt + KB hardcoded | Nao | externalizar |
| RAG base | unica, sem tenant | Nao | separar KB por clinica |
| dados institucionais | seed hardcoded | Nao | parametrizar |
| follow-up | inexistente | Nao | criar pipeline |
| permissoes e perfis | inexistentes | Nao | criar auth/RBAC |
| dominios/subdominios | docs existem, runtime nao usa | Parcial | alinhar env/CORS/deploy |
| envs por clinica | `CLINIC_*` existe no core | Parcial | conectar ao runtime real |

## 5.3. O que ja esta preparado para nova clinica
- `ClinicSettings` ja modela identidade, contato, features, LLM, RAG, horario, convenios e branding.
- `ClinicPrompts` ja modela prompt complementar por clinica.
- `QdrantStore` / `LlamaIndexStore` do core ja pensam em colecao por `clinic_id`.
- Docs de onboarding e deploy ja descrevem `CLINIC_*`.

## 5.4. O que hoje teria de ser alterado manualmente
- `apps/api/app/main.py` para titulo/logs
- `apps/api/app/ai_engine/response_builder.py` para nome/persona da clinica
- `scripts/seed_data.py` para profissionais, horarios, telefone, endereco, convenios e KB
- `frontend/src/app/layout.tsx` e `frontend/src/components/layout/sidebar.tsx` para branding
- textos do dashboard e placeholders de integracao
- qualquer documento existente em `rag_documents` se o seed ja tiver rodado

## 5.5. O que deveria virar configuracao
- nome curto e nome longo da clinica
- horarios e politicas
- convenios aceitos
- telefone, endereco, cidade, timezone
- chatbot greeting e tom
- modelo/provider por deploy
- KB e categorias
- canais habilitados
- CORS/dominios publicos
- cores/logo

## 5.6. O que deveria virar core global
- dominio paciente
- dominio agenda
- motor de handoff
- auditoria
- contratos de API
- validacao de seguranca e LGPD
- ciclo de embedding/retrieval
- auth/RBAC

## 5.7. O que deveria virar core por clinica
- branding
- mensagens de saudacao
- profissionais
- convenios
- horarios
- regras locais
- credenciais de canal
- KB documental
- dominio/subdominio
- politicas de agendamento e cancelamento

## 5.8. O que impede escalar hoje
- ausencia de `clinic_id`
- hardcodes de Minutare Med
- seed automatico com dados da primeira clinica
- ausencia de auth/RBAC
- ausencia de segregacao da KB
- frontend tambem acoplado a uma marca

## PLAYBOOK - O QUE MUDAR PARA SUBIR O SISTEMA EM UMA NOVA CLINICA

1. Criar `clinic_id` e tenantizar a base.
2. Parar de seedar Minutare Med no bootstrap padrao.
3. Externalizar branding e prompts.
4. Separar a knowledge base por clinica.
5. Parametrizar canais e credenciais.
6. Corrigir contratos do painel.
7. Criar auth minima antes de multi-clinic.
8. Carregar profissionais, agenda e KB por import oficial.

---

## 6. RAG - como esta sendo feito e qual e o gargalo

## 6.1. Onde existe RAG hoje
- Runtime real do MVP:
  - `apps/api/app/services/rag_service.py`
  - `apps/api/app/repositories/rag_repository.py`
  - `apps/api/app/api/routes/rag.py`
  - `AIOrchestrator._query_rag(...)`
- Scripts ligados ao runtime:
  - `scripts/seed_data.py`
  - `scripts/ingest_docs.py`
- Core futuro:
  - `src/inteliclinic/core/rag/*`
  - `scripts/evaluate_rag.py`

## 6.2. Onde deveria existir mas ainda nao existe de forma operacional
- KB separada por clinica no runtime principal
- pipeline de parser de arquivos no runtime principal
- reranking
- citacao/grounding robusto
- governanca de atualizacao/versionamento real
- GraphRAG

## 6.3. Fluxos de RAG encontrados

### RAG-01. RAG do MVP em PostgreSQL/pgvector
- Nome/area: FAQ e duvidas operacionais do atendimento
- Objetivo: responder perguntas administrativas e de politicas da clinica
- Fonte de dados:
  - `POST /api/v1/rag/ingest`
  - `scripts/seed_data.py`
  - `scripts/ingest_docs.py`
- Pipeline de ingestao:
  1. cria `RagDocument`
  2. faz `chunk_text` por caracteres
  3. tenta embedding por OpenAI ou Gemini
  4. persiste `RagChunk`
- Estrategia de chunk:
  - tamanho fixo de caracteres
  - `settings.rag_chunk_size`
  - overlap `settings.rag_chunk_overlap`
- Embedding/modelo:
  - OpenAI `text-embedding-3-small`
  - Gemini `text-embedding-004`
- Base de armazenamento:
  - tabelas `rag_documents` e `rag_chunks`
  - vetor em pgvector
- Estrategia de busca:
  - cosine similarity em SQL
  - fallback textual `ILIKE`
- Filtros:
  - apenas `category`
  - nenhum filtro por tenant/clinica
- Como injeta contexto no prompt:
  - no fluxo LLM, `response_builder` prefixa ate 3 documentos em `## DOCUMENTOS RELEVANTES (RAG)`
  - no fluxo sem LLM, usa o primeiro chunk e anexa `Fonte`
- Como evita alucinacao:
  - parcialmente, pelo prompt e pelo uso do chunk
  - nao ha validacao/citacao formal
- Limitacoes atuais:
  - ingestao so textual
  - sem tenant
  - sem reranker
  - sem politica de atualizacao
- Gargalos atuais:
  - governanca e separacao por clinica
  - qualidade documental e nao apenas retrieval

### RAG-02. Ingestao markdown offline
- Nome/area: ingestao de docs locais
- Objetivo: popular a base com markdowns de apoio
- Fonte de dados:
  - diretorio `GUIAS-DEV` por padrao
- Pipeline de ingestao:
  1. abre `.md`
  2. quebra por `##`
  3. classifica categoria por regex
  4. salva via DB ou API
- Estrategia de chunk:
  - fixa, 500 com overlap 100 no modo DB
- Embedding/modelo:
  - no modo DB nao gera embedding
  - no modo API depende do runtime
- Base de armazenamento:
  - Postgres do MVP
- Estrategia de busca:
  - herdada do runtime
- Filtros:
  - categoria apenas
- Como injeta contexto no prompt:
  - indireto, via runtime
- Como evita alucinacao:
  - nao evita diretamente
- Limitacoes atuais:
  - ingestao de markdown local apenas
  - sem metadata de clinica
- Gargalos atuais:
  - qualidade e governanca da fonte

### RAG-03. RAG do core Qdrant/LlamaIndex
- Nome/area: arquitetura alvo por clinica
- Objetivo: KB por colecao/tenant com retrieval melhor estruturado
- Fonte de dados:
  - documentos parseados por Docling/Markdown parser
- Pipeline de ingestao:
  1. seleciona parser
  2. parseia documento
  3. aplica enrichers
  4. chunka
  5. deveria embedar e fazer upsert
  6. etapa 5 esta em TODO
- Estrategia de chunk:
  - `TextChunker` ou `SemanticChunker`
- Embedding/modelo:
  - OpenAI embeddings via LlamaIndex store
- Base de armazenamento:
  - Qdrant por `clinic_id`
- Estrategia de busca:
  - dense
  - hibrido planejado
- Filtros:
  - `clinic_id`
  - `doc_type_filter`
- Como injeta contexto no prompt:
  - `ClinicQueryEngine` e `response_node` do grafo
- Como evita alucinacao:
  - grounding por excerto + contexto estruturado
- Limitacoes atuais:
  - ingestao nao conclui indexacao
  - sparse retriever vazio
  - fora do runtime principal
- Gargalos atuais:
  - pipeline incompleta
  - falta de wiring com produto real

## 6.4. Respostas objetivas para as perguntas centrais de RAG
- O RAG esta sendo feito de forma generica ou por dominio?
  - runtime atual: generico por `category`
  - core futuro: tenta organizar por tipo de documento e por clinica
- Ha separacao por clinica?
  - runtime atual: nao
  - core futuro: sim no desenho
- Ha separacao por modulo?
  - runtime atual: so por `category`
  - core futuro: parcialmente
- Ha controle de atualizacao?
  - runtime atual: praticamente nao
  - campo `version` existe, mas sem governanca real
- O gargalo e ingestao, embeddings, retrieval, contexto, qualidade documental, custo, latencia, arquitetura ou governanca?
  - principal gargalo atual: `governanca + tenantizacao + acoplamento da KB`

## DIAGNOSTICO FINAL DO RAG
- O que ja esta bom:
  - ha um caminho real de ingestao e consulta no MVP
  - pgvector com fallback textual da um minimo de funcionalidade
  - o core futuro tem boa direcao para colecao por clinica
- O que esta fraco:
  - chunking simples por caractere
  - sem tenant
  - sem citacao forte
  - sem reranking
  - sem governanca de atualizacao
- O que esta improvisado:
  - seed de documentos da Minutare Med
  - ingestion script para `GUIAS-DEV`
  - uso de `category` como unico recorte semantico
- O principal gargalo:
  - a KB do runtime ainda nao e modelada como conhecimento por clinica
  - a ingestao e pouco governada
  - a separacao entre MVP real e core futuro gera duas historias de RAG concorrentes
- O que precisa mudar primeiro:
  1. tenantizar `rag_documents` e `rag_chunks` no runtime real ou concluir a migracao para Qdrant por clinica
  2. retirar docs hardcoded do seed automatico
  3. definir pipeline oficial de ingestao por tipo de documento
  4. corrigir como o contexto RAG entra nas respostas de todas as intents relevantes
  5. instituir versionamento/governanca da KB

---

## 7. Discrepancias entre docs e codigo

- `README.md` e varios docs vendem Qdrant/LlamaIndex/LangGraph como stack ativa, mas o runtime real usa `apps/api` + pgvector.
- `docs/API_MAP.md` nao reflete todas as rotas realmente implementadas.
- `docs/RUNBOOK.md` menciona lacunas que ja nao batem com o codigo atual, como ausencia de certos CRUDs e testes.
- `docs/deployment/dedicated-deploy.md` aponta para formas de uso e classes que nao batem exatamente com o codigo da integracao Telegram atual.

---

## 8. Conclusao tecnica

- O projeto tem um MVP funcional de atendimento administrativo por Telegram.
- O que ja existe de verdade e suficiente para uma primeira operacao controlada, mas nao para multi-clinic escalavel.
- As maiores dividas tecnicas para a proxima fase sao:
  - tenantizacao
  - auth/RBAC
  - desacoplamento de branding e dados de clinica
  - unificacao do caminho oficial de IA e RAG
  - correcoes de contrato frontend/backend
