"""Guards for input validation and output safety.

Implements:
- InjectionGuard: blocks prompt injection via patient messages
- MedicalSafetyGuard: prevents diagnosis, medication recommendations
- ConfidenceGuard: forces fallback when AI confidence is too low

Integration with Guardrails AI:
    Guardrails AI (https://github.com/guardrails-ai/guardrails) can be used
    as an additional validation layer on top of these guards.
    To integrate, wrap the guard output in a guardrails.Guard pipeline.

    Example:
        import guardrails as gd
        guard = gd.Guard.from_pydantic(output_class=StructuredResponse)
        validated = guard.parse(llm_output)
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class GuardResult:
    """Result from a guard validation check."""

    passed: bool
    violations: list[str] = field(default_factory=list)
    corrected_output: str | None = None
    action: str = "pass"  # "pass" | "block" | "correct" | "escalate"
    guard_name: str = ""

    @property
    def is_blocked(self) -> bool:
        return self.action == "block"

    @property
    def needs_escalation(self) -> bool:
        return self.action == "escalate"


class InjectionGuard:
    """Prevents prompt injection attacks via patient messages.

    Detects attempts to override system instructions, change persona,
    or inject malicious content through the patient-facing chat channel.
    """

    name = "injection_guard"

    INJECTION_PATTERNS = [
        r"ignore (previous|all|the above|instructions)",
        r"system\s*prompt",
        r"você é agora",
        r"novo (sistema|assistente|persona|modo)",
        r"<\s*script[\s>]",
        r"jailbreak",
        r"DAN\s*mode",
        r"ignore\s+todas",
        r"\[INST\]",
        r"</s>",
        r"assistant:\s*",  # Trying to inject an assistant turn
    ]

    async def validate(self, message: str) -> GuardResult:
        """Validate an incoming patient message for injection attempts."""
        for pattern in self.INJECTION_PATTERNS:
            if re.search(pattern, message, re.IGNORECASE):
                logger.warning("Injection attempt detected — pattern: %s", pattern)
                return GuardResult(
                    passed=False,
                    violations=[f"injection_pattern: '{pattern}'"],
                    action="block",
                    corrected_output="Não consigo processar essa mensagem. Como posso ajudá-lo com seu agendamento?",
                    guard_name=self.name,
                )
        return GuardResult(passed=True, action="pass", guard_name=self.name)


class MedicalSafetyGuard:
    """Validates AI responses against CFM 2.454/2022 medical safety rules.

    Hard rules — no exceptions:
    - Never provide diagnosis or clinical assessment
    - Never recommend specific medications or dosages
    - Always recommend professional consultation for clinical questions
    - Detect and escalate urgency/emergency signals

    This guard is applied to OUTBOUND responses (after LLM generation).
    """

    name = "medical_safety_guard"

    DIAGNOSIS_PATTERNS = [
        r"você (tem|está com|sofre de|apresenta)\s+\w+",
        r"seu (diagnóstico|problema|caso|quadro) é",
        r"parece (ser|que é|que você tem)\s+\w+(ite|ose|ismo|emia|algia)",
        r"isso indica\s+\w+",
        r"sintomas de\s+\w+(ite|ose|ismo)",
    ]

    MEDICATION_PATTERNS = [
        r"tome\s+\w+",
        r"use\s+\d+\s*mg",
        r"(dipirona|ibuprofeno|paracetamol|amoxicilina|omeprazol|losartana)\b",
        r"comprimido[s]?\s+de\s+\w+",
        r"medicamento[s]?\s+para\s+\w+",
    ]

    URGENCY_PATTERNS = [
        r"dor no peito",
        r"falta de ar",
        r"perda de consciência",
        r"sangramento intenso",
        r"acidente vascular",
        r"derrame",
        r"\binfarto\b",
        r"avc\b",
        r"convuls[aã]o",
        r"desmaio",
        r"vômito (de sangue|com sangue)",
    ]

    SAFE_FALLBACK = (
        "Não posso fornecer informações médicas diagnósticas ou prescrições. "
        "Para questões clínicas, consulte nosso corpo médico. "
        "Posso ajudar com agendamentos, convênios e informações administrativas."
    )

    async def validate(self, response: str, context: dict | None = None) -> GuardResult:
        """Validate an outbound AI response."""
        violations: list[str] = []
        response_lower = response.lower()

        for pattern in self.DIAGNOSIS_PATTERNS:
            if re.search(pattern, response_lower):
                violations.append(f"diagnosis_attempt: '{pattern}'")

        for pattern in self.MEDICATION_PATTERNS:
            if re.search(pattern, response_lower):
                violations.append(f"medication_recommendation: '{pattern}'")

        urgency_detected = any(
            re.search(p, response_lower) for p in self.URGENCY_PATTERNS
        )

        if violations:
            logger.warning(
                "MedicalSafetyGuard blocked response — violations: %s", violations
            )
            return GuardResult(
                passed=False,
                violations=violations,
                action="block",
                corrected_output=self.SAFE_FALLBACK,
                guard_name=self.name,
            )

        # Urgency in response → escalate, but don't block
        if urgency_detected and context and context.get("is_outbound"):
            return GuardResult(
                passed=True,
                violations=["urgency_signal_in_response"],
                action="escalate",
                guard_name=self.name,
            )

        return GuardResult(passed=True, action="pass", guard_name=self.name)


class ConfidenceGuard:
    """Forces a safe fallback response when AI confidence is too low."""

    name = "confidence_guard"

    def __init__(self, min_confidence: float = 0.55):
        self.min_confidence = min_confidence

    async def validate(self, response: str, confidence: float, context: dict | None = None) -> GuardResult:
        if confidence < self.min_confidence:
            logger.info(
                "ConfidenceGuard triggered — confidence %.2f < %.2f",
                confidence,
                self.min_confidence,
            )
            return GuardResult(
                passed=False,
                violations=[f"low_confidence: {confidence:.2f}"],
                action="block",
                corrected_output=(
                    "Não tenho certeza suficiente para responder a isso. "
                    "Vou transferir para um de nossos atendentes. "
                    "Aguarde um momento."
                ),
                guard_name=self.name,
            )
        return GuardResult(passed=True, action="pass", guard_name=self.name)
