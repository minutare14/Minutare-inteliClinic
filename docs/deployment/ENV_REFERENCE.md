# ENV_REFERENCE — Minutare InteliClinic

Mapa completo de todas as variáveis de ambiente do projeto.

**Legenda de obrigatoriedade:**
- `LOCAL` — obrigatória em ambiente local
- `VPS` — obrigatória no deploy na VPS
- `BUILD` — precisa estar definida antes do `docker compose build`
- `OPCIONAL` — tem valor padrão seguro

---

## 1. Identidade do Deploy (Docker Compose / Dokploy)

| Variável | Obrig. | Exemplo | Onde é usada | Impacto |
|---|---|---|---|---|
| `COMPOSE_PROJECT_NAME` | VPS | `minutare` | `docker-compose.yml` | Nome dos containers e routers Traefik. Use letras/hífens. |
| `FRONTEND_DOMAIN` | VPS | `painel.suaclinica.com.br` | `docker-compose.yml` labels Traefik | Domínio público do frontend. Traefik emite TLS. |
| `API_DOMAIN` | VPS | `api.suaclinica.com.br` | `docker-compose.yml` labels Traefik | Domínio público da API. Telegram webhook aponta aqui. |

> **Nota Dokploy:** `COMPOSE_PROJECT_NAME` é usado nos nomes de routers Traefik — dois deploys com o mesmo nome causam conflito no proxy.

---

## 2. Banco de Dados — PostgreSQL 16 + pgvector

| Variável | Obrig. | Exemplo | Onde é usada | Impacto |
|---|---|---|---|---|
| `POSTGRES_USER` | LOCAL / VPS | `minutare` | `docker-compose.yml`, entrypoint | Usuário do banco. |
| `POSTGRES_PASSWORD` | LOCAL / VPS | `senha-forte-aqui` | `docker-compose.yml`, entrypoint | Senha do banco. Use `openssl rand -hex 32`. |
| `POSTGRES_DB` | LOCAL / VPS | `minutare_prod` | `docker-compose.yml`, entrypoint | Nome do banco. |
| `DATABASE_URL` | OPCIONAL | `postgresql+asyncpg://user:pass@db:5432/db` | `app/core/config.py`, entrypoint | Montada automaticamente no compose. Defina só se banco for externo. |

> `DATABASE_URL` no compose é sempre `postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}` — não precisa definir manualmente.

---

## 3. Aplicação — API FastAPI

| Variável | Obrig. | Exemplo | Onde é usada | Impacto |
|---|---|---|---|---|
| `APP_ENV` | VPS | `production` | `config.py`, `main.py`, entrypoint | `production` desativa debug, SQLite e reload. |
| `APP_DEBUG` | OPCIONAL | `false` | `config.py` | Ativa traceback detalhado nas respostas. |
| `APP_LOG_LEVEL` | OPCIONAL | `INFO` | `config.py`, entrypoint | Nível de log do Uvicorn e da aplicação. |
| `APP_SECRET_KEY` | VPS | (32 chars hex) | `config.py` | Usado para assinatura interna. Gerar com `openssl rand -hex 32`. |
| `CORS_ORIGINS` | VPS | `["https://painel.suaclinica.com.br"]` | `main.py` middleware CORS | Lista JSON de origens permitidas. Wildcard `*` expõe a API publicamente. |
| `UVICORN_WORKERS` | OPCIONAL | `1` | `entrypoint.sh` | Workers Uvicorn. Manter 1 com async + SQLAlchemy connection pool. |

---

## 4. Frontend — Next.js

| Variável | Obrig. | Exemplo | Onde é usada | Impacto |
|---|---|---|---|---|
| `NEXT_PUBLIC_API_URL` | VPS + BUILD | `https://api.suaclinica.com.br` | `docker-compose.yml` build arg, `frontend/src/lib/api.ts` | **Baked no bundle em build time.** Deve apontar para o domínio público da API. Toda chamada do browser vai para esse endereço. |
| `NODE_ENV` | OPCIONAL | `production` | `frontend/Dockerfile` | Definida automaticamente no Dockerfile. |
| `PORT` | OPCIONAL | `3000` | `frontend/Dockerfile` | Porta interna do Next.js. |
| `HOSTNAME` | OPCIONAL | `0.0.0.0` | `frontend/Dockerfile` | Bind do servidor Next.js. |

