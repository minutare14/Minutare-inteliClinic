"""
LLM Client — Provider-agnostic abstraction for LLM calls.

Adapted from qwen-test's llm_client.py + gemini_client.py + groq_client.py.
Supports: Groq, OpenAI, Anthropic, Gemini (via OpenAI-compatible endpoint or native).
Falls back gracefully when no provider is configured.

Provider selection order:
  1. settings.llm_provider (explicit) — se configurado como "groq", "openai", etc.
  2. Auto-detect pela primeira API key disponível: Groq → OpenAI → Anthropic → Gemini

Factory pattern: call_llm() picks the active provider from settings.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# Retry config
MAX_RETRIES = 3
RETRY_BACKOFF = 1.5  # seconds, multiplied each retry
TIMEOUT_SECONDS = 30


async def call_llm(
    messages: list[dict],
    *,
    temperature: float = 0.7,
    max_tokens: int = 1024,
    json_mode: bool = False,
) -> dict[str, Any] | None:
    """
    Call the configured LLM provider.

    Returns:
        {"content": str, "parsed": dict|None, "metrics": dict} or None on failure.
    """
    provider = _resolve_provider()

    if provider == "groq":
        return await _call_groq(messages, temperature, max_tokens, json_mode)
    elif provider == "openai":
        return await _call_openai(messages, temperature, max_tokens, json_mode)
    elif provider == "anthropic":
        return await _call_anthropic(messages, temperature, max_tokens)
    elif provider == "gemini":
        return await _call_gemini(messages, temperature, max_tokens, json_mode)
    else:
        logger.warning("No LLM provider configured — returning None")
        return None


def _resolve_provider() -> str | None:
    """
    Determine which provider to use.

    Priority:
      1. settings.llm_provider se definido explicitamente (ex: LLM_PROVIDER=groq)
      2. Auto-detect pela primeira API key disponível: Groq → OpenAI → Anthropic → Gemini
    """
    explicit = (settings.llm_provider or "").strip().lower()
    if explicit:
        key_map = {
            "groq": settings.groq_api_key,
            "openai": settings.openai_api_key,
            "anthropic": settings.anthropic_api_key,
            "gemini": settings.gemini_api_key,
        }
        if explicit not in key_map:
            logger.warning("LLM_PROVIDER='%s' desconhecido — tentando auto-detect", explicit)
        elif not key_map[explicit]:
            logger.warning("LLM_PROVIDER='%s' configurado mas chave API ausente", explicit)
        else:
            return explicit

    # Auto-detect
    if settings.groq_api_key:
        return "groq"
    if settings.openai_api_key:
        return "openai"
    if settings.anthropic_api_key:
        return "anthropic"
    if settings.gemini_api_key:
        return "gemini"
    return None


# ─── Groq (OpenAI-compatible) ─────────────────────────────────
# Endpoint: https://api.groq.com/openai/v1/chat/completions
# Default model: llama-3.3-70b-versatile
# Docs: https://console.groq.com/docs/openai


async def _call_groq(
    messages: list[dict],
    temperature: float,
    max_tokens: int,
    json_mode: bool,
) -> dict[str, Any] | None:
    """Call Groq Chat Completions API (OpenAI-compatible)."""
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.groq_api_key}",
        "Content-Type": "application/json",
    }
    body: dict[str, Any] = {
        "model": settings.llm_model or "llama-3.3-70b-versatile",
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}

    return await _http_call(url, headers, body, provider="groq")


# ─── OpenAI / OpenAI-compatible ───────────────────────────────


async def _call_openai(
    messages: list[dict],
    temperature: float,
    max_tokens: int,
    json_mode: bool,
) -> dict[str, Any] | None:
    """Call OpenAI Chat Completions API."""
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }
    body: dict[str, Any] = {
        "model": settings.llm_model or "gpt-4o-mini",
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}

    return await _http_call(url, headers, body, provider="openai")


# ─── Anthropic ─────────────────────────────────────────────────


async def _call_anthropic(
    messages: list[dict],
    temperature: float,
    max_tokens: int,
) -> dict[str, Any] | None:
    """Call Anthropic Messages API."""
    url = "https://api.anthropic.com/v1/messages"

    # Extract system prompt from messages
    system_text = ""
    api_messages = []
    for msg in messages:
        if msg["role"] == "system":
            system_text += msg["content"] + "\n"
        else:
            api_messages.append({"role": msg["role"], "content": msg["content"]})

    headers = {
        "x-api-key": settings.anthropic_api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    body: dict[str, Any] = {
        "model": settings.llm_model or "claude-sonnet-4-20250514",
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": api_messages,
    }
    if system_text.strip():
        body["system"] = system_text.strip()

    return await _http_call(url, headers, body, provider="anthropic")


# ─── Gemini (via Google AI Studio REST) ───────────────────────


async def _call_gemini(
    messages: list[dict],
    temperature: float,
    max_tokens: int,
    json_mode: bool,
) -> dict[str, Any] | None:
    """Call Google Gemini generateContent API."""
    model = settings.llm_model or "gemini-2.5-flash"
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}"
        f":generateContent?key={settings.gemini_api_key}"
    )

    # Convert messages to Gemini format
    system_text = ""
    contents = []
    for msg in messages:
        if msg["role"] == "system":
            system_text += msg["content"] + "\n"
        else:
            role = "user" if msg["role"] == "user" else "model"
            contents.append({"role": role, "parts": [{"text": msg["content"]}]})

    body: dict[str, Any] = {
        "contents": contents,
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        },
    }
    if system_text.strip():
        body["systemInstruction"] = {"parts": [{"text": system_text.strip()}]}
    if json_mode:
        body["generationConfig"]["responseMimeType"] = "application/json"

    headers = {"Content-Type": "application/json"}
    return await _http_call(url, headers, body, provider="gemini")


# ─── HTTP transport with retry ─────────────────────────────────


async def _http_call(
    url: str,
    headers: dict,
    body: dict,
    *,
    provider: str,
) -> dict[str, Any] | None:
    """Execute HTTP POST with retry logic and response parsing."""
    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        t0 = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
                resp = await client.post(url, headers=headers, json=body)

            elapsed_ms = round((time.monotonic() - t0) * 1000)

            if resp.status_code == 429 or resp.status_code >= 500:
                wait = RETRY_BACKOFF * attempt
                logger.warning(
                    "LLM %s returned %d, retrying in %.1fs (attempt %d/%d)",
                    provider, resp.status_code, wait, attempt, MAX_RETRIES,
                )
                last_error = f"HTTP {resp.status_code}"
                import asyncio
                await asyncio.sleep(wait)
                continue

            resp.raise_for_status()
            data = resp.json()

            content = _extract_content(data, provider)
            parsed = _try_parse_json(content)

            return {
                "content": content,
                "parsed": parsed,
                "metrics": {
                    "provider": provider,
                    "elapsed_ms": elapsed_ms,
                    "attempt": attempt,
                },
            }

        except httpx.TimeoutException:
            last_error = "timeout"
            logger.warning("LLM %s timeout (attempt %d/%d)", provider, attempt, MAX_RETRIES)
        except httpx.HTTPStatusError as exc:
            last_error = f"HTTP {exc.response.status_code}"
            logger.error("LLM %s HTTP error: %s", provider, exc)
            break  # Don't retry client errors (4xx except 429)
        except Exception as exc:
            last_error = str(exc)
            logger.exception("LLM %s unexpected error", provider)
            break

    logger.error("LLM %s failed after %d attempts: %s", provider, MAX_RETRIES, last_error)
    return None


def _extract_content(data: dict, provider: str) -> str:
    """Extract text content from provider-specific response format."""
    if provider in ("openai", "groq"):
        # Groq usa o mesmo formato de resposta que OpenAI
        return data["choices"][0]["message"]["content"]
    elif provider == "anthropic":
        return data["content"][0]["text"]
    elif provider == "gemini":
        return data["candidates"][0]["content"]["parts"][0]["text"]
    return ""


def _try_parse_json(text: str | None) -> dict | None:
    """Try to parse response as JSON, cleaning markdown fences if needed."""
    if not text:
        return None
    cleaned = text.strip()
    # Remove markdown code blocks
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines).strip()
    try:
        return json.loads(cleaned)
    except (json.JSONDecodeError, ValueError):
        return None
