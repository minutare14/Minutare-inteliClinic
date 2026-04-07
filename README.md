# Minutare InteliClinic

Plataforma de IA para gestão completa de clínicas médicas, com deploy dedicado por clínica.

> **Regra arquitetural:** Nova clínica = novo deploy da mesma base, com nova configuração local. Não é permitido criar uma nova base de código por cliente.

---

## Natureza do produto

O InteliClinic é um **produto único** com **deploy dedicado por clínica**:

- Cada clínica roda em sua própria VPS, com instância completa e isolada
- Não há multi-tenancy em runtime — os dados de uma clínica nunca ficam na mesma instância que outra
- O repositório é compartilhado como produto; a configuração é exclusiva de cada deploy
- Atualizações do produto chegam a todas as clínicas via `git pull` + restart

---

## Stack

| Camada | Tecnologia | Função |
|--------|-----------|--------|
| **AI Engine** | LangGraph | Orquestração de agentes, grafo, estado, HITL |
| **NLU** | Instructor | Extração estruturada de mensagens confusas |
| **Parsing** | Docling | PDFs de convênio, TISS, protocolos, manuais |
| **RAG** | LlamaIndex | Framework principal de retrieval e indexação |
| **Vector Store** | Qdrant | Banco vetorial (collection exclusiva por clínica) |
| **Safety** | Guardrails AI + CFM policies | Validação, segurança médica, compliance |
| **Analytics** | PyOD | Detecção de glosas e anomalias financeiras |
| **Evaluation** | RAGAS | Avaliação de qualidade do RAG |
| **Backend** | FastAPI, SQLAlchemy async, PostgreSQL 16 + pgvector | API e persistência |
| **Frontend** | Next.js 16, TypeScript, Tailwind CSS | Painel operacional |
| **Canal** | Telegram Bot API (webhook) | Atendimento ao paciente |

---

## Estrutura do repositório

```
src/
  inteliclinic/
    core/                    ← CORE GLOBAL (produto, reutilizável em qualquer deploy)
      ai_engine/             ← LangGraph: orquestração
        state/               ← ClinicState (TypedDict)
        nodes/               ← reception, scheduling, insurance, financial, glosa, supervisor...
        graphs/              ← StateGraph compilado
        langgraph/           ← GraphConfig, builder
      nlu/                   ← Instructor: extração estruturada
        schemas/             ← ExtractedMessage, Intent, ConfidenceLevel
        extractors/          ← InstructorMessageExtractor
        pipelines/           ← ExtractionPipeline
      rag/                   ← LlamaIndex + Qdrant + Docling
        ingestion/           ← Docling parser, chunkers, IngestPipeline
        indexes/             ← LlamaIndexStore
        query/               ← ClinicQueryEngine, RAGResult
        retrievers/          ← HybridRetriever (dense + sparse + RRF)
        stores/              ← QdrantStore
        graphrag/            ← Interface Phase 2 (GraphRAG)
      safety/                ← Guardrails AI + CFM + validação híbrida
        guards/              ← InjectionGuard, MedicalSafetyGuard, ConfidenceGuard
        policies/            ← CFMPolicy, UrgencyPolicy, DataPrivacyPolicy, PolicyRegistry
        validators/          ← ResponseValidator (pipeline completo)
      analytics/             ← PyOD: inteligência operacional
        anomaly/             ← AnomalyDetector, FeatureExtractor, AnomalyPipeline
      evaluation/            ← RAGAS: avaliação do RAG
        rag/                 ← RAGEvaluator, EvaluationDataset, EvaluationReport
      domain/                ← Modelos ORM, repositórios
      services/              ← Business logic
      observability/         ← Logging estruturado
      integrations/          ← Adapters: Telegram, WhatsApp (Phase 2), LiveKit (Phase 2)
    clinic/                  ← CAMADA LOCAL (exclusiva deste deploy)
      config/                ← ClinicSettings (env vars: CLINIC_*)
      branding/              ← ClinicBrand: nome, logo, cores, saudação
      prompts/               ← ClinicPrompts: contexto, tom, regras locais
      knowledge/             ← Documentos indexados no Qdrant desta clínica
      policies/              ← Políticas operacionais locais
      seeds/                 ← Dados iniciais (profissionais, slots)
    api/                     ← FastAPI routes, schemas
    workers/                 ← Background tasks (ingestão, notificações, analytics)

apps/
  api/                       ← Implementação atual (MVP compatível)
    app/                     ← Código existente (em migração para src/)
    tests/                   ← 86 testes automatizados

frontend/                    ← Painel operacional (Next.js 16)

infra/
  docker/                    ← Docker Compose, .env.example

docs/
  architecture/
    core-vs-clinic.md        ← Separação core global × camada local
  deployment/
    dedicated-deploy.md      ← Como configurar um deploy dedicado por clínica
  clinic-onboarding/
    new-clinic.md            ← Passo a passo de onboarding de nova clínica

config/
  examples/
    clinic.example.yaml      ← Template completo de configuração por clínica

scripts/
  seed_data.py               ← Seed de dados iniciais
  ingest_docs.py             ← Ingestão de documentos na knowledge base
  evaluate_rag.py            ← Avaliação de qualidade do RAG (RAGAS)

tests/
  rag/                       ← Testes e datasets de avaliação RAG
```

