# Deploy Dedicado por Clínica

## Modelo de deployment

O InteliClinic utiliza **deploy dedicado por clínica**:

- Cada clínica roda em uma **VPS exclusiva**
- Cada VPS tem sua própria instância completa do sistema
- Não existe multi-tenancy — os dados de uma clínica **nunca** ficam na mesma instância que outra
- O repositório é único, mas cada deploy é independente

```
┌─────────────────────┐     ┌─────────────────────┐     ┌─────────────────────┐
│   VPS Clínica A     │     │   VPS Clínica B     │     │   VPS Clínica C     │
│                     │     │                     │     │                     │
│  InteliClinic 0.2   │     │  InteliClinic 0.2   │     │  InteliClinic 0.2   │
│  PostgreSQL         │     │  PostgreSQL         │     │  PostgreSQL         │
│  Qdrant             │     │  Qdrant             │     │  Qdrant             │
│  clinic.yaml (A)    │     │  clinic.yaml (B)    │     │  clinic.yaml (C)    │
│  .env (A)           │     │  .env (B)           │     │  .env (C)           │
└─────────────────────┘     └─────────────────────┘     └─────────────────────┘
     Mesma base de                Mesma base de               Mesma base de
     código (v0.2)                código (v0.2)               código (v0.2)
```

---

## Pré-requisitos

### VPS mínima recomendada
- **CPU:** 2 vCPUs
- **RAM:** 4 GB (8 GB recomendado)
- **Disco:** 40 GB SSD
- **OS:** Ubuntu 22.04 LTS ou Debian 12
- **Docker:** 24.x + Docker Compose v2

### Serviços provisionados por VPS
- PostgreSQL 16 + pgvector
- Qdrant (vector store)
- FastAPI (API + AI engine)
- Next.js frontend (opcional)
- Nginx (reverse proxy, opcional)

---

## Configuração de um novo deploy

### 1. Clonar o repositório

```bash
git clone git@github.com:minutare14/minutare-inteliclinic.git
cd minutare-inteliclinic
git checkout main  # ou tag de release específica
```

### 2. Configurar variáveis de ambiente

```bash
cp .env.example .env
```

Edite `.env` com os valores reais desta clínica:

```bash
# Identidade da clínica
CLINIC_ID=clinica_saude_sp
CLINIC_NAME="Clínica Saúde São Paulo"
CLINIC_SHORT_NAME="Clínica Saúde"
CLINIC_CNPJ=00.000.000/0001-00
CLINIC_DOMAIN=bot.clinicasaude.com.br

# Banco de dados (desta VPS)
POSTGRES_USER=inteliclinic
POSTGRES_PASSWORD=<senha_forte_aqui>
POSTGRES_DB=inteliclinic_prod
DATABASE_URL=postgresql+asyncpg://inteliclinic:<senha>@db:5432/inteliclinic_prod

# Telegram (token do bot desta clínica)
TELEGRAM_BOT_TOKEN=<token_do_botfather>
TELEGRAM_WEBHOOK_URL=https://bot.clinicasaude.com.br/api/v1/telegram/webhook
TELEGRAM_WEBHOOK_SECRET=<secret_aleatorio>

# LLM
OPENAI_API_KEY=sk-...
CLINIC_LLM_MODEL=gpt-4o-mini

# Qdrant (vetor desta VPS)
CLINIC_QDRANT_URL=http://qdrant:6333

# Features
CLINIC_FEATURE_SCHEDULING=true
CLINIC_FEATURE_INSURANCE_QUERY=true
CLINIC_FEATURE_FINANCIAL=false
CLINIC_FEATURE_GLOSA_DETECTION=false
```

### 3. Configurar clinic.yaml (opcional)

Para configurações mais ricas (listas, textos multilinha):

```bash
cp config/examples/clinic.example.yaml clinic.yaml
```

Edite `clinic.yaml` com dados da clínica.

### 4. Adicionar documentos de knowledge base

```bash
# Copiar PDFs e documentos da clínica
cp /path/to/convenios/*.pdf src/inteliclinic/clinic/knowledge/
cp /path/to/faq.md src/inteliclinic/clinic/knowledge/
cp /path/to/tabela_precos.pdf src/inteliclinic/clinic/knowledge/
```

