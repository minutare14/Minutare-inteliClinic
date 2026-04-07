"""Financial node — handles price, payment method, and billing queries.

Processes the 'financial' intent.

Responsibilities:
- Look up pricing for procedures/specialties from RAG or configured price tables.
- Explain payment methods accepted (card, PIX, boleto, installments).
- Compare private (particular) vs. insurance (convênio) costs when relevant.
- Never quote definitive prices without a disclaimer — prices may vary.
- Surface installment options when total cost is high.
"""

from __future__ import annotations

import logging
from typing import Any

from inteliclinic.core.ai_engine.state.clinic_state import ClinicState, ClinicStateUpdate

logger = logging.getLogger(__name__)

# Default payment methods — overridden per clinic via config/context
_DEFAULT_PAYMENT_METHODS = [
    "Cartão de crédito (até 12x sem juros)",
    "Cartão de débito",
    "PIX",
    "Dinheiro",
    "Boleto bancário",
]

_INSTALLMENT_THRESHOLD_BRL = 300.0
"""Above this value, installment information is automatically included in the response."""


def _extract_financial_params(extracted_data: dict[str, Any]) -> dict[str, Any]:
    """Extract financial query parameters from NLU extraction output."""
    return {
        "specialty": extracted_data.get("desired_specialty"),
        "professional": extracted_data.get("desired_professional"),
        "insurance_plan": extracted_data.get("insurance_plan"),
        "original_text": extracted_data.get("original_text", ""),
    }


async def _query_pricing_from_rag(
    specialty: str | None,
    insurance_plan: str | None,
    rag_results: list[dict[str, Any]],
) -> dict[str, Any]:
    """Extract pricing information from RAG results.

    Searches for entries related to the requested specialty and payment modality.

    Returns a dict with:
        found: bool
        private_price_brl: float | None
        insurance_copay_brl: float | None
        price_range: str | None  — textual range when exact price is unavailable
        excerpts: list[str]
    """
    if not specialty:
        return {"found": False, "private_price_brl": None, "insurance_copay_brl": None,
                "price_range": None, "excerpts": []}

    specialty_lower = specialty.lower()
    relevant = [
        r for r in rag_results
        if specialty_lower in r.get("content", "").lower()
        and any(kw in r.get("content", "").lower() for kw in
                ["preço", "valor", "consulta", "particular", "convênio", "r$", "reais"])
    ]

    if not relevant:
        return {"found": False, "private_price_brl": None, "insurance_copay_brl": None,
                "price_range": None, "excerpts": []}

    sorted_r = sorted(relevant, key=lambda x: x.get("score", 0.0), reverse=True)[:3]
    excerpts = [r["content"] for r in sorted_r]

    # Attempt to parse a price from the text (simplified regex-free heuristic)
    # Real implementation would use a structured price table.
    private_price: float | None = None
    copay: float | None = None

    for excerpt in excerpts:
        tokens = excerpt.lower().replace("r$", "").split()
        for i, token in enumerate(tokens):
            try:
                value = float(token.replace(",", "."))
                if 20 <= value <= 10000:  # plausible medical price range in BRL
                    if "particular" in " ".join(tokens[max(0, i-5):i+5]):
                        private_price = private_price or value
                    elif "convênio" in " ".join(tokens[max(0, i-5):i+5]) or "copag" in " ".join(tokens[max(0, i-5):i+5]):
                        copay = copay or value
                    else:
                        private_price = private_price or value
            except ValueError:
                continue

    return {
        "found": True,
        "private_price_brl": private_price,
        "insurance_copay_brl": copay,
        "price_range": None if private_price else "consulte a recepção para valores atualizados",
        "excerpts": excerpts,
    }


def _build_payment_summary(
    pricing: dict[str, Any],
    insurance_plan: str | None,
    payment_methods: list[str],
) -> str:
    """Compose a human-readable payment summary for the response node to use."""
    lines: list[str] = []

    if pricing.get("found"):
        if pricing.get("private_price_brl"):
            lines.append(f"Valor particular: R$ {pricing['private_price_brl']:.2f}")
        if insurance_plan and pricing.get("insurance_copay_brl"):
            lines.append(f"Copagamento ({insurance_plan}): R$ {pricing['insurance_copay_brl']:.2f}")
        elif insurance_plan:
            lines.append(f"Para o plano {insurance_plan}, o valor pode variar. Confirme com nossa equipe.")
        if pricing.get("price_range"):
            lines.append(f"Referência de preço: {pricing['price_range']}")
    else:
        lines.append("Não localizamos o valor exato em nossa base. Nossa equipe pode informar o preço atualizado.")

    lines.append("\nFormas de pagamento aceitas:")
    lines.extend(f"  • {method}" for method in payment_methods)

    private_price = pricing.get("private_price_brl", 0) or 0
    if private_price >= _INSTALLMENT_THRESHOLD_BRL:
        lines.append(
            f"\nConsultas acima de R$ {_INSTALLMENT_THRESHOLD_BRL:.0f} podem ser parceladas em até 12x "
            "no cartão de crédito sem juros. Consulte nossa recepção."
        )

    return "\n".join(lines)


async def financial_node(state: ClinicState) -> ClinicStateUpdate:
    """LangGraph node — answers financial/pricing queries.

    Args:
        state: Current ClinicState.

    Returns:
        ClinicStateUpdate with context['financial'] containing pricing info,
        payment methods, and a price disclaimer.

    Behavior:
        - Queries RAG for specialty pricing.
        - Builds comparison between private and insurance costs when applicable.
        - Always appends disclaimer about price variability.
        - Surfaces installment options when total cost exceeds threshold.
    """
    extracted_data: dict[str, Any] = state.get("extracted_data", {})
    rag_results: list[dict[str, Any]] = state.get("rag_results", [])
    context: dict[str, Any] = dict(state.get("context", {}))

    params = _extract_financial_params(extracted_data)

    logger.info(
        "financial_node: specialty=%s | insurance=%s | rag_count=%d",
        params["specialty"],
        params["insurance_plan"],
        len(rag_results),
    )

    # ── Retrieve pricing from RAG ──────────────────────────────────────────────
    pricing = await _query_pricing_from_rag(
        params["specialty"],
        params["insurance_plan"],
        rag_results,
    )

    # Per-clinic payment methods (could be loaded from clinic config in the future)
    payment_methods = _DEFAULT_PAYMENT_METHODS

    # ── Compose summary ────────────────────────────────────────────────────────
    payment_summary = _build_payment_summary(pricing, params["insurance_plan"], payment_methods)

    context["financial"] = {
        "specialty": params["specialty"],
        "insurance_plan": params["insurance_plan"],
        "pricing": pricing,
        "payment_methods": payment_methods,
        "payment_summary": payment_summary,
        "disclaimer": (
            "Os valores informados são de referência e podem ser alterados sem aviso prévio. "
            "Confirme o valor final com nossa equipe de atendimento antes de agendar."
        ),
    }

    return ClinicStateUpdate(context=context)
