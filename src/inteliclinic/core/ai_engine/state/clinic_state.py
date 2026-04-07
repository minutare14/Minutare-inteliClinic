"""LangGraph state definition for a clinic AI session.

ClinicState is the single shared state object passed between all graph nodes.
It is defined as a TypedDict so LangGraph can introspect and merge partial updates.

Design notes:
- All fields are optional at initialization except `messages`.
- Nodes return ClinicStateUpdate (partial TypedDict) — only the fields they modify.
- LangGraph merges updates automatically via its reducer logic.
- `next_node` is used by conditional edges when a node needs to override routing.
"""

from __future__ import annotations

from typing import Any, TypedDict


class ClinicState(TypedDict, total=False):
    """Full state for a clinic AI conversation session.

    Passed between every LangGraph node. Each node reads what it needs
    and returns a ClinicStateUpdate with only the fields it modified.

    Conversation lifecycle:
        1. reception sets patient_id, current_intent, extracted_data
        2. Intent-specific node (scheduling/insurance/financial/glosa) processes request
        3. supervisor checks for escalation conditions
        4. response or fallback generates the final reply
    """

    # ── Identity ──────────────────────────────────────────────────────────────
    patient_id: str | None
    """Unique patient identifier, None if the patient has not been identified yet."""

    conversation_id: str | None
    """Unique ID for this conversation thread (used for checkpointing)."""

    # ── Message history ───────────────────────────────────────────────────────
    messages: list[dict[str, Any]]
    """Raw conversation history in OpenAI message format:
    [{"role": "user"|"assistant"|"system", "content": str}, ...]
    Appended to by reception and response nodes.
    """

    # ── NLU / Intent ──────────────────────────────────────────────────────────
    current_intent: str | None
    """Detected intent from NLU extraction.
    One of: 'scheduling', 'insurance', 'financial', 'glosa',
            'urgent', 'faq', 'greeting', 'cancel', 'reschedule', 'other'.
    """

    extracted_data: dict[str, Any]
    """Structured data extracted by InstructorMessageExtractor.
    Contains all fields from ExtractedMessage as a plain dict.
    Example keys: desired_specialty, desired_date, insurance_plan, confidence, ...
    """

    # ── Multi-turn / Pending Actions ──────────────────────────────────────────
    pending_action: dict[str, Any] | None
    """Stores state for actions requiring confirmation or additional input.
    Example: {"action": "book_appointment", "slot_id": "...", "awaiting": "confirmation"}
    Cleared once the action is resolved or cancelled.
    """

    # ── Context ───────────────────────────────────────────────────────────────
    context: dict[str, Any]
    """Free-form conversation context accumulated across turns.
    Nodes write their output here for the response node to consume.
    Example keys: available_slots, selected_slot, insurance_coverage_summary,
                  financial_breakdown, glosa_risk_score, response_text.
    """

    # ── RAG ───────────────────────────────────────────────────────────────────
    rag_results: list[dict[str, Any]]
    """Results retrieved from the vector store (RAG).
    Each entry: {"source": str, "content": str, "score": float, "metadata": dict}
    """

    # ── Safety ────────────────────────────────────────────────────────────────
    safety_flags: list[str]
    """List of active safety flags.
    Populated by reception and any node that detects a safety concern.
    Examples: 'urgency_detected', 'medical_advice_attempt', 'legal_risk',
              'patient_distress', 'pii_exposure_risk'.
    """

    requires_human_handoff: bool
    """True when the conversation must be escalated to a human agent."""

    handoff_reason: str | None
    """Human-readable explanation of why handoff was triggered.
    Shown to the human agent picking up the conversation.
    """

    # ── Quality ───────────────────────────────────────────────────────────────
    confidence: float
    """Overall confidence score for the current turn (0.0 – 1.0).
    Aggregated from NLU extraction confidence and node-specific signals.
    Below GraphConfig.supervisor_threshold → triggers supervisor escalation check.
    """

    # ── Error handling ────────────────────────────────────────────────────────
    error: str | None
    """Error message if any node encountered an unrecoverable exception.
    Presence of a non-None error routes the graph to the fallback node.
    """

    # ── Graph routing ─────────────────────────────────────────────────────────
    next_node: str | None
    """Explicit override for the next node to visit.
    Normally None — routing is determined by conditional edge functions.
    Set by a node only when it needs to bypass standard routing logic.
    Example: supervisor sets next_node='human_handoff' when escalating.
    """


class ClinicStateUpdate(TypedDict, total=False):
    """Partial state update returned by individual nodes.

    Nodes return only the fields they modify. LangGraph merges this
    into the full ClinicState. All fields are optional (total=False).

    Example — reception node return:
        return ClinicStateUpdate(
            current_intent="scheduling",
            extracted_data=extracted.model_dump(),
            confidence=extracted.confidence,
            messages=[*state["messages"], {"role": "system", "content": "..."}],
        )
    """

    patient_id: str | None
    conversation_id: str | None
    messages: list[dict[str, Any]]
    current_intent: str | None
    extracted_data: dict[str, Any]
    pending_action: dict[str, Any] | None
    context: dict[str, Any]
    rag_results: list[dict[str, Any]]
    safety_flags: list[str]
    requires_human_handoff: bool
    handoff_reason: str | None
    confidence: float
    error: str | None
    next_node: str | None


def make_initial_state(
    conversation_id: str,
    patient_id: str | None = None,
    initial_message: str | None = None,
) -> ClinicState:
    """Factory for creating a fresh ClinicState at the start of a conversation.

    Args:
        conversation_id: Unique thread identifier (used as LangGraph thread_id).
        patient_id:      Known patient ID, or None for anonymous sessions.
        initial_message: The first user message, if available.

    Returns:
        A fully initialized ClinicState with safe defaults.
    """
    messages: list[dict[str, Any]] = []
    if initial_message:
        messages.append({"role": "user", "content": initial_message})

    return ClinicState(
        patient_id=patient_id,
        conversation_id=conversation_id,
        messages=messages,
        current_intent=None,
        extracted_data={},
        pending_action=None,
        context={},
        rag_results=[],
        safety_flags=[],
        requires_human_handoff=False,
        handoff_reason=None,
        confidence=1.0,
        error=None,
        next_node=None,
    )
