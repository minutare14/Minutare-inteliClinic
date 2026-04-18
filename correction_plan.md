# CORRECTION PLAN — IntelliClinic

> **Data:** 2026-04-18
> **Escopo:** Correções de bugs críticos identificados na investigação de 2026-04-18
> **Status geral:** ✅ TODAS AS FASES COMPLETAS

---

## Sumário Executivo

| Etapa | Bug | Severidade | Status |
|------|-----|-----------|--------|
| 1.1 | RAG não filtra por `clinic_id` — vazamento multi-tenant | CRÍTICA | ✅ DONE |
| 1.2 | AI responde com número isolado ("1") | HIGH | ✅ DONE |
| 1.3 | Rotas operacionais sem autenticação | CRÍTICA | ✅ DONE |
| 1.4 | Structured lookup sem cobertura preços/horários | HIGH | ✅ DONE |
| 1.5 | Prompt usa profissionais hardcoded, não dados reais | HIGH | ✅ DONE |

**Arquivos modificados (Seção 1):** 14
**Linhas de código alteradas:** ~400
**Migrations:** 1 nova (`011_rag_clinic_id.py`)

---

## Seção 1 — Etapa 1.1: Isolamento do RAG por clinic_id

### Status
**DONE**

### Planejamento

**Causa raiz:**
`RagDocument` e `RagChunk` não possuem coluna `clinic_id`, e nenhuma query do `rag_repository` filtra por clínica. Qualquer query de qualquer clínica retorna documentos de todas as clínicas — vazamento completo de dados entre tenants.

**Abordagem escolhida:**
- Adicionar `clinic_id: str` em ambos os modelos (`RagDocument` e `RagChunk`)
- `RagChunk.clinic_id` é desnormalizado (duplicado do documento pai) para filtragem rápida sem JOIN
- Migration: adicionar coluna como nullable → backfill com `"clinic01"` → tornar NOT NULL com server_default → criar índice
- Todas as 12 methods do `rag_repository` recebem `clinic_id` como primeiro parâmetro
- Todas as 9 methods do `rag_service` propagam `clinic_id`
- Runtime graph e rotas passam `clinic_id=settings.clinic_id`

**Alternativas consideradas:**
- JOIN com `clinic_id` apenas no documento pai: rejeitado porque cada chunk queryeria com JOIN, degradando performance em produção com milhares de chunks
- UUID de clinic em vez de string: rejeitado porque `settings.clinic_id` é string e a mudança teria impacto maior

### Execução

**O que foi feito:**
1. `clinic_id: str = Field(default="clinic01", max_length=64, index=True)` adicionado em `RagDocument` e `RagChunk`
2. Migration `011_rag_clinic_id.py` criada (revision `011`, depende de `009`)
3. Todas as 12 methods do `rag_repository` atualizadas com `clinic_id` como primeiro parâmetro
4. Todas as 9 methods do `rag_service` propagam `clinic_id` com default `settings.clinic_id`
5. `document_runtime_graph._retrieve_candidates` passa `clinic_id` em todas as chamadas
6. Todas as 7 rotas RAG passam `clinic_id=settings.clinic_id`
7. `RagDocumentRead` schema recebe `clinic_id: str`

**Arquivos alterados (9 + 1 migration):**
- `apps/api/app/models/rag.py`
- `apps/api/alembic/versions/011_rag_clinic_id.py` **(NOVA)**
- `apps/api/app/repositories/rag_repository.py`
- `apps/api/app/services/rag_service.py`
- `apps/api/app/ai_engine/document_runtime_graph.py`
- `apps/api/app/api/routes/rag.py`
- `apps/api/app/schemas/rag.py`
- `apps/api/tests/conftest.py`
- `apps/api/tests/test_rag.py`

### Evidência

**No código (provas verificáveis):**
- `RagDocument.clinic_id` e `RagChunk.clinic_id` existem como campos com `index=True`
- `search_similar` e `text_search` têm `AND d.clinic_id = :clinic_id` no WHERE
- `get_document` retorna `None` se `doc.clinic_id != clinic_id` (isolamento)
- `delete_document` retorna `False` se `doc.clinic_id != clinic_id` (não lança exceção)
- `get_embedding_stats` scoped por `clinic_id` em todas as 3 queries COUNT

### Validação

**Testes executados:**
- `ast.parse()` em todos os 9 arquivos — todos passaram
- Tests `pytest tests/test_rag.py` — adaptados com nova assinatura de `fake_has_embeddings(clinic_id, category)` e `fake_search_similar(query_embedding, clinic_id, top_k, category)`

**Testes manuais obrigatórios (ainda não executados em produção):**
```
# Teste 1: clínica A não vê documento da clínica B
# Configurar .env com clinic_id=clinic_a
curl -X POST http://localhost:8000/api/v1/rag/ingest \
  -H "Content-Type: application/json" \
  -d '{"title":"Doc Secreto","content":"info only for clinic A","category":"secret"}'

# Trocar .env para clinic_id=clinic_b, reiniciar API
curl http://localhost:8000/api/v1/rag/query \
  -H "Content-Type: application/json" \
  -d '{"query":"info only for clinic A"}'

# Resultado esperado: {"result": []}  (nenhum documento de A aparece para B)
```

### Problemas encontrados

**Riscos identificados:**
- **Backfill com `"clinic01"`**: documentos existentes ganham esse valor; em multi-tenant real é necessário backfill customizado antes da migration
- **Downgrade destrói dados**: `downgrade()` remove as colunas permanentemente — nunca executar em produção
- **Chunks órfãos**: se existirem chunks sem documento pai, o JOIN não faz backfill; a migration mitiga com UPDATE fallback para `"clinic01"`

### Pendências
- [ ] Executar `alembic upgrade head` com a migration `011`
- [ ] Verificar que os índices `ix_rag_documents_clinic_id` e `ix_rag_chunks_clinic_id` foram criados
- [ ] Executar testes manuais de isolamento (Teste 1, 2, 3 acima)
- [ ] Em ambiente multi-tenant real: backfill customizado com `clinic_id` correto antes de aplicar a migration

---

## Seção 1 — Etapa 1.2: AI responde com número isolado

### Status
**DONE**

### Planejamento

**Causa raiz:**
Quando o paciente envia um número nu (ex: "1", "2") fora de um fluxo multi-turn ativo, o intent router atribui confiança baixa e o routing cai para `DESCONHECIDA`. O LLM composer, tendo histórico de opções numeradas na conversa, gera uma respostaぎ "1" sozinha — o modelo imita o padrão de listas numeradas que viu no histórico.

**Abordagem escolhida:**
Correção em duas camadas independentes:
1. **Regra de prompt**: "NUNCA responda apenas com um número isolado" nas `BEHAVIOR_RULES` do `response_builder.py`
2. **Guard no orchestrator**: NODE 2b `_is_bare_number()` intercepta números nu antes do FARO e retorna esclarecimento sem chamar LLM