> `NEXT_PUBLIC_API_URL` é a variável mais crítica do frontend. Se errada, o painel não consegue chamar a API.

---

## 5. Inteligência Artificial / LLM

| Variável | Obrig. | Exemplo | Onde é usada | Impacto |
|---|---|---|---|---|
| `OPENAI_API_KEY` | VPS (se usar OpenAI) | `sk-...` | `config.py`, `llm_client.py`, `response_builder.py` | Sem chave, o sistema cai para templates de resposta hardcoded. |
| `ANTHROPIC_API_KEY` | OPCIONAL | `sk-ant-...` | `config.py`, `llm_client.py` | Alternativa ao OpenAI. |
| `GEMINI_API_KEY` | OPCIONAL | `AIzaSy...` | `config.py`, `llm_client.py` | Alternativa ao OpenAI. |
| `EMBEDDING_PROVIDER` | OPCIONAL | `openai` | `config.py` | Provider para geração de embeddings. Valores: `openai`, `anthropic`, `local`. |
| `LLM_MODEL` | OPCIONAL | _(vazio)_ | `config.py`, `llm_client.py` | Override do modelo. Vazio usa o default do provider. |

> Sem nenhuma API key, o orquestrador funciona em modo template (respostas fixas). O Telegram recebe resposta mas sem IA generativa.

---

## 6. Telegram Bot

| Variável | Obrig. | Exemplo | Onde é usada | Impacto |
|---|---|---|---|---|
| `TELEGRAM_BOT_TOKEN` | VPS | `123456:ABC-...` | `config.py`, `telegram/client.py` | Token do BotFather. Sem ele, nenhuma mensagem é enviada/recebida. |
| `TELEGRAM_WEBHOOK_URL` | VPS | `https://api.suaclinica.com.br/api/v1/telegram/webhook` | `config.py`, rota de set-webhook | URL pública que o Telegram chama. Deve ser HTTPS e acessível. |
| `TELEGRAM_WEBHOOK_SECRET` | VPS | (32 chars hex) | `config.py`, `webhook_handler.py` | Valida que a requisição veio do Telegram. Gerar com `openssl rand -hex 32`. |

> O webhook não é registrado automaticamente no start. Deve ser configurado via `POST /api/v1/telegram/set-webhook` após o deploy.

---

## 7. RAG — Retrieval-Augmented Generation

| Variável | Obrig. | Exemplo | Onde é usada | Impacto |
|---|---|---|---|---|
| `QDRANT_URL` | OPCIONAL | `http://qdrant:6333` | `config.py`, repositórios RAG | Injetado automaticamente no compose. Defina só se Qdrant for externo. |
| `RAG_CONFIDENCE_THRESHOLD` | OPCIONAL | `0.75` | `config.py`, `rag_service.py` | Limiar mínimo de similaridade para usar um chunk. Abaixo disso, cai para fallback. |
| `RAG_TOP_K` | OPCIONAL | `5` | `config.py`, `rag_repository.py` | Número de chunks retornados por query. |
| `RAG_CHUNK_SIZE` | OPCIONAL | `500` | `config.py`, pipeline de ingestão | Tamanho dos chunks em caracteres. |
| `RAG_CHUNK_OVERLAP` | OPCIONAL | `100` | `config.py`, pipeline de ingestão | Sobreposição entre chunks consecutivos. |

> O RAG operacional do MVP usa PostgreSQL + pgvector, não Qdrant. O Qdrant está presente no compose para uso futuro.

---

## 8. Identidade da Clínica

| Variável | Obrig. | Exemplo | Onde é usada | Impacto |
|---|---|---|---|---|
| `CLINIC_ID` | VPS | `clinica_saude_sp` | Seed, `ClinicSettings` | Slug identificador único desta instância. Usado na separação futura de dados. |
| `CLINIC_NAME` | VPS | `Clínica Saúde SP` | Seed, prompts, seed_data | Nome completo exibido nas respostas e seeds. |
| `CLINIC_SHORT_NAME` | OPCIONAL | `Clínica Saúde` | Seed, branding | Nome curto do chatbot. |
| `CLINIC_CNPJ` | OPCIONAL | `00.000.000/0001-00` | Seed, documentos | CNPJ da clínica. |
| `CLINIC_DOMAIN` | OPCIONAL | `suaclinica.com.br` | Seed, documentos | Domínio do site da clínica. |
| `CLINIC_PHONE` | OPCIONAL | `(11) 9 0000-0000` | Seed, prompts | Telefone exibido nas respostas. |
| `CLINIC_CITY` | OPCIONAL | `São Paulo` | Seed | Cidade. |
| `CLINIC_STATE` | OPCIONAL | `SP` | Seed | UF. |
| `CLINIC_TIMEZONE` | OPCIONAL | `America/Sao_Paulo` | Agendamento, lógica de horário | Fuso horário para interpretação de datas. |

