"""Supervisor node — human-in-the-loop escalation gate.

This node is always executed after the intent-specific node and before response generation.
It decides whether the conversation should continue to the automated response node or
be escalated (handed off) to a human agent.

Escalation triggers (checked in priority order):
1. Urgency detected (patient emergency)
2. Explicit patient request for a human agent
3. Safety flags raised by any upstream node
4. Low confidence (below supervisor_threshold)
5. Unresolvable error in a prior node
6. Excessive conversation turns without resolution

When escalation is required:
- sets requires_human_handoff = True
- sets handoff_reason with a descriptive message for the human agent
- sets next_node = "human_handoff" (consumed by the conditional edge)

When no escalation is needed:
- returns ClinicStateUpdate with requires_human_handoff = False
- next_node remains None (graph proceeds to response)
"""

from __future__ import annotations

import logging
from typing import Any

from inteliclinic.core.ai_engine.state.clinic_state import ClinicState, ClinicStateUpdate

logger = logging.getLogger(__name__)

# ── Escalation thresholds (overridden by GraphConfig per clinic) ───────────────
_DEFAULT_SUPERVISOR_THRESHOLD = 0.50
"""Confidence below this value triggers escalation."""

_DEFAULT_MAX_TURNS = 20
"""Maximum turns before proactive escalation to prevent runaway conversations."""

# ── Safety flags that always trigger immediate escalation ──────────────────────
_CRITICAL_FLAGS = {
    "urgency_detected",
    "urgent_intent",
    "patient_distress",
    "medical_advice_attempt",
    "legal_risk",
    "pii_exposure_risk",
}

# ── Phrases in original text that indicate the patient wants a human ───────────
_HUMAN_REQUEST_SIGNALS = [
    "falar com atendente",
    "falar com humano",
    "falar com uma pessoa",
    "quero um atendente",
    "quero um humano",
    "me transfere",
    "me passa para",
    "atendimento humano",
    "não quero falar com robô",
    "não quero falar com bot",
]


def _patient_requested_human(extracted_data: dict[str, Any]) -> bool:
    """Return True if the patient explicitly asked to speak to a human agent."""
    original = extracted_data.get("original_text", "").lower()
    return any(signal in original for signal in _HUMAN_REQUEST_SIGNALS)


def _has_critical_safety_flag(safety_flags: list[str]) -> str | None:
    """Return the first critical safety flag found, or None."""
    for flag in safety_flags:
        if flag in _CRITICAL_FLAGS:
            return flag
    return None


def _count_turns(messages: list[dict[str, Any]]) -> int:
    """Count the number of full user+assistant conversation turns."""
    user_messages = sum(1 for m in messages if m.get("role") == "user")
    return user_messages