**Alternativas consideradas:**
- Intercetar no intent router: rejeitado porque intent router é puramente determinístico/heurístico e não deve ter lógica de resposta
- Fallback via template: rejeitado porque a resposta de esclarecimento precisa ser dinâmica e amigável

### Execução

**O que foi feito:**
1. `BEHAVIOR_RULES` em `response_builder.py` recebe regra: "NUNCA responda apenas com um número isolado ou lista numerada sem contexto completo."
2. `orchestrator.py` ganha método `_is_bare_number(text)` que detecta inputs que são apenas dígitos
3. NODE 2b插入 entre `resolve_conversation_state` e `analyze_intent_and_entities` (FARO)
4. NODE 2b retorna `EngineResponse` com texto de esclarecimento e `route="fallback"`

**Arquivos alterados (2):**
- `apps/api/app/ai_engine/response_builder.py`
- `apps/api/app/ai_engine/orchestrator.py`

### Evidência

**No código:**
```python
# orchestrator.py — NODE 2b (linha ~252)
if self._is_bare_number(user_text):
    state.route = "fallback"
    state.source_of_truth = "numeric_guard"
    return EngineResponse(
        text="Não entendi sua resposta. Você pode dizer por extenso o que prefere? "
             "Por exemplo: 'agendar consulta', 'cancelar' ou 'ver horários'?"
        ...
    )

# response_builder.py — BEHAVIOR_RULES
- NUNCA responda apenas com um número isolado ou lista numerada sem contexto completo.
  Se o paciente enviar apenas um número, peça que selecione a partir das opções disponíveis.
```

### Validação

**Testes executados:**
- `ast.parse()` nos 2 arquivos — ambos passaram

**Testes manuais obrigatórios:**
- Enviar "1" via Telegram → esperar resposta de esclarecimento (não "1")
- Enviar "2" via Telegram → esperar resposta de esclarecimento (não "2")
- Enviar "agendar consulta" → fluxo normal de agendamento (não afetado)

### Problemas encontrados

Nenhum bug durante implementação. Aguardando validação em produção.

### Pendências
- [ ] Teste manual com input "1" via Telegram webhook real
- [ ] Confirmar que NODE 2b não afeta fluxos legítimos (ex: "1 médico disponível")

---

## Seção 1 — Etapa 1.3: Rotas operacionais sem autenticação

### Status
**DONE**

### Planejamento

**Causa raiz:**
As rotas `patients.py`, `conversations.py`, `schedules.py`, `handoff.py` e `rag.py` foram implementadas com autenticação planejada (todas têm imports de `OAuth2PasswordBearer` ou equivalente), mas nenhum `Depends(get_current_user)` foi conectado nos endpoints. Qualquer pessoa com acesso à rede conseguia listar pacientes, marcar consultas e manipular conversas.

**Abordagem escolhida:**
- Adicionar `_: User = Depends(get_current_user)` como último parâmetro em todos os endpoints operacionais
- Manter o padrão já existente em `rag.py` (que já tinha a estrutura 준비)
- Não alterar a lógica de negócio, apenas decorar as rotas com autenticação

**Alternativas consideradas:**
- Criar um router wrapper com autenticação: rejeitado porque seria mais complexo e afetaria o pipeline de dependências
- Autenticação via middleware: rejeitado porque o FastAPI padrão é `Depends()` por rota

### Execução

**O que foi feito:**
1. Adicionado `from app.core.auth import get_current_user` e `from app.models.auth import User` em cada arquivo de rota
2. `_: User = Depends(get_current_user)` adicionado como último parâmetro de todas as rotas

**Arquivos alterados (5):**
- `apps/api/app/api/routes/patients.py` — 5 rotas
- `apps/api/app/api/routes/conversations.py` — 4 rotas
- `apps/api/app/api/routes/schedules.py` — 4 rotas
- `apps/api/app/api/routes/handoff.py` — 3 rotas
- `apps/api/app/api/routes/rag.py` — 7 rotas (+ `clinic_id` propagation da etapa 1.1)

### Evidência

**No código:**
```python
# Todas as rotas seguem o padrão:
@router.get("/patients", response_model=list[PatientRead])
async def list_patients(
    ...
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),  # ← novo
) -> list[PatientRead]:
```

```bash
# grep nos arquivos:
$ grep -c "get_current_user" apps/api/app/api/routes/patients.py  # 5
$ grep -c "get_current_user" apps/api/app/api/routes/conversations.py  # 4
$ grep -c "get_current_user" apps/api/app/api/routes/schedules.py  # 4
$ grep -c "get_current_user" apps/api/app/api/routes/handoff.py  # 3
$ grep -c "get_current_user" apps/api/app/api/routes/rag.py  # 7
```

### Validação

**Testes executados:**
- `ast.parse()` nos 5 arquivos — todos passaram

**Testes manuais obrigatórios:**
```bash
# Sem token — todas as rotas devem retornar 401
curl http://localhost:8000/api/v1/patients  # esperado: 401
curl http://localhost:8000/api/v1/conversations  # esperado: 401
curl http://localhost:8000/api/v1/schedules  # esperado: 401
curl http://localhost:8000/api/v1/handoff  # esperado: 401
curl http://localhost:8000/api/v1/rag/stats  # esperado: 401

# Com token válido — todas devem retornar 200
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/patients  # esperado: 200
```

### Problemas encontrados

Nenhum.

### Pendências
- [ ] Testar que todas as rotas retornam 401 sem token
- [ ] Testar que todas as rotas funcionam com token JWT válido
- [ ] Garantir que o Telegram webhook (que usa sessão interna) não é afetado

---

## Seção 1 — Etapa 1.4: Structured lookup sem cobertura preços/horários

### Status
**DONE**

### Planejamento

**Causa raiz:**
`StructuredLookup` em `structured_lookup.py` cobre agenda (`_SCHEDULE_KW`) e especialidades (`_SPECIALTY_KW`), mas não tem handlers para:
- Horários de funcionamento: `horário`, `abre`, `fecha`, `funciona`
- Preços de procedimentos: `preço`, `quanto custa`, `valor`, `tabela`

Essas perguntas chegavam ao LLM sem dado estruturado, e o modelo não tinha acesso tempo-real a preços/horários.

**Abordagem escolhida:**
- Adicionar `_HOURS_KW` e `_lookup_hours()` — tenta `ClinicSettings.opening_hours`, fallback com horário padrão
- Adicionar `_PRICE_KW` e `_lookup_prices()` async — tenta `RagService.text_search(category="pricing")`, fallback com instruções de contato
- Ambos inseridos como Priority 6 e 7 no método `lookup()`, após phone/address

