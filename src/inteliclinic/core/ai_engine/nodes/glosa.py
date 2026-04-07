"""Glosa node — internal billing anomaly detection.

Processes the 'glosa' intent, which is staff/system-initiated (not patient-facing).

A 'glosa' (billing gloss) occurs when a health insurer rejects or reduces payment
for a procedure, citing rule violations. This node analyses the billing data in the
conversation context and returns a risk score with a structured explanation.

Responsibilities:
- Read billing/procedure data from extracted_data and context.
- Integrate with core.analytics.anomaly for risk scoring.
- Return a glosa risk score (0.0–1.0) with explanation and recommended action.
- Flag high-risk cases for human review via safety_flags.

Note: This node is internal — patient messages never route here directly.
"""

from __future__ import annotations

import logging
from typing import Any

from inteliclinic.core.ai_engine.state.clinic_state import ClinicState, ClinicStateUpdate

logger = logging.getLogger(__name__)

# Risk thresholds for glosa classification
_LOW_RISK_THRESHOLD = 0.30
_MEDIUM_RISK_THRESHOLD = 0.60
_HIGH_RISK_THRESHOLD = 0.80


def _risk_label(score: float) -> str:
    """Convert a numeric risk score to a human-readable label."""
    if score >= _HIGH_RISK_THRESHOLD:
        return "alto"
    if score >= _MEDIUM_RISK_THRESHOLD:
        return "médio"
    if score >= _LOW_RISK_THRESHOLD:
        return "baixo"
    return "mínimo"


def _recommended_action(score: float, reasons: list[str]) -> str:
    """Suggest a corrective action based on risk score and detected anomalies."""
    if score >= _HIGH_RISK_THRESHOLD:
        return (
            "Revisar imediatamente com a equipe de faturamento. "
            "Considerar recurso (recurso de glosa) junto à operadora antes do prazo."
        )
    if score >= _MEDIUM_RISK_THRESHOLD:
        return (
            "Verificar documentação de suporte (relatório médico, guia, CID). "
            "Corrigir o lançamento se houver erro de codificação."
        )
    if score >= _LOW_RISK_THRESHOLD:
        return "Monitorar. Garantir que a documentação do procedimento está completa e arquivada."
    return "Risco mínimo detectado. Nenhuma ação imediata necessária."


async def _compute_glosa_risk(billing_data: dict[str, Any]) -> tuple[float, list[str]]:
    """Compute a glosa risk score for the given billing record.

    In production, this delegates to core.analytics.anomaly which uses an ML model
    or rule-based engine trained on historical glosa data.

    Args:
        billing_data: Billing record with procedure codes, insurer, values, etc.

    Returns:
        Tuple of (risk_score: float 0–1, reasons: list[str] explaining the score).
    """
    # Attempt to import the analytics anomaly module (may not be available in all deploys)
    try:
        from inteliclinic.core.analytics.anomaly import compute_anomaly_score  # type: ignore[import]
        score, reasons = await compute_anomaly_score(billing_data)
        return float(score), list(reasons)
    except ImportError:
        logger.debug("glosa_node: core.analytics.anomaly not available — using rule-based fallback")

    # ── Rule-based fallback ────────────────────────────────────────────────────
    # Applies simple heuristic rules that represent common glosa triggers.
    reasons: list[str] = []
    score = 0.0

    procedure_code = str(billing_data.get("procedure_code", ""))
    procedure_value = float(billing_data.get("value_brl", 0.0))
    insurer = str(billing_data.get("insurer", ""))
    has_authorization = billing_data.get("has_prior_authorization", True)
    cid_code = str(billing_data.get("cid_code", ""))
    execution_date = billing_data.get("execution_date")
    submission_date = billing_data.get("submission_date")

    # Rule 1: Missing prior authorization
    if not has_authorization:
        score += 0.35
        reasons.append("Procedimento executado sem guia de autorização prévia registrada.")

    # Rule 2: Missing or invalid CID code
    if not cid_code or len(cid_code) < 3:
        score += 0.20
        reasons.append("CID ausente ou incompleto no lançamento.")

    # Rule 3: Abnormally high procedure value
    expected_cap = 5000.0  # Simplified — real system uses procedure-specific caps
    if procedure_value > expected_cap:
        score += 0.25
        reasons.append(
            f"Valor do procedimento (R$ {procedure_value:.2f}) acima do teto esperado "
            f"(R$ {expected_cap:.2f}) para este código."
        )

    # Rule 4: Submission delay (>30 days from execution)
    if execution_date and submission_date:
        try:
            from datetime import date
            exec_d = date.fromisoformat(str(execution_date))
            sub_d = date.fromisoformat(str(submission_date))
            delay_days = (sub_d - exec_d).days
            if delay_days > 30:
                score += 0.15
                reasons.append(
                    f"Faturamento enviado com {delay_days} dias de atraso após a execução."
                )
        except (ValueError, TypeError):
            pass

    # Rule 5: High-risk insurer pattern (some insurers have stricter rules)
    high_risk_insurers = {"amil", "sulamerica"}
    if insurer.lower() in high_risk_insurers and procedure_value > 1000:
        score += 0.10
        reasons.append(
            f"Operadora {insurer} tem histórico de glosa mais frequente para "
            "procedimentos acima de R$ 1.000."
        )

    # Clamp score to [0, 1]
    score = min(score, 1.0)

    if not reasons:
        reasons.append("Nenhuma anomalia detectada nas regras básicas verificadas.")

    return score, reasons


