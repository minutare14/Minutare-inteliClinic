"""Main LangGraph StateGraph for clinic orchestration.

Graph topology
──────────────

    [START]
       │
       ▼
  reception  ←── entry point: NLU extraction, patient identification
       │
       ▼ (route_intent)
  ┌────┴──────────────────────────────────────┐
  │ scheduling │ insurance │ financial │ glosa │ fallback
  └────────────────────────────────────────────┘
       │
       ▼ (always)
  supervisor  ←── escalation gate (optional interrupt point)
       │
       ▼ (should_escalate)
  ┌────┴─────────────┐
  response       [END] (human_handoff)
       │
      [END]

Design notes:
- `route_intent` reads state.current_intent to select the next processing node.
- `should_escalate` reads state.requires_human_handoff to branch after supervisor.
- MemorySaver checkpointer persists state across turns using conversation_id as thread_id.
- `interrupt_before=["supervisor"]` enables human-in-the-loop review before escalation.
"""

from __future__ import annotations

import logging
from typing import Any

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from inteliclinic.core.ai_engine.state.clinic_state import ClinicState
from inteliclinic.core.ai_engine.nodes.reception import reception_node
from inteliclinic.core.ai_engine.nodes.scheduling import scheduling_node
from inteliclinic.core.ai_engine.nodes.insurance import insurance_node
from inteliclinic.core.ai_engine.nodes.financial import financial_node
from inteliclinic.core.ai_engine.nodes.glosa import glosa_node
from inteliclinic.core.ai_engine.nodes.supervisor import supervisor_node
from inteliclinic.core.ai_engine.nodes.fallback import fallback_node
from inteliclinic.core.ai_engine.nodes.response import response_node

logger = logging.getLogger(__name__)

# Type alias — LangGraph's compiled graph type for annotations
CompiledGraph = Any  # langgraph.graph.CompiledStateGraph


# ── Routing functions ─────────────────────────────────────────────────────────

def route_intent(state: ClinicState) -> str:
    """Conditional edge function: reception → intent-specific node.

    Reads state.current_intent and maps it to a node name registered in the graph.
    Falls back to 'fallback' for unknown or low-confidence intents.

    Args:
        state: Current ClinicState after reception_node has run.

    Returns:
        Name of the next node to execute.
    """
    intent: str | None = state.get("current_intent")
    error: str | None = state.get("error")
    confidence: float = state.get("confidence", 1.0)

    # If reception itself errored, go straight to fallback
    if error:
        logger.debug("route_intent: error detected → fallback")
        return "fallback"

    # Map intent values to node names
    intent_map: dict[str, str] = {
        "scheduling": "scheduling",
        "cancel": "scheduling",       # cancellation is handled inside scheduling_node
        "reschedule": "scheduling",   # rescheduling is handled inside scheduling_node
        "insurance": "insurance",
        "financial": "financial",
        "glosa": "glosa",
        "urgent": "fallback",         # urgency → fallback → supervisor picks it up
        "greeting": "response",       # simple greeting → skip to response directly
        "faq": "response",            # FAQ → response node uses RAG
        "other": "fallback",
    }

    next_node = intent_map.get(intent or "", "fallback")

    # Override with fallback if confidence is critically low regardless of intent
    if confidence < 0.30 and next_node not in ("fallback", "response"):
        logger.debug(
            "route_intent: confidence %.2f too low for intent=%s → fallback", confidence, intent
        )
        return "fallback"

    logger.debug("route_intent: intent=%s → %s", intent, next_node)
    return next_node


def should_escalate(state: ClinicState) -> str:
    """Conditional edge function: supervisor → response OR END (human handoff).

    Reads state.requires_human_handoff to determine whether the conversation
    should continue with an automated response or be escalated to a human.

    Args:
        state: Current ClinicState after supervisor_node has run.

    Returns:
        "response" to continue automated flow, or END to terminate and hand off.
    """
    requires_handoff: bool = state.get("requires_human_handoff", False)

    if requires_handoff:
        logger.debug("should_escalate: handoff required → END")
        return END  # The human agent system picks up the conversation from here

    logger.debug("should_escalate: no handoff → response")
    return "response"


# ── Graph builder ─────────────────────────────────────────────────────────────

def build_clinic_graph(config: dict | None = None) -> CompiledGraph:
    """Build and compile the main clinic orchestration graph.

    Graph flow:
        reception → [scheduling | insurance | financial | glosa | fallback | response]
                 ↓
            supervisor (always) → [response | human_handoff (END)]

    Args:
        config: Optional configuration dict. Recognized keys:
            - interrupt_before_supervisor (bool): If True, insert an interrupt before
              the supervisor node to allow human review. Default False.
            - use_memory_saver (bool): If True, attach MemorySaver for persistence. Default True.

    Returns:
        A compiled LangGraph StateGraph ready to invoke.
    """
    cfg = config or {}
    interrupt_before_supervisor: bool = cfg.get("interrupt_before_supervisor", False)
    use_memory_saver: bool = cfg.get("use_memory_saver", True)

    # ── Build the graph ────────────────────────────────────────────────────────
    graph = StateGraph(ClinicState)

    # ── Register all nodes ─────────────────────────────────────────────────────
    graph.add_node("reception", reception_node)
    graph.add_node("scheduling", scheduling_node)
    graph.add_node("insurance", insurance_node)
    graph.add_node("financial", financial_node)
    graph.add_node("glosa", glosa_node)
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("fallback", fallback_node)
    graph.add_node("response", response_node)

    # ── Set entry point ────────────────────────────────────────────────────────
    graph.set_entry_point("reception")

    # ── Conditional edges: reception → intent-specific node ────────────────────
    graph.add_conditional_edges(
        "reception",
        route_intent,
        {
            "scheduling": "scheduling",
            "insurance": "insurance",
            "financial": "financial",
            "glosa": "glosa",
            "fallback": "fallback",
            "response": "response",
        },
    )

    # ── Direct edges: intent nodes → supervisor ────────────────────────────────
    # Every intent node passes through supervisor before generating a response.
    for node_name in ("scheduling", "insurance", "financial", "glosa"):
        graph.add_edge(node_name, "supervisor")

    # Fallback also goes through supervisor (supervisor may escalate urgency cases)
    graph.add_edge("fallback", "supervisor")

    # ── Conditional edges: supervisor → response or END ────────────────────────
    graph.add_conditional_edges(
        "supervisor",
        should_escalate,
        {
            "response": "response",
            END: END,
        },
    )

    # ── Terminal edge: response → END ─────────────────────────────────────────
    graph.add_edge("response", END)

    # ── Compile with optional MemorySaver and interrupt support ────────────────
    interrupt_before: list[str] = ["supervisor"] if interrupt_before_supervisor else []

    if use_memory_saver:
        checkpointer = MemorySaver()
        compiled = graph.compile(
            checkpointer=checkpointer,
            interrupt_before=interrupt_before,
        )
    else:
        compiled = graph.compile(interrupt_before=interrupt_before)

    logger.info(
        "build_clinic_graph: graph compiled | interrupt_before=%s | memory_saver=%s",
        interrupt_before,
        use_memory_saver,
    )
    return compiled
