# Onboarding de Nova Clínica

Guia passo a passo para provisionar uma nova clínica no InteliClinic.

> **Lembrete:** Não crie um fork do repositório. Uma nova clínica é um novo **deploy** da mesma base.

---

## Pré-onboarding: coleta de informações

Antes de iniciar, colete as seguintes informações com a clínica:

### Identidade
- [ ] Nome completo legal da clínica
- [ ] Nome curto (para o chatbot)
- [ ] CNPJ
- [ ] Endereço completo
- [ ] Telefone de contato

### Configuração operacional
- [ ] Especialidades médicas atendidas
- [ ] Profissionais (nome, CRM, especialidade)
- [ ] Horários de atendimento (dias e horários)
- [ ] Convênios aceitos (lista completa)
- [ ] Se aceita particular

### Integrações
- [ ] Token do Telegram Bot (criado via @BotFather)
- [ ] Domínio público para o webhook (ex: `bot.clinicasaude.com.br`)
- [ ] Chave da API do LLM (OpenAI, Anthropic ou Gemini)

### Documentos (para knowledge base)
- [ ] PDF dos convênios aceitos (tabelas de cobertura)
- [ ] FAQ da clínica (formato MD ou PDF)
- [ ] Tabela de preços particulares
- [ ] Protocolos internos relevantes (opcional)
- [ ] Manual de agendamento (opcional)

---

## Passo 1: Preparar a VPS

```bash
# Instalar Docker
curl -fsSL https://get.docker.com | bash
sudo usermod -aG docker $USER

# Verificar
docker --version
docker compose version
```

---

## Passo 2: Clonar o repositório

```bash
git clone git@github.com:minutare14/minutare-inteliclinic.git clinica-saude-sp
cd clinica-saude-sp
git checkout main
```

---

## Passo 3: Configurar identidade da clínica

```bash
cp .env.example .env
```

Edite `.env`:

```env
# Identidade
CLINIC_ID=clinica_saude_sp          # único, lowercase, sem espaços
CLINIC_NAME=Clínica Saúde São Paulo
CLINIC_SHORT_NAME=Clínica Saúde
CLINIC_CNPJ=00.000.000/0001-00
CLINIC_DOMAIN=bot.clinicasaude.com.br
CLINIC_PHONE=(11) 0000-0000
CLINIC_CITY=São Paulo
CLINIC_STATE=SP

# Features (habilitar o que a clínica precisa)
CLINIC_FEATURE_SCHEDULING=true
CLINIC_FEATURE_INSURANCE_QUERY=true
CLINIC_FEATURE_FINANCIAL=false
CLINIC_FEATURE_GLOSA_DETECTION=false
```

---

## Passo 4: Configurar branding do chatbot

No mesmo `.env`:

```env
CLINIC_CHATBOT_NAME=Ana
CLINIC_CHATBOT_GREETING=Olá! Sou a Ana, assistente virtual da {clinic_name}. Como posso ajudá-lo?
CLINIC_PRIMARY_COLOR=#0066CC
```

---

## Passo 5: Configurar horários e convênios

```env
# Horários
CLINIC_BUSINESS_HOURS_START=08:00
CLINIC_BUSINESS_HOURS_END=18:00
CLINIC_BUSINESS_DAYS=[1,2,3,4,5]    # seg-sex

# Convênios (lista separada por vírgula)
CLINIC_ACCEPTED_INSURANCES=["Unimed", "Bradesco Saúde", "Amil", "SulAmérica"]
CLINIC_ACCEPTS_PRIVATE=true
```

---

## Passo 6: Configurar credenciais

```env
# Banco de dados
POSTGRES_USER=inteliclinic
POSTGRES_PASSWORD=<senha_forte_gerada>
POSTGRES_DB=inteliclinic_prod
DATABASE_URL=postgresql+asyncpg://inteliclinic:<senha>@db:5432/inteliclinic_prod

# Telegram
TELEGRAM_BOT_TOKEN=<token_do_botfather>
TELEGRAM_WEBHOOK_URL=https://bot.clinicasaude.com.br/api/v1/telegram/webhook
TELEGRAM_WEBHOOK_SECRET=<string_aleatoria_32_chars>

# LLM
OPENAI_API_KEY=sk-...
CLINIC_LLM_MODEL=gpt-4o-mini

# Qdrant
CLINIC_QDRANT_URL=http://qdrant:6333
```

---

## Passo 7: Adicionar documentos da knowledge base

```bash
# Criar diretório de conhecimento local
mkdir -p src/inteliclinic/clinic/knowledge/

# Copiar documentos da clínica
cp /tmp/convenio_unimed.pdf       src/inteliclinic/clinic/knowledge/
cp /tmp/convenio_bradesco.pdf     src/inteliclinic/clinic/knowledge/
cp /tmp/faq_clinica.md            src/inteliclinic/clinic/knowledge/
cp /tmp/tabela_particular.pdf     src/inteliclinic/clinic/knowledge/
```

---

## Passo 8: Configurar prompts complementares (opcional)

Crie `src/inteliclinic/clinic/prompts/prompts.yaml`:

