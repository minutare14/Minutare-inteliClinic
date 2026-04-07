"""NLU extraction pipeline — high-level entry point consumed by LangGraph nodes.

ExtractionPipeline wraps InstructorMessageExtractor with:
- Configurable retry logic (up to max_retries attempts)
- Per-attempt timeout enforcement
- Conservative fallback construction on total failure
- Factory method for config-dict-based instantiation

The pipeline is the single integration point between the graph nodes and the NLU layer.
Nodes import and call ExtractionPipeline.process() — they do not interact with
InstructorMessageExtractor directly.

Usage:
    pipeline = ExtractionPipeline.from_config({
        "provider": "openai",
        "model": "gpt-4o-mini",
        "max_retries": 3,
    })
    result = await pipeline.process(
        message="Quero marcar uma consulta de dermatologia para esta semana",
        history=[{"role": "assistant", "content": "Olá! Como posso ajudar?"}],
    )
    print(result.intent)   # Intent.SCHEDULING
    print(result.desired_specialty)  # "dermatologia"
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from inteliclinic.core.nlu.extractors.message_extractor import InstructorMessageExtractor
from inteliclinic.core.nlu.schemas.message_schemas import (
    ExtractedMessage,
    Intent,
    ConfidenceLevel,
)

logger = logging.getLogger(__name__)

# ── Pipeline defaults ──────────────────────────────────────────────────────────
_DEFAULT_PROVIDER = "openai"
_DEFAULT_MODEL = "gpt-4o-mini"
_DEFAULT_MAX_RETRIES = 3
_DEFAULT_TIMEOUT_SECONDS = 15.0


def _make_timeout_fallback(original_text: str) -> ExtractedMessage:
    """Conservative ExtractedMessage for timeout scenarios."""
    return ExtractedMessage(
        intent=Intent.OTHER,
        confidence=0.0,
        confidence_level=ConfidenceLevel.LOW,
        original_text=original_text,
        is_ambiguous=True,
        ambiguity_reason="Tempo de resposta excedido — extração não concluída.",
        needs_clarification=True,
        clarification_question=(
            "Desculpe a demora. Poderia repetir o que precisa? "
            "Estou aqui para ajudar."
        ),
    )


def _make_error_fallback(original_text: str, reason: str) -> ExtractedMessage:
    """Conservative ExtractedMessage for unrecoverable error scenarios."""
    return ExtractedMessage(
        intent=Intent.OTHER,
        confidence=0.0,
        confidence_level=ConfidenceLevel.LOW,
        original_text=original_text,
        is_ambiguous=True,
        ambiguity_reason=f"Erro na extração: {reason}",
        needs_clarification=True,
        clarification_question=(
            "Não consegui processar sua mensagem corretamente. "
            "Poderia reformular o que precisa?"
        ),
    )


class ExtractionPipeline:
    """Orchestrates NLU extraction with retries, timeouts, and fallback handling.

    Attributes:
        extractor:       The InstructorMessageExtractor instance.
        max_retries:     Maximum number of extraction attempts before giving up.
        timeout_seconds: Per-attempt timeout in seconds.
    """

    def __init__(
        self,
        extractor: InstructorMessageExtractor,
        max_retries: int = _DEFAULT_MAX_RETRIES,
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self.extractor = extractor
        self.max_retries = max_retries
        self.timeout_seconds = timeout_seconds

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> ExtractionPipeline:
        """Factory method: build an ExtractionPipeline from a plain config dict.

        Config keys (all optional — defaults are used when omitted):
            provider (str):         LLM provider ("openai" | "anthropic"). Default "openai".
            model (str):            Model identifier. Default "gpt-4o-mini".
            api_key (str):          API key. Default "" (uses env vars).
            max_retries (int):      Retry attempts. Default 3.
            timeout_seconds (float): Per-attempt timeout. Default 15.0.

        Args:
            config: Configuration dict, e.g., loaded from clinic YAML.

        Returns:
            Ready-to-use ExtractionPipeline instance.
        """
        provider = config.get("provider", _DEFAULT_PROVIDER)
        model = config.get("model", _DEFAULT_MODEL)
        api_key = config.get("api_key", "")
        max_retries = int(config.get("max_retries", _DEFAULT_MAX_RETRIES))
        timeout_seconds = float(config.get("timeout_seconds", _DEFAULT_TIMEOUT_SECONDS))

        # Instructor's internal retry count (Pydantic validation retries inside one call)
        instructor_retries = max(1, max_retries - 1)

        extractor = InstructorMessageExtractor(
            provider=provider,
            model=model,
            api_key=api_key,
            max_retries=instructor_retries,
        )

        logger.info(
            "ExtractionPipeline.from_config: provider=%s | model=%s | retries=%d | timeout=%.1fs",
            provider,
            model,
            max_retries,
            timeout_seconds,
        )
        return cls(
            extractor=extractor,
            max_retries=max_retries,
            timeout_seconds=timeout_seconds,
        )

    async def process(
        self,
        message: str,
        history: list[dict[str, Any]] | None = None,
        context: dict[str, Any] | None = None,
    ) -> ExtractedMessage:
        """Extract structured data from a patient message with retry and timeout.

        Attempts extraction up to max_retries times. On each attempt, a per-attempt
        timeout is enforced. If all attempts fail, a conservative fallback is returned.

        Args:
            message: Raw patient message text.
            history: Prior conversation messages (OpenAI format). None = no history.
            context: Optional session context dict for the extractor.

        Returns:
            ExtractedMessage — validated structured data, or conservative fallback.
        """
        if not message or not message.strip():
            logger.warning("ExtractionPipeline.process: empty message received")
            return _make_error_fallback("", "Mensagem vazia recebida.")

        history = history or []
        last_exception: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            try:
                logger.debug(
                    "ExtractionPipeline.process: attempt %d/%d | message='%s...'",
                    attempt,
                    self.max_retries,
                    message[:50],
                )

                # Enforce per-attempt timeout
                extraction_coro = (
                    self.extractor.extract_with_history(message, history, context)
                    if history
                    else self.extractor.extract(message, context)
                )
                result: ExtractedMessage = await asyncio.wait_for(
                    extraction_coro,
                    timeout=self.timeout_seconds,
                )

                logger.info(
                    "ExtractionPipeline.process: success on attempt %d | intent=%s | confidence=%.2f",
                    attempt,
                    result.intent.value,
                    result.confidence,
                )
                return result

            except asyncio.TimeoutError:
                logger.warning(
                    "ExtractionPipeline.process: timeout on attempt %d/%d (%.1fs)",
                    attempt,
                    self.max_retries,
                    self.timeout_seconds,
                )
                last_exception = asyncio.TimeoutError(
                    f"Extraction timed out after {self.timeout_seconds}s"
                )

            except Exception as exc:
                logger.warning(
                    "ExtractionPipeline.process: error on attempt %d/%d: %s",
                    attempt,
                    self.max_retries,
                    exc,
                )
                last_exception = exc

            # Brief pause between retries to avoid hammering the API on transient errors
            if attempt < self.max_retries:
                await asyncio.sleep(0.5 * attempt)  # Linear backoff: 0.5s, 1.0s, 1.5s, ...

        # All attempts exhausted
        logger.error(
            "ExtractionPipeline.process: all %d attempts failed for message='%s...' | last_error=%s",
            self.max_retries,
            message[:50],
            last_exception,
        )

        if isinstance(last_exception, asyncio.TimeoutError):
            return _make_timeout_fallback(message)

        reason = str(last_exception) if last_exception else "Erro desconhecido"
        return _make_error_fallback(message, reason)

    async def process_batch(
        self,
        messages: list[str],
        context: dict[str, Any] | None = None,
    ) -> list[ExtractedMessage]:
        """Process multiple messages concurrently.

        Useful for bulk analysis (e.g., offline batch processing of historical messages).
        Each message is processed independently with its own timeout.

        Args:
            messages: List of raw message strings to process.
            context:  Shared context applied to all extractions.

        Returns:
            List of ExtractedMessage results in the same order as input.
        """
        tasks = [
            self.process(message=msg, history=[], context=context)
            for msg in messages
        ]
        results = await asyncio.gather(*tasks, return_exceptions=False)
        return list(results)
