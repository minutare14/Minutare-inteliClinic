"""Insurance node — handles health insurance (convênio) coverage and authorization queries.

Processes the 'insurance' intent.

Responsibilities:
- Extract insurance plan name and requested procedure/specialty from extracted_data.
- Query the RAG (vector store) for coverage information for the given plan.
- Synthesize a coverage summary into context['insurance'].
- Flag cases where authorization (guia) is required before scheduling.
- Never make definitive coverage promises — always direct patient to confirm with insurer.
"""

from __future__ import annotations

import logging
from typing import Any

from inteliclinic.core.ai_engine.state.clinic_state import ClinicState, ClinicStateUpdate

logger = logging.getLogger(__name__)


async def _query_rag_for_insurance(
    insurance_plan: str,
    specialty: str | None,
    rag_results: list[dict[str, Any]],
) -> dict[str, Any]:
    """Search existing RAG results for insurance coverage data.

    In a deployed clinic, this would be pre-populated by the RAG retrieval node
    that runs before intent-specific nodes. Here we parse whatever rag_results
    are already in the state and filter for insurance-related content.

    Args:
        insurance_plan: Name of the insurance plan to look up.
        specialty: Optional specialty being requested.
        rag_results: RAG results already fetched and stored in ClinicState.

    Returns:
        Dict with coverage summary, authorization_required flag, and source references.
    """
    # Filter RAG results that are relevant to the insurance plan
    plan_lower = insurance_plan.lower()
    specialty_lower = (specialty or "").lower()

    relevant = [
        r for r in rag_results
        if plan_lower in r.get("content", "").lower()
        or plan_lower in str(r.get("metadata", {})).lower()
        or (specialty_lower and specialty_lower in r.get("content", "").lower())
    ]

    if relevant:
        # Aggregate content from the most relevant results (top 3 by score)
        sorted_results = sorted(relevant, key=lambda x: x.get("score", 0.0), reverse=True)[:3]
        coverage_excerpts = [r["content"] for r in sorted_results]
        sources = [r.get("source", "base de conhecimento") for r in sorted_results]
        return {
            "found": True,
            "insurance_plan": insurance_plan,
            "specialty": specialty,
            "coverage_excerpts": coverage_excerpts,
            "sources": list(set(sources)),
            "authorization_required": _infer_authorization_required(coverage_excerpts, specialty),
        }

    # No RAG results found for this plan
    return {
        "found": False,
        "insurance_plan": insurance_plan,
        "specialty": specialty,
        "coverage_excerpts": [],
        "sources": [],
        "authorization_required": None,  # Unknown — patient must verify with insurer
    }


def _infer_authorization_required(excerpts: list[str], specialty: str | None) -> bool | None:
    """Heuristically determine if authorization (guia) is required.

    Returns True if authorization keywords are found, False if explicitly not required,
    or None when the information is inconclusive.
    """
    combined = " ".join(excerpts).lower()
    requires_keywords = {"guia", "autorização", "autorizar", "pré-autorização", "solicitação prévia"}
    not_requires_keywords = {"sem necessidade de guia", "não exige autorização", "atendimento direto"}

    if any(kw in combined for kw in not_requires_keywords):
        return False
    if any(kw in combined for kw in requires_keywords):
        return True
    return None


def _build_disclaimer() -> str:
    """Return the standard insurance disclaimer to append to all coverage responses."""
    return (
        "As informações acima são baseadas nos dados disponíveis em nosso sistema e podem "
        "estar desatualizadas. Recomendamos confirmar a cobertura diretamente com sua operadora "
        "antes de agendar o procedimento."
    )


async def insurance_node(state: ClinicState) -> ClinicStateUpdate:
    """LangGraph node — answers insurance coverage and authorization queries.

    Args:
        state: Current ClinicState.

    Returns:
        ClinicStateUpdate with context['insurance'] populated with coverage data,
        authorization requirements, and the standard disclaimer.

    Behavior:
        - If insurance plan is not mentioned → asks patient to provide it.
        - If RAG has coverage data → returns summarized coverage info.
        - If RAG has no data → returns generic response directing patient to insurer.
        - Always appends disclaimer advising patient to confirm with insurer directly.
    """
    extracted_data: dict[str, Any] = state.get("extracted_data", {})
    rag_results: list[dict[str, Any]] = state.get("rag_results", [])
    context: dict[str, Any] = dict(state.get("context", {}))
    safety_flags: list[str] = list(state.get("safety_flags", []))

    insurance_plan: str | None = extracted_data.get("insurance_plan")
    specialty: str | None = extracted_data.get("desired_specialty")
    original_text: str = extracted_data.get("original_text", "")

    logger.info(
        "insurance_node: plan=%s | specialty=%s | rag_count=%d",
        insurance_plan,
        specialty,
        len(rag_results),
    )

    # ── No insurance plan mentioned ────────────────────────────────────────────
    if not insurance_plan:
        # Try to detect if patient is asking about a specific plan embedded in their message
        # If not extractable, ask which plan they have
        context["insurance"] = {
            "status": "needs_plan_info",
            "message": "Por favor, informe o nome do seu plano de saúde para que eu possa verificar a cobertura.",
            "specialty_requested": specialty,
        }
        return ClinicStateUpdate(context=context)

    # ── Query RAG for coverage data ────────────────────────────────────────────
    coverage_data = await _query_rag_for_insurance(insurance_plan, specialty, rag_results)

    if coverage_data["found"]:
        auth_required = coverage_data.get("authorization_required")
        if auth_required is True:
            auth_message = (
                f"Para {specialty or 'este procedimento'} com o plano {insurance_plan}, "
                "é necessária uma guia de autorização prévia. "
                "Nossa equipe pode solicitar a guia — deseja que eu inicie esse processo?"
            )
        elif auth_required is False:
            auth_message = (
                f"Para {specialty or 'este procedimento'} com o plano {insurance_plan}, "
                "não é necessária guia de autorização prévia. "
                "Você pode agendar diretamente."
            )
        else:
            auth_message = (
                f"Não foi possível determinar automaticamente se o plano {insurance_plan} "
                f"exige guia para {specialty or 'este procedimento'}. "
                "Recomendamos verificar com sua operadora."
            )

        context["insurance"] = {
            "status": "coverage_found",
            "insurance_plan": insurance_plan,
            "specialty": specialty,
            "authorization_required": auth_required,
            "authorization_message": auth_message,
            "coverage_excerpts": coverage_data["coverage_excerpts"],
            "sources": coverage_data["sources"],
            "disclaimer": _build_disclaimer(),
        }
    else:
        # No coverage data in RAG — give generic response
        logger.info("insurance_node: no RAG data found for plan=%s", insurance_plan)
        context["insurance"] = {
            "status": "no_data",
            "insurance_plan": insurance_plan,
            "specialty": specialty,
            "message": (
                f"Não encontramos informações específicas sobre o plano {insurance_plan} "
                f"em nossa base de dados. "
                "Recomendamos entrar em contato com sua operadora para confirmar a cobertura."
            ),
            "disclaimer": _build_disclaimer(),
        }

    # Add safety flag if patient might be expecting a definitive coverage guarantee
    if "definitive_coverage_request" not in safety_flags:
        definitive_keywords = {"cobre", "cobre sim", "está coberto", "tenho cobertura"}
        if any(kw in original_text.lower() for kw in definitive_keywords):
            safety_flags.append("definitive_coverage_request")

    return ClinicStateUpdate(context=context, safety_flags=safety_flags)
