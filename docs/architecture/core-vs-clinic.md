# Arquitetura: Core Global vs Camada da Clínica

## Princípio fundamental

O InteliClinic é um **produto único com deploy dedicado por clínica**.

Isso significa:
- O repositório é **um único produto**, não um conjunto de projetos separados
- Cada clínica roda em sua **própria VPS**, com sua própria instância completa
- A separação é feita por **configuração**, não por fork de código
- **Não existe multi-tenancy em runtime**

> **Regra operacional:** Nova clínica = novo deploy da mesma base, com nova configuração local. Não é permitido criar uma nova base de código por cliente.

---

## O que é o Core Global

Tudo que pertence ao **produto** e é reutilizável em qualquer deploy de clínica.

**Localização:** `src/inteliclinic/core/`

| Módulo | Caminho | Responsabilidade |
|--------|---------|-----------------|
| AI Engine | `core/ai_engine/` | LangGraph: orquestração, grafos, nós, estado, HITL |
| NLU | `core/nlu/` | Instructor: extração estruturada de mensagens |
| RAG | `core/rag/` | LlamaIndex + Qdrant: indexação, retrieval, queries |
| Safety | `core/safety/` | Guardrails AI + regras CFM + validadores |
| Analytics | `core/analytics/` | PyOD: detecção de glosas e anomalias financeiras |
| Evaluation | `core/evaluation/` | RAGAS: avaliação de qualidade do RAG |
| Domain | `core/domain/` | Modelos ORM, repositórios, contratos de dados |
| Services | `core/services/` | Lógica de negócio (schedule, patient, RAG, audit) |
| Observability | `core/observability/` | Logging estruturado, tracing, métricas |
| Integrations | `core/integrations/` | Adapters: Telegram, WhatsApp, LiveKit (Phase 2) |

### Regras do core global

1. **Sem hardcode de dados de clínica** — nenhum nome, CNPJ, convênio, CRM de médico
2. **Sem if/else por clínica** — personalização via injeção de configuração, nunca via condicionais
3. **Sem acesso direto a secrets** — sempre via `ClinicSettings` (env vars)
4. **Sem dependência de dados locais** — o core funciona com qualquer knowledge base

---

## O que é a Camada da Clínica

Tudo que **muda por deploy** — configurações, assets, dados e documentos de uma clínica específica.

**Localização:** `src/inteliclinic/clinic/`

| Diretório | Conteúdo |
|-----------|----------|
| `clinic/config/` | `ClinicSettings`: identity, features, LLM, RAG, business hours |
| `clinic/branding/` | Nome, logo, cores, nome do chatbot, saudação |
| `clinic/prompts/` | Prompts complementares (especialidades, tom, regras locais) |
| `clinic/knowledge/` | Documentos a indexar (PDFs de convênio, FAQs, protocolos) |
| `clinic/policies/` | Políticas operacionais locais (estendem core/safety/policies/) |
| `clinic/seeds/` | Dados iniciais: profissionais, slots, documentos RAG |

### Regras da camada da clínica

