# VPS Deploy Checklist — Minutare InteliClinic / climesa (Dokploy)

Domínios desta instância:
- **API**: `https://api.inteliclinic.minutarecore.space`
- **Frontend**: `https://inteliclinic.minutarecore.space`

Use este checklist na ordem apresentada. Cada item deve ser confirmado antes de avançar.

---

## Pré-requisitos na VPS

- [ ] Docker 24.x instalado (`docker --version`)
- [ ] Docker Compose v2 instalado (`docker compose version`)
- [ ] Dokploy instalado e Traefik ativo
- [ ] Rede `dokploy-network` criada (`docker network ls | grep dokploy-network`)
- [ ] VPS com mínimo 4 GB RAM e 40 GB disco
- [ ] Acesso SSH à VPS

---

## 1. DNS

- [ ] Criar registro A `api.inteliclinic.minutarecore.space` → IP da VPS
- [ ] Criar registro A `inteliclinic.minutarecore.space` → IP da VPS
- [ ] Aguardar propagação DNS (`dig api.inteliclinic.minutarecore.space`)
- [ ] Confirmar que os domínios resolvem corretamente antes de subir o compose

---

## 2. Portas na VPS

| Porta | Serviço | Visibilidade |
|---|---|---|
| 80 | Traefik HTTP (redirect para HTTPS) | Pública |
| 443 | Traefik HTTPS | Pública |
| 8000 | API (interna) | Apenas via Traefik |
| 3000 | Frontend (interno) | Apenas via Traefik |
| 5432 | PostgreSQL (interno) | Nunca expor |
| 6333 | Qdrant (interno) | Nunca expor |

- [ ] Porta 80 aberta no firewall da VPS
- [ ] Porta 443 aberta no firewall da VPS
- [ ] Portas 5432 e 6333 fechadas para tráfego externo

---

## 3. Código na VPS

```bash
git clone git@github.com:minutare14/minutare-inteliclinic.git
cd minutare-inteliclinic
git checkout main
```

- [ ] Repositório clonado na VPS
- [ ] Branch correta (`git branch`)

---

## 4. Arquivo de ambiente

```bash
cp .env.vps.example .env
nano .env
```

**Variáveis obrigatórias — já preenchidas no `.env.vps.example`:**

| Variável | Valor definido |
|---|---|
| `COMPOSE_PROJECT_NAME` | `climesa` |
| `FRONTEND_DOMAIN` | `inteliclinic.minutarecore.space` |
| `API_DOMAIN` | `api.inteliclinic.minutarecore.space` |
| `NEXT_PUBLIC_API_URL` | `https://api.inteliclinic.minutarecore.space` |
| `POSTGRES_PASSWORD` | `ASD14200` |
| `APP_SECRET_KEY` | `ASD14200` *(trocar por valor gerado: `openssl rand -hex 32`)* |
| `CORS_ORIGINS` | `["https://inteliclinic.minutarecore.space"]` |
| `LLM_PROVIDER` | `groq` |
| `LLM_MODEL` | `llama-3.3-70b-versatile` |
| `TELEGRAM_WEBHOOK_URL` | `https://api.inteliclinic.minutarecore.space/api/v1/telegram/webhook` |
| `TELEGRAM_WEBHOOK_SECRET` | `ASD14200` *(trocar por valor gerado: `openssl rand -hex 32`)* |
| `TELEGRAM_AUTO_WEBHOOK` | `true` |
| `CLINIC_ID` | `climesa` |
| `CLINIC_NAME` | `climesa` |

**Variáveis que você DEVE preencher manualmente no `.env`:**

- [ ] `GROQ_API_KEY` — chave obtida em https://console.groq.com/keys
- [ ] `TELEGRAM_BOT_TOKEN` — token do BotFather
- [ ] *(Opcional)* `OPENAI_API_KEY` — se quiser embeddings vetoriais no RAG

---

## 5. Build e subida

```bash
# Build (NEXT_PUBLIC_API_URL deve estar no .env antes deste passo)
docker compose build

# Subir todos os serviços
docker compose up -d
```

- [ ] Build concluído sem erros
- [ ] `docker compose ps` mostra todos os containers `Up`

---

## 6. Verificar containers

```bash
docker compose ps
docker compose logs db --tail 20
docker compose logs api --tail 40
docker compose logs frontend --tail 20
```

- [ ] `db` — status `healthy`
- [ ] `qdrant` — status `Up` (pode demorar ~30s)
- [ ] `api` — status `healthy` (aguardar até 90s — roda migrations + seed + webhook no start)
- [ ] `frontend` — status `healthy`

---

## 7. Volumes persistentes

```bash
docker volume ls | grep climesa
```

- [ ] Volume `climesa_pgdata` criado (dados PostgreSQL)
- [ ] Volume `climesa_qdrant_data` criado (índices Qdrant)

> **Crítico:** nunca apagar esses volumes em produção. Fazer backup regularmente.

