"""Response validation pipeline — orchestrates all safety layers.

Validation order:
    1. InjectionGuard (input)  — block before any processing
    2. PolicyRegistry          — evaluate business rules
    3. MedicalSafetyGuard (output) — validate final response
    4. ConfidenceGuard         — force fallback on low confidence

Usage:
    validator = ResponseValidator.default()

    # Validate incoming message
    input_result = await validator.validate_input(patient_message)
    if input_result.is_blocked:
        return input_result.corrected_output

    # ... generate AI response ...

    # Validate outgoing response
    output_result = await validator.validate_output(ai_response, state)
    if output_result.is_blocked:
        return output_result.corrected_output
    if output_result.needs_escalation:
        trigger_human_handoff()
"""
from __future__ import annotations

import logging

from ..guards.output_guards import (
    ConfidenceGuard,
    GuardResult,
    InjectionGuard,
    MedicalSafetyGuard,
)
from ..policies.medical_policies import PolicyRegistry

logger = logging.getLogger(__name__)


class ResponseValidator:
    """Orchestrates the full validation cycle for InteliClinic.

    Combines:
    - Input guards (injection detection)
    - Policy evaluation (business rules)
    - Output guards (medical safety, confidence)
    """

    def __init__(
        self,
        injection_guard: InjectionGuard,
        medical_guard: MedicalSafetyGuard,
        confidence_guard: ConfidenceGuard,
        policy_registry: PolicyRegistry,
    ):
        self.injection_guard = injection_guard
        self.medical_guard = medical_guard
        self.confidence_guard = confidence_guard
        self.policy_registry = policy_registry

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def validate_input(self, message: str) -> GuardResult:
        """Validate an incoming patient message.

        Checks for injection attempts before any AI processing.
        """
        result = await self.injection_guard.validate(message)
        if not result.passed:
            logger.warning("Input blocked by %s: %s", result.guard_name, result.violations)
        return result

    async def validate_output(
        self,
        response: str,
        state: dict,
    ) -> GuardResult:
        """Validate an outgoing AI-generated response.

        Checks:
        1. Policy registry (CFM, urgency, LGPD)
        2. MedicalSafetyGuard (diagnosis/medication patterns)
        3. ConfidenceGuard (confidence threshold)
        """
        intent = state.get("current_intent", "")
        confidence = state.get("confidence", 1.0)
        safety_flags = state.get("safety_flags", [])

        # 1. Policy evaluation
        policy_results = self.policy_registry.evaluate_all(
            intent=intent,
            content=response,
            context=state,
        )
        if self.policy_registry.is_blocked(policy_results):
            reason = self.policy_registry.get_block_reason(policy_results)
            return GuardResult(
                passed=False,
                violations=[reason or "policy_block"],
                action="block",
                corrected_output=reason,
                guard_name="policy_registry",
            )
        if self.policy_registry.requires_escalation(policy_results):
            reason = self.policy_registry.get_escalation_reason(policy_results)
            return GuardResult(
                passed=True,
                violations=[],
                action="escalate",
                corrected_output=reason,
                guard_name="policy_registry",
            )

        # 2. Medical safety guard
        context = {"is_outbound": True, "safety_flags": safety_flags}
        medical_result = await self.medical_guard.validate(response, context)
        if not medical_result.passed or medical_result.needs_escalation:
            return medical_result

        # 3. Confidence guard
        confidence_result = await self.confidence_guard.validate(response, confidence, context)
        if not confidence_result.passed:
            return confidence_result

        return GuardResult(passed=True, action="pass", guard_name="response_validator")

    async def validate_full_cycle(
        self,
        input_message: str,
        response: str,
        state: dict,
    ) -> tuple[GuardResult, GuardResult]:
        """Run the complete input → output validation cycle.

        Returns:
            Tuple of (input_result, output_result).
            If input is blocked, output_result mirrors input_result.
        """
        input_result = await self.validate_input(input_message)
        if not input_result.passed:
            return input_result, input_result

        output_result = await self.validate_output(response, state)
        return input_result, output_result

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def default(cls) -> "ResponseValidator":
        """Create a validator with all default safety layers active."""
        return cls(
            injection_guard=InjectionGuard(),
            medical_guard=MedicalSafetyGuard(),
            confidence_guard=ConfidenceGuard(min_confidence=0.55),
            policy_registry=PolicyRegistry.default(),
        )

    @classmethod
    def from_config(cls, config: dict) -> "ResponseValidator":
        """Build validator from clinic configuration.

        config keys:
            min_confidence: float (default 0.55)
            extra_policies: list of policy class names to register
        """
        registry = PolicyRegistry.default()
        # Per-clinic policies loaded from clinic/policies/ at deploy time
        return cls(
            injection_guard=InjectionGuard(),
            medical_guard=MedicalSafetyGuard(),
            confidence_guard=ConfidenceGuard(
                min_confidence=config.get("min_confidence", 0.55)
            ),
            policy_registry=registry,
        )