Documentos suportados: `.pdf`, `.docx`, `.pptx`, `.md`, `.txt`

### 5. Subir a stack Docker

```bash
cd infra/docker
docker compose up -d
```

Isso inicia:
- `db`: PostgreSQL 16 com pgvector
- `qdrant`: Qdrant vector store
- `api`: FastAPI + AI engine

### 6. Executar migrations

```bash
docker compose exec api alembic upgrade head
```

### 7. Ingerir knowledge base

```bash
docker compose exec api python scripts/ingest_docs.py \
    --source src/inteliclinic/clinic/knowledge/
```

### 8. Seed de dados iniciais

```bash
docker compose exec api python scripts/seed_data.py
```

Isso cria profissionais, slots iniciais e documentos RAG de exemplo.

### 9. Configurar Telegram webhook

```bash
docker compose exec api python -c "
from app.integrations.telegram.client import TelegramClient
import asyncio, os

async def set_webhook():
    client = TelegramClient(os.getenv('TELEGRAM_BOT_TOKEN'))
    result = await client.set_webhook(
        url=os.getenv('TELEGRAM_WEBHOOK_URL'),
        secret_token=os.getenv('TELEGRAM_WEBHOOK_SECRET'),
    )
    print(result)

asyncio.run(set_webhook())
"
```

---

## Secrets e credenciais

### O que muda por deploy (NUNCA commitar no repositório)

| Secret | Env Var | Descrição |
|--------|---------|-----------|
| Telegram bot token | `TELEGRAM_BOT_TOKEN` | Token único por clínica |
| Webhook secret | `TELEGRAM_WEBHOOK_SECRET` | Segurança do webhook |
| OpenAI API key | `OPENAI_API_KEY` | Chave da clínica ou compartilhada |
| Anthropic API key | `ANTHROPIC_API_KEY` | Alternativa ao OpenAI |
| DB password | `POSTGRES_PASSWORD` | Senha do banco desta VPS |
| App secret | `APP_SECRET_KEY` | JWT e crypto desta instância |

Todos os secrets ficam apenas no arquivo `.env` da VPS, nunca no repositório.

### Gerenciamento de secrets recomendado
- **Produção:** Doppler, HashiCorp Vault, ou AWS Secrets Manager
- **Desenvolvimento:** Arquivo `.env` local (no `.gitignore`)

---

## Validação do deploy

### Smoke tests

```bash
# Health check
curl https://bot.clinicasaude.com.br/api/v1/health

# Verificar DB
curl https://bot.clinicasaude.com.br/api/v1/health/db

# Testar RAG
curl -X POST https://bot.clinicasaude.com.br/api/v1/rag/query \
    -H "Content-Type: application/json" \
    -d '{"query": "Quais convênios são aceitos?"}'
```

### Verificações obrigatórias antes de ir ao ar

- [ ] `GET /health` retorna 200
- [ ] `GET /health/db` retorna status "ok"
- [ ] Telegram webhook ativo e respondendo
- [ ] Knowledge base indexada (pelo menos 1 documento)
- [ ] Pelo menos 1 profissional cadastrado com slots disponíveis
- [ ] Guardrails funcionando (testar mensagem de diagnóstico)
- [ ] Configuração Qdrant collection exclusiva para esta clínica

---

## Atualizações do produto

Quando uma nova versão do InteliClinic for lançada:

```bash
# Atualizar código (mesma VPS)
git pull origin main

# Executar migrations se houver
docker compose exec api alembic upgrade head

# Reiniciar serviços
docker compose restart api

# Verificar saúde
curl /api/v1/health
```

A configuração da clínica (`.env`, `clinic.yaml`, documentos) **não muda** durante updates do produto.

---

## Isolamento de dados

| Recurso | Isolamento |
|---------|-----------|
| PostgreSQL | VPS exclusiva — sem compartilhamento |
| Qdrant | VPS exclusiva + collection separada por `clinic_id` |
| Logs | VPS exclusiva |
| Backups | VPS exclusiva |
| SSL/TLS | Certificado por domínio |

Nenhum dado de uma clínica trafega ou é armazenado em infraestrutura de outra clínica.