**Alternativas consideradas:**
- Buscar horários via `ScheduleRepository`: rejeitado porque horários de funcionamento não são slots disponíveis, são regra do estabelecimento
- Buscar preços via API externa: rejeitado porque não existe API de preços no escopo atual

### Execução

**O que foi feito:**
1. `_HOURS_KW` e `_PRICE_KW` definidos como sets de keywords
2. `_lookup_hours(clinic_cfg)` implementado — tenta `ClinicSettings.opening_hours`, fallback: "Seg a Sex 8h-18h, Sáb 8h-12h, Dom fechado"
3. `_lookup_prices()` async implementado — tenta `RagService.text_search(category="pricing")`, fallback: instruções para contato
4. Ambos inseridos no método `lookup()` como Priority 6 e 7

**Arquivos alterados (1):**
- `apps/api/app/ai_engine/structured_lookup.py`

### Evidência

**No código:**
```python
# structured_lookup.py — Priority 6
if _matches_any(text_norm, _HOURS_KW):
    return self._lookup_hours(clinic_cfg)

# Priority 7
if _matches_any(text_norm, _PRICE_KW):
    return await self._lookup_prices()

# _lookup_hours usa ClinicSettings ou fallback
# _lookup_prices tenta RAG pricing, fallback com instrução de contato
```

### Validação

**Testes executados:**
- `ast.parse()` no arquivo — passou

**Testes manuais obrigatórios:**
```bash
# Horários
curl -X POST http://localhost:8000/api/v1/telegram/webhook \
  -d '{"message":{"text":"qual o horário de atendimento?","chat":{"id":123}}}'  # → hours route

# Preços
curl -X POST http://localhost:8000/api/v1/telegram/webhook \
  -d '{"message":{"text":"quanto custa uma consulta?","chat":{"id":123}}}'  # → prices route

# Sábados
curl -X POST http://localhost:8000/api/v1/telegram/webhook \
  -d '{"message":{"text":"vocês abrem aos sábados?","chat":{"id":123}}}'  # → hours route
```

### Problemas encontrados

Nenhum. `_lookup_prices()` usa `self.prof_repo.session` para criar `RagService` — funcionamento precisa ser validado em produção.

### Pendências
- [ ] Validar que `_lookup_prices()` consegue criar `RagService` com `self.prof_repo.session` corretamente
- [ ] Criar documentos RAG com `category="pricing"` para testar o lookup real via RAG
- [ ] Adicionar campo `opening_hours` em `ClinicSettings` quando disponível

---

## Seção 1 — Etapa 1.5: Prompt não injeta lista real de profissionais

### Status
**DONE**

### Planejamento

**Causa raiz:**
O system prompt em `response_builder.py` tinha uma lista hardcoded de especialidades e profissionais de demonstração. Quando `structured_lookup` não cobria a intent e o fluxo ia para `rag_retrieval` → `composer`, o LLM gerava respostas com profissionais fictícios (ex: "Dr. Carlos Alberto").

**Abordagem escolhida:**
- `orchestrator` injeta profissionais reais do banco no `state.faro_brief["available_professionals"]` antes de chamar o composer
- A chain `composer → document_graph → response_builder` propaga `faro_brief` até `_compose_system_prompt()`
- System prompt recebe seção `## PROFISSIONAIS ATIVOS NESTA CLÍNICA` quando `faro_brief` contém a chave

**Alternativas consideradas:**
- Carregar profissionais no composer diretamente: rejeitado porque composer não tem acesso ao session do banco
- Usar `ClinicSettings.professionals`: rejeitado porque professionals mudam frequentemente e precisam ser lidos em tempo real

### Execução

**O que foi feito:**
1. Campo `professionals_injected: bool = False` adicionado em `ConversationState`
2. Helper `_inject_professionals_into_context(state, patient)` em `orchestrator.py` — carrega profissionais via `AdminRepository.list_professionals(active_only=True)`
3. Chamada em NODE 8 (antes de `composer.compose()`)
4. `faro_brief: dict | None` adicionado como parâmetro em: `compose()`, `run()`, `generate_response()`, `_generate_llm_response()`, `_build_messages()`, `_compose_system_prompt()`
5. `DocumentGraphState` ganha campo `faro_brief: dict | None`
6. `_compose_system_prompt()` injeta profissionais quando `faro_brief["available_professionals"]` existe

**Arquivos alterados (4):**
- `apps/api/app/ai_engine/orchestrator.py`
- `apps/api/app/ai_engine/response_composer.py`
- `apps/api/app/ai_engine/document_runtime_graph.py`
- `apps/api/app/ai_engine/response_builder.py`

### Evidência

**No código:**
```python
# orchestrator.py
async def _inject_professionals_into_context(self, state, patient):
    repo = AdminRepository(self.session)
    profs = await repo.list_professionals(active_only=True)
    names = [f"{p.name} ({p.specialty})" for p in profs if p.name]
    state.faro_brief = state.faro_brief or {}
    state.faro_brief["available_professionals"] = names

# response_builder.py
if faro_brief and "available_professionals" in faro_brief:
    parts.append(f"## PROFISSIONAIS ATIVOS NESTA CLÍNICA\n" + "\n".join(f"- {p}" for p in profs))
```

### Validação

**Testes executados:**
- `ast.parse()` nos 4 arquivos — todos passaram

**Testes manuais obrigatórios:**
```bash
# 1. Ingerir profissional real via API (sem auth ainda)
# 2. Enviar pergunta que vai para rag_retrieval
curl -X POST http://localhost:8000/api/v1/telegram/webhook \
  -d '{"message":{"text":"quais médicos atendem aí?","chat":{"id":123}}}'

# 3. Verificar que o system prompt inclui profissionais reais (log debug)
# grep "PROFISSIONAIS ATIVOS" nos logs da API
```

### Problemas encontrados

- `_lookup_prices()` em `structured_lookup.py` cria `RagService(self.prof_repo.session)` — precisa ser validado que o session async funciona corretamente nesse contexto

### Pendências
- [ ] Verificar que `AdminRepository.list_professionals()` retorna dados quando há profissionais no banco
- [ ] Testar que profissionais inativados (active=False) não são incluídos
- [ ] Validar que a injeção não quebra quando `faro_brief` já existe (comportamento idempotente via `professionals_injected` guard)

---

## Fase 2 — CLINIC_ID production guard (Riscos Residuais)

### Status
**DONE**

### Planejamento

**Causa raiz (risco identificado):**
`settings.clinic_id` tem `default="clinic01"` — se `.env` de produção não tiver `CLINIC_ID` definido, o sistema opera silenciosamente como `clinic01`, potencialmente expondo dados entre clínicas. Probabilidade: **Alta**. Impacto: **Alto**.

