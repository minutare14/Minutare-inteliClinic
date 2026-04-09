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

## Onboarding de Nova Clínica

> Esta seção descreve o procedimento oficial para adicionar uma nova clínica ao produto. Não existe outro caminho além deste.

### Conceito arquitetural

O InteliClinic é construído sobre uma separação explícita entre o que pertence ao produto e o que pertence ao deploy de cada clínica:

| Camada | O que contém | Onde vive |
|--------|-------------|-----------|
| **Core global** | Engine de IA, RAG, safety, analytics, API, integrações | `src/inteliclinic/core/` — mesmo em todos os deploys |
| **Camada local** | Config, branding, knowledge base, seeds, políticas locais | `src/inteliclinic/clinic/` — exclusivo de cada deploy |

Cada clínica recebe sua própria VPS, com infraestrutura completamente isolada:

- **Banco de dados próprio** — PostgreSQL exclusivo, sem dados de outras clínicas
- **Vector store próprio** — Qdrant com collection `inteliclinic_{clinic_id}`, sem cruzamento de bases
- **Canal próprio** — token de Telegram exclusivo do bot desta clínica
- **Knowledge base própria** — documentos indexados separadamente, nunca compartilhados
- **Variáveis de ambiente próprias** — `.env` exclusivo, com credenciais desta instância

O isolamento não é opcional. É o que garante segurança de dados, compliance com LGPD e independência operacional entre clínicas.

---

### O que criar para cada nova clínica

Antes de iniciar, provisione os seguintes recursos exclusivos desta clínica:

- [ ] **`.env` próprio** — cópia de `.env.example` preenchida com dados reais desta clínica
- [ ] **Banco PostgreSQL** — instância isolada (via Docker ou serviço gerenciado)
- [ ] **Instância Qdrant** — vector store exclusivo; a collection é criada automaticamente pelo sistema
- [ ] **Bot Telegram** — criado via @BotFather, token exclusivo desta clínica
- [ ] **Chave de API LLM** — OpenAI, Anthropic ou Gemini configurada para este deploy
- [ ] **Domínio/URL público** — para o webhook do Telegram e acesso ao painel
- [ ] **Pasta de configuração local** — `src/inteliclinic/clinic/` preenchida com dados reais
- [ ] **Knowledge base** — PDFs de convênio, FAQs, tabelas de preços e protocolos desta clínica
- [ ] **Seeds** — lista de profissionais, especialidades e grade inicial de horários
- [ ] **Usuários admin** — credenciais dos gestores que acessarão o painel operacional

---

### Estrutura local por clínica

Para cada deploy, a camada local deve estar organizada assim:

```
src/inteliclinic/clinic/
  config/
    clinic_settings.py       ← ClinicSettings carrega de CLINIC_* env vars
    example_settings.py      ← Referência — não usar em produção
  branding/
    brand.py                 ← Nome, chatbot, cores (derivado das settings)
    logo.png                 ← Logo da clínica (opcional)
  prompts/
    prompts.yaml             ← Especialidades, tom, regras locais em linguagem natural
  knowledge/
    convenio_unimed.pdf      ← Documentos reais desta clínica
    convenio_bradesco.pdf
    faq_clinica.md
    tabela_particular.pdf
    protocolos/
      pos_cirurgico.pdf
  policies/
    local_policies.py        ← Políticas operacionais específicas (opcional)
  seeds/
    professionals.json       ← Profissionais a cadastrar no primeiro deploy
    slots_config.json        ← Grade horária inicial (opcional)
```

O `config/examples/clinic.example.yaml` contém um template completo com todos os campos disponíveis.

---

### Passo a passo de onboarding

Siga esta sequência na ordem. Cada passo depende do anterior.

**1. Criar a configuração da clínica**

```bash
# Copiar template de configuração
cp config/examples/clinic.example.yaml clinic.yaml
cp infra/docker/.env.example .env

# Preencher identidade no .env
CLINIC_ID=clinica_saude_sp
CLINIC_NAME="Clínica Saúde São Paulo"
CLINIC_SHORT_NAME="Clínica Saúde"
CLINIC_CNPJ=00.000.000/0001-00
CLINIC_DOMAIN=bot.clinicasaude.com.br
```

**2. Definir branding e dados institucionais**

```bash
# No .env, configurar chatbot e horários
CLINIC_CHATBOT_NAME=Ana
CLINIC_CHATBOT_GREETING="Olá! Sou a Ana, assistente virtual da {clinic_name}. Como posso ajudá-lo?"
CLINIC_BUSINESS_HOURS_START=08:00
CLINIC_BUSINESS_HOURS_END=18:00
CLINIC_BUSINESS_DAYS=[1,2,3,4,5]
CLINIC_ACCEPTED_INSURANCES=["Unimed", "Bradesco Saúde", "Amil"]
```

Criar `src/inteliclinic/clinic/prompts/prompts.yaml` com o contexto local:

```yaml
tone: professional
specialty_context: |
  Clínica especializada em ortopedia e fisioterapia.
  Profissionais: Dr. Carlos Silva (ortopedia), Dra. Maria Lima (fisioterapia).
insurance_notes: |
  Unimed: consulta sem necessidade de guia para rotina.
  Bradesco: exames complexos requerem autorização prévia.
additional_rules:
  - Procedimentos acima de R$ 800 requerem confirmação por ligação.
  - Não agendar mais de 3 sessões de fisio por semana sem aprovação médica.
```

**3. Cadastrar médicos, especialidades e convênios**

Criar `src/inteliclinic/clinic/seeds/professionals.json`:

```json
[
  {
    "name": "Dr. Carlos Silva",
    "crm": "CRM-SP 123456",
    "specialty": "Ortopedia",
    "consultation_duration_min": 30,
    "schedule": { "days": [1,2,3,4,5], "start": "08:00", "end": "17:00" }
  },
  {
    "name": "Dra. Maria Lima",
    "crm": "CREFITO-SP 67890",
    "specialty": "Fisioterapia",
    "consultation_duration_min": 45,
    "schedule": { "days": [1,2,3,4,5], "start": "09:00", "end": "18:00" }
  }
]
```

**4. Adicionar documentos da knowledge base**

```bash
# Copiar documentos reais desta clínica
cp /origem/convenio_unimed.pdf     src/inteliclinic/clinic/knowledge/
cp /origem/convenio_bradesco.pdf   src/inteliclinic/clinic/knowledge/
cp /origem/faq_clinica.md          src/inteliclinic/clinic/knowledge/
cp /origem/tabela_particular.pdf   src/inteliclinic/clinic/knowledge/
```

Formatos suportados: `.pdf`, `.docx`, `.pptx`, `.md`, `.txt`

**5. Subir a infraestrutura isolada**

```bash
cd infra/docker
docker compose up -d

# Verificar se todos os serviços estão saudáveis
docker compose ps
# Esperado: db (healthy), qdrant (running), api (running)
```

**6. Rodar migrations**

```bash
docker compose exec api alembic upgrade head
```

**7. Rodar ingestão do RAG**

```bash
docker compose exec api python scripts/ingest_docs.py \
    --source src/inteliclinic/clinic/knowledge/

# Verificar documentos indexados
curl http://localhost:8000/api/v1/rag/documents
```

A collection Qdrant `inteliclinic_{CLINIC_ID}` é criada automaticamente neste passo.

**8. Rodar seeds**

```bash
docker compose exec api python scripts/seed_data.py \
    --professionals src/inteliclinic/clinic/seeds/professionals.json
```

**9. Configurar integrações (Telegram)**

```bash
# Registrar webhook do bot desta clínica
curl -X POST http://localhost:8000/api/v1/telegram/set-webhook \
    -H "Content-Type: application/json" \
    -d '{"url": "https://bot.clinicasaude.com.br/api/v1/telegram/webhook"}'

# Confirmar registro
curl http://localhost:8000/api/v1/telegram/webhook-info
```

**10. Validar fluxos principais**

```bash
# Health geral
curl https://bot.clinicasaude.com.br/api/v1/health

# Health do banco
curl https://bot.clinicasaude.com.br/api/v1/health/db

# RAG respondendo
curl -X POST https://bot.clinicasaude.com.br/api/v1/rag/query \
    -H "Content-Type: application/json" \
    -d '{"query": "Quais convênios são aceitos?"}'

# Avaliação de qualidade do RAG
python scripts/evaluate_rag.py \
    --dataset tests/rag/eval_dataset.jsonl \
    --output results/homologacao_$(date +%Y%m%d).json
```

---

### Checklist de homologação

Execute este checklist antes de liberar a clínica para uso.

**Infraestrutura**
- [ ] `GET /health` retorna 200
- [ ] `GET /health/db` retorna `status: ok`
- [ ] Qdrant acessível e collection criada (`inteliclinic_{CLINIC_ID}`)
- [ ] SSL ativo no domínio público

**Telegram**
- [ ] Bot criado e token configurado no `.env`
- [ ] Webhook registrado e respondendo
- [ ] Bot envia mensagem de boas-vindas ao iniciar conversa

**Cadastros**
- [ ] Pelo menos 1 profissional cadastrado com CRM e especialidade
- [ ] Slots de agenda disponíveis para os próximos 7 dias
- [ ] Paciente de teste criado e vinculado a uma conversa

**RAG**
- [ ] Pelo menos 3 documentos indexados na knowledge base
- [ ] Query sobre convênios retorna resultado relevante
- [ ] Query sobre horários retorna resultado correto

**Fluxos do chatbot**
- [ ] Agendamento via Telegram funcionando de ponta a ponta
- [ ] Cancelamento de consulta funcionando
- [ ] Consulta de convênios respondendo com base no RAG
- [ ] Handoff disparando quando necessário

**Segurança**
- [ ] Mensagem com tentativa de diagnóstico é bloqueada pelos guardrails
- [ ] Tentativa de injeção de prompt é bloqueada
- [ ] Auditoria registrando eventos corretamente

---

### O que nunca fazer

Estas ações violam a arquitetura do produto e comprometem a operação de todas as clínicas:

| Proibido | Por quê |
|----------|---------|
| Criar fork do repositório por clínica | Fragmenta o produto, impossibilita atualizações centralizadas |
| Hardcodar convênios, CRMs ou nomes de médicos no `core/` | Polui o produto com dados de uma única clínica |
| Usar `if clinic_id == "..."` em qualquer arquivo de `core/` | Acoplamento de dados no produto — use configuração |
| Compartilhar banco PostgreSQL entre clínicas | Violação de LGPD, risco de vazamento de dados de pacientes |
| Compartilhar collection Qdrant entre clínicas | Contamina a knowledge base, respostas incorretas |
| Misturar documentos de clínicas diferentes em `clinic/knowledge/` | Mesma razão — RAG vai trazer contexto errado |
| Modificar `core/safety/policies/medical_policies.py` por demanda de uma clínica | Regras CFM são universais; políticas locais ficam em `clinic/policies/` |
| Subir `.env` com credenciais reais no repositório | Expõe tokens, senhas e chaves de API |

---

## Painel como Interface Operacional Principal

O frontend não é um painel de leitura. É o **console operacional do sistema**.

A API é a camada de execução. O terminal e os scripts são auxiliares para automação e setup. O painel é o caminho principal de uso da clínica no dia a dia.

```
Fluxo correto:
  Operador → Painel → API → Banco / IA / Integrações

Scripts / curl → apenas para automação, deploy e setup inicial
```

### Por que isso importa

Quando operações importantes dependem do terminal, o sistema cria uma barreira técnica que impede a equipe clínica de operar com autonomia. Receptivistas, gestores e administradores precisam conseguir fazer seu trabalho pelo painel — sem depender de um desenvolvedor para cada ação.

### Arquitetura de responsabilidades

| Camada | Responsabilidade |
|--------|-----------------|
| **Painel (frontend)** | Interface principal para toda operação diária — recepção, agenda, handoff, conhecimento, governança |
| **API (backend)** | Execução das regras de negócio, validações, persistência, IA |
| **Scripts** | Setup inicial (seed, ingestão de docs), automações em batch, CI/CD |
| **Terminal/curl** | Debug técnico, onboarding de deploy, operações de infraestrutura |

A lógica de negócio **nunca** fica no frontend. O painel chama a API; a API executa as regras.

---

### Operações disponíveis no painel

#### Operação diária (Recepção)

| Operação | Página | Status |
|----------|--------|--------|
| Visualizar lista de pacientes | `/patients` | Disponível |
| Criar novo paciente | `/patients` | Disponível |
| Editar dados do paciente | `/patients/[id]` | Disponível |
| Ver histórico de conversas | `/conversations` | Disponível |
| Ver mensagens de uma conversa | `/conversations/[id]` | Disponível |
| Visualizar agenda (por profissional, data, status) | `/schedules` | Disponível |
| Cancelar agendamento | `/schedules` | Disponível |
| Assumir handoff (escalar para atendimento humano) | `/handoffs` | Disponível |
| Marcar handoff como resolvido | `/handoffs` | Disponível |

#### Administração da clínica (Gestão)

| Operação | Página | Status |
|----------|--------|--------|
| Listar profissionais | `/professionals` | Disponível |
| Cadastrar novo profissional | `/professionals` | Disponível |
| Editar dados do profissional | `/professionals` | Disponível |
| Desativar profissional | `/professionals` | Disponível |
| Ver dashboard com KPIs | `/dashboard` | Disponível |
| Ver eventos de auditoria | `/audit` | Disponível |

#### Knowledge Base / RAG

| Operação | Página | Status |
|----------|--------|--------|
| Listar documentos da base | `/rag` | Disponível |
| Adicionar documento à base (via texto) | `/rag` | Disponível |
| Testar query RAG no painel | `/rag` | Disponível |
| Upload de PDFs (via ingestão automática) | Scripts + `/rag` | Script + visualização |

#### Integrações

| Operação | Página | Status |
|----------|--------|--------|
| Ver status do webhook Telegram | `/integrations` | Disponível |
| Configurar URL do webhook | `/integrations` | Disponível |
| Verificar erros de integração | `/integrations` | Disponível |
| WhatsApp / LiveKit | — | Fase 2 |

#### Governança / Auditoria

| Operação | Página | Status |
|----------|--------|--------|
| Visualizar trilha de auditoria | `/audit` | Disponível |
| Filtrar por ator, ação, recurso | `/audit` | Disponível |
| Status do sistema (API, DB) | `/settings` | Disponível |

---

### Perfis de acesso (RBAC — preparado para fase 2)

O painel está estruturado para suportar controle de acesso por perfil. A implementação de autenticação JWT + RBAC completa está na fase 2, mas as rotas e menus já consideram a separação:

| Perfil | Acesso |
|--------|--------|
| **Recepcionista** | Pacientes, Agenda, Conversas, Handoffs |
| **Gestor** | Tudo da recepção + Profissionais, Dashboard, RAG (leitura) |
| **Administrador** | Tudo + RAG (escrita), Integrações, Auditoria, Configurações |
| **Suporte técnico** | Configurações, Integrações, Auditoria, sem dados clínicos |

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
