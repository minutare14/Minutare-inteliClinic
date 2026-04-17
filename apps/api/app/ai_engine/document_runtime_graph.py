from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, TypedDict

from app.ai_engine.clients.llm_client import call_llm
from app.ai_engine.context_manager import ConversationContext
from app.ai_engine.intent_router import FaroBrief, Intent
from app.ai_engine.response_builder import TEMPLATE_RESPONSES, generate_response
from app.core.config import settings
from app.models.admin import ClinicSettings
from app.observability.langsmith import trace_step
from app.repositories.admin_repository import AdminRepository
from app.services.rag_service import RagService, _query_terms, _rerank_vector_rows, get_embedding

logger = logging.getLogger(__name__)

try:  # pragma: no cover - import is validated in runtime builds
    from langgraph.graph import END, START, StateGraph

    LANGGRAPH_AVAILABLE = True
except Exception:  # pragma: no cover - graceful fallback if dependency missing
    END = "__end__"
    START = "__start__"
    StateGraph = None
    LANGGRAPH_AVAILABLE = False


RAG_INTENTS = {Intent.DUVIDA_OPERACIONAL, Intent.POLITICAS}

DEFAULT_QUERY_REWRITE_PROMPT = """
Voce reescreve perguntas administrativas para melhorar retrieval documental da clinica.
- Preserve a intencao original.
- Nao invente fatos.
- Expanda siglas curtas quando fizer sentido.
- Inclua termos operacionais explicitos quando estiverem implicitos.
- Responda APENAS em JSON com a chave "rewritten_query".
""".strip()

DEFAULT_DOCUMENT_GRADING_PROMPT = """
Voce avalia se trechos documentais sao bons o suficiente para responder duvidas operacionais.
- Aprove apenas trechos diretamente relevantes para a pergunta.
- Rejeite conteudo vago, duplicado ou fora do escopo.
- Responda APENAS em JSON com a chave "approved_chunk_ids" contendo uma lista.
""".strip()

SAFE_RAG_FALLBACK = (
    "Nao encontrei contexto documental confiavel o suficiente para responder com seguranca. "
    "Posso encaminhar para a equipe humana ou voce pode detalhar melhor a duvida."
)


class DocumentGraphState(TypedDict, total=False):
    context: ConversationContext
    faro: FaroBrief
    user_text: str
    clinic_name: str | None
    chatbot_name: str | None
    custom_system_prompt: str | None
    insurance_context: str | None
    rag_top_k: int | None
    clinic_cfg: ClinicSettings | None
    prefilled_response: str | None
    prefilled_route: str | None
    prefilled_source_of_truth: str | None
    prefilled_mode: str | None
    route: str
    source_of_truth: str
    mode: str
    response_text: str
    active_query: str
    rewritten_query: str | None
    rewritten_queries: list[str]
    prompt_sources: dict[str, str]
    prompt_contents: dict[str, str]
    retrieval_attempts: int
    query_rewrite_attempts: int
    query_rewrite_used: bool
    document_grading_used: bool
    document_grading_threshold: float
    document_grading_strategy: str
    retrieval_mode: str
    initial_candidates: list[dict[str, Any]]
    approved_candidates: list[dict[str, Any]]
    rejected_candidates: list[dict[str, Any]]
    final_candidates: list[dict[str, Any]]
    reranker_used: bool
    reranker_model: str | None
    reranker_top_k_initial: int
    reranker_top_k_final: int
    reranker_latency_ms: float
    reranker_fallback: bool
    reranker_ranking_changed: bool
    fallback_used: bool
    langgraph_used: bool
    audit_payload: dict[str, Any]


@dataclass
class DocumentRuntimeResult:
    text: str
    mode: str
    route: str
    source_of_truth: str
    rag_used: bool
    rag_result_count: int
    retrieval_mode: str
    fallback_used: bool
    reranker_used: bool = False
    reranker_model: str | None = None
    reranker_top_k_initial: int = 0
    reranker_top_k_final: int = 0
    reranker_latency_ms: float = 0.0
    reranker_fallback: bool = False
    reranker_ranking_changed: bool = False
    langgraph_used: bool = False
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
    selected_chunks: list[dict[str, Any]] = field(default_factory=list)
    audit_payload: dict[str, Any] = field(default_factory=dict)


