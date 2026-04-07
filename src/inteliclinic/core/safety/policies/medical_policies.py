"""Core medical compliance policies — apply to ALL clinic deploys.

Global rules based on:
- CFM 2.454/2022 (Telemedicina e atendimento mediado por tecnologia)
- CFM 2.217/2018 (Prontuário eletrônico)
- LGPD (Lei 13.709/2018) — data privacy
- ANS regulations for health insurance operations

Per-clinic policies live in src/inteliclinic/clinic/policies/ and may
extend or restrict these, but never override core CFM rules.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class PolicyAction(str, Enum):
    ALLOW = "allow"
    BLOCK = "block"
    ESCALATE = "escalate"
    WARN = "warn"


@dataclass
class PolicyResult:
    action: PolicyAction
    reason: str
    policy_name: str


class BasePolicy:
    """Base class for all policies."""

    name: str = "base_policy"

    def evaluate(self, intent: str, content: str, context: dict) -> PolicyResult:
        raise NotImplementedError


class CFMPolicy(BasePolicy):
    """CFM 2.454/2022 — AI cannot diagnose or prescribe via digital channels.

    This rule is ABSOLUTE and cannot be overridden by per-clinic policies.
    """

    name = "cfm_2454_telemedicina"

    BLOCKED_INTENTS = {
        "diagnosis_request",
        "medication_advice",
        "clinical_protocol_advice",
        "second_opinion",
        "exam_result_interpretation",
    }

    def evaluate(self, intent: str, content: str, context: dict) -> PolicyResult:
        if intent in self.BLOCKED_INTENTS:
            return PolicyResult(
                action=PolicyAction.BLOCK,
                reason=(
                    "CFM 2.454/2022: diagnóstico, prescrição e interpretação de exames "
                    "são exclusivos do médico. A IA não pode realizar essas funções."
                ),
                policy_name=self.name,
            )
        return PolicyResult(action=PolicyAction.ALLOW, reason="ok", policy_name=self.name)


class UrgencyPolicy(BasePolicy):
    """Escalation policy for medical urgency and emergency signals.

    When urgency is detected in the patient's message or state flags,
    immediately escalate to human agent and provide emergency guidance.
    """

    name = "urgency_escalation"

    EMERGENCY_RESPONSE = (
        "⚠️ Detectei uma possível situação de urgência. "
        "Ligue imediatamente para o SAMU (192) ou vá ao pronto-socorro mais próximo. "
        "Estou transferindo para nossa equipe de atendimento agora."
    )

    def evaluate(self, intent: str, content: str, context: dict) -> PolicyResult:
        safety_flags = context.get("safety_flags", [])
        if "urgency_detected" in safety_flags or intent == "urgent":
            return PolicyResult(
                action=PolicyAction.ESCALATE,
                reason=self.EMERGENCY_RESPONSE,
                policy_name=self.name,
            )
        return PolicyResult(action=PolicyAction.ALLOW, reason="ok", policy_name=self.name)


class DataPrivacyPolicy(BasePolicy):
    """LGPD compliance — no PII in logs, no sharing between clinic deploys."""

    name = "lgpd_data_privacy"

    SENSITIVE_FIELDS = {"cpf", "rg", "cartao_sus", "senha", "cartao_credito"}

    def evaluate(self, intent: str, content: str, context: dict) -> PolicyResult:
        content_lower = content.lower()
        for field in self.SENSITIVE_FIELDS:
            if field in content_lower:
                return PolicyResult(
                    action=PolicyAction.WARN,
                    reason=f"LGPD: campo sensível '{field}' detectado na resposta",
                    policy_name=self.name,
                )
        return PolicyResult(action=PolicyAction.ALLOW, reason="ok", policy_name=self.name)


class PolicyRegistry:
    """Registry of all active policies for this deploy.

    Core policies (always active):
        CFMPolicy, UrgencyPolicy, DataPrivacyPolicy

    Per-clinic policies are registered via register() during deploy setup.
    See src/inteliclinic/clinic/policies/ for clinic-specific extensions.
    """

    def __init__(self, include_core: bool = True):
        self._policies: list[BasePolicy] = []
        if include_core:
            self._policies.extend([CFMPolicy(), UrgencyPolicy(), DataPrivacyPolicy()])

    def register(self, policy: BasePolicy) -> None:
        """Add a per-clinic policy to this registry."""
        self._policies.append(policy)
        logger.info("Policy registered: %s", policy.name)

    def evaluate_all(
        self, intent: str, content: str, context: dict
    ) -> list[PolicyResult]:
        """Evaluate all registered policies and return results."""
        return [p.evaluate(intent, content, context) for p in self._policies]

    def is_blocked(self, results: list[PolicyResult]) -> bool:
        return any(r.action == PolicyAction.BLOCK for r in results)

    def requires_escalation(self, results: list[PolicyResult]) -> bool:
        return any(r.action == PolicyAction.ESCALATE for r in results)

    def get_block_reason(self, results: list[PolicyResult]) -> str | None:
        for r in results:
            if r.action == PolicyAction.BLOCK:
                return r.reason
        return None

    def get_escalation_reason(self, results: list[PolicyResult]) -> str | None:
        for r in results:
            if r.action == PolicyAction.ESCALATE:
                return r.reason
        return None

    @classmethod
    def default(cls) -> "PolicyRegistry":
        """Create registry with all core policies enabled."""
        return cls(include_core=True)