---

## 8. Health checks

```bash
# API
curl -sf https://api.inteliclinic.minutarecore.space/health

# DB via API
curl -sf https://api.inteliclinic.minutarecore.space/health/db

# Frontend
curl -sf https://inteliclinic.minutarecore.space/api/health
```

- [ ] `GET /health` retorna `{"status":"ok","service":"minutare-med"}`
- [ ] `GET /health/db` retorna `{"status":"ok","database":"connected"}`
- [ ] `GET /api/health` (frontend) retorna `{"status":"ok","service":"minutare-frontend"}`

---

## 9. TLS / HTTPS

- [ ] `https://api.inteliclinic.minutarecore.space/health` responde sem erro de certificado
- [ ] `https://inteliclinic.minutarecore.space` abre sem erro de certificado
- [ ] Certificado Let's Encrypt emitido pelo Traefik (aguardar até 2 min após primeira requisição)

---

## 10. Telegram Webhook (automático)

Com `TELEGRAM_AUTO_WEBHOOK=true`, o webhook é registrado automaticamente no startup da API.
Verifique nos logs da API:

```bash
docker compose logs api | grep -i webhook
```

Deve aparecer algo como:
```
INFO  Webhook atual: (nenhum)
INFO  Webhook desejado: https://api.inteliclinic.minutarecore.space/api/v1/telegram/webhook
INFO  Webhook registrado com sucesso: https://api.inteliclinic.minutarecore.space/api/v1/telegram/webhook
```

Se já estiver correto de um deploy anterior:
```
INFO  Webhook já está correto — nenhuma ação necessária.
```

Para verificar o status manualmente:
```bash
curl -sf https://api.inteliclinic.minutarecore.space/api/v1/telegram/webhook-info
```

Para registrar manualmente (se necessário):
```bash
curl -X POST https://api.inteliclinic.minutarecore.space/api/v1/telegram/set-webhook \
    -H "Content-Type: application/json" \
    -d '{}'
```

- [ ] Logs mostram webhook registrado ou já correto
- [ ] `webhook-info` mostra `url` preenchida
- [ ] Enviar mensagem de teste para o bot no Telegram e verificar resposta

---

## 11. IA / Groq

Verifique nos logs da API que o provider está ativo:

```bash
docker compose logs api | grep -i "groq\|llm\|provider"
```

Para testar a IA via RAG:
```bash
curl -X POST https://api.inteliclinic.minutarecore.space/api/v1/rag/query \
    -H "Content-Type: application/json" \
    -d '{"query": "Quais convênios são aceitos?"}'
```

- [ ] Nenhum erro de `GROQ_API_KEY` nos logs
- [ ] Query RAG retorna resultado com `answer` gerado (não apenas template)

---

## 12. RAG — Knowledge Base

```bash
# Verificar documentos ingeridos pelo seed
curl -sf https://api.inteliclinic.minutarecore.space/api/v1/rag/documents
```

- [ ] Pelo menos 1 documento listado (seed popula automaticamente)

---

## 13. Painel Frontend

- [ ] Abrir `https://inteliclinic.minutarecore.space` no browser
- [ ] Dashboard carrega sem erros de console
- [ ] Página de Profissionais lista os profissionais do seed
- [ ] Página de Integrações → Telegram mostra status do webhook

---

## 14. Ordem de observação nos logs após subir

```bash
# 1. DB — precisa estar healthy antes de tudo
docker compose logs db -f

# 2. API — migrations + seed + webhook + start (pode levar 60-90s)
docker compose logs api -f

# 3. Frontend — build standalone + start (~120s)
docker compose logs frontend -f
```

**Sinais de problema:**

| Log | Possível causa |
|---|---|
| `DB not available after 60s` | POSTGRES_* vars erradas ou DB não subiu |
| `alembic.exc.CommandError` | Migration falhou — verificar DATABASE_URL |
| `Error: Cannot find module` | Build do Next.js incompleto — rebuild |
| `TELEGRAM_BOT_TOKEN não definido` | Variável faltando no .env |
| `GROQ_API_KEY` ausente | LLM_PROVIDER=groq mas chave não preenchida |
| `Signature mismatch` no webhook | TELEGRAM_WEBHOOK_SECRET incorreto |

---

## 15. Backup (configurar após validação)

- [ ] Configurar backup diário do volume `climesa_pgdata`
- [ ] Configurar backup do volume `climesa_qdrant_data` (índices vetoriais)
- [ ] Testar restore do backup em ambiente separado

---

## 16. Atualização futura

```bash
git pull origin main
docker compose build api frontend
docker compose up -d --no-deps api frontend
docker compose exec api alembic upgrade head
```

- [ ] Migrations executadas após cada atualização que contenha `alembic/versions/*`
- [ ] Verificar health checks após restart
- [ ] O webhook Telegram será revalidado automaticamente no próximo startup
