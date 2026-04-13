"""
register_telegram_webhook.py — Registro automático e idempotente do webhook do Telegram.

Chamado pelo entrypoint.sh se TELEGRAM_AUTO_WEBHOOK=true.

Lógica:
  1. Verifica se TELEGRAM_BOT_TOKEN e TELEGRAM_WEBHOOK_URL estão definidos.
  2. Consulta o webhook atual via getWebhookInfo.
  3. Só chama setWebhook se a URL atual for diferente da configurada.
  4. Inclui o secret token se TELEGRAM_WEBHOOK_SECRET estiver definido.
  5. Retorna exit code 0 em sucesso/skip, 1 em falha crítica.

Uso:
  python scripts/register_telegram_webhook.py

Variáveis lidas do ambiente:
  TELEGRAM_BOT_TOKEN        — obrigatória
  TELEGRAM_WEBHOOK_URL      — obrigatória
  TELEGRAM_WEBHOOK_SECRET   — opcional mas recomendada
  TELEGRAM_AUTO_WEBHOOK     — deve ser "true" para executar (guarda)
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
    auto = os.environ.get("TELEGRAM_AUTO_WEBHOOK", "false").strip().lower()
    if auto != "true":
        logger.info("TELEGRAM_AUTO_WEBHOOK não está habilitado — pulando registro do webhook.")
        return 0

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    webhook_url = os.environ.get("TELEGRAM_WEBHOOK_URL", "").strip()
    secret = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "").strip() or None

    if not token:
        logger.warning("TELEGRAM_BOT_TOKEN não definido — pulando.")
        return 0

    if not webhook_url:
        logger.warning("TELEGRAM_WEBHOOK_URL não definido — pulando.")
        return 0

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