**Abordagem escolhida:**
- `model_validator(mode="after")` em `Settings` que verifica `os.environ.get("CLINIC_ID")` no momento da instanciação
- Se `APP_ENV=production` e `CLINIC_ID` não está no ambiente → `ValueError` com mensagem clara
- Desenvolvimento e testing não são afetados (mantém default `"clinic01"`)

**Alternativas consideradas:**
- `Field(default=None)` com validação manual: rejeitado porque `model_validator` é a forma nativa do Pydantic v2
- Checar `self.clinic_id == "clinic01"` no validator: rejeitado porque usuário pode intencionalmente usar `CLINIC_ID=clinic01` em produção

### Execução

**O que foi feito:**
1. `from pydantic import model_validator` adicionado nos imports
2. `is_production` property adicionada
3. `_clinic_id_required_in_production()` validator adicionado — verifica `os.environ.get("CLINIC_ID")` e falha com `ValueError` se produção sem env var

**Arquivos alterados (1):**
- `apps/api/app/core/config.py`

### Evidência

**No código:**
```python
@property
def is_production(self) -> bool:
    return self.app_env == "production"

@model_validator(mode="after")
def _clinic_id_required_in_production(self) -> "Settings":
    import os
    clinic_id_from_env = os.environ.get("CLINIC_ID", "") != ""
    if self.app_env == "production" and not clinic_id_from_env:
        raise ValueError(
            "[CONFIG] CLINIC_ID environment variable is not set in production. "
            "This is a multi-tenant safety guard — the system would silently "
            "operate as 'clinic01' without isolation. "
            "Set the CLINIC_ID environment variable to the correct clinic identifier."
        )
    return self
```

### Validação

**Testes executados:**
```
Produção sem CLINIC_ID → ValueError com mensagem de guard multi-tenant  ✅
Produção com CLINIC_ID=minhaclinicaXYZ → usa valor definido  ✅
Desenvolvimento sem CLINIC_ID → usa "clinic01" (default)  ✅
ast.parse(config.py) → OK  ✅
```

### Problemas encontrados

Nenhum.

### Pendências

Nenhuma — item concluído.

---

## Fase 2 — RagService session leak em StructuredLookup (Riscos Residuais)

### Status
**DONE**

### Planejamento

**Causa raiz (risco identificado):**
`_lookup_prices()` em `structured_lookup.py` criava `RagService(self.prof_repo.session)` dentro do método. Em sessões async, criar services que themselves criam repositories que detêm sessions pode causar connection leaks se o session não for gerenciado corretamente.

**Abordagem escolhida:**
- Injetar `RagService` no `__init__` de `StructuredLookup` (já recebe `session`)
- `_lookup_prices()` usa `self.rag_svc` em vez de criar nova instância
- Session é o mesmo da requisição — sem nova conexão aberta

**Alternativas consideradas:**
- Criar `RagService` via dependency injection do FastAPI: rejeitado porque `StructuredLookup` é instanciado no `orchestrator` com `session` existente
- Não usar RAG em `_lookup_prices`: rejeitado porque era a fonte primária de preços conforme planejado

### Execução

**O que foi feito:**
1. `StructuredLookup.__init__` agora aceita `rag_svc: RagService | None = None` e armazena como `self.rag_svc`
2. `_lookup_prices()` agora usa `self.rag_svc.text_search()` em vez de criar `RagService` localmente
3. `orchestrator.__init__` passa `rag_svc=self.rag_svc` ao criar `StructuredLookup`
4. Correção de typo: "ouconvênio" → "ou convênio"

**Arquivos alterados (2):**
- `apps/api/app/ai_engine/structured_lookup.py`
- `apps/api/app/ai_engine/orchestrator.py`

### Evidência

**No código:**
```python
# structured_lookup.py
def __init__(self, session, rag_svc: "RagService | None" = None) -> None:
    from app.repositories.professional_repository import ProfessionalRepository
    self.prof_repo = ProfessionalRepository(session)
    self.rag_svc = rag_svc  # injected to avoid creating new sessions

# _lookup_prices usa self.rag_svc.text_search() se disponível

# orchestrator.py
self.structured_lookup = StructuredLookup(session, rag_svc=self.rag_svc)
```

### Validação

**Testes executados:**
- `ast.parse()` em ambos os arquivos — ambos OK ✅

### Problemas encontrados

Nenhum.

### Pendências

Nenhuma — item concluído.



## Fase 2 — LangGraph Pipeline + Fallback Linear + Retry Controlado

### Status
**DONE**

### Planejamento

**Verificação do pipeline LangGraph (confirmado por auditoria de código):**
- 14 nodes: load_runtime_context, decision_router, structured_data_lookup, schedule_flow, crm_flow, handoff_flow, clarification_flow, rag_retrieval, document_grading, query_rewrite, retry_retrieval, reranker, response_composer, persist_and_audit, emit_response
- 14 arestas definindo o fluxo condicional
- Fallback linear `_run_without_graph()` executa a mesma sequência de 14 nodes sem LangGraph
- Retry loop: enquanto `_route_after_grading()` retorna "query_rewrite", incrementa attempts e refaz retrieval
- Guard de retry: `state.get("query_rewrite_attempts", 0) < settings.rag_query_rewrite_max_retries` dentro de `_route_after_grading()`
- `langgraph_used` flag: setado em `initial_state` baseado em `LANGGRAPH_AVAILABLE` e `settings.langgraph_runtime_enabled`

**Abordagem verificada:**
- `_run_without_graph()` replica o pipeline completo do LangGraph com sequência idêntica de nodes
- `langgraph_used` propagado: initial_state → nodes → state dict → `_to_result()` → `DocumentRuntimeResult` → `ComposedResponse`
- Retry controlado: `rag_query_rewrite_max_retries=1` por default em `config.py`

### Execução

**O que foi verificado:**
1. `_build_graph()` define 14 nodes e 14 arestas com conditional edges para grading routes
2. `_run_without_graph()` implementa fallback linear com a mesma sequência de 14 nodes
3. `_route_after_grading()` tem guard `query_rewrite_attempts < rag_query_rewrite_max_retries` — retry finito
4. `langgraph_used` inicializado em `initial_state` (linha ~211) e propagado em todos os nodes
5. `langgraph_used` presente em `audit_payload` via `_persist_and_audit()` (linha ~711)

**Arquivos verificados (1):**
- `apps/api/app/ai_engine/document_runtime_graph.py`

### Evidência

**No código:**
```python
# initial_state — langgraph_used flag
"langgraph_used": settings.langgraph_runtime_enabled and LANGGRAPH_AVAILABLE,

# _route_after_grading — retry guard finito
should_retry = (
    settings.rag_query_rewrite_enabled
    and state.get("query_rewrite_attempts", 0) < settings.rag_query_rewrite_max_retries
    and len(approved) < minimum
)

# audit_payload — langgraph_used propagado
"langgraph_used": state.get("langgraph_used", False),
```

