"""Response node — final LLM-backed response generation.

This is the last node in the happy path (no escalation, no fallback).
It takes all the data assembled by upstream nodes and generates a coherent,
natural-language response for the patient.

Data sources available for response generation:
- context['scheduling']   : slot options, booking confirmation, cancellation status
- context['insurance']    : coverage info, authorization requirements
- context['financial']    : pricing, payment methods
- context['glosa']        : risk score and recommended action (internal only)
- context['response_text']: pre-built response from fallback node (if present)
- rag_results             : raw RAG excerpts for grounding
- messages                : full conversation history

Safety constraints:
- Never include medical diagnoses or clinical recommendations.
- Never promise definitive insurance coverage or prices.
- Always include appropriate disclaimers when citing prices or coverage.
- Responses must be in Brazilian Portuguese unless the patient wrote in another language.
- Responses must be concise (≤ 250 words for standard queries).
"""

from __future__ import annotations

import logging
from typing import Any

from inteliclinic.core.ai_engine.state.clinic_state import ClinicState, ClinicStateUpdate

logger = logging.getLogger(__name__)

# ── System prompt for response generation ─────────────────────────────────────
_SYSTEM_PROMPT = """Você é um assistente virtual de uma clínica médica brasileira, educado, empático e profissional.

Seu papel é ajudar pacientes com:
- Agendamentos de consultas e exames
- Informações sobre convênios e planos de saúde
- Valores e formas de pagamento
- Dúvidas gerais sobre a clínica

Regras invioláveis:
1. NUNCA ofereça diagnósticos, conselhos médicos ou interpretação de exames.
2. NUNCA afirme categoricamente que um procedimento está coberto pelo plano — sempre oriente a confirmar com a operadora.
3. NUNCA invente informações. Se não souber, diga que vai verificar com a equipe.
4. Responda em português brasileiro, de forma clara e concisa (máximo 200 palavras).
5. Seja acolhedor e tranquilizador — muitos pacientes estão em situações de estresse.
6. Sempre ofereça um próximo passo claro ao final da resposta.
"""


def _build_context_summary(context: dict[str, Any]) -> str:
    """Summarize the structured data assembled by upstream nodes into a text block.

    This summary is injected into the LLM prompt as grounding context,
    ensuring the response reflects the actual data retrieved (not hallucinations).
    """
    parts: list[str] = []

    if scheduling := context.get("scheduling"):
        status = scheduling.get("status", "")
        if status == "awaiting_confirmation":
            slot = scheduling.get("suggested_slot", {})
            parts.append(
                f"AGENDAMENTO: Horário sugerido — {slot.get('datetime', '?')} "
                f"com {slot.get('professional', '?')} ({slot.get('specialty', '?')}). "
                "Aguardando confirmação do paciente."
            )
        elif status == "booked":
            slot = scheduling.get("slot", {})
            parts.append(
                f"AGENDAMENTO: Consulta confirmada — {slot.get('datetime', '?')} "
                f"com {slot.get('professional', '?')}."
            )
        elif status == "cancelled":
            parts.append("AGENDAMENTO: Consulta cancelada com sucesso.")
        elif status == "no_slots":
            parts.append("AGENDAMENTO: Nenhum horário disponível encontrado para os critérios informados.")
        elif status == "needs_specialty":
            parts.append("AGENDAMENTO: Especialidade não informada — necessário perguntar ao paciente.")
        elif scheduling.get("message"):
            parts.append(f"AGENDAMENTO: {scheduling['message']}")

    if insurance := context.get("insurance"):
        if insurance.get("status") == "coverage_found":
            parts.append(
                f"CONVÊNIO ({insurance.get('insurance_plan', '?')}): "
                f"{insurance.get('authorization_message', '')}"
            )
        elif insurance.get("message"):
            parts.append(f"CONVÊNIO: {insurance['message']}")

    if financial := context.get("financial"):
        if summary := financial.get("payment_summary"):
            parts.append(f"FINANCEIRO:\n{summary}")

    if glosa := context.get("glosa"):
        if glosa.get("status") == "analysed":
            parts.append(
                f"GLOSA: Risco {glosa.get('risk_label', '?')} "
                f"(score={glosa.get('risk_score', 0):.2f}). "
                f"Ação: {glosa.get('recommended_action', '')}"
            )

    return "\n\n".join(parts) if parts else "Sem dados estruturados disponíveis."


