"""Fallback node — safe conservative response when confidence is too low or an error occurred.

This node is the safety net of the graph. It activates when:
- The supervisor determines confidence is too low but human handoff is not yet required.
- A node sets error in the state.
- The intent is "other" and the system cannot determine what the patient needs.

Core principles:
- NEVER diagnoses or makes clinical inferences.
- NEVER extrapolates intent beyond what the patient explicitly said.
- Always offers a clear path forward (clarification question or human agent option).
- Responses are in Brazilian Portuguese, polite, and reassuring.
"""

from __future__ import annotations

import logging
from typing import Any

from inteliclinic.core.ai_engine.state.clinic_state import ClinicState, ClinicStateUpdate

logger = logging.getLogger(__name__)

# ── Canned response templates ──────────────────────────────────────────────────
# These are safe, reviewed responses that cannot produce harmful outputs.

_RESPONSE_AMBIGUOUS = (
    "Olá! Recebi sua mensagem, mas preciso de um pouco mais de informação para te ajudar melhor. "
    "Poderia me contar com mais detalhes o que você precisa? "
    "Por exemplo: agendar uma consulta, tirar dúvidas sobre convênio, informações de pagamento, "
    "ou outra solicitação?"
)

_RESPONSE_LOW_CONFIDENCE = (
    "Desculpe, não consegui entender completamente sua solicitação. "
    "Poderia reformular sua pergunta? "
    "Estou aqui para ajudar com agendamentos, informações sobre convênios, "
    "valores de consultas e dúvidas gerais sobre a clínica."
)

_RESPONSE_ERROR = (
    "Tivemos um problema técnico ao processar sua mensagem. "
    "Peço desculpas pelo inconveniente. "
    "Você pode tentar novamente ou, se preferir, entrar em contato diretamente com nossa recepção."
)

_RESPONSE_UNKNOWN_INTENT = (
    "Olá! Posso te ajudar com:\n"
    "• Agendamento de consultas\n"
    "• Informações sobre planos de saúde e convênios\n"
    "• Valores e formas de pagamento\n"
    "• Dúvidas gerais sobre a clínica\n\n"
    "O que você precisa hoje?"
)

_RESPONSE_URGENCY_FALLBACK = (
    "Percebi que sua mensagem pode indicar uma situação urgente. "
    "Por favor, se for uma emergência médica, ligue imediatamente para o SAMU (192) "
    "ou dirija-se ao pronto-socorro mais próximo. "
    "Se precisar de atendimento prioritário na clínica, vou te conectar com nossa equipe agora."
)


def _select_fallback_response(
    intent: str | None,
    error: str | None,
    confidence: float,
    safety_flags: list[str],
    extracted_data: dict[str, Any],
) -> str:
    """Select the most appropriate fallback response template.

    Priority order:
    1. Urgency/emergency detected → urgency response
    2. Error in state → error response
    3. Low confidence (message was parseable but uncertain) → low confidence response
    4. Ambiguous intent → ambiguous response
    5. Unknown/unhandled intent → menu response
    """
    if "urgency_detected" in safety_flags or "urgent_intent" in safety_flags:
        return _RESPONSE_URGENCY_FALLBACK

    if error:
        return _RESPONSE_ERROR

    if confidence < 0.40:
        return _RESPONSE_LOW_CONFIDENCE

    if extracted_data.get("is_ambiguous"):
        clarification = extracted_data.get("clarification_question")
        if clarification:
            return (
                f"Não tenho certeza se entendi sua solicitação corretamente. "
                f"{clarification}"
            )
        return _RESPONSE_AMBIGUOUS

    if intent in (None, "other"):
        return _RESPONSE_UNKNOWN_INTENT

    return _RESPONSE_LOW_CONFIDENCE


async def fallback_node(state: ClinicState) -> ClinicStateUpdate:
    """LangGraph node — generates a safe, conservative fallback response.

    Args:
        state: Current ClinicState.

    Returns:
        ClinicStateUpdate with context['response_text'] set to the fallback message.
        Also clears the error field to prevent repeated fallback loops.

    This node is the terminal response node for low-confidence or error paths.
    It sets context['response_text'] which the response node (if also in the path)
    or the graph output handler will use to send the reply to the patient.
    """
    intent: str | None = state.get("current_intent")
    error: str | None = state.get("error")
    confidence: float = state.get("confidence", 0.0)
    safety_flags: list[str] = state.get("safety_flags", [])
    extracted_data: dict[str, Any] = state.get("extracted_data", {})
    context: dict[str, Any] = dict(state.get("context", {}))

    logger.info(
        "fallback_node: intent=%s | confidence=%.2f | error=%s | flags=%s",
        intent,
        confidence,
        error,
        safety_flags,
    )

    response_text = _select_fallback_response(
        intent=intent,
        error=error,
        confidence=confidence,
        safety_flags=safety_flags,
        extracted_data=extracted_data,
    )

    # Always offer the human agent option at the end of a fallback response
    # unless it is already an urgency message (which routes to handoff)
    is_urgency = "urgency_detected" in safety_flags or "urgent_intent" in safety_flags
    if not is_urgency and not response_text.endswith("equipe agora."):
        response_text += (
            "\n\nSe preferir, posso te conectar com um de nossos atendentes. "
            "É só me dizer!"
        )

    context["response_text"] = response_text
    context["response_source"] = "fallback"

    # Clear the error so the graph does not loop back into fallback on the next turn
    return ClinicStateUpdate(
        context=context,
        error=None,
    )