class DocumentRuntimeGraph:
    def __init__(self, rag_svc: RagService, admin_repo: AdminRepository) -> None:
        self.rag_svc = rag_svc
        self.admin_repo = admin_repo
        self._compiled_graph = self._build_graph() if LANGGRAPH_AVAILABLE else None

    async def run(
        self,
        *,
        context: ConversationContext,
        faro: FaroBrief,
        user_text: str,
        clinic_name: str | None,
        chatbot_name: str | None,
        custom_system_prompt: str | None,
        insurance_context: str | None,
        rag_top_k: int | None,
        clinic_cfg: ClinicSettings | None,
        prompt_source_response_builder: str,
        prefilled_response: str | None = None,
        prefilled_route: str | None = None,
        prefilled_source_of_truth: str | None = None,
        prefilled_mode: str | None = None,
    ) -> DocumentRuntimeResult:
        initial_state: DocumentGraphState = {
            "context": context,
            "faro": faro,
            "user_text": user_text,
            "clinic_name": clinic_name,
            "chatbot_name": chatbot_name,
            "custom_system_prompt": custom_system_prompt,
            "insurance_context": insurance_context,
            "rag_top_k": rag_top_k,
            "clinic_cfg": clinic_cfg,
            "prefilled_response": prefilled_response,
            "prefilled_route": prefilled_route,
            "prefilled_source_of_truth": prefilled_source_of_truth or "none",
            "prefilled_mode": prefilled_mode or "template",
            "route": "unknown",
            "source_of_truth": prefilled_source_of_truth or "none",
            "mode": prefilled_mode or "template",
            "response_text": "",
            "active_query": user_text,
            "rewritten_query": None,
            "rewritten_queries": [],
            "prompt_sources": {"response_builder": prompt_source_response_builder},
            "prompt_contents": {},
            "retrieval_attempts": 0,
            "query_rewrite_attempts": 0,
            "query_rewrite_used": False,
            "document_grading_used": False,
            "document_grading_threshold": self._document_grading_threshold(clinic_cfg),
            "document_grading_strategy": "disabled",
            "retrieval_mode": "none",
            "initial_candidates": [],
            "approved_candidates": [],
            "rejected_candidates": [],
            "final_candidates": [],
            "reranker_used": False,
            "reranker_model": None,
            "reranker_top_k_initial": 0,
            "reranker_top_k_final": 0,
            "reranker_latency_ms": 0.0,
            "reranker_fallback": False,
            "reranker_ranking_changed": False,
            "fallback_used": False,
            "langgraph_used": settings.langgraph_runtime_enabled and LANGGRAPH_AVAILABLE,
            "audit_payload": {},
        }

        if self._compiled_graph is not None and settings.langgraph_runtime_enabled:
            state = await self._compiled_graph.ainvoke(initial_state)
        else:
            state = await self._run_without_graph(initial_state)

        return self._to_result(state)

    def _build_graph(self):
        graph = StateGraph(DocumentGraphState)
        graph.add_node("load_runtime_context", self._load_runtime_context)
        graph.add_node("decision_router", self._decision_router)
        graph.add_node("structured_data_lookup", self._structured_data_lookup)
        graph.add_node("schedule_flow", self._schedule_flow)
        graph.add_node("crm_flow", self._crm_flow)
        graph.add_node("handoff_flow", self._handoff_flow)
        graph.add_node("clarification_flow", self._clarification_flow)
        graph.add_node("rag_retrieval", self._rag_retrieval)
        graph.add_node("document_grading", self._document_grading)
        graph.add_node("query_rewrite", self._query_rewrite)
        graph.add_node("retry_retrieval", self._retry_retrieval)
        graph.add_node("reranker", self._reranker)
        graph.add_node("response_composer", self._response_composer)
        graph.add_node("persist_and_audit", self._persist_and_audit)
        graph.add_node("emit_response", self._emit_response)

        graph.add_edge(START, "load_runtime_context")
        graph.add_edge("load_runtime_context", "decision_router")
        graph.add_conditional_edges(
            "decision_router",
            self._route_from_decision,
            {
                "structured_data_lookup": "structured_data_lookup",
                "schedule_flow": "schedule_flow",
                "crm_flow": "crm_flow",
                "handoff_flow": "handoff_flow",
                "clarification_flow": "clarification_flow",
                "rag_retrieval": "rag_retrieval",
                "response_composer": "response_composer",
            },
        )
        graph.add_edge("structured_data_lookup", "response_composer")
        graph.add_edge("schedule_flow", "response_composer")
        graph.add_edge("crm_flow", "response_composer")
        graph.add_edge("handoff_flow", "response_composer")
        graph.add_edge("clarification_flow", "response_composer")
        graph.add_edge("rag_retrieval", "document_grading")
        graph.add_conditional_edges(
            "document_grading",
            self._route_after_grading,
            {
                "query_rewrite": "query_rewrite",
                "reranker": "reranker",
                "response_composer": "response_composer",
            },
        )
        graph.add_edge("query_rewrite", "retry_retrieval")
        graph.add_edge("retry_retrieval", "rag_retrieval")
        graph.add_edge("reranker", "response_composer")
        graph.add_edge("response_composer", "persist_and_audit")
        graph.add_edge("persist_and_audit", "emit_response")
        graph.add_edge("emit_response", END)
        return graph.compile()

    async def _run_without_graph(self, state: DocumentGraphState) -> DocumentGraphState:
        state.update(await self._load_runtime_context(state))
        state.update(await self._decision_router(state))
        route = self._route_from_decision(state)
        if route == "structured_data_lookup":
            state.update(await self._structured_data_lookup(state))
        elif route == "schedule_flow":
            state.update(await self._schedule_flow(state))
        elif route == "crm_flow":
            state.update(await self._crm_flow(state))
        elif route == "handoff_flow":
            state.update(await self._handoff_flow(state))
        elif route == "clarification_flow":
            state.update(await self._clarification_flow(state))
        elif route == "rag_retrieval":
            state.update(await self._rag_retrieval(state))
            state.update(await self._document_grading(state))
            while self._route_after_grading(state) == "query_rewrite":
                state.update(await self._query_rewrite(state))
                state.update(await self._retry_retrieval(state))
                state.update(await self._rag_retrieval(state))
                state.update(await self._document_grading(state))
            if self._route_after_grading(state) == "reranker":
                state.update(await self._reranker(state))
        state.update(await self._response_composer(state))
        state.update(await self._persist_and_audit(state))
        state.update(await self._emit_response(state))
        return state

    async def _load_runtime_context(self, state: DocumentGraphState) -> dict[str, Any]:
        async with trace_step(
            "load_runtime_context",
            inputs={"clinic_name": state.get("clinic_name"), "chatbot_name": state.get("chatbot_name")},
            tags=["runtime_context"],
        ) as run:
            prompt_sources = dict(state.get("prompt_sources") or {})
            prompt_contents = dict(state.get("prompt_contents") or {})

            query_rewrite_prompt = await self.admin_repo.get_active_prompt(settings.clinic_id, "query_rewrite")
            document_grading_prompt = await self.admin_repo.get_active_prompt(settings.clinic_id, "document_grading")

            if query_rewrite_prompt:
                prompt_sources["query_rewrite"] = "db_registry"
                prompt_contents["query_rewrite"] = query_rewrite_prompt.content
            else:
                prompt_sources["query_rewrite"] = "default"
                prompt_contents["query_rewrite"] = DEFAULT_QUERY_REWRITE_PROMPT

            if document_grading_prompt:
                prompt_sources["document_grading"] = "db_registry"
                prompt_contents["document_grading"] = document_grading_prompt.content
            else:
                prompt_sources["document_grading"] = "default"
                prompt_contents["document_grading"] = DEFAULT_DOCUMENT_GRADING_PROMPT

            if run is not None:
                run.end(outputs={"prompt_sources": prompt_sources})
            return {
                "prompt_sources": prompt_sources,
                "prompt_contents": prompt_contents,
                "langgraph_used": state.get("langgraph_used", False),
            }

    async def _decision_router(self, state: DocumentGraphState) -> dict[str, Any]:
        route = "response_composer"
        source = state.get("source_of_truth") or "none"
        prefilled_route = state.get("prefilled_route")

        if prefilled_route:
            route = prefilled_route
            source = state.get("prefilled_source_of_truth") or source
        elif state["faro"].intent in RAG_INTENTS:
            route = "rag_retrieval"
            source = "rag"
        elif state["faro"].intent == Intent.FALAR_COM_HUMANO:
            route = "handoff_flow"
            source = "handoff"
        elif state["faro"].intent == Intent.DESCONHECIDA:
            route = "clarification_flow"
            source = "template"

        logger.info(
            "[GRAPH:decision_router] route=%s intent=%s prefilled=%s",
            route,
            state["faro"].intent.value,
            str(bool(prefilled_route)).lower(),
        )
        return {"route": route, "source_of_truth": source}

    def _route_from_decision(self, state: DocumentGraphState) -> str:
        return state.get("route", "response_composer")

    async def _structured_data_lookup(self, state: DocumentGraphState) -> dict[str, Any]:
        async with trace_step(
            "structured_data_lookup",
            inputs={"route": state.get("route"), "has_prefilled_response": bool(state.get("prefilled_response"))},
            tags=["structured_data_lookup"],
        ) as run:
            text = state.get("prefilled_response") or ""
            if run is not None:
                run.end(outputs={"response_preview": text[:200], "source_of_truth": state.get("source_of_truth")})
            return {
                "response_text": text,
                "mode": state.get("prefilled_mode") or "structured",
                "source_of_truth": state.get("prefilled_source_of_truth") or state.get("source_of_truth") or "structured",
            }

    async def _schedule_flow(self, state: DocumentGraphState) -> dict[str, Any]:
        async with trace_step(
            "schedule_flow",
            inputs={"route": state.get("route")},
            tags=["schedule_flow"],
        ) as run:
            text = state.get("prefilled_response") or ""
            if run is not None:
                run.end(outputs={"response_preview": text[:200]})
            return {
                "response_text": text,
                "mode": state.get("prefilled_mode") or "action",
                "source_of_truth": state.get("prefilled_source_of_truth") or "schedule_db",
            }

    async def _crm_flow(self, state: DocumentGraphState) -> dict[str, Any]:
        text = state.get("prefilled_response") or ""
        return {
            "response_text": text,
            "mode": state.get("prefilled_mode") or "crm",
            "source_of_truth": state.get("prefilled_source_of_truth") or "crm",
        }

    async def _handoff_flow(self, state: DocumentGraphState) -> dict[str, Any]:
        async with trace_step(
            "handoff_flow",
            inputs={"intent": state["faro"].intent.value},
            tags=["handoff_flow"],
        ) as run:
            text = state.get("prefilled_response") or TEMPLATE_RESPONSES[Intent.FALAR_COM_HUMANO]
            if run is not None:
                run.end(outputs={"response_preview": text[:200]})
            return {
                "response_text": text,
                "mode": state.get("prefilled_mode") or "handoff",
                "source_of_truth": state.get("prefilled_source_of_truth") or "handoff",
            }

    async def _clarification_flow(self, state: DocumentGraphState) -> dict[str, Any]:
        async with trace_step(
            "clarification_flow",
            inputs={"intent": state["faro"].intent.value},
            tags=["clarification_flow"],
        ) as run:
            text = state.get("prefilled_response") or TEMPLATE_RESPONSES[Intent.DESCONHECIDA]
            if run is not None:
                run.end(outputs={"response_preview": text[:200]})
            return {
                "response_text": text,
                "mode": state.get("prefilled_mode") or "clarification",
                "source_of_truth": state.get("prefilled_source_of_truth") or "template",
            }

    async def _rag_retrieval(self, state: DocumentGraphState) -> dict[str, Any]:
        query_text = state.get("active_query") or state["user_text"]
        top_k_initial = self._top_k_initial(state)

        async with trace_step(
            "rag_retrieval",
            inputs={"query": query_text, "top_k_initial": top_k_initial},
            tags=["rag_retrieval"],
            metadata={"source_of_truth": "rag"},
        ) as run:
            rows, retrieval_mode = await self._retrieve_candidates(query_text, top_k_initial)
            logger.info(
                "[GRAPH:rag_retrieval] attempt=%d query=%r retrieval_mode=%s candidates=%d",
                state.get("retrieval_attempts", 0) + 1,
                query_text[:160],
                retrieval_mode,
                len(rows),
            )
            if run is not None:
                run.end(
                    outputs={
                        "candidate_count": len(rows),
                        "retrieval_mode": retrieval_mode,
                        "chunk_ids": [str(row.get("chunk_id")) for row in rows[:10]],
                    }
                )
            return {
                "initial_candidates": rows,
                "retrieval_attempts": state.get("retrieval_attempts", 0) + 1,
                "retrieval_mode": retrieval_mode,
                "route": "rag_retrieval",
                "source_of_truth": "rag",
                "response_text": "",
                "final_candidates": [],
            }

    async def _document_grading(self, state: DocumentGraphState) -> dict[str, Any]:
        rows = state.get("initial_candidates") or []
        threshold = state.get("document_grading_threshold", settings.rag_document_grading_min_score)

        async with trace_step(
            "document_grading",
            inputs={"candidate_count": len(rows), "threshold": threshold},
            tags=["document_grading"],
        ) as run:
            approved, rejected = self._heuristic_grade(state["active_query"], rows, threshold)
            strategy = "heuristic"

            llm_approved_ids = None
            if rows and self._can_use_llm() and state["prompt_sources"].get("document_grading") == "db_registry":
                llm_approved_ids = await self._llm_grade_documents(state, rows[:5])
                if llm_approved_ids is not None:
                    approved = [row for row in rows if str(row.get("chunk_id")) in llm_approved_ids]
                    rejected = [row for row in rows if str(row.get("chunk_id")) not in llm_approved_ids]
                    strategy = "heuristic_plus_llm"

            logger.info(
                "[GRAPH:document_grading] strategy=%s approved=%d rejected=%d threshold=%.2f",
                strategy,
                len(approved),
                len(rejected),
                threshold,
            )
            if run is not None:
                run.end(
                    outputs={
                        "approved_count": len(approved),
                        "rejected_count": len(rejected),
                        "approved_chunk_ids": [str(row.get("chunk_id")) for row in approved[:10]],
                    }
                )
            return {
                "approved_candidates": approved,
                "rejected_candidates": rejected,
                "document_grading_used": settings.rag_document_grading_enabled,
                "document_grading_strategy": strategy,
            }

    def _route_after_grading(self, state: DocumentGraphState) -> str:
        approved = state.get("approved_candidates") or []
        minimum = max(1, settings.rag_document_grading_min_approved_chunks)
        should_retry = (
            settings.rag_query_rewrite_enabled
            and state.get("query_rewrite_attempts", 0) < settings.rag_query_rewrite_max_retries
            and len(approved) < minimum
        )
        if len(approved) >= minimum:
            return "reranker"
        if should_retry:
            return "query_rewrite"
        return "response_composer"

    async def _query_rewrite(self, state: DocumentGraphState) -> dict[str, Any]:
        async with trace_step(
            "query_rewrite",
            inputs={"query": state.get("active_query"), "attempt": state.get("query_rewrite_attempts", 0) + 1},
            tags=["query_rewrite"],
        ) as run:
            rewritten_query = await self._rewrite_query(state)
            rewritten_queries = list(state.get("rewritten_queries") or [])
            if rewritten_query:
                rewritten_queries.append(rewritten_query)
            if run is not None:
                run.end(outputs={"rewritten_query": rewritten_query})
            return {
                "active_query": rewritten_query or state.get("active_query") or state["user_text"],
                "rewritten_query": rewritten_query or state.get("rewritten_query"),
                "rewritten_queries": rewritten_queries,
                "query_rewrite_attempts": state.get("query_rewrite_attempts", 0) + 1,
                "query_rewrite_used": bool(rewritten_query),
            }

    async def _retry_retrieval(self, state: DocumentGraphState) -> dict[str, Any]:
        logger.info(
            "[GRAPH:retry_retrieval] attempt=%d active_query=%r",
            state.get("query_rewrite_attempts", 0),
            (state.get("active_query") or "")[:160],
        )
        return {
            "approved_candidates": [],
            "rejected_candidates": [],
            "final_candidates": [],
        }

    async def _reranker(self, state: DocumentGraphState) -> dict[str, Any]:
        approved = state.get("approved_candidates") or []
        top_k_final = self._top_k_final(state)

        async with trace_step(
            "reranker",
            inputs={"approved_count": len(approved), "top_k_final": top_k_final},
            tags=["reranker"],
        ) as run:
            rerank_result = await self.rag_svc._reranker.rerank(
                state.get("active_query") or state["user_text"],
                approved,
                top_k=top_k_final,
            )
            final_rows = [
                {
                    "chunk_id": candidate.chunk_id,
                    "document_id": candidate.document_id,
                    "document_title": candidate.title,
                    "content": candidate.content,
                    "category": candidate.category,
                    "score": candidate.reranker_score,
                }
                for candidate in rerank_result.candidates
            ]
            for index, row in enumerate(final_rows[:5], start=1):
                logger.info(
                    "[GRAPH:reranker] rank=%d chunk_id=%s score=%.4f title=%r",
                    index,
                    row.get("chunk_id"),
                    float(row.get("score", 0.0)),
                    (row.get("document_title") or "")[:80],
                )
            if run is not None:
                run.end(
                    outputs={
                        "final_candidate_count": len(final_rows),
                        "reranker_model": rerank_result.model_used,
                        "chunk_ids": [str(row.get("chunk_id")) for row in final_rows[:10]],
                    }
                )
            return {
                "final_candidates": final_rows,
                "reranker_used": self.rag_svc._reranker.model_name != "noop",
                "reranker_model": rerank_result.model_used,
                "reranker_top_k_initial": rerank_result.top_k_initial,
                "reranker_top_k_final": rerank_result.top_k_final,
                "reranker_latency_ms": rerank_result.latency_ms,
                "reranker_fallback": rerank_result.fallback_used,
                "reranker_ranking_changed": rerank_result.ranking_changed,
            }

    async def _response_composer(self, state: DocumentGraphState) -> dict[str, Any]:
        async with trace_step(
            "response_composer",
            inputs={
                "route": state.get("route"),
                "prefilled": bool(state.get("prefilled_response")),
                "retrieval_attempts": state.get("retrieval_attempts", 0),
            },
            tags=["response_composer"],
        ) as run:
            if state.get("response_text"):
                text = state["response_text"]
                mode = state.get("mode") or "template"
                fallback_used = mode in {"clarification", "handoff"}
            elif state.get("prefilled_response"):
                text = state["prefilled_response"] or ""
                mode = state.get("prefilled_mode") or "template"
                fallback_used = False
            elif state.get("route") == "rag_retrieval":
                final_rows = state.get("final_candidates") or state.get("approved_candidates") or []
                if final_rows:
                    rag_results = [
                        {
                            "content": row.get("content", ""),
                            "document_title": row.get("document_title", "Documento"),
                            "score": float(row.get("score", 0.0)),
                        }
                        for row in final_rows
                    ]
                    text, used_llm = await generate_response(
                        context=state["context"],
                        user_text=state["user_text"],
                        faro=state["faro"],
                        rag_results=rag_results,
                        clinic_name=state.get("clinic_name"),
                        chatbot_name=state.get("chatbot_name"),
                        custom_system_prompt=state.get("custom_system_prompt"),
                        insurance_context=state.get("insurance_context"),
                    )
                    mode = "rag_llm" if used_llm else "rag_template"
                    fallback_used = False
                else:
                    text = SAFE_RAG_FALLBACK
                    mode = "rag_safe_fallback"
                    fallback_used = True
                    state["route"] = "clarification_flow"
                    state["source_of_truth"] = "template"
            else:
                text, used_llm = await generate_response(
                    context=state["context"],
                    user_text=state["user_text"],
                    faro=state["faro"],
                    rag_results=None,
                    clinic_name=state.get("clinic_name"),
                    chatbot_name=state.get("chatbot_name"),
                    custom_system_prompt=state.get("custom_system_prompt"),
                    insurance_context=state.get("insurance_context"),
                )
                mode = "llm" if used_llm else "template"
                fallback_used = not used_llm

            if run is not None:
                run.end(outputs={"mode": mode, "response_preview": text[:240]})
            return {
                "response_text": text,
                "mode": mode,
                "fallback_used": fallback_used,
            }

    async def _persist_and_audit(self, state: DocumentGraphState) -> dict[str, Any]:
        selected_chunks = [
            {
                "chunk_id": str(row.get("chunk_id")),
                "document_title": row.get("document_title"),
                "score": float(row.get("score", 0.0)),
            }
            for row in (state.get("final_candidates") or state.get("approved_candidates") or [])[:5]
        ]
        audit_payload = {
            "langgraph_used": state.get("langgraph_used", False),
            "route": state.get("route"),
            "source_of_truth": state.get("source_of_truth"),
            "mode": state.get("mode"),
            "retrieval_mode": state.get("retrieval_mode"),
            "retrieval_attempts": state.get("retrieval_attempts", 0),
            "query_rewrite_used": state.get("query_rewrite_used", False),
            "query_rewrite_attempts": state.get("query_rewrite_attempts", 0),
            "rewritten_query": state.get("rewritten_query"),
            "document_grading_used": state.get("document_grading_used", False),
            "document_grading_threshold": state.get("document_grading_threshold", 0.0),
            "document_grading_strategy": state.get("document_grading_strategy", "disabled"),
            "initial_candidate_count": len(state.get("initial_candidates") or []),
            "approved_candidate_count": len(state.get("approved_candidates") or []),
            "rejected_candidate_count": len(state.get("rejected_candidates") or []),
            "final_candidate_count": len(state.get("final_candidates") or []),
            "prompt_source_response_builder": state.get("prompt_sources", {}).get("response_builder", "env_default"),
            "prompt_source_query_rewrite": state.get("prompt_sources", {}).get("query_rewrite", "default"),
            "prompt_source_document_grading": state.get("prompt_sources", {}).get("document_grading", "default"),
            "selected_chunks": selected_chunks,
        }
        logger.info("[GRAPH:persist_and_audit] %s", json.dumps(audit_payload, ensure_ascii=True))
        return {"audit_payload": audit_payload}

    async def _emit_response(self, state: DocumentGraphState) -> dict[str, Any]:
        return {}

    async def _retrieve_candidates(self, query_text: str, top_k: int) -> tuple[list[dict[str, Any]], str]:
        embedded_chunks_available = await self.rag_svc.repo.has_embeddings(None)
        embedding_config = await self.rag_svc._resolve_embedding_config()
        config_error = self.rag_svc._embedding_config_error(embedding_config)

        if embedded_chunks_available and not config_error:
            query_embedding = await get_embedding(
                query_text,
                phase="query",
                embedding_config=embedding_config,
            )
            if query_embedding is not None:
                rows = await self.rag_svc.repo.search_similar(query_embedding, top_k=top_k)
                rows = _rerank_vector_rows(query_text, rows)
                if rows:
                    return rows, "vector"

        rows = await self.rag_svc.repo.text_search(query_text, top_k=top_k)
        return rows, "text"

    def _heuristic_grade(
        self,
        query_text: str,
        rows: list[dict[str, Any]],
        threshold: float,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        approved: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []
        query_terms = _query_terms(query_text)

        for row in rows:
            haystack = self._normalize_text(
                f"{row.get('document_title', '')} {row.get('content', '')}"
            )
            hits = sum(1 for term in query_terms if term in haystack)
            lexical = hits / len(query_terms) if query_terms else 0.0
            score = float(row.get("score", 0.0))
            title_bonus = 0.10 if any(
                term in self._normalize_text(row.get("document_title", ""))
                for term in query_terms[:3]
            ) else 0.0
            grade_score = round((score * 0.6) + (lexical * 0.3) + title_bonus, 4)
            enriched = dict(row)
            enriched["grade_score"] = grade_score
            enriched["grade_lexical_score"] = round(lexical, 4)
            if grade_score >= threshold:
                approved.append(enriched)
            else:
                rejected.append(enriched)

        return approved, rejected

    async def _llm_grade_documents(
        self,
        state: DocumentGraphState,
        rows: list[dict[str, Any]],
    ) -> set[str] | None:
        prompt = state["prompt_contents"].get("document_grading") or DEFAULT_DOCUMENT_GRADING_PROMPT
        prompt = self._interpolate_prompt(prompt, state)
        user_payload = {
            "question": state["active_query"],
            "documents": [
                {
                    "chunk_id": str(row.get("chunk_id")),
                    "title": row.get("document_title"),
                    "score": round(float(row.get("score", 0.0)), 4),
                    "excerpt": (row.get("content") or "")[:800],
                }
                for row in rows
            ],
        }
        result = await call_llm(
            [
                {"role": "system", "content": prompt},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
            ],
            temperature=0.0,
            max_tokens=500,
            json_mode=True,
        )
        parsed = result.get("parsed") if result else None
        if not isinstance(parsed, dict):
            return None
        approved_chunk_ids = parsed.get("approved_chunk_ids")
        if not isinstance(approved_chunk_ids, list):
            return None
        return {str(chunk_id) for chunk_id in approved_chunk_ids}

    async def _rewrite_query(self, state: DocumentGraphState) -> str | None:
        current_query = state.get("active_query") or state["user_text"]
        if self._can_use_llm():
            prompt = state["prompt_contents"].get("query_rewrite") or DEFAULT_QUERY_REWRITE_PROMPT
            prompt = self._interpolate_prompt(prompt, state)
            result = await call_llm(
                [
                    {"role": "system", "content": prompt},
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "question": current_query,
                                "intent": state["faro"].intent.value,
                                "entities": state["faro"].entities,
                                "rejected_chunks": [
                                    {
                                        "chunk_id": str(row.get("chunk_id")),
                                        "title": row.get("document_title"),
                                    }
                                    for row in (state.get("rejected_candidates") or [])[:5]
                                ],
                            },
                            ensure_ascii=False,
                        ),
                    },
                ],
                temperature=settings.rag_query_rewrite_temperature,
                max_tokens=300,
                json_mode=True,
            )
            parsed = result.get("parsed") if result else None
            if isinstance(parsed, dict):
                rewritten = (parsed.get("rewritten_query") or "").strip()
                if rewritten and self._normalize_text(rewritten) != self._normalize_text(current_query):
                    return rewritten

        fallback = self._deterministic_rewrite(current_query, state["faro"].entities)
        if fallback and self._normalize_text(fallback) != self._normalize_text(current_query):
            return fallback
        return None

    def _deterministic_rewrite(self, current_query: str, entities: dict[str, Any]) -> str:
        additions: list[str] = []
        for key in ("specialty", "doctor_name", "insurance", "procedure"):
            value = entities.get(key)
            if value and str(value).lower() not in current_query.lower():
                additions.append(str(value))
        if not additions:
            return current_query
        return f"{current_query.strip()} {' '.join(additions)}".strip()

    def _document_grading_threshold(self, clinic_cfg: ClinicSettings | None) -> float:
        if clinic_cfg and clinic_cfg.rag_confidence_threshold:
            return max(0.35, min(clinic_cfg.rag_confidence_threshold, 0.9))
        return max(0.35, min(settings.rag_document_grading_min_score, 0.9))

    def _top_k_initial(self, state: DocumentGraphState) -> int:
        if settings.rag_reranker_enabled and self.rag_svc._reranker.model_name != "noop":
            return settings.rag_reranker_top_k_initial
        if state.get("rag_top_k"):
            return max(int(state["rag_top_k"]), 5)
        return max(settings.rag_top_k, 5)

    def _top_k_final(self, state: DocumentGraphState) -> int:
        if state.get("rag_top_k"):
            return int(state["rag_top_k"])
        if settings.rag_reranker_enabled and self.rag_svc._reranker.model_name != "noop":
            return settings.rag_reranker_top_k_final
        return settings.rag_top_k

    def _can_use_llm(self) -> bool:
        return bool(
            settings.groq_api_key
            or settings.openai_api_key
            or settings.anthropic_api_key
            or settings.gemini_api_key
        )

    def _interpolate_prompt(self, prompt: str, state: DocumentGraphState) -> str:
        return (
            prompt.replace("{clinic_name}", state.get("clinic_name") or settings.clinic_name)
            .replace("{chatbot_name}", state.get("chatbot_name") or settings.clinic_chatbot_name)
        )

    def _normalize_text(self, text: str) -> str:
        return re.sub(r"\s+", " ", text.lower()).strip()

    def _to_result(self, state: DocumentGraphState) -> DocumentRuntimeResult:
        final_candidates = state.get("final_candidates") or state.get("approved_candidates") or []
        return DocumentRuntimeResult(
            text=state.get("response_text") or "",
            mode=state.get("mode") or "template",
            route=state.get("route") or "fallback",
            source_of_truth=state.get("source_of_truth") or "none",
            rag_used=bool(final_candidates),
            rag_result_count=len(final_candidates),
            retrieval_mode=state.get("retrieval_mode") or "none",
            fallback_used=state.get("fallback_used", False),
            reranker_used=state.get("reranker_used", False),
            reranker_model=state.get("reranker_model"),
            reranker_top_k_initial=state.get("reranker_top_k_initial", 0),
            reranker_top_k_final=state.get("reranker_top_k_final", 0),
            reranker_latency_ms=state.get("reranker_latency_ms", 0.0),
            reranker_fallback=state.get("reranker_fallback", False),
            reranker_ranking_changed=state.get("reranker_ranking_changed", False),
            langgraph_used=state.get("langgraph_used", False),
            document_grading_used=state.get("document_grading_used", False),
            document_grading_threshold=state.get("document_grading_threshold", 0.0),
            document_grading_strategy=state.get("document_grading_strategy", "disabled"),
            approved_document_count=len(state.get("approved_candidates") or []),
            rejected_document_count=len(state.get("rejected_candidates") or []),
            query_rewrite_used=state.get("query_rewrite_used", False),
            query_rewrite_attempts=state.get("query_rewrite_attempts", 0),
            rewritten_query=state.get("rewritten_query"),
            retrieval_attempts=state.get("retrieval_attempts", 0),
            initial_candidate_count=len(state.get("initial_candidates") or []),
            final_candidate_count=len(final_candidates),
            prompt_source_response_builder=state.get("prompt_sources", {}).get("response_builder", "env_default"),
            prompt_source_query_rewrite=state.get("prompt_sources", {}).get("query_rewrite", "default"),
            prompt_source_document_grading=state.get("prompt_sources", {}).get("document_grading", "default"),
            selected_chunks=[
                {
                    "chunk_id": str(row.get("chunk_id")),
                    "document_title": row.get("document_title"),
                    "score": float(row.get("score", 0.0)),
                }
                for row in final_candidates[:5]
            ],
            audit_payload=state.get("audit_payload") or {},
        )