async def supervisor_node(state: ClinicState) -> ClinicStateUpdate:
    """LangGraph node — determines whether to escalate to a human agent.

    Args:
        state: Current ClinicState after all upstream nodes have run.

    Returns:
        ClinicStateUpdate. If escalation is required:
            requires_human_handoff=True, handoff_reason=<str>, next_node="human_handoff"
        Otherwise:
            requires_human_handoff=False, next_node=None (proceed to response)

    This node is designed to be an interrupt point in the graph when
    human_interrupt_nodes includes "supervisor" in GraphConfig.
    """
    safety_flags: list[str] = state.get("safety_flags", [])
    confidence: float = state.get("confidence", 1.0)
    error: str | None = state.get("error")
    extracted_data: dict[str, Any] = state.get("extracted_data", {})
    messages: list[dict[str, Any]] = state.get("messages", [])
    current_intent: str | None = state.get("current_intent")
    patient_id: str | None = state.get("patient_id")

    # Read thresholds from context config (set by GraphConfig during graph compilation)
    graph_config: dict[str, Any] = state.get("context", {}).get("_graph_config", {})
    supervisor_threshold: float = graph_config.get("supervisor_threshold", _DEFAULT_SUPERVISOR_THRESHOLD)
    max_turns: int = graph_config.get("max_turns", _DEFAULT_MAX_TURNS)

    logger.info(
        "supervisor_node: confidence=%.2f | threshold=%.2f | flags=%s | error=%s",
        confidence,
        supervisor_threshold,
        safety_flags,
        error,
    )

    # ── Check 1: Critical safety flags (highest priority) ──────────────────────
    critical_flag = _has_critical_safety_flag(safety_flags)
    if critical_flag:
        reason = _build_handoff_reason(
            trigger="critical_safety_flag",
            detail=f"Flag de segurança crítica detectada: '{critical_flag}'",
            patient_id=patient_id,
            intent=current_intent,
            confidence=confidence,
        )
        logger.warning("supervisor_node: escalating — critical flag '%s'", critical_flag)
        return ClinicStateUpdate(
            requires_human_handoff=True,
            handoff_reason=reason,
            next_node="human_handoff",
        )

    # ── Check 2: Patient explicitly requested a human agent ────────────────────
    if _patient_requested_human(extracted_data):
        reason = _build_handoff_reason(
            trigger="patient_request",
            detail="Paciente solicitou atendimento com agente humano.",
            patient_id=patient_id,
            intent=current_intent,
            confidence=confidence,
        )
        logger.info("supervisor_node: escalating — patient requested human")
        return ClinicStateUpdate(
            requires_human_handoff=True,
            handoff_reason=reason,
            next_node="human_handoff",
        )

    # ── Check 3: Node error ────────────────────────────────────────────────────
    if error:
        reason = _build_handoff_reason(
            trigger="node_error",
            detail=f"Erro interno no processamento: {error}",
            patient_id=patient_id,
            intent=current_intent,
            confidence=confidence,
        )
        logger.warning("supervisor_node: escalating — node error: %s", error)
        return ClinicStateUpdate(
            requires_human_handoff=True,
            handoff_reason=reason,
            next_node="human_handoff",
        )

    # ── Check 4: Low confidence ────────────────────────────────────────────────
    if confidence < supervisor_threshold:
        reason = _build_handoff_reason(
            trigger="low_confidence",
            detail=f"Confiança da extração ({confidence:.0%}) abaixo do limiar ({supervisor_threshold:.0%}).",
            patient_id=patient_id,
            intent=current_intent,
            confidence=confidence,
        )
        logger.info(
            "supervisor_node: escalating — low confidence %.2f < %.2f",
            confidence,
            supervisor_threshold,
        )
        return ClinicStateUpdate(
            requires_human_handoff=True,
            handoff_reason=reason,
            next_node="human_handoff",
        )

    # ── Check 5: Conversation turn limit exceeded ──────────────────────────────
    turn_count = _count_turns(messages)
    if turn_count >= max_turns:
        reason = _build_handoff_reason(
            trigger="max_turns_exceeded",
            detail=f"Conversa atingiu o limite de {max_turns} turnos sem resolução.",
            patient_id=patient_id,
            intent=current_intent,
            confidence=confidence,
        )
        logger.info("supervisor_node: escalating — max turns %d reached", turn_count)
        return ClinicStateUpdate(
            requires_human_handoff=True,
            handoff_reason=reason,
            next_node="human_handoff",
        )

    # ── No escalation needed ────────────────────────────────────────────────────
    logger.info("supervisor_node: no escalation — proceeding to response")
    return ClinicStateUpdate(
        requires_human_handoff=False,
        next_node=None,
    )


def _build_handoff_reason(
    trigger: str,
    detail: str,
    patient_id: str | None,
    intent: str | None,
    confidence: float,
) -> str:
    """Construct a structured handoff reason message for the receiving human agent."""
    patient_info = f"paciente={patient_id}" if patient_id else "paciente não identificado"
    return (
        f"[HANDOFF — {trigger.upper()}] {detail} | "
        f"Contexto: {patient_info}, intenção={intent or 'desconhecida'}, "
        f"confiança={confidence:.0%}"
    )
