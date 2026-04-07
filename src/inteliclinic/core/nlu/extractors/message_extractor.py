"""Message extractor using Instructor for structured output from LLMs.

Uses instructor library: https://github.com/567-labs/instructor
Wraps an OpenAI or Anthropic async client with Instructor for type-safe extraction.
The extractor validates its output against ExtractedMessage (a Pydantic model),
automatically retrying on validation errors using Instructor's built-in retry logic.

Supported providers:
- "openai"    : Uses AsyncOpenAI + instructor.from_openai()
- "anthropic" : Uses AsyncAnthropic + instructor.from_anthropic()

Usage:
    extractor = InstructorMessageExtractor(provider="openai", model="gpt-4o-mini")
    result = await extractor.extract("Preciso marcar uma consulta de cardiologia")
    print(result.intent)      # Intent.SCHEDULING
    print(result.confidence)  # e.g. 0.93
"""

from __future__ import annotations

import logging
from typing import Any

from inteliclinic.core.nlu.schemas.message_schemas import ExtractedMessage, Intent, ConfidenceLevel

logger = logging.getLogger(__name__)

# ── Conservative fallback ExtractedMessage ────────────────────────────────────
# Returned when the LLM call fails entirely (network error, quota exceeded, etc.)

def _make_fallback_extraction(original_text: str) -> ExtractedMessage:
    """Construct a safe, conservative ExtractedMessage when extraction fails.

    The fallback always marks the intent as OTHER with zero confidence,
    which guarantees the graph routes to the fallback node instead of
    attempting to process malformed data.
    """
    return ExtractedMessage(
        intent=Intent.OTHER,
        confidence=0.0,
        confidence_level=ConfidenceLevel.LOW,
        original_text=original_text,
        is_ambiguous=True,
        ambiguity_reason="Falha na extração automática — processamento indisponível.",
        needs_clarification=True,
        clarification_question="Poderia repetir sua solicitação? Terei prazer em ajudar.",
    )


def _build_user_message(message: str, context: dict[str, Any] | None) -> str:
    """Compose the user-facing message content for the extraction prompt.

    Optionally includes session context (patient ID, current intent from prior turn)
    to improve extraction accuracy in multi-turn conversations.
    """
    parts = [f"Mensagem do paciente:\n{message}"]

    if context:
        if ctx_intent := context.get("current_intent"):
            parts.append(f"\nContexto — intenção anterior: {ctx_intent}")
        if ctx_specialty := context.get("last_specialty"):
            parts.append(f"Contexto — especialidade em discussão: {ctx_specialty}")
        if ctx_insurance := context.get("last_insurance"):
            parts.append(f"Contexto — plano de saúde mencionado: {ctx_insurance}")

    return "\n".join(parts)


