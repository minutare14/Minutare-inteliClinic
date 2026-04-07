"""Reception node — entry point for every clinic conversation turn.

Responsibilities:
1. Append the latest user message to the conversation history.
2. Detect whether the patient is identified (patient_id set).
3. Run NLU extraction via ExtractionPipeline to determine intent and structured data.
4. Propagate urgency and safety flags to the state.
5. Return a ClinicStateUpdate with the fields that changed.

This node is always the first node executed in the graph.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    # Avoid circular imports at runtime; TYPE_CHECKING is False at execution time.
    pass

from inteliclinic.core.ai_engine.state.clinic_state import ClinicState, ClinicStateUpdate
from inteliclinic.core.nlu.pipelines.extraction_pipeline import ExtractionPipeline

logger = logging.getLogger(__name__)

# Module-level pipeline instance (initialized lazily to avoid import-time side effects)
_pipeline: ExtractionPipeline | None = None


def _get_pipeline() -> ExtractionPipeline:
    """Return (or lazily initialize) the shared ExtractionPipeline."""
    global _pipeline
    if _pipeline is None:
        _pipeline = ExtractionPipeline.from_config({})
    return _pipeline


def _is_new_patient(state: ClinicState) -> bool:
    """Determine if this is the very first message in the conversation.

    A session is considered 'new' when the conversation history only contains
    the single message that triggered this node execution (i.e., one message total).
    """
    return len(state.get("messages", [])) <= 1


def _build_safety_flags(extracted_data: dict[str, Any], existing_flags: list[str]) -> list[str]:
    """Merge safety flags from NLU extraction with any pre-existing flags.

    Args:
        extracted_data: The .to_state_dict() output from ExtractedMessage.
        existing_flags: Safety flags already present in the state.

    Returns:
        Deduplicated list of safety flags.
    """
    flags = list(existing_flags)

    if extracted_data.get("urgency_detected"):
        if "urgency_detected" not in flags:
            flags.append("urgency_detected")

    if extracted_data.get("intent") == "urgent":
        if "urgent_intent" not in flags:
            flags.append("urgent_intent")

    if extracted_data.get("language_detected") not in ("pt", "en", "es"):
        if "unknown_language" not in flags:
            flags.append("unknown_language")

    return flags


async def reception_node(state: ClinicState) -> ClinicStateUpdate:
    """LangGraph node — processes the incoming user message and populates intent/NLU data.

    Args:
        state: The current ClinicState shared across all nodes.

    Returns:
        ClinicStateUpdate with updated messages, current_intent, extracted_data,
        confidence, safety_flags, and (when needed) error.

    Flow:
        1. Extract the last user message from state.messages.
        2. Log patient identification status (new vs. returning).
        3. Run ExtractionPipeline to get a structured ExtractedMessage.
        4. Build updated safety_flags from urgency signals in extraction output.
        5. Map extracted intent to ClinicState.current_intent string.
        6. Return ClinicStateUpdate with all modified fields.
    """
    messages: list[dict[str, Any]] = state.get("messages", [])
    patient_id: str | None = state.get("patient_id")
    existing_flags: list[str] = state.get("safety_flags", [])

    # ── Step 1: Identify the incoming user message ─────────────────────────────
    user_messages = [m for m in messages if m.get("role") == "user"]
    if not user_messages:
        logger.warning("reception_node called with no user messages in state.")
        return ClinicStateUpdate(
            error="reception_node: no user message found in state",
            current_intent="other",
            confidence=0.0,
        )

    latest_message: str = user_messages[-1].get("content", "")

    # ── Step 2: Log patient identification context ─────────────────────────────
    if patient_id:
        logger.info(
            "reception_node: returning patient=%s | message_count=%d",
            patient_id,
            len(messages),
        )
    else:
        logger.info(
            "reception_node: unidentified patient | is_new=%s | message_count=%d",
            _is_new_patient(state),
            len(messages),
        )

    # ── Step 3: Run NLU extraction ─────────────────────────────────────────────
    # Build conversation history excluding the latest message (already passed separately)
    history: list[dict[str, Any]] = messages[:-1]

    try:
        pipeline = _get_pipeline()
        extracted = await pipeline.process(latest_message, history)
    except Exception as exc:
        logger.exception("reception_node: NLU extraction failed: %s", exc)
        return ClinicStateUpdate(
            error=f"NLU extraction failed: {exc}",
            current_intent="other",
            confidence=0.0,
            safety_flags=existing_flags,
        )

    extracted_dict = extracted.to_state_dict()

    # ── Step 4: Propagate safety/urgency flags ─────────────────────────────────
    updated_flags = _build_safety_flags(extracted_dict, existing_flags)

    # ── Step 5: Map NLU intent to state intent string ──────────────────────────
    # extracted.intent is an Intent enum; .value gives the string representation.
    current_intent: str = extracted.intent.value

    logger.info(
        "reception_node: intent=%s | confidence=%.2f | flags=%s",
        current_intent,
        extracted.confidence,
        updated_flags,
    )

    # ── Step 6: Return partial state update ────────────────────────────────────
    return ClinicStateUpdate(
        current_intent=current_intent,
        extracted_data=extracted_dict,
        confidence=extracted.confidence,
        safety_flags=updated_flags,
        # Clear any stale error from a previous turn
        error=None,
    )
