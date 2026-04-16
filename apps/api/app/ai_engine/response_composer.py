"""
Response Composer: decides between structured RAG output, LLM, or fallback.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from app.ai_engine.context_manager import ConversationContext
from app.ai_engine.intent_router import FaroBrief, Intent
from app.ai_engine.response_builder import generate_response
from app.services.rag_service import RagQueryExecution, RagService

logger = logging.getLogger(__name__)

RAG_INTENTS = {Intent.DUVIDA_OPERACIONAL, Intent.POLITICAS}


@dataclass
class ComposedResponse:
    text: str
    mode: str  # rag_llm | rag_template | llm | template
    rag_used: bool = False
    rag_result_count: int = 0
    insurance_injected: bool = False
    retrieval_mode: str = "none"
    fallback_used: bool = False
    # Reranker metadata forwarded from RagQueryExecution
    reranker_used: bool = False
    reranker_model: str | None = None
    reranker_top_k_initial: int = 0
    reranker_top_k_final: int = 0
    reranker_latency_ms: float = 0.0
    reranker_fallback: bool = False
    reranker_ranking_changed: bool = False


class ResponseComposer:
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
        rag_results: list[dict] | None = None
        retrieval_mode = "none"
        rag_execution = None

        if faro.intent in RAG_INTENTS:
            rag_execution = await self._query_rag(user_text, top_k=rag_top_k)
            retrieval_mode = rag_execution.retrieval_mode
            if rag_execution.results:
                rag_results = [
                    {
                        "content": r.content,
                        "document_title": r.document_title,
                        "score": r.score,
                    }
                    for r in rag_execution.results
                ]
                logger.info(
                    "[COMPOSER] intent=%s rag_used=true retrieval_mode=%s results=%d",
                    faro.intent.value,
                    retrieval_mode,
                    len(rag_results),
                )
            else:
                logger.info(
                    "[COMPOSER] intent=%s rag_used=false retrieval_mode=%s results=0",
                    faro.intent.value,
                    retrieval_mode,
                )

        text, used_llm = await generate_response(
            context=context,
            user_text=user_text,
            faro=faro,
            rag_results=rag_results,
            clinic_name=clinic_name,
            chatbot_name=chatbot_name,
            custom_system_prompt=custom_system_prompt,
            insurance_context=insurance_context,
        )

        if rag_results and used_llm:
            mode = "rag_llm"
        elif rag_results:
            mode = "rag_template"
        elif used_llm:
            mode = "llm"
        else:
            mode = "template"

        logger.info(
            "[COMPOSER] route_mode=%s rag_used=%s rag_results=%d retrieval_mode=%s llm=%s fallback_used=%s",
            mode,
            str(bool(rag_results)).lower(),
            len(rag_results) if rag_results else 0,
            retrieval_mode,
            str(used_llm).lower(),
            str(not bool(rag_results)).lower(),
        )
        resp = ComposedResponse(
            text=text,
            mode=mode,
            rag_used=bool(rag_results),
            rag_result_count=len(rag_results) if rag_results else 0,
            insurance_injected=bool(insurance_context),
            retrieval_mode=retrieval_mode,
            fallback_used=not bool(rag_results),
        )

        # Propagate reranker metadata from the execution
        if faro.intent in RAG_INTENTS and rag_execution is not None:
            resp.reranker_used = rag_execution.reranker_used
            resp.reranker_model = rag_execution.reranker_model
            resp.reranker_top_k_initial = rag_execution.reranker_top_k_initial
            resp.reranker_top_k_final = rag_execution.reranker_top_k_final
            resp.reranker_latency_ms = rag_execution.reranker_latency_ms
            resp.reranker_fallback = rag_execution.reranker_fallback
            resp.reranker_ranking_changed = rag_execution.reranker_ranking_changed

        return resp

    async def _query_rag(self, text: str, top_k: int | None = None) -> RagQueryExecution:
        return await self.rag_svc.query_with_metadata(text, top_k=top_k)