def _build_rag_excerpt(rag_results: list[dict[str, Any]], max_chars: int = 800) -> str:
    """Format RAG results into a compact excerpt for the LLM prompt."""
    if not rag_results:
        return ""
    excerpts = []
    total = 0
    for r in sorted(rag_results, key=lambda x: x.get("score", 0.0), reverse=True):
        content = r.get("content", "")
        source = r.get("source", "base de conhecimento")
        snippet = f"[{source}]: {content[:300]}"
        if total + len(snippet) > max_chars:
            break
        excerpts.append(snippet)
        total += len(snippet)
    return "\n".join(excerpts)


async def _call_llm(
    messages: list[dict[str, Any]],
    system: str,
) -> str:
    """Call the LLM to generate the final patient response.

    In production, this uses the configured LLM client (OpenAI/Anthropic/Gemini)
    injected via the clinic's configuration. Here we provide a well-defined interface
    that clinic deployers replace with their actual client.

    Args:
        messages: Full chat history in OpenAI format, including the injected context.
        system:   System prompt.

    Returns:
        The assistant's response text.
    """
    try:
        from openai import AsyncOpenAI  # type: ignore[import]
        import os

        client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": system}, *messages],
            max_tokens=400,
            temperature=0.3,  # Low temperature for factual, consistent responses
        )
        return response.choices[0].message.content or ""
    except Exception as exc:
        logger.warning("response_node: LLM call failed: %s — using context summary as response", exc)
        return ""


async def response_node(state: ClinicState) -> ClinicStateUpdate:
    """LangGraph node — generates the final patient-facing response using the LLM.

    Args:
        state: Current ClinicState with all upstream data populated.

    Returns:
        ClinicStateUpdate with updated messages (assistant reply appended)
        and context['response_text'] set to the generated response.

    Flow:
        1. If fallback already set context['response_text'], use it directly.
        2. Otherwise, build a grounded LLM prompt from context + RAG results.
        3. Call the LLM to generate the response.
        4. Append the assistant message to the conversation history.
        5. Return the updated messages and response_text.
    """
    context: dict[str, Any] = dict(state.get("context", {}))
    rag_results: list[dict[str, Any]] = state.get("rag_results", [])
    messages: list[dict[str, Any]] = list(state.get("messages", []))
    language: str = state.get("extracted_data", {}).get("language_detected", "pt")

    # ── Step 1: Check if fallback already produced a response ──────────────────
    pre_built_response: str | None = context.get("response_text")
    if pre_built_response and context.get("response_source") == "fallback":
        logger.info("response_node: using pre-built fallback response")
        messages.append({"role": "assistant", "content": pre_built_response})
        return ClinicStateUpdate(messages=messages, context=context)

    # ── Step 2: Build grounded context for the LLM ────────────────────────────
    context_summary = _build_context_summary(context)
    rag_excerpt = _build_rag_excerpt(rag_results)

    # Adjust language instruction if patient wrote in a non-Portuguese language
    lang_instruction = ""
    if language == "en":
        lang_instruction = "\nRespond in English since the patient wrote in English."
    elif language == "es":
        lang_instruction = "\nResponda en español, ya que el paciente escribió en español."

    # Inject grounding context as a system-level message before the last user message
    grounding_message: dict[str, Any] = {
        "role": "system",
        "content": (
            f"DADOS DO ATENDIMENTO ATUAL:\n{context_summary}"
            + (f"\n\nINFORMAÇÕES DA BASE DE CONHECIMENTO:\n{rag_excerpt}" if rag_excerpt else "")
            + lang_instruction
        ),
    }

    # Build the prompt messages: history + grounding + last user message
    # Keep full history but cap at last 10 exchanges to avoid token bloat
    history_cap = 20  # 10 user + 10 assistant messages
    capped_messages = messages[-history_cap:] if len(messages) > history_cap else messages

    prompt_messages = [*capped_messages[:-1], grounding_message, capped_messages[-1]] if capped_messages else []

    # ── Step 3: Call the LLM ──────────────────────────────────────────────────
    logger.info(
        "response_node: calling LLM | history_len=%d | context_keys=%s",
        len(prompt_messages),
        list(context.keys()),
    )

    response_text = await _call_llm(prompt_messages, _SYSTEM_PROMPT)

    # ── Step 4: Fallback if LLM call failed ───────────────────────────────────
    if not response_text:
        response_text = (
            "Desculpe, ocorreu um problema ao gerar sua resposta. "
            "Nossa equipe de atendimento pode te ajudar diretamente."
        )

    # ── Step 5: Update conversation history ───────────────────────────────────
    messages.append({"role": "assistant", "content": response_text})
    context["response_text"] = response_text
    context["response_source"] = "llm"

    logger.info("response_node: response generated (%d chars)", len(response_text))

    return ClinicStateUpdate(messages=messages, context=context)