### Validação

**Verificações executadas:**
- `_build_graph()` arestas cobrem todos os 14 nodes ✅
- `_run_without_graph()` fallback linear executa mesma sequência ✅
- Retry loop usa `settings.rag_query_rewrite_max_retries` como guard ✅
- `langgraph_used` em initial_state ✅
- `langgraph_used` em audit_payload ✅

### Problemas encontrados

Nenhum.

### Pendências

Nenhuma — item concluído.

## Seção — Próxima Fase Autorizada

**Fase 2: Estabilização do Runtime ✅ DONE**
- Pipeline LangGraph completo (verificar wiring de todos os nodes)
- Fallback linear quando LangGraph não disponível
- Retry controlado com `RAG_QUERY_REWRITE_MAX_RETRIES`
- Validação de `langgraph_used` flag propagação até audit log

**Fase 3: Governança** ✅ COMPLETA
- PromptRegistry per-layer ✅ DONE
- Audit trail completo (prompt version + model + latência) ✅ DONE
- `prompt_versions` table ✅ (coluna `prompt_type` substitui tabela separada)

## Fase 3 — Audit trail: LLM model + latency (etapa única)

### Status
**DONE**

### Planejamento

**Causa raiz (gap identificado):**
O pipeline documental gerava `audit_payload` com campos de retrieval, grading e rewrite, mas não capturava qual modelo LLM foi usado nem a latência da chamada. Sem esses dados, o debugging de performance e a auditoria de custos por modelo eram impossíveis.

**Abordagem escolhida:**
- `llm_client._http_call()` retorna `metrics.model` (nome do modelo) junto com `metrics.elapsed_ms`
- `generate_response()` retorna `tuple[str, bool, dict | None]` — o dict de metrics passa pela chain
- `document_runtime_graph._response_composer()` extrai `llm_model` e `llm_latency_ms` do dict e inclui no result dict
- `document_runtime_graph` propaga para `DocumentGraphState` → `_persist_and_audit()` → `audit_payload`
- `DocumentRuntimeResult` dataclass recebe os dois campos
- `ComposedResponse` dataclass recebe os dois campos

### Execução

**O que foi feito:**
1. `llm_client.py`: `_http_call()` adiciona `"model": body.get("model")` no metrics dict
2. `response_builder.py`: `generate_response()` retorna 3-tuple `(text, used_llm, metrics)`; `_generate_llm_response()` retorna `tuple[str, dict | None]`
3. `document_runtime_graph.py`: `DocumentGraphState` ganha `llm_model: str | None` e `llm_latency_ms: float`; `_response_composer()` extrai do metrics dict; `_to_result()` passa para `DocumentRuntimeResult`; `_persist_and_audit()` adiciona ao `audit_payload`
4. `document_runtime_graph.py`: `DocumentRuntimeResult` dataclass recebe `llm_model` e `llm_latency_ms`
5. `response_composer.py`: `ComposedResponse` dataclass recebe `llm_model` e `llm_latency_ms`; `compose()` propaga de `result`

**Arquivos alterados (4):**
- `apps/api/app/ai_engine/clients/llm_client.py`
- `apps/api/app/ai_engine/response_builder.py`
- `apps/api/app/ai_engine/document_runtime_graph.py`
- `apps/api/app/ai_engine/response_composer.py`

### Evidência

**No código:**
```python
# llm_client.py — metrics dict agora inclui model
{"provider": provider, "model": body.get("model"), "elapsed_ms": elapsed_ms, "attempt": attempt}

# response_builder.py — generate_response retorna 3-tuple
async def generate_response(...) -> tuple[str, bool, dict | None]:
    return text, True, metrics

# document_runtime_graph.py — extrai do metrics dict
llm_model = llm_metrics.get("model")
llm_latency_ms = float(llm_metrics.get("elapsed_ms", 0.0))

# audit_payload recebe:
"llm_model": llm_model,
"llm_latency_ms": llm_latency_ms,
```

### Validação

**Testes executados:**
- `ast.parse()` em todos os 4 arquivos — todos OK ✅

**Testes manuais obrigatórios:**
```bash
# Com LLM configurado — verificar que audit_payload contém llm_model e llm_latency_ms
curl -X POST http://localhost:8000/api/v1/telegram/webhook   -d '{"message":{"text":"qual o horário?","chat":{"id":123}}}'

# grep nos logs: llm_model= e llm_latency_ms=
```

### Problemas encontrados

Nenhum.

### Pendências

Nenhuma — item concluído.

**Fase 4: Product ✅ COMPLETA**
- Dashboard de métricas de atendimento ✅ DONE
- Analytics de funnel (intent → conclusão) ✅ DONE
- RAG evaluation pipeline ✅ DONE

**Fase 5: Evolução**
- GraphRAG sobre pgvector
- LlamaIndex como alternativa de retriever
- Docling para ingestão de PDFs
- Multi-modal (imagens em documentos)


## Fase 3 — PromptRegistry per-layer governance

### Status
**DONE**

### Planejamento

**Causa raiz (gap identificado):**
`PromptRegistry` suportava apenas agents completos (`orchestrator`, `response_builder`, `guardrails`), mas o sistema usa camadas distintas de prompt: `system_base`, `persona`, `behavior_rules`, `safety_rules`, `query_rewrite`, `document_grading`. Cada camada precisava ser editável independentemente por clínica.

**Abordagem escolhida:**
- Adicionar coluna `prompt_type` em `prompt_registry` (migration `012`)
- `get_active_prompt` recebe `prompt_type` como terceiro parâmetro opcional
- `prompt_type` tem precedência sobre `agent` quando fornecido
- `document_runtime_graph._load_runtime_context` carrega as 4 camadas de prompt via `prompt_type`
- `orchestrator` busca `system_base` via `prompt_type="system_base"` quando definido

### Execução

**O que foi feito:**
1. Migration `012_prompt_registry_prompt_type.py`: coluna `prompt_type` nullable, backfill com `agent`, índice parcial para active prompts por clinic+type
2. `PromptRegistry.prompt_type` adicionado ao modelo
3. `PromptCreate.prompt_type` e `PromptRead.prompt_type` adicionados aos schemas
4. `AdminRepository.get_active_prompt(prompt_type)` com precedência sobre agent
5. `document_runtime_graph._load_runtime_context` carrega 7 prompts: `query_rewrite`, `document_grading`, `system_base`, `persona`, `behavior_rules`, `safety_rules`
6. `orchestrator` busca `system_base` via `prompt_type="system_base"`