```yaml
# Tom de comunicação: formal | professional | friendly
tone: professional

# Contexto das especialidades (injetado no system prompt)
specialty_context: |
  Esta clínica é especializada em ortopedia, fisioterapia e medicina esportiva.
  Principais profissionais:
  - Dr. Carlos Silva — Ortopedia (CRM-SP 12345)
  - Dra. Maria Lima — Fisioterapia (CREFITO 67890)

# Informações sobre convênios
insurance_notes: |
  Aceitos: Unimed, Bradesco Saúde, Amil e SulAmérica.
  Para Unimed: consulta sem necessidade de guia de autorização prévia.
  Para Bradesco: exames complexos requerem autorização prévia.

# Regras operacionais adicionais
additional_rules:
  - Para agendamentos de urgência, sempre perguntar se o paciente já tem cadastro.
  - Procedimentos acima de R$ 500 requerem confirmação por ligação.
  - Não marcar mais de 3 consultas por semana para o mesmo paciente sem aprovação da recepção.
```

---

## Passo 9: Subir a stack

```bash
cd infra/docker
docker compose up -d

# Verificar se todos os serviços subiram
docker compose ps
```

Serviços esperados: `db` (healthy), `qdrant` (running), `api` (running)

---

## Passo 10: Executar migrations

```bash
docker compose exec api alembic upgrade head
```

---

## Passo 11: Ingerir knowledge base

```bash
docker compose exec api python scripts/ingest_docs.py \
    --source src/inteliclinic/clinic/knowledge/ \
    --clinic-id $CLINIC_ID
```

Verificar resultado:
```bash
curl http://localhost:8000/api/v1/rag/documents | python -m json.tool
```

---

## Passo 12: Seed de profissionais e agenda

Crie `src/inteliclinic/clinic/seeds/professionals.json`:

```json
[
  {
    "name": "Dr. Carlos Silva",
    "crm": "CRM-SP 12345",
    "specialty": "Ortopedia",
    "phone": "(11) 9999-0001",
    "consultation_duration_min": 30,
    "schedule": {
      "days": [1, 2, 3, 4, 5],
      "start": "08:00",
      "end": "17:00"
    }
  },
  {
    "name": "Dra. Maria Lima",
    "crm": "CREFITO-SP 67890",
    "specialty": "Fisioterapia",
    "phone": "(11) 9999-0002",
    "consultation_duration_min": 45,
    "schedule": {
      "days": [1, 2, 3, 4, 5],
      "start": "09:00",
      "end": "18:00"
    }
  }
]
```

```bash
docker compose exec api python scripts/seed_data.py \
    --professionals src/inteliclinic/clinic/seeds/professionals.json
```

---

## Passo 13: Configurar Telegram webhook

```bash
# Registrar o webhook
curl -X POST http://localhost:8000/api/v1/telegram/set-webhook \
    -H "Content-Type: application/json" \
    -d '{"url": "https://bot.clinicasaude.com.br/api/v1/telegram/webhook"}'

# Verificar
curl http://localhost:8000/api/v1/telegram/webhook-info
```

---

## Passo 14: Smoke tests

```bash
# Health geral
curl https://bot.clinicasaude.com.br/api/v1/health

# Health do banco
curl https://bot.clinicasaude.com.br/api/v1/health/db

# Testar RAG
curl -X POST https://bot.clinicasaude.com.br/api/v1/rag/query \
    -H "Content-Type: application/json" \
    -d '{"query": "Quais convênios são aceitos?"}'

# Verificar profissionais cadastrados
curl https://bot.clinicasaude.com.br/api/v1/professionals
```

---

## Checklist final de go-live

- [ ] `.env` configurado com dados reais da clínica
- [ ] Stack Docker rodando (db healthy, api running, qdrant running)
- [ ] Migrations executadas com sucesso
- [ ] Knowledge base indexada (≥ 3 documentos)
- [ ] Profissionais cadastrados com slots disponíveis
- [ ] Telegram webhook ativo e respondendo
- [ ] `/health` retorna 200
- [ ] `/health/db` retorna ok
- [ ] RAG respondendo corretamente sobre convênios
- [ ] Guardrails bloqueando mensagens de diagnóstico (teste obrigatório)
- [ ] SSL configurado no domínio
- [ ] Backup do PostgreSQL configurado
- [ ] Alertas de monitoramento configurados

---

## Manutenção pós-deploy

### Adicionar novo profissional
```bash
curl -X POST https://bot.clinicasaude.com.br/api/v1/professionals \
    -H "Content-Type: application/json" \
    -d '{"name": "Dr. Novo", "crm": "CRM-SP 99999", "specialty": "Clínica Geral"}'
```

### Adicionar novo documento à knowledge base
```bash
cp novo_convenio.pdf src/inteliclinic/clinic/knowledge/
docker compose exec api python scripts/ingest_docs.py \
    --source src/inteliclinic/clinic/knowledge/novo_convenio.pdf
```

### Atualizar versão do produto
```bash
git pull origin main
docker compose exec api alembic upgrade head
docker compose restart api
```

### Executar avaliação do RAG
```bash
docker compose exec api python scripts/evaluate_rag.py \
    --dataset tests/rag/eval_dataset.jsonl \
    --output results/rag_eval_$(date +%Y%m%d).json
```
