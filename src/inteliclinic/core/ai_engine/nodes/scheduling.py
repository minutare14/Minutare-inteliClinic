"""Scheduling node — handles appointment booking, cancellation, and rescheduling.

Processes the 'scheduling', 'cancel', and 'reschedule' intents.

Responsibilities:
- Extract scheduling parameters (specialty, professional, date, time, insurance) from extracted_data.
- Determine the scheduling sub-action (book / cancel / reschedule).
- Search for available slots (stub: replaced by real integration per clinic deploy).
- Set pending_action when confirmation from the patient is needed.
- Populate context['scheduling'] with slot options or confirmation data.
- Never book without explicit patient confirmation (multi-turn safety).
"""

from __future__ import annotations

import logging
from datetime import datetime, date
from typing import Any

from inteliclinic.core.ai_engine.state.clinic_state import ClinicState, ClinicStateUpdate

logger = logging.getLogger(__name__)

# ── Scheduling sub-actions derived from intent ─────────────────────────────────
_CANCEL_INTENTS = {"cancel"}
_RESCHEDULE_INTENTS = {"reschedule"}
_BOOK_INTENTS = {"scheduling"}


def _determine_sub_action(intent: str, pending: dict[str, Any] | None) -> str:
    """Return the scheduling sub-action for the current turn.

    If there is an active pending_action, we are in a confirmation flow
    and the sub-action is carried over from the previous turn.
    """
    if pending and pending.get("action") in ("book_appointment", "cancel_appointment", "reschedule_appointment"):
        return pending["action"]
    if intent in _CANCEL_INTENTS:
        return "cancel_appointment"
    if intent in _RESCHEDULE_INTENTS:
        return "reschedule_appointment"
    return "book_appointment"


def _extract_scheduling_params(extracted_data: dict[str, Any]) -> dict[str, Any]:
    """Pull the scheduling-relevant fields from the NLU extraction dict."""
    return {
        "specialty": extracted_data.get("desired_specialty"),
        "professional": extracted_data.get("desired_professional"),
        "date": extracted_data.get("desired_date"),
        "time": extracted_data.get("desired_time"),
        "insurance_plan": extracted_data.get("insurance_plan"),
    }


async def _search_available_slots(params: dict[str, Any], patient_id: str | None) -> list[dict[str, Any]]:
    """Search for available appointment slots.

    In a real clinic deploy this calls the clinic's scheduling API or database.
    Returns a list of slot dicts, each with: slot_id, professional, datetime, specialty, modality.
    """
    # Placeholder implementation — replaced by clinic-specific integration layer.
    specialty = params.get("specialty") or "geral"
    desired_date_str = params.get("date") or date.today().isoformat()

    logger.debug("Searching slots for specialty=%s date=%s", specialty, desired_date_str)

    # Return mock slots so the graph can be tested end-to-end before real integration.
    return [
        {
            "slot_id": f"slot-{specialty}-001",
            "professional": params.get("professional") or f"Dr. Especialista em {specialty.title()}",
            "specialty": specialty,
            "datetime": f"{desired_date_str}T09:00:00",
            "modality": "presencial",
            "insurance_accepted": params.get("insurance_plan") is not None,
        },
        {
            "slot_id": f"slot-{specialty}-002",
            "professional": params.get("professional") or f"Dr. Especialista em {specialty.title()}",
            "specialty": specialty,
            "datetime": f"{desired_date_str}T14:00:00",
            "modality": "presencial",
            "insurance_accepted": params.get("insurance_plan") is not None,
        },
    ]


def _check_confirmation_received(pending: dict[str, Any], extracted_data: dict[str, Any]) -> bool:
    """Determine whether the patient's latest message is a positive confirmation.

    Checks for affirmative intent signals in the raw text stored in extracted_data.
    This is a simple heuristic; real implementations can use a dedicated intent model.
    """
    original = extracted_data.get("original_text", "").lower()
    affirmatives = {"sim", "confirmo", "pode agendar", "pode marcar", "ok", "isso", "exato", "correto"}
    return any(word in original for word in affirmatives)


