"""
Guardrails — Safety and governance layer for AI responses.

Adapted from existing app/ai/guardrails.py + minutare.ai safety rules.
Enforces CFM 2.454/2026 + LGPD compliance:
- No diagnosis or clinical advice
- Urgency detection → SAMU referral
- Clinical question detection → disclaimer
- Low confidence → handoff
- Consent validation
"""
from __future__ import annotations

import re
import logging
from dataclasses import dataclass
from enum import Enum

from app.core.config import settings

logger = logging.getLogger(__name__)


class GuardrailAction(str, Enum):
    ALLOW = "allow"
    ADD_DISCLAIMER = "add_disclaimer"
    FORCE_HANDOFF = "force_handoff"
    BLOCK = "block"


@dataclass
class GuardrailResult:
    """Result of guardrail evaluation."""
    action: GuardrailAction
    modified_response: str
    reason: str | None = None
    urgency_detected: bool = False
    clinical_detected: bool = False


# ─── Keyword patterns ──────────────────────────────────────────

CLINICAL_KEYWORDS = [
    r"\bdiagn[oó]stico\w*\b", r"\btratamento\w*\b",
    r"\bmedicamento\w*\b", r"\brem[eé]dio\w*\b", r"\bprescri[cç][aã]o\w*\b",
    r"\bdose\w*\b", r"\bdosagem\b", r"\bsintoma\w*\b",
    r"\bdoen[cç]a\w*\b", r"\binfec[cç][aã]o\w*\b",
    r"\bcirurgia\w*\b", r"\bopera[cç][aã]o\w*\b",
    r"\bexame\s+de\s+sangue\b", r"\bresultado\w*\s+de\s+exame\b",
    r"\blaud[oa]\w*\b",
]

URGENCY_KEYWORDS = [
    r"\bdor\s+(?:no\s+)?peito\b", r"\bfalta\s+de\s+ar\b",
    r"\bsangramento\b", r"\bdesmai\w*\b",
    r"\bconvuls[aã]o\w*\b", r"\bemerg[eê]ncia\w*\b",
    r"\burgente\b", r"\burg[eê]ncia\b",
    r"\binfart[oa]\w*\b", r"\bavc\b", r"\bderrame\b",
    r"\btentativa\s+de\s+suic[ií]dio\b", r"\bsuic[ií]dio\b",
    r"\benvenenamento\b", r"\bintoxica[cç][aã]o\b",
]

PROMPT_INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"esqueça\s+as\s+instruções",
    r"ignore\s+as\s+regras",
    r"finja\s+que\s+você\s+é",
    r"você\s+agora\s+é",
    r"system\s*prompt",
    r"reveal\s+your\s+(system\s+)?prompt",
]

# ─── Static messages ──────────────────────────────────────────

DISCLAIMER_PT = (
    "⚠️ Sou um assistente virtual da clínica e posso ajudar com "
    "informações administrativas e operacionais. Para questões clínicas, "
    "consulte diretamente seu médico."
)

URGENCY_MESSAGE = (
    "🚨 Se você está em uma situação de emergência médica, "
    "ligue imediatamente para o SAMU (192) ou dirija-se ao "
    "pronto-socorro mais próximo."
)

HANDOFF_LOW_CONFIDENCE = (
    "Compreendo que esta é uma questão importante. Para garantir a melhor "
    "resposta, estou encaminhando você para nossa equipe de atendimento."
)

PROMPT_INJECTION_RESPONSE = (
    "Desculpe, não posso processar essa solicitação. "
    "Posso ajudar com agendamentos, dúvidas sobre a clínica "
    "ou encaminhar para um atendente."
)


# ─── Detection functions ──────────────────────────────────────


def detect_urgency(text: str) -> bool:
    """Detect potential medical urgency keywords."""
    text_lower = text.lower()
    return any(re.search(p, text_lower) for p in URGENCY_KEYWORDS)