---

## 9. Features por Clínica

| Variável | Obrig. | Default | Impacto |
|---|---|---|---|
| `CLINIC_FEATURE_SCHEDULING` | OPCIONAL | `true` | Habilita agendamento via chatbot. |
| `CLINIC_FEATURE_INSURANCE_QUERY` | OPCIONAL | `true` | Habilita consulta de convênios. |
| `CLINIC_FEATURE_FINANCIAL` | OPCIONAL | `false` | Habilita módulo financeiro (ainda em Plano). |
| `CLINIC_FEATURE_GLOSA_DETECTION` | OPCIONAL | `false` | Detecção de glosas (ainda em Plano). |
| `CLINIC_FEATURE_VOICE` | OPCIONAL | `false` | Canal de voz/LiveKit (ainda em Plano). |
| `CLINIC_FEATURE_GRAPHRAG` | OPCIONAL | `false` | GraphRAG (ainda em Plano). |

---

## 10. Branding do Chatbot

| Variável | Obrig. | Exemplo | Impacto |
|---|---|---|---|
| `CLINIC_CHATBOT_NAME` | OPCIONAL | `Assistente` | Nome do bot nas mensagens. |
| `CLINIC_CHATBOT_GREETING` | OPCIONAL | `Olá! Sou o assistente da {clinic_name}...` | Mensagem de saudação inicial. |
| `CLINIC_PRIMARY_COLOR` | OPCIONAL | `#0066CC` | Cor primária no frontend (futuro uso). |

---

## 11. Horário de Funcionamento

| Variável | Obrig. | Exemplo | Impacto |
|---|---|---|---|
| `CLINIC_BUSINESS_HOURS_START` | OPCIONAL | `08:00` | Início do atendimento. |
| `CLINIC_BUSINESS_HOURS_END` | OPCIONAL | `18:00` | Fim do atendimento. |
| `CLINIC_BUSINESS_DAYS` | OPCIONAL | `[1,2,3,4,5]` | Dias úteis. 1=seg, 6=sab, 7=dom. |

---

## 12. Convênios

| Variável | Obrig. | Exemplo | Impacto |
|---|---|---|---|
| `CLINIC_ACCEPTED_INSURANCES` | OPCIONAL | `["Unimed","Bradesco"]` | Lista usada em respostas de convênios. |
| `CLINIC_ACCEPTS_PRIVATE` | OPCIONAL | `true` | Habilita atendimento particular. |

---

## Resumo por escopo

### Obrigatórias localmente

```
POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB
APP_SECRET_KEY
OPENAI_API_KEY (ou outro LLM)
```

### Obrigatórias na VPS

```
COMPOSE_PROJECT_NAME
FRONTEND_DOMAIN
API_DOMAIN
POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB
APP_ENV=production
APP_SECRET_KEY
CORS_ORIGINS
NEXT_PUBLIC_API_URL  ← precisa estar definida ANTES do build
OPENAI_API_KEY (ou outro LLM)
TELEGRAM_BOT_TOKEN
TELEGRAM_WEBHOOK_URL
TELEGRAM_WEBHOOK_SECRET
CLINIC_ID
CLINIC_NAME
```

### Variáveis que afetam build Docker

- `NEXT_PUBLIC_API_URL` — baked no bundle Next.js em `docker compose build`

### Variáveis que afetam o roteamento Dokploy/Traefik

- `COMPOSE_PROJECT_NAME`
- `FRONTEND_DOMAIN`
- `API_DOMAIN`

### Variáveis que afetam integrações externas

- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_URL`, `TELEGRAM_WEBHOOK_SECRET`
- `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `GEMINI_API_KEY`

### Variáveis injetadas automaticamente pelo docker-compose (não definir manualmente)

- `DATABASE_URL` → `postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}`
- `QDRANT_URL` → `http://qdrant:6333`
