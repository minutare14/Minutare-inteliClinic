# VPS Deploy Checklist — Minutare InteliClinic (Dokploy)

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

- [ ] Criar registro A `api.suaclinica.com.br` → IP da VPS
- [ ] Criar registro A `painel.suaclinica.com.br` → IP da VPS
- [ ] Aguardar propagação DNS (`dig api.suaclinica.com.br`)
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
nano .env   # ou editor de sua preferência
```

**Variáveis obrigatórias a preencher:**

- [ ] `COMPOSE_PROJECT_NAME` — slug único (ex: `clinica-saude-sp`)
- [ ] `FRONTEND_DOMAIN` — domínio real do painel
- [ ] `API_DOMAIN` — domínio real da API
- [ ] `POSTGRES_PASSWORD` — senha forte (`openssl rand -hex 32`)
- [ ] `APP_SECRET_KEY` — chave forte (`openssl rand -hex 32`)
- [ ] `CORS_ORIGINS` — `["https://painel.suaclinica.com.br"]`
- [ ] `NEXT_PUBLIC_API_URL` — `https://api.suaclinica.com.br` ← **antes do build**
- [ ] `OPENAI_API_KEY` (ou outro LLM)
- [ ] `TELEGRAM_BOT_TOKEN`
- [ ] `TELEGRAM_WEBHOOK_URL` — `https://api.suaclinica.com.br/api/v1/telegram/webhook`
- [ ] `TELEGRAM_WEBHOOK_SECRET` — string aleatória (`openssl rand -hex 32`)
- [ ] `CLINIC_ID` — slug único da clínica
- [ ] `CLINIC_NAME` — nome da clínica

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
- [ ] `api` — status `healthy` (aguardar até 90s — roda migrations + seed no start)
- [ ] `frontend` — status `healthy`

---

## 7. Volumes persistentes

```bash
docker volume ls | grep minutare
```

- [ ] Volume `minutare-*_pgdata` criado (dados PostgreSQL)
- [ ] Volume `minutare-*_qdrant_data` criado (índices Qdrant)

> **Crítico:** nunca apagar esses volumes em produção. Fazer backup regularmente.

---

## 8. Health checks

```bash
# API
curl -sf https://api.suaclinica.com.br/health

# DB via API
curl -sf https://api.suaclinica.com.br/health/db

# Frontend
curl -sf https://painel.suaclinica.com.br/api/health
```

- [ ] `GET /health` retorna `{"status":"ok","service":"minutare-med"}`
- [ ] `GET /health/db` retorna `{"status":"ok","database":"connected"}`
- [ ] `GET /api/health` (frontend) retorna `{"status":"ok","service":"minutare-frontend"}`

---

## 9. TLS / HTTPS

- [ ] `https://api.suaclinica.com.br/health` responde sem erro de certificado
- [ ] `https://painel.suaclinica.com.br` abre sem erro de certificado
- [ ] Certificado Let's Encrypt emitido pelo Traefik (aguardar até 2 min após primeira requisição)

---

## 10. Telegram Webhook

```bash
# Registrar webhook no Telegram
curl -sf https://api.suaclinica.com.br/api/v1/telegram/set-webhook?url=https://api.suaclinica.com.br/api/v1/telegram/webhook

# Verificar status do webhook
curl -sf https://api.suaclinica.com.br/api/v1/telegram/webhook-info
```

- [ ] Webhook registrado com sucesso
- [ ] `webhook-info` mostra `url` preenchida e `pending_update_count: 0`
- [ ] Enviar mensagem de teste para o bot no Telegram e verificar resposta

---

## 11. RAG — Knowledge Base

```bash
# Verificar documentos ingeridos pelo seed
curl -sf https://api.suaclinica.com.br/api/v1/rag/documents

# Testar busca RAG
curl -X POST https://api.suaclinica.com.br/api/v1/rag/query \
    -H "Content-Type: application/json" \
    -d '{"query": "Quais convênios são aceitos?"}'
```

- [ ] Pelo menos 1 documento listado (seed popula automaticamente)
- [ ] Query RAG retorna resultado com `answer` preenchido

---

## 12. Painel Frontend

- [ ] Abrir `https://painel.suaclinica.com.br` no browser
- [ ] Dashboard carrega sem erros de console
- [ ] Página de Profissionais lista os profissionais do seed
- [ ] Página de Integrações → Telegram mostra status do webhook

---

## 13. Ordem de observação nos logs após subir

Monitore nessa ordem:

```bash
# 1. DB — precisa estar healthy antes de tudo
docker compose logs db -f

# 2. API — migrations + seed + start (pode levar 60-90s)
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
| `TELEGRAM_BOT_TOKEN not set` | Variável faltando no .env |
| `Signature mismatch` no webhook | TELEGRAM_WEBHOOK_SECRET incorreto |

---

## 14. Backup (configurar após validação)

- [ ] Configurar backup diário do volume `pgdata`
- [ ] Configurar backup do volume `qdrant_data` (índices vetoriais)
- [ ] Testar restore do backup em ambiente separado

---

## 15. Atualização futura

```bash
git pull origin main
docker compose build api frontend
docker compose up -d --no-deps api frontend
docker compose exec api alembic upgrade head
```

- [ ] Migrations executadas após cada atualização que contenha `alembic/versions/*`
- [ ] Verificar health checks após restart