def detect_clinical_question(text: str) -> bool:
    """Detect if user is asking a clinical (not administrative) question."""
    text_lower = text.lower()
    return any(re.search(p, text_lower) for p in CLINICAL_KEYWORDS)


def detect_prompt_injection(text: str) -> bool:
    """Detect prompt injection attempts."""
    text_lower = text.lower()
    return any(re.search(p, text_lower) for p in PROMPT_INJECTION_PATTERNS)


_DEFAULT_HANDOFF_THRESHOLD = 0.55  # fallback quando DB não tem config


def needs_handoff(confidence: float, threshold: float | None = None) -> bool:
    """Check if confidence is below the handoff threshold.

    Uses the explicit threshold when provided (loaded from clinic_settings).
    Falls back to 0.55 default (not rag_confidence_threshold — those are different concepts).
    """
    effective_threshold = threshold if threshold is not None else _DEFAULT_HANDOFF_THRESHOLD
    return confidence < effective_threshold


# ─── Main guardrail evaluation ─────────────────────────────────


def evaluate(
    user_text: str,
    ai_response: str,
    confidence: float,
    consented_ai: bool = True,
    handoff_enabled: bool = True,
    handoff_confidence_threshold: float | None = None,
    clinical_questions_block: bool = True,
) -> GuardrailResult:
    """
    Evaluate AI response through all guardrail layers.

    Order of checks (highest priority first):
    1. Prompt injection → block
    2. No AI consent → force handoff (if handoff_enabled)
    3. Urgency → prepend warning + allow
    4. Clinical question → add disclaimer (if clinical_questions_block)
    5. Low confidence → force handoff (if handoff_enabled)
    6. Otherwise → allow
    """
    # 1. Prompt injection (always enforced regardless of settings)
    if detect_prompt_injection(user_text):
        logger.warning("Prompt injection detected: %s", user_text[:80])
        return GuardrailResult(
            action=GuardrailAction.BLOCK,
            modified_response=PROMPT_INJECTION_RESPONSE,
            reason="prompt_injection",
        )

    # 2. AI consent check
    if not consented_ai:
        if handoff_enabled:
            return GuardrailResult(
                action=GuardrailAction.FORCE_HANDOFF,
                modified_response=(
                    "Para garantir o melhor atendimento, estou encaminhando "
                    "você para nossa equipe. Um momento, por favor."
                ),
                reason="no_ai_consent",
            )
        return GuardrailResult(
            action=GuardrailAction.ADD_DISCLAIMER,
            modified_response="Para usar o assistente, precisamos do seu consentimento. Por favor, confirme que aceita o atendimento via IA.",
            reason="no_ai_consent",
        )

    # 3. Urgency detection (always enforced — patient safety)
    urgency = detect_urgency(user_text)
    if urgency:
        return GuardrailResult(
            action=GuardrailAction.ADD_DISCLAIMER,
            modified_response=f"{URGENCY_MESSAGE}\n\n{ai_response}",
            reason="urgency_detected",
            urgency_detected=True,
        )

    # 4. Clinical question — respects clinical_questions_block config
    clinical = detect_clinical_question(user_text)
    if clinical and clinical_questions_block:
        return GuardrailResult(
            action=GuardrailAction.ADD_DISCLAIMER,
            modified_response=f"{DISCLAIMER_PT}\n\n{ai_response}",
            reason="clinical_question",
            clinical_detected=True,
        )

    # 5. Low confidence — respects handoff_enabled and configurable threshold
    if handoff_enabled and needs_handoff(confidence, handoff_confidence_threshold):
        return GuardrailResult(
            action=GuardrailAction.FORCE_HANDOFF,
            modified_response=HANDOFF_LOW_CONFIDENCE,
            reason="low_confidence",
        )

    # 6. All clear
    return GuardrailResult(
        action=GuardrailAction.ALLOW,
        modified_response=ai_response,
    )