async def scheduling_node(state: ClinicState) -> ClinicStateUpdate:
    """LangGraph node — orchestrates appointment scheduling flows.

    Args:
        state: Current ClinicState.

    Returns:
        ClinicStateUpdate with context (slot options or confirmation), pending_action,
        and optionally requires_human_handoff for complex edge cases.

    Multi-turn flow for booking:
        Turn 1 → NLU extraction → search slots → set pending_action awaiting confirmation
        Turn 2 → patient confirms → book_appointment → clear pending_action
    """
    extracted_data: dict[str, Any] = state.get("extracted_data", {})
    current_intent: str = state.get("current_intent", "scheduling")
    pending: dict[str, Any] | None = state.get("pending_action")
    patient_id: str | None = state.get("patient_id")
    context: dict[str, Any] = dict(state.get("context", {}))

    sub_action = _determine_sub_action(current_intent, pending)
    params = _extract_scheduling_params(extracted_data)

    logger.info(
        "scheduling_node: sub_action=%s | specialty=%s | date=%s | insurance=%s",
        sub_action,
        params["specialty"],
        params["date"],
        params["insurance_plan"],
    )

    # ── Handle cancellation ────────────────────────────────────────────────────
    if sub_action == "cancel_appointment":
        if pending and pending.get("awaiting") == "confirmation":
            if _check_confirmation_received(pending, extracted_data):
                # Patient confirmed cancellation — proceed (real integration would call API)
                logger.info("scheduling_node: cancellation confirmed for patient=%s", patient_id)
                context["scheduling"] = {
                    "action": "cancel_appointment",
                    "status": "cancelled",
                    "message": "Consulta cancelada com sucesso. Você receberá uma confirmação por e-mail.",
                }
                return ClinicStateUpdate(context=context, pending_action=None)
            else:
                # Patient did not confirm — abort cancellation
                context["scheduling"] = {
                    "action": "cancel_appointment",
                    "status": "aborted",
                    "message": "Entendido, o cancelamento não foi realizado.",
                }
                return ClinicStateUpdate(context=context, pending_action=None)
        else:
            # First turn of cancellation — ask for confirmation
            context["scheduling"] = {
                "action": "cancel_appointment",
                "status": "awaiting_confirmation",
                "message": "Você tem certeza que deseja cancelar sua consulta?",
            }
            return ClinicStateUpdate(
                context=context,
                pending_action={"action": "cancel_appointment", "awaiting": "confirmation"},
            )

    # ── Handle rescheduling ────────────────────────────────────────────────────
    if sub_action == "reschedule_appointment":
        if not params["date"] and not params["time"]:
            # Need date/time to reschedule
            context["scheduling"] = {
                "action": "reschedule_appointment",
                "status": "needs_info",
                "message": "Para reagendar, por favor informe a nova data e horário desejados.",
            }
            return ClinicStateUpdate(context=context)

        slots = await _search_available_slots(params, patient_id)
        context["scheduling"] = {
            "action": "reschedule_appointment",
            "status": "slots_found",
            "available_slots": slots,
            "params": params,
        }
        return ClinicStateUpdate(
            context=context,
            pending_action={
                "action": "reschedule_appointment",
                "awaiting": "slot_selection",
                "params": params,
                "slots": slots,
            },
        )

    # ── Handle booking ─────────────────────────────────────────────────────────
    if sub_action == "book_appointment":
        # If there is a pending booking confirmation, process it
        if pending and pending.get("awaiting") == "confirmation":
            if _check_confirmation_received(pending, extracted_data):
                slot = pending.get("selected_slot", {})
                logger.info("scheduling_node: booking confirmed | slot=%s | patient=%s", slot.get("slot_id"), patient_id)
                context["scheduling"] = {
                    "action": "book_appointment",
                    "status": "booked",
                    "slot": slot,
                    "message": (
                        f"Consulta agendada com sucesso para {slot.get('datetime', '(sem data)')} "
                        f"com {slot.get('professional', 'o profissional')}."
                    ),
                }
                return ClinicStateUpdate(context=context, pending_action=None)
            else:
                context["scheduling"] = {
                    "action": "book_appointment",
                    "status": "aborted",
                    "message": "Agendamento cancelado. Posso te ajudar com outra coisa?",
                }
                return ClinicStateUpdate(context=context, pending_action=None)

        # No pending action — first turn: search for slots
        if not params["specialty"] and not params["professional"]:
            # Not enough info to search — ask for specialty
            context["scheduling"] = {
                "action": "book_appointment",
                "status": "needs_specialty",
                "message": "Para agendar uma consulta, qual especialidade médica você precisa?",
            }
            return ClinicStateUpdate(context=context)

        slots = await _search_available_slots(params, patient_id)

        if not slots:
            context["scheduling"] = {
                "action": "book_appointment",
                "status": "no_slots",
                "params": params,
                "message": "Não encontramos horários disponíveis para essa especialidade na data solicitada.",
            }
            return ClinicStateUpdate(context=context)

        # Present first slot as suggestion and await confirmation
        suggested_slot = slots[0]
        context["scheduling"] = {
            "action": "book_appointment",
            "status": "awaiting_confirmation",
            "available_slots": slots,
            "suggested_slot": suggested_slot,
            "params": params,
        }
        return ClinicStateUpdate(
            context=context,
            pending_action={
                "action": "book_appointment",
                "awaiting": "confirmation",
                "selected_slot": suggested_slot,
                "all_slots": slots,
                "params": params,
            },
        )

    # Fallthrough — unknown sub_action
    logger.warning("scheduling_node: unhandled sub_action=%s", sub_action)
    context["scheduling"] = {"status": "error", "message": "Não foi possível processar sua solicitação de agendamento."}
    return ClinicStateUpdate(context=context, error=f"Unknown scheduling sub_action: {sub_action}")