class InstructorMessageExtractor:
    """Extracts structured data from patient messages using Instructor.

    Attributes:
        provider: LLM provider name ("openai" or "anthropic").
        model:    Model identifier string.
        api_key:  API key for the provider (falls back to env vars if empty).
        max_retries: Number of Instructor validation retries on Pydantic errors.
    """

    def __init__(
        self,
        provider: str = "openai",
        model: str = "gpt-4o-mini",
        api_key: str = "",
        max_retries: int = 3,
    ) -> None:
        self.provider = provider.lower()
        self.model = model
        self.api_key = api_key
        self.max_retries = max_retries
        self._client: Any = None  # Lazy-initialized on first call

    def _get_client(self) -> Any:
        """Initialize and return the Instructor-wrapped LLM client.

        The client is cached after the first call (one instance per extractor).
        This avoids re-authenticating on every extraction request.
        """
        if self._client is not None:
            return self._client

        import os

        if self.provider == "openai":
            import instructor
            from openai import AsyncOpenAI

            raw_client = AsyncOpenAI(
                api_key=self.api_key or os.environ.get("OPENAI_API_KEY", "")
            )
            self._client = instructor.from_openai(raw_client)

        elif self.provider == "anthropic":
            import instructor
            from anthropic import AsyncAnthropic

            raw_client = AsyncAnthropic(
                api_key=self.api_key or os.environ.get("ANTHROPIC_API_KEY", "")
            )
            self._client = instructor.from_anthropic(raw_client)

        else:
            raise ValueError(
                f"Unsupported provider: '{self.provider}'. "
                "Supported providers: 'openai', 'anthropic'."
            )

        logger.debug(
            "InstructorMessageExtractor: client initialized | provider=%s | model=%s",
            self.provider,
            self.model,
        )
        return self._client

    def _build_system_prompt(self) -> str:
        """System prompt for NLU extraction. Medical clinic context.

        The prompt is intentionally conservative:
        - Prefers marking ambiguous messages as ambiguous over guessing.
        - Explicitly prohibits clinical inference.
        - Sets the expected output language to Brazilian Portuguese for `clarification_question`.
        """
        return """Você é um especialista em extração de informações de mensagens de pacientes de clínicas médicas brasileiras.

Analise a mensagem do paciente e extraia informações estruturadas com máxima precisão.

REGRAS OBRIGATÓRIAS:
1. Seja conservador com a confiança — prefira confiança baixa a extrapolações.
2. NUNCA assuma intenção médica, diagnóstica ou clínica.
3. Se a mensagem for ambígua, marque is_ambiguous=true e forneça uma clarification_question em português.
4. Se urgência for detectada (dor intensa, falta de ar, emergência), marque urgency_detected=true e adicione urgency_signals.
5. desired_date deve ser normalizado para formato ISO 8601 (YYYY-MM-DD) sempre que possível.
6. Preserve nomes de planos de saúde exatamente como mencionados pelo paciente.
7. clarification_question deve ser em português brasileiro, educada e perguntar apenas UMA coisa.
8. confidence_level é derivado automaticamente de confidence — não é necessário definir.
9. O campo original_text deve conter exatamente a mensagem do paciente, sem modificações.
"""

    async def extract(
        self,
        message: str,
        context: dict[str, Any] | None = None,
    ) -> ExtractedMessage:
        """Extract structured data from a single patient message.

        Uses Instructor's retry mechanism for Pydantic validation errors.
        Falls back to a conservative ExtractedMessage on unrecoverable failures.

        Args:
            message: Raw patient message text.
            context: Optional session context dict to improve extraction accuracy.

        Returns:
            ExtractedMessage with validated structured data.
        """
        user_content = _build_user_message(message, context)
        messages = [{"role": "user", "content": user_content}]
        return await self._run_extraction(message, messages)

    async def extract_with_history(
        self,
        message: str,
        history: list[dict[str, Any]],
        context: dict[str, Any] | None = None,
    ) -> ExtractedMessage:
        """Extract structured data with conversation history for better context.

        Including prior messages helps the extractor resolve pronoun references
        (e.g., "eu disse ortopedia antes") and carry over known fields (insurance plan,
        specialty) from previous turns without the patient repeating them.

        Args:
            message: Latest patient message text.
            history: Prior messages in OpenAI format [{"role": ..., "content": ...}].
                     Only user and assistant messages are included; system messages are stripped.
            context: Optional session context dict.

        Returns:
            ExtractedMessage with validated structured data.
        """
        # Keep only user/assistant messages from history (last 6 messages = 3 turns)
        filtered_history = [
            m for m in history
            if m.get("role") in ("user", "assistant")
        ][-6:]

        user_content = _build_user_message(message, context)
        messages = [*filtered_history, {"role": "user", "content": user_content}]
        return await self._run_extraction(message, messages)

    async def _run_extraction(
        self,
        original_text: str,
        messages: list[dict[str, Any]],
    ) -> ExtractedMessage:
        """Internal extraction runner. Handles provider differences and error handling.

        Args:
            original_text: The raw patient message (used in fallback construction).
            messages:      Full message list to send to the LLM.

        Returns:
            Validated ExtractedMessage or conservative fallback on failure.
        """
        try:
            client = self._get_client()
            system_prompt = self._build_system_prompt()

            if self.provider == "openai":
                result: ExtractedMessage = await client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "system", "content": system_prompt}, *messages],
                    response_model=ExtractedMessage,
                    max_retries=self.max_retries,
                    temperature=0.1,  # Low temperature for deterministic extraction
                )
            elif self.provider == "anthropic":
                result = await client.messages.create(
                    model=self.model,
                    system=system_prompt,
                    messages=messages,
                    response_model=ExtractedMessage,
                    max_retries=self.max_retries,
                    max_tokens=1024,
                )
            else:
                raise ValueError(f"Unsupported provider: {self.provider}")

            logger.debug(
                "InstructorMessageExtractor: extraction complete | intent=%s | confidence=%.2f",
                result.intent.value,
                result.confidence,
            )
            return result

        except Exception as exc:
            logger.exception(
                "InstructorMessageExtractor: extraction failed for message '%s...': %s",
                original_text[:60],
                exc,
            )
            return _make_fallback_extraction(original_text)