---

## Separação core global × camada da clínica

### Core global (`src/inteliclinic/core/`)
Pertence ao **produto**. É reutilizado em todos os deploys sem modificação.

### Camada da clínica (`src/inteliclinic/clinic/`)
Pertence ao **deploy**. Contém apenas:
- Configurações (`CLINIC_*` env vars)
- Branding (nome, chatbot, cores)
- Prompts complementares
- Documentos da knowledge base (PDFs, FAQs, tabelas)
- Políticas operacionais locais
- Seeds iniciais

### O que nunca fazer
- Criar fork do repositório para uma nova clínica
- Duplicar lógica de agentes por cliente
- Hardcodar convênios, CRMs ou nomes de médicos no core
- Usar `if clinic_id == "..."` no código do produto
- Compartilhar Qdrant collection entre clínicas

---

## Tecnologias e fases

| Tecnologia | Fase | Status |
|-----------|------|--------|
| LangGraph | 1 | Estrutura criada — `core/ai_engine/` |
| Instructor | 1 | Estrutura criada — `core/nlu/` |
| Docling | 1 | Estrutura criada — `core/rag/ingestion/` |
| Guardrails AI | 1 | Estrutura criada — `core/safety/` |
| LlamaIndex | 1 | Estrutura criada — `core/rag/` |
| Qdrant | 1 | Estrutura criada — `core/rag/stores/` |
| PyOD | 1 | Estrutura criada — `core/analytics/anomaly/` |
| RAGAS | 1 | Estrutura criada — `core/evaluation/rag/` |
| GraphRAG | 2 | Interface definida — `core/rag/graphrag/` |
| LiveKit Agents | 2 | Planejado — `core/integrations/voice/` |
| medspaCy | 2 | Planejado — NLP clínico |

---

## Como rodar (deploy local)

### Backend + banco + Qdrant (Docker)

```bash
# 1. Configurar variáveis de ambiente
cp infra/docker/.env.example infra/docker/.env
# Editar .env com seus dados

# 2. Subir a stack
cd infra/docker
docker compose up -d

# 3. Migrations
docker compose exec api alembic upgrade head

# 4. Ingerir documentos
docker compose exec api python scripts/ingest_docs.py \
    --source src/inteliclinic/clinic/knowledge/

# 5. Seed inicial
docker compose exec api python scripts/seed_data.py
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Painel: http://localhost:3000

### Testes

```bash
cd apps/api
python -m pytest tests/ -v
```

### Avaliação do RAG

```bash
python scripts/evaluate_rag.py \
    --dataset tests/rag/eval_dataset.jsonl \
    --output results/rag_eval.json
```

---

## Documentação

| Documento | Descrição |
|-----------|-----------|
| `docs/architecture/core-vs-clinic.md` | Separação arquitetural detalhada com exemplos |
| `docs/deployment/dedicated-deploy.md` | Como configurar um deploy por clínica |
| `docs/clinic-onboarding/new-clinic.md` | Passo a passo de onboarding |
| `config/examples/clinic.example.yaml` | Template completo de configuração |
| `docs/RUNBOOK.md` | Setup e operação |
| `docs/API_MAP.md` | Endpoints da API |
| `docs/DB_SCHEMA.md` | Schema do banco de dados |

---

## Status

| Componente | Status |
|-----------|--------|
| MVP backend (FastAPI + PostgreSQL) | Funcional — 86 testes |
| Frontend operacional (Next.js) | Funcional |
| Integração Telegram | Funcional |
| Arquitetura core/clinic | Implementada (v0.2) |
| LangGraph engine | Estrutura implementada |
| Instructor NLU | Estrutura implementada |
| Docling ingestion | Estrutura implementada |
| Guardrails + Safety | Estrutura implementada |
| LlamaIndex + Qdrant | Estrutura implementada |
| PyOD anomaly detection | Estrutura implementada |
| RAGAS evaluation | Estrutura implementada |
| GraphRAG | Interface Phase 2 definida |
| LiveKit voice | Planejado Phase 2 |
