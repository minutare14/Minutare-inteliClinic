"""
Response Composer — Single responsibility point for RAG/action/LLM/template routing.

The orchestrator delegates the "what kind of response to generate" decision here.
Multi-turn state management (pending_action) stays in the orchestrator since it
requires DB writes and cross-turn context.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.ai_engine.context_manager import ConversationContext
from app.ai_engine.intent_router import FaroBrief, Intent
from app.ai_engine.response_builder import generate_response
from app.services.rag_service import RagService

logger = logging.getLogger(__name__)

# Intents that always go to RAG before LLM (never short-circuit to template alone)
RAG_INTENTS = {Intent.DUVIDA_OPERACIONAL, Intent.POLITICAS}


@dataclass
class ComposedResponse:
    """Structured result from ResponseComposer.compose()."""
    text: str
    mode: str          # "rag_llm" | "llm" | "template"
    rag_used: bool = False
    rag_result_count: int = 0
    insurance_injected: bool = False


class ResponseComposer:
    """
    Encapsulates the decision of whether to use RAG + LLM, LLM alone, or template.

    Does NOT handle:
    - Action intents (book/cancel/reschedule) → handled by orchestrator._execute_action()
    - Multi-turn pending state → handled by orchestrator._handle_pending_action()
    - Guardrails → evaluated by orchestrator before and after compose()

    Call compose() when the orchestrator has determined no action was executed and
    a natural-language response is needed.
    """

    def __init__(self, rag_svc: RagService) -> None:
        self.rag_svc = rag_svc

    async def compose(
        self,
        context: ConversationContext,
        faro: FaroBrief,
        user_text: str,
        clinic_name: str | None = None,
        chatbot_name: str | None = None,
        custom_system_prompt: str | None = None,
        insurance_context: str | None = None,
        rag_top_k: int | None = None,
    ) -> ComposedResponse:
        """
        Decide between RAG+LLM and LLM/template, then generate the response.

        Returns a ComposedResponse with the text and metadata about which path was taken.
        """
        rag_results: list[dict] | None = None

        # RAG query for knowledge intents
        if faro.intent in RAG_INTENTS:
            rag_results = await self._query_rag(user_text, top_k=rag_top_k)
            if rag_results:
                logger.info("[COMPOSER] RAG: %d resultados para intent=%s", len(rag_results), faro.intent.value)
            else:
                logger.info("[COMPOSER] RAG: sem resultados para intent=%s — usando LLM puro", faro.intent.value)

        # Generate response (LLM or template fallback)
        text = await generate_response(
            context=context,
            user_text=user_text,
            faro=faro,
            rag_results=rag_results,
            clinic_name=clinic_name,
            chatbot_name=chatbot_name,
            custom_system_prompt=custom_system_prompt,
            insurance_context=insurance_context,
        )

        mode = "rag_llm" if rag_results else "llm"
        return ComposedResponse(
            text=text,
            mode=mode,
            rag_used=bool(rag_results),
            rag_result_count=len(rag_results) if rag_results else 0,
            insurance_injected=bool(insurance_context),
        )

    async def _query_rag(self, text: str, top_k: int | None = None) -> list[dict] | None:
        """Query RAG with vector search, fallback to text search."""
        try:
            results = await self.rag_svc.query(text, top_k=top_k)
            if results:
                return [
                    {
                        "content": r.content,
                        "document_title": r.document_title,
                        "score": r.score,
                    }
                    for r in results
                ]
        except Exception:
            logger.debug("[COMPOSER] Vector RAG query failed, trying text search")

        try:
            results = await self.rag_svc.text_search(text)
            if results:
                return results
        except Exception:
            logger.exception("[COMPOSER] RAG text search also failed for: %s", text[:80])

        return None
