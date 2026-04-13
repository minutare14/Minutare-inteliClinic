"""
register_telegram_webhook.py — Registro automático e idempotente do webhook do Telegram.

Chamado pelo entrypoint.sh no startup.

Lógica:
  1. Verifica se TELEGRAM_BOT_TOKEN está definido.
  2. Deriva a URL do webhook de API_DOMAIN se TELEGRAM_WEBHOOK_URL não estiver definida.
     URL derivada: https://{API_DOMAIN}/api/v1/telegram/webhook
  3. Consulta o webhook atual via getWebhookInfo.
  4. Só chama setWebhook se a URL atual for diferente da desejada.
  5. Inclui o secret token se TELEGRAM_WEBHOOK_SECRET estiver definido.
  6. Retorna exit code 0 em sucesso/skip, 1 em falha crítica.

Uso:
  python scripts/register_telegram_webhook.py

Variáveis lidas do ambiente:
  TELEGRAM_BOT_TOKEN        — obrigatória para executar
  API_DOMAIN                — usado para derivar URL (ex: api.clinica.com.br)
  TELEGRAM_WEBHOOK_URL      — opcional; se definida, sobrepõe API_DOMAIN
  TELEGRAM_WEBHOOK_SECRET   — opcional mas recomendada
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys

import httpx

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}"


def _api(method: str, token: str) -> str:
    return f"{TELEGRAM_API.format(token=token)}/{method}"


def _resolve_webhook_url() -> str:
    """Retorna a URL do webhook: explícita tem prioridade; senão, deriva de API_DOMAIN."""
    explicit = os.environ.get("TELEGRAM_WEBHOOK_URL", "").strip()
    if explicit and explicit not in ("[PREENCHER]", ""):
        return explicit
    domain = os.environ.get("API_DOMAIN", "").strip()
    if domain and domain not in ("[PREENCHER]", ""):
        return f"https://{domain}/api/v1/telegram/webhook"
    return ""


async def get_current_webhook(token: str) -> str | None:
    """Retorna a URL do webhook atualmente registrado, ou None."""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(_api("getWebhookInfo", token))
            resp.raise_for_status()
            data = resp.json()
            if data.get("ok"):
                return data.get("result", {}).get("url") or None
    except Exception as exc:
        logger.warning("Não foi possível consultar webhook info: %s", exc)
    return None


async def set_webhook(token: str, url: str, secret: str | None) -> bool:
    """Registra o webhook no Telegram. Retorna True em sucesso."""
    payload: dict = {"url": url}
    if secret:
        payload["secret_token"] = secret

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(_api("setWebhook", token), json=payload)
            resp.raise_for_status()
            data = resp.json()
            if data.get("ok"):
                logger.info("Webhook registrado com sucesso: %s", url)
                return True
            logger.error("Telegram recusou setWebhook: %s", data.get("description"))
            return False
    except Exception as exc:
        logger.error("Erro ao chamar setWebhook: %s", exc)
        return False


async def main() -> int:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token or token == "[PREENCHER]":
        logger.info("TELEGRAM_BOT_TOKEN não definido — pulando registro do webhook.")
        return 0

    webhook_url = _resolve_webhook_url()
    if not webhook_url:
        logger.warning(
            "Não foi possível determinar a URL do webhook. "
            "Defina API_DOMAIN ou TELEGRAM_WEBHOOK_URL."
        )
        return 0

    secret = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "").strip() or None

    current = await get_current_webhook(token)
    logger.info("Webhook atual: %s", current or "(nenhum)")
    logger.info("Webhook desejado: %s", webhook_url)

    if current == webhook_url:
        logger.info("Webhook já está correto — nenhuma ação necessária.")
        return 0

    ok = await set_webhook(token, webhook_url, secret)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