1. **Sem lógica de produto** — só configuração, assets e dados
2. **Não importar de clinic/ em core/** — dependência deve ser unidirecional (core → clinic ✗, clinic usa core ✓)
3. **Sem dados de outra clínica** — cada deploy tem sua própria pasta e Qdrant collection
4. **Substituível sem redeployar o core** — trocar um documento ou prompt não requer mudança de código

---

## O que pode e o que não pode ser customizado

### ✅ Pode customizar (camada da clínica)

| O que | Como |
|-------|------|
| Nome e identidade | `CLINIC_NAME`, `CLINIC_SHORT_NAME` env vars |
| Chatbot name e saudação | `CLINIC_CHATBOT_NAME`, `CLINIC_CHATBOT_GREETING` |
| Horários de atendimento | `CLINIC_BUSINESS_HOURS_START/END`, `CLINIC_BUSINESS_DAYS` |
| Convênios aceitos | `CLINIC_ACCEPTED_INSURANCES` |
| Features habilitadas | `CLINIC_FEATURE_SCHEDULING`, `CLINIC_FEATURE_GLOSA_DETECTION`, etc. |
| Ton de comunicação | `clinic/prompts/base_prompts.py` → `ClinicPrompts.tone` |
| Especialidades no prompt | `ClinicPrompts.specialty_context` |
| Documentos do RAG | Arquivos em `clinic/knowledge/`, ingeridos no Qdrant |
| Políticas operacionais | Classe extendendo `BasePolicy` registrada no `PolicyRegistry` |
| Modelo LLM | `CLINIC_LLM_PROVIDER`, `CLINIC_LLM_MODEL` |
| Threshold de confiança | `CLINIC_MIN_CONFIDENCE` |

### ❌ Não pode (viola a separação core × clínica)

| O que | Por quê |
|-------|---------|
| Criar fork do repositório por clínica | Fragmenta o produto, impossibilita atualizações centralizadas |
| Duplicar lógica de agentes por cliente | Duplicação de código, divergência de comportamento |
| Hardcodar convênios, CRM, nomes no core | Viola isolamento, impede reutilização |
| Usar if/else `if clinic_id == "unimed_sp"` no core | Anti-pattern: acoplamento de dados no produto |
| Compartilhar Qdrant collection entre clínicas | Vazamento de dados, violação de LGPD |
| Referenciar `clinic/` diretamente em `core/` | Inversão de dependência incorreta |

---

## Tecnologias e onde vivem

| Tecnologia | Localização no Core | Função |
|-----------|-------------------|--------|
| **LangGraph** | `core/ai_engine/langgraph/`, `core/ai_engine/graphs/`, `core/ai_engine/nodes/`, `core/ai_engine/state/` | Motor de orquestração dos agentes |
| **Instructor** | `core/nlu/extractors/`, `core/nlu/schemas/`, `core/nlu/pipelines/` | Extração estruturada de mensagens |
| **Docling** | `core/rag/ingestion/parsers/docling_parser.py` | Parsing de PDFs e documentos |
| **Guardrails AI** | `core/safety/guards/output_guards.py` | Validação estrutural de outputs |
| **LlamaIndex** | `core/rag/indexes/`, `core/rag/query/`, `core/rag/retrievers/` | Framework principal do RAG |
| **Qdrant** | `core/rag/stores/qdrant_store.py` | Vector store (collection por clínica) |
| **GraphRAG** | `core/rag/graphrag/` | Fase 2 — knowledge graph (interface definida) |
| **PyOD** | `core/analytics/anomaly/` | Detecção de glosas e anomalias financeiras |
| **RAGAS** | `core/evaluation/rag/` | Avaliação de qualidade do RAG |

---

## Exemplos práticos

### Onboarding de nova clínica (sem fork)

```bash
# 1. Clonar a base (mesmo repositório)
git clone git@github.com:minutare14/minutare-inteliclinic.git
cd minutare-inteliclinic

# 2. Criar configuração da clínica
cp config/examples/clinic.example.yaml clinic.yaml
# Editar clinic.yaml com dados da nova clínica

# 3. Configurar .env
cp .env.example .env
# Preencher: CLINIC_ID, CLINIC_NAME, OPENAI_API_KEY, DATABASE_URL, etc.

# 4. Adicionar documentos da clínica
cp convenio_unimed.pdf src/inteliclinic/clinic/knowledge/
cp faq_clinica.md src/inteliclinic/clinic/knowledge/

# 5. Subir o deploy
docker compose up -d

# 6. Ingerir knowledge base
python scripts/ingest_docs.py --source src/inteliclinic/clinic/knowledge/

# 7. Validar
python scripts/validate_config.py
```

### Adicionar uma nova regra local de política

```python
# src/inteliclinic/clinic/policies/local_policies.py
from inteliclinic.core.safety.policies.medical_policies import BasePolicy, PolicyAction, PolicyResult

class OutsideHoursPolicy(BasePolicy):
    """Bloqueia respostas automáticas fora do horário."""
    name = "outside_hours_policy"

    def evaluate(self, intent: str, content: str, context: dict) -> PolicyResult:
        from datetime import datetime, time
        now = datetime.now().time()
        if not (time(8, 0) <= now <= time(18, 0)):
            return PolicyResult(
                action=PolicyAction.ESCALATE,
                reason="Fora do horário de atendimento — encaminhar para atendimento humano",
                policy_name=self.name,
            )
        return PolicyResult(action=PolicyAction.ALLOW, reason="ok", policy_name=self.name)

# No startup da aplicação:
from inteliclinic.core.safety.policies.medical_policies import PolicyRegistry
registry = PolicyRegistry.default()
registry.register(OutsideHoursPolicy())
```

---

## Diagrama de dependências

```
src/inteliclinic/
│
├── core/                    ← PRODUTO (global, reutilizável)
│   ├── ai_engine/           ←── LangGraph
│   │   ├── state/           ←── ClinicState (TypedDict)
│   │   ├── nodes/           ←── reception, scheduling, insurance, ...
│   │   ├── graphs/          ←── main_graph (StateGraph compilado)
│   │   └── langgraph/       ←── GraphConfig, builder
│   ├── nlu/                 ←── Instructor (ExtractedMessage)
│   ├── rag/                 ←── LlamaIndex + Qdrant
│   │   ├── ingestion/       ←── Docling parser pipeline
│   │   ├── indexes/         ←── LlamaIndexStore
│   │   ├── query/           ←── ClinicQueryEngine
│   │   ├── retrievers/      ←── HybridRetriever
│   │   ├── stores/          ←── QdrantStore
│   │   └── graphrag/        ←── Interface (Phase 2)
│   ├── safety/              ←── Guardrails AI + CFM policies
│   ├── analytics/           ←── PyOD (glosa, financial)
│   └── evaluation/          ←── RAGAS
│
├── clinic/                  ← CLÍNICA (local, por deploy)
│   ├── config/              ←── ClinicSettings (env vars)
│   ├── branding/            ←── ClinicBrand
│   ├── prompts/             ←── ClinicPrompts (complementares)
│   ├── knowledge/           ←── Documentos → Qdrant collection exclusiva
│   ├── policies/            ←── Políticas operacionais locais
│   └── seeds/               ←── Dados iniciais do deploy
│
└── api/                     ← ENTREGA (FastAPI routes)
```

**Regra de dependência:**
- `core/` → não depende de `clinic/`
- `clinic/` → pode usar `core/`
- `api/` → usa `core/` e lê `clinic/config/`