async def glosa_node(state: ClinicState) -> ClinicStateUpdate:
    """LangGraph node — analyses billing data for glosa risk.

    Args:
        state: Current ClinicState. Expected to have billing_data in context
               or extracted_data when invoked by a billing workflow.

    Returns:
        ClinicStateUpdate with context['glosa'] containing:
            - risk_score: float 0–1
            - risk_label: "mínimo" | "baixo" | "médio" | "alto"
            - reasons: list[str] of anomaly explanations
            - recommended_action: str with corrective steps
            - requires_review: bool (True when score >= medium threshold)
    """
    extracted_data: dict[str, Any] = state.get("extracted_data", {})
    context: dict[str, Any] = dict(state.get("context", {}))
    safety_flags: list[str] = list(state.get("safety_flags", []))

    # Billing data can come from context (set by a billing integration) or extracted_data
    billing_data: dict[str, Any] = context.get("billing_data") or extracted_data.get("billing_data") or {}

    if not billing_data:
        logger.warning("glosa_node: no billing_data in context or extracted_data")
        context["glosa"] = {
            "status": "no_data",
            "message": "Nenhum dado de faturamento disponível para análise de glosa.",
            "risk_score": 0.0,
            "risk_label": "mínimo",
        }
        return ClinicStateUpdate(context=context)

    logger.info(
        "glosa_node: analysing billing record | procedure=%s | insurer=%s",
        billing_data.get("procedure_code"),
        billing_data.get("insurer"),
    )

    # ── Compute risk score ─────────────────────────────────────────────────────
    risk_score, reasons = await _compute_glosa_risk(billing_data)
    label = _risk_label(risk_score)
    action = _recommended_action(risk_score, reasons)
    requires_review = risk_score >= _MEDIUM_RISK_THRESHOLD

    logger.info(
        "glosa_node: risk_score=%.2f | label=%s | requires_review=%s",
        risk_score,
        label,
        requires_review,
    )

    # ── Flag high-risk cases for human review ──────────────────────────────────
    if requires_review and "glosa_risk_review" not in safety_flags:
        safety_flags.append("glosa_risk_review")

    context["glosa"] = {
        "status": "analysed",
        "risk_score": risk_score,
        "risk_label": label,
        "reasons": reasons,
        "recommended_action": action,
        "requires_review": requires_review,
        "billing_data_snapshot": billing_data,
    }

    return ClinicStateUpdate(
        context=context,
        safety_flags=safety_flags,
        confidence=1.0 - risk_score,  # Higher risk → lower system confidence in the record
    )