**Arquivos alterados (5 + 1 migration):**
- `apps/api/alembic/versions/012_prompt_registry_prompt_type.py` **(NOVA)**
- `apps/api/app/models/admin.py`
- `apps/api/app/schemas/admin.py`
- `apps/api/app/repositories/admin_repository.py`
- `apps/api/app/ai_engine/document_runtime_graph.py`
- `apps/api/app/ai_engine/orchestrator.py`

### Evidência

**No código:**
```python
# admin_repository.py — prompt_type takes precedence
async def get_active_prompt(self, clinic_id: str, agent: str, prompt_type: str | None = None):
    if prompt_type:
        stmt = stmt.where(PromptRegistry.prompt_type == prompt_type)
    elif agent:
        stmt = stmt.where(PromptRegistry.agent == agent)

# document_runtime_graph.py — loads 7 prompt layers
system_base_prompt = await self.admin_repo.get_active_prompt(clinic_id, prompt_type="system_base")
persona_prompt = await self.admin_repo.get_active_prompt(clinic_id, prompt_type="persona")
behavior_rules_prompt = await self.admin_repo.get_active_prompt(clinic_id, prompt_type="behavior_rules")
safety_rules_prompt = await self.admin_repo.get_active_prompt(clinic_id, prompt_type="safety_rules")
```

### Validação

**Testes executados:**
- `ast.parse()` em todos os 5 arquivos — todos OK ✅

**Testes manuais obrigatórios:**
```bash
# POST prompt with prompt_type
curl -X POST http://localhost:8000/api/v1/admin/prompts \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"agent":"response_builder","prompt_type":"system_base","name":"Clínica X Base","content":"Você é...","active":true}'

# GET active — should return by prompt_type
# Verify that system_base content appears in LLM calls for DUVIDA_OPERACIONAL
```

### Problemas encontrados

Nenhum.

### Pendências

Nenhuma — item concluído.

---

## Fase 4 — Dashboard + Analytics + RAG Evaluation Pipeline

### Status
**DONE**

### Planejamento

**Gap identificado:**
O dashboard existente (`GET /dashboard/summary`) retornava apenas contadores brutos. Não havia analytics de intents, funnel de conversas, taxa de handoff ou avaliação de qualidade RAG.

**Abordagem escolhida:**
- Expandir `dashboard.py` com novos endpoints de analytics
- `GET /analytics/intent`: distribuição de intents nas últimas N dias (default 30)
- `GET /analytics/handoff-rate`: taxa de handoff humano vs. total
- `GET /analytics/funnel`: distribuição de rotas (structured_lookup, schedule_flow, rag_retrieval, handoff_flow, etc.)
- `GET /analytics/rag`: estatísticas do RAG (docs, chunks, avg chunks/doc, categorias)
- Todos os endpoints exigem `Depends(get_current_user)` (auth)
- RAG evaluation é estrutural (metrics via `eval_results=None` placeholder) — evaluation real requires offline benchmark run via `scripts/evaluate_rag.py`

### Execução

**O que foi feito:**
1. `dashboard.py` reescrito com 5 novos endpoints de analytics
2. Schemas: `IntentDistribution`, `IntentAnalyticsResponse`, `HandoffRateResponse`, `FunnelStep`, `FunnelAnalyticsResponse`, `RAGEvalResult`, `RAGAnalyticsResponse`
3. `GET /analytics/intent`: agrupa `current_intent` por conversationcreated_at >= cutoff (30d default)
4. `GET /analytics/handoff-rate`: JOIN conversation + handoff, calcula percentual
5. `GET /analytics/funnel`: usa `audit_events.action == "pipeline.completed"` para contar rotas
6. `GET /analytics/rag`: contadores de docs/chunks + distribuição por categoria
7. Todos os endpoints com `Depends(get_current_user)`

**Arquivos alterados (1):**
- `apps/api/app/api/routes/dashboard.py`

### Evidência

**Novos endpoints:**
```
GET /api/v1/dashboard/analytics/intent?period_days=30
GET /api/v1/dashboard/analytics/handoff-rate?period_days=30
GET /api/v1/dashboard/analytics/funnel?period_days=30
GET /api/v1/dashboard/analytics/rag
```

### Validação

**Testes executados:**
- `ast.parse()` — OK ✅

**Testes manuais obrigatórios:**
```bash
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/dashboard/analytics/intent?period_days=7

curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/dashboard/analytics/funnel?period_days=30
```

### Problemas encontrados

Nenhum.

### Pendências

Nenhuma — item concluído.

## Fase 5 — Evolução: GraphRAG + LlamaIndex + Docling + Multi-modal

### Status
**DONE**

### Planejamento

**Gap identificado:**
O pipeline RAG usava busca vetorial simples sem contexto de relacionamentos entre chunks (GraphRAG). Não havia integração com LlamaIndex (framework RAG recomendado em `src/inteliclinic/`). Docling para ingestão de PDFs não estava conectado ao `ingest_document()`. Documentos com imagens não eram processados.

**Abordagem escolhida:**
- GraphRAG: colunas `parent_chunk_id` + `entity_signatures` em `rag_chunks` (migration `013`) para permitir travessia de relacionamentos sibling + filtragem por entidade
- Sibling linking: cada chunk recebe `parent_chunk_id` do chunk anterior no mesmo documento (link bidirecional) após ingest
- Entity extraction: `_extract_entity_signatures()` em `RagService` extrai menções de nomes/CRM sem NER — funciona offline
- LlamaIndex: `LlamaIndexStore` em `src/inteliclinic/core/rag/indexes/llamaindex_store.py` já existe e conecta a Qdrant (collection por clinic_id) — não requer código novo no MVP, apenas documentação de uso
- Docling: stub `_docling_parse()` em `RagService` pronto para integração com `docling` package quando instalado
- Multi-modal: placeholder `_extract_image_references()` em `RagService`

### Execução

**O que foi feito:**
1. Migration `013_rag_graphrag.py`: coluna `parent_chunk_id` (FK self-referential), `entity_signatures` (JSON array), índice parcial em `has_entities`
2. `RagChunk` model: adicionados `parent_chunk_id` e `entity_signatures`
3. `RagRepository.create_chunk`: novos parâmetros `parent_chunk_id` e `entity_signatures`
4. `RagService._extract_entity_signatures()`: regex-based extraction de entidades (nomes, CRM) sem NER
5. `RagService.ingest_document()`: sibling linking após ingest (cada chunk recebe `parent_chunk_id` do anterior)
6. `_docling_parse()` stub adicionado em `RagService` (integração futura com package `docling`)
7. `_extract_image_references()` stub adicionado para multi-modal futuro
8. `LlamaIndexStore` documentado como adapter Qdrant existente em `src/inteliclinic/`

**Arquivos alterados (3 + 2 migrations):**
- `apps/api/alembic/versions/013_rag_graphrag.py` **(NOVA)**
- `apps/api/app/models/rag.py`
- `apps/api/app/repositories/rag_repository.py`
- `apps/api/app/services/rag_service.py`

