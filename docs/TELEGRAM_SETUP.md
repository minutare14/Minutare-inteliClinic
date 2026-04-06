# Telegram Bot Setup — Minutare Med

## 1. Criar o Bot

1. Abra o Telegram e converse com o [@BotFather](https://t.me/BotFather)
2. Envie `/newbot`
3. Escolha um nome: `Minutare Med`
4. Escolha um username: `minutare_med_bot` (deve terminar com `_bot`)
5. Copie o token gerado (formato: `123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11`)

## 2. Configurar Variáveis de Ambiente

No arquivo `.env`:

```env
TELEGRAM_BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
TELEGRAM_WEBHOOK_URL=https://seu-dominio.com/api/v1/telegram/webhook
TELEGRAM_WEBHOOK_SECRET=uma_string_secreta_aleatoria
```

## 3. Expor a API Publicamente (Desenvolvimento)

Para desenvolvimento local, use [ngrok](https://ngrok.com/):

```bash
# Instale ngrok
# Inicie o tunnel
ngrok http 8000
```

Copie a URL HTTPS gerada (ex: `https://abc123.ngrok-free.app`) e use como base para o webhook.

## 4. Registrar o Webhook

Com a API rodando:

```bash
# Via endpoint da API
curl -X POST "http://localhost:8000/api/v1/telegram/set-webhook?url=https://abc123.ngrok-free.app/api/v1/telegram/webhook"

# Ou diretamente na API do Telegram
curl "https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://abc123.ngrok-free.app/api/v1/telegram/webhook&secret_token=<SECRET>"
```

## 5. Verificar Webhook

```bash
curl http://localhost:8000/api/v1/telegram/webhook-info
```

## 6. Testar

1. Abra o Telegram e procure por `@minutare_med_bot`
2. Envie `/start` ou "Olá"
3. O bot deve responder com a mensagem de boas-vindas
4. Teste os fluxos:
   - "Quero agendar uma consulta" → fluxo de agendamento
   - "Quais convênios vocês aceitam?" → resposta RAG
   - "Quero falar com um atendente" → handoff

## 7. Webhook Secret (Segurança)

O Telegram envia o header `X-Telegram-Bot-Api-Secret-Token` em cada request.
A API valida esse header contra `TELEGRAM_WEBHOOK_SECRET`.
Em produção, sempre configure esse secret.

## Troubleshooting

- **Bot não responde:** verifique se o webhook está registrado (`/webhook-info`)
- **Erro 403:** verifique o `TELEGRAM_WEBHOOK_SECRET`
- **Erro 500:** verifique os logs da API (`docker-compose logs api`)
- **Mensagens não chegam:** verifique se a URL é HTTPS e acessível externamente
