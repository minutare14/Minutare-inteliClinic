"""
Response Composer: centraliza a composicao final para respostas estruturadas,
agenda, handoff, clarificacao e RAG documental com LangGraph.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.ai_engine.context_manager import ConversationContext
from app.ai_engine.document_runtime_graph import DocumentRuntimeGraph
from app.ai_engine.intent_router import FaroBrief
from app.models.admin import ClinicSettings
from app.repositories.admin_repository import AdminRepository
from app.services.rag_service import RagService

logger = logging.getLogger(__name__)


@dataclass
class ComposedResponse:
    text: str
    mode: str
    route: str = "fallback"
    source_of_truth: str = "none"
    rag_used: bool = False
    rag_result_count: int = 0
    insurance_injected: bool = False
    retrieval_mode: str = "none"
    fallback_used: bool = False
    reranker_used: bool = False
    reranker_model: str | None = None
    reranker_top_k_initial: int = 0
    reranker_top_k_final: int = 0
    reranker_latency_ms: float = 0.0
    reranker_fallback: bool = False
    reranker_ranking_changed: bool = False
    langgraph_used: bool = False
    llm_model: str | None = None
    llm_latency_ms: float = 0.0
    document_grading_used: bool = False
    document_grading_threshold: float = 0.0
    document_grading_strategy: str = "disabled"
    approved_document_count: int = 0
    rejected_document_count: int = 0
    query_rewrite_used: bool = False
    query_rewrite_attempts: int = 0
    rewritten_query: str | None = None
    retrieval_attempts: int = 0
    initial_candidate_count: int = 0
    final_candidate_count: int = 0
    prompt_source_response_builder: str = "env_default"
    prompt_source_query_rewrite: str = "default"
    prompt_source_document_grading: str = "default"
    selected_chunks: list[dict] = field(default_factory=list)
    audit_payload: dict = field(default_factory=dict)


class ResponseComposer:
    def __init__(self, rag_svc: RagService, admin_repo: AdminRepository) -> None:
        self.rag_svc = rag_svc
        self.admin_repo = admin_repo
        self.document_graph = DocumentRuntimeGraph(rag_svc, admin_repo)

    async def compose(
        self,
        *,
        context: ConversationContext,
        faro: FaroBrief,
        faro_brief: dict | None = None,
        user_text: str,
        clinic_cfg: ClinicSettings | None = None,
        clinic_name: str | None = None,
        chatbot_name: str | None = None,
        custom_system_prompt: str | None = None,
        insurance_context: str | None = None,
        rag_top_k: int | None = None,
        prompt_source: str = "env_default",
        prefilled_response: str | None = None,
        prefilled_route: str | None = None,
        prefilled_source_of_truth: str | None = None,
        prefilled_mode: str | None = None,
    ) -> ComposedResponse:
        logger.info(
            "[COMPOSER] route_hint=%s prompt_source=%s prefilled=%s",
            prefilled_route or "auto",
            prompt_source,
            str(bool(prefilled_response)).lower(),
        )
        result = await self.document_graph.run(
            context=context,
            faro=faro,
            faro_brief=faro_brief,
            user_text=user_text,
            clinic_name=clinic_name,
            chatbot_name=chatbot_name,
            custom_system_prompt=custom_system_prompt,
            insurance_context=insurance_context,
            rag_top_k=rag_top_k,
            clinic_cfg=clinic_cfg,
            prompt_source_response_builder=prompt_source,
            prefilled_response=prefilled_response,
            prefilled_route=prefilled_route,
            prefilled_source_of_truth=prefilled_source_of_truth,
            prefilled_mode=prefilled_mode,
        )
        return ComposedResponse(
            text=result.text,
            mode=result.mode,
            route=result.route,
            source_of_truth=result.source_of_truth,
            rag_used=result.rag_used,
            rag_result_count=result.rag_result_count,
            insurance_injected=bool(insurance_context),
            retrieval_mode=result.retrieval_mode,
            fallback_used=result.fallback_used,
            reranker_used=result.reranker_used,
            reranker_model=result.reranker_model,
            reranker_top_k_initial=result.reranker_top_k_initial,
            reranker_top_k_final=result.reranker_top_k_final,
            reranker_latency_ms=result.reranker_latency_ms,
            reranker_fallback=result.reranker_fallback,
            reranker_ranking_changed=result.reranker_ranking_changed,
            langgraph_used=result.langgraph_used,
            document_grading_used=result.document_grading_used,
            document_grading_threshold=result.document_grading_threshold,
            document_grading_strategy=result.document_grading_strategy,
            approved_document_count=result.approved_document_count,
            rejected_document_count=result.rejected_document_count,
            query_rewrite_used=result.query_rewrite_used,
            query_rewrite_attempts=result.query_rewrite_attempts,
            rewritten_query=result.rewritten_query,
            retrieval_attempts=result.retrieval_attempts,
            initial_candidate_count=result.initial_candidate_count,
            final_candidate_count=result.final_candidate_count,
            prompt_source_response_builder=result.prompt_source_response_builder,
            prompt_source_query_rewrite=result.prompt_source_query_rewrite,
            prompt_source_document_grading=result.prompt_source_document_grading,
            selected_chunks=result.selected_chunks,
            audit_payload=result.audit_payload,
            llm_model=result.llm_model,
            llm_latency_ms=result.llm_latency_ms,
        )