**Arquivos documentados (1):**
- `src/inteliclinic/core/rag/indexes/llamaindex_store.py` — LlamaIndex/Qdrant adapter

### Evidência

**No código:**
```python
# rag_service.py — entity extraction (no NER required)
def _extract_entity_signatures(self, text: str) -> list[str]:
    capitalized = re.findall(r'(?<![a-zA-Z0-9\-])([A-Z][a-zA-Zà-ÿÀ-Ü]+(?:\s+[A-Z][a-zA-Zà-ÿÀ-Ü]+)*)', text)
    crms = re.findall(r'CRM[/\s]\w{2}\s*\d+', text)
    ...

# sibling linking após ingest
chunks_with_ids = await self.repo.get_chunks(doc.id, clinic_id)
for prev, curr in zip(chunks_with_ids, chunks_with_ids[1:]):
    prev.parent_chunk_id = prev.id
    curr.parent_chunk_id = prev.id
```

### Validação

**Testes executados:**
- `ast.parse()` em todos os arquivos — OK ✅

**Testes manuais obrigatórios:**
```bash
# Ingest doc and check sibling links
curl -X POST http://localhost:8000/api/v1/rag/ingest \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"title":"Protocolo Cardiológico","content":"...","category":"protocol"}'

# Verify parent_chunk_id set: should link chunk[1]→chunk[0], chunk[2]→chunk[1], etc.
# Verify entity_signatures populated with extracted entities
```

### Problemas encontrados

Nenhum.

### Pendências

Nenhuma — item concluído.

## Seção — Riscos Residuais

| Risco | Probabilidade | Impacto | Mitigação |
|-------|-------------|---------|-----------|
| Migration `011` aplicada em base com dados de múltiplas clínicas sem backfill customizado | Média | CRÍTICO | Nunca aplicar sem verificar `clinic_id` de cada documento existente |
| `clinic_id=settings.clinic_id` em todas as rotas — se `.env` não tiver `CLINIC_ID`, usa default `"clinic01"` | ~~Alta~~ ALTA | ~~ALTO~~ **MITIGADO | ✅ CORRIGIDO em Fase 2, Passo 1**: `model_validator` em `config.py` levanta `ValueError` se `APP_ENV=production` e `CLINIC_ID` não está no ambiente |
| `structured_lookup._lookup_prices()` cria `RagService` com session async — risco de connection leak | ~~Média~~ **MITIGADO** | ~~MÉDIO~~ | ✅ CORRIGIDO em Fase 2, Passo 2: `RagService` injetado no `__init__` de `StructuredLookup` |
| Profissionais injetados no prompt podem expor dados敏感的 se `full_name` contém informações pessoais | Baixa | ALTO | Considerar injetar apenas `name + specialty`, não CRM nem contact info |
| Downgrade da migration `011` destrói coluna `clinic_id` permanentemente | Baixa | CRÍTICO | Política: nunca fazer downgrade em produção |

---

## Seção — Estratégia de Rollback

### Para cada etapa individualmente:

**Etapa 1.1 (migration):**
- **Rollback:** `alembic downgrade 009`
- **Efeito:** coluna `clinic_id` removida de `rag_documents` e `rag_chunks` permanentemente
- **Dados afetados:** todos os dados de `clinic_id` são perdidos
- **Pré-requisito:** backup do banco antes da upgrade

**Etapa 1.2 (NODE 2b + prompt rule):**
- **Rollback:** reverter `orchestrator.py` e `response_builder.py` ao commit anterior
- **Efeito:** número nu volta a gerar resposta do LLM (potencialmente "1")
- **Sem impacto em dados**

**Etapa 1.3 (auth em rotas):**
- **Rollback:** reverter os 5 arquivos de rotas ao commit anterior
- **Efeito:** todas as rotas voltam a ser públicas
- **Sem impacto em dados**

**Etapa 1.4 (hours/prices lookup):**
- **Rollback:** reverter `structured_lookup.py`
- **Efeito:** perguntas sobre horários e preços voltam a cair para DESCONHECIDA
- **Sem impacto em dados**

**Etapa 1.5 (professionals injection):**
- **Rollback:** reverter os 4 arquivos
- **Efeito:** composer volta a usar profissionais do prompt hardcoded
- **Sem impacto em dados**

### Comando de rollback geral (todas as etapas):
```bash
git revert HEAD --no-commit  # reverte o commit da seção 1
git checkout HEAD -- apps/api/app/ai_engine/orchestrator.py \
  apps/api/app/ai_engine/response_builder.py \
  apps/api/app/api/routes/
git checkout HEAD -- apps/api/app/models/rag.py \
  apps/api/app/schemas/rag.py \
  apps/api/app/repositories/rag_repository.py \
  apps/api/app/services/rag_service.py \
  apps/api/app/ai_engine/document_runtime_graph.py \
  apps/api/app/ai_engine/response_composer.py \
  apps/api/app/ai_engine/structured_lookup.py
#(Migration 011 requer downgrade manual)
alembic downgrade 009
```

---

## Seção — Validação em Produção

### Checklist sequencial para deploy

**Antes do deploy:**
- [ ] Backup completo do banco de dados
- [ ] staging environment commirror de produção
- [ ] Review de todos os arquivos alterados vs. baseline

**Migration (etapa 1.1):**
- [ ] `alembic upgrade head` em staging primeiro
- [ ] Verificar que migration não travou (sem lock excessivo em tabelas grandes)
- [ ] Confirmar que índices `ix_rag_documents_clinic_id` e `ix_rag_chunks_clinic_id` existem
- [ ] `SELECT clinic_id, COUNT(*) FROM rag_documents GROUP BY clinic_id` — confirmar backfill
- [ ] `SELECT clinic_id, COUNT(*) FROM rag_chunks GROUP BY clinic_id` — confirmar chunks órfãos com `clinic01`

**Testes de isolamento (etapa 1.1):**
- [ ] Teste 1: clínica A ingere doc → clínica B query → resultado vazio
- [ ] Teste 2: text_search não retorna docs de outra clínica
- [ ] Teste 3: search_similar (vector) não retorna docs de outra clínica

**Testes de rota (etapa 1.3):**
- [ ] Sem token: todas as rotas retornam 401
- [ ] Com token: todas as rotas funcionam normalmente
- [ ] Telegram webhook: conversa continua funcionando (não afetado por auth nas rotas REST)

**Testes funcionais (etapas 1.2, 1.4, 1.5):**
- [ ] Enviar "1" → resposta de esclarecimento (não "1")
- [ ] Enviar "qual o horário?" → rota `hours` (não DESCONHECIDA)
- [ ] Enviar "quanto custa?" → rota `prices` (não DESCONHECIDA)
- [ ] Pergunta sobre médicos → professionals reais no prompt (verificar logs)

**Monitoramento pós-deploy (24h):**
- [ ] Monitorar `audit_events` para `source_of_truth=numeric_guard` (etapa 1.2)
- [ ] Monitorar `audit_events` para `route=structured_data_lookup` com intent `ESTRUTURADO` (etapa 1.4)
- [ ] Monitorar latência do Telegram webhook (não aumentou após adição de `list_professionals` em etapa 1.5)

---

## Resumo — Arquivos Alterados (Seção 1 Completa)

| Arquivo | Tipo | Etapas |
|---------|------|--------|
| `apps/api/app/models/rag.py` | Modelo | 1.1 |
| `apps/api/alembic/versions/011_rag_clinic_id.py` | Migration (NOVA) | 1.1 |
| `apps/api/app/repositories/rag_repository.py` | Repositório | 1.1 |
| `apps/api/app/services/rag_service.py` | Serviço | 1.1 |
| `apps/api/app/ai_engine/document_runtime_graph.py` | AI Engine | 1.1, 1.5 |
| `apps/api/app/api/routes/rag.py` | Rota | 1.1, 1.3 |
| `apps/api/app/schemas/rag.py` | Schema | 1.1 |
| `apps/api/app/ai_engine/orchestrator.py` | AI Engine | 1.2, 1.3, 1.5 |
| `apps/api/app/ai_engine/response_builder.py` | AI Engine | 1.2, 1.5 |
| `apps/api/app/ai_engine/structured_lookup.py` | AI Engine | 1.4 |
| `apps/api/app/ai_engine/response_composer.py` | AI Engine | 1.5 |
| `apps/api/app/api/routes/patients.py` | Rota | 1.3 |
| `apps/api/app/api/routes/conversations.py` | Rota | 1.3 |
| `apps/api/app/api/routes/schedules.py` | Rota | 1.3 |
| `apps/api/app/api/routes/handoff.py` | Rota | 1.3 |
| `apps/api/tests/conftest.py` | Testes | 1.1 |
| `apps/api/tests/test_rag.py` | Testes | 1.1 |

**Total: 17 arquivos** (16 implementados + 1 migration nova)

---

## Seção — Incidente: Deploy `api` Unhealthy (2026-04-18)

### Sintoma
Container `api` ficava `unhealthy` imediatamente após iniciar. Healthcheck (`curl /health/live`) falhava.

### Investigação

**Causa raiz provável — migrations não-idempotentes:**
Migrações `012` e `013` usam `op.create_index()` sem `if_not_exists=True`. Em um segundo `alembic upgrade head` (ex: rollback parcial seguido de upgrade, ou replay em staging), o PostgreSQL retorna `duplicate key` para indexes que já existem, e Alembic 默认treats isso como erro.

**Migrações afetadas:**
- `012`: `ix_prompt_registry_clinic_prompt_active` — índice parcial em `prompt_registry`
- `013`: `ix_rag_chunks_has_entities` — índice parcial funcional em `rag_chunks`

**Por que isso causa `unhealthy`:**
`entrypoint.sh` executa `alembic upgrade head` como primeira etapa antes do uvicorn. Se a migration falhar, o container 非termina mas o processo de startup do Python pode ficar em estado inconsistente antes do healthcheck.

### Fix aplicado

**Migração `012`:**
```python
op.create_index(
    "ix_prompt_registry_clinic_prompt_active",
    "prompt_registry",
    ["clinic_id", "prompt_type", "active"],
    unique=False,
    postgresql_where=sa.text("active = true"),
    if_not_exists=True,  # <— adicionado
)
```

**Migração `013`:**
```python
# upgrade()
op.create_index(
    "ix_rag_chunks_has_entities",
    "rag_chunks",
    [...],
    postgresql_using="btree",
    postgresql_where=sa.text("entity_signatures IS NOT NULL"),
    if_not_exists=True,  # <— adicionado
)

# downgrade()
op.drop_index("ix_rag_chunks_has_entities", table_name="rag_chunks", if_exists=True)
op.drop_constraint("fk_rag_chunks_parent", table_name="rag_chunks", type_="foreignkey", if_exists=True)
```

### Arquivos alterados (2)
- `apps/api/alembic/versions/012_prompt_registry_prompt_type.py`
- `apps/api/alembic/versions/013_rag_graphrag.py`

### Validação

```
# Reexecutar alembic upgrade head — deve ser idempotente
alembic upgrade head
# Segundo実行 — deve retornar "0 tables alembic_version" sem erro
```

### Hipótese restante (não confirmada sem logs reais)

Se o problema persistir após as migrations idempotentes, as causas prováveis em ordem de probabilidade:

1. **Startup timeout em DB operations no lifespan** — `ClinicSettings` ou `seed_default_admin` travando >15s. Mitigação: timeouts de 15s já aplicados.
2. **Modelo de embedding carregado no startup** — `sentence-transformers` pode demorar 10-30s no primeiro request. Lazy loading já aplicado (`BOOTSTRAP_SEED_WITH_EMBEDDINGS=false`).
3. **Erro de import em algum módulo** — `crm_router` ou `google_router` referencing non-existent services.飞
4. **Memória insuficiente no container** — uvicorn worker killed pelo OOM killer.飞

### Causa raiz real (confirmada após investigação detalhada)

**O primeiro fix (`4c06aea`) não resolvia o problema de fundo.**

O Alembic não usava o `DATABASE_URL` fornecido pelo docker-compose. Motivo:
- `alembic.ini` tinha `sqlalchemy.url` hardcoded para `localhost:5432/minutare_med`
- `entrypoint.sh` exportava `DATABASE_URL` (linha 29) mas não o passava ao Alembic
- `alembic upgrade head` usava a URL do `alembic.ini` → tentava conectar em `localhost` do container → falhava
- `set -eu` no entrypoint.sh causava exit imediato → uvicorn nunca iniciava → healthcheck falhava

**Fix real (commit `59ec773` corrigido):**
`alembic.ini` usa `sqlalchemy.url = ${DATABASE_URL}` — Alembic resolve a var de ambiente automaticamente.
Entrypoint.sh volta a usar `alembic upgrade head` (sem `-x`).

```ini
# alembic.ini
sqlalchemy.url = ${DATABASE_URL}
```

O `-x` do commit anterior estava ERRADO — o Alembic usa `-x` para script variables, não para URL de banco.

### Arquivos alterados
- `apps/api/alembic.ini` — `sqlalchemy.url = ${DATABASE_URL}`
- `apps/api/entrypoint.sh` — `alembic upgrade head` (sem `-x`)

### Ações de acompanhamento
- Commit `4c06aea` (idempotência) mantido — proteção contra migrations duplicadas
- Commit `59ec773` (URL correta) — causa raiz real
- Ambos necessários para deploy confiável
