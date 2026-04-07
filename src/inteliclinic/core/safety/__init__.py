"""Safety module — hybrid validation layer.

Combines three complementary layers:

1. Guardrails AI (structural validation)
   Validates output format, required fields, and basic content rules.
   Reference: https://github.com/guardrails-ai/guardrails

2. Business rules (medical ethics / CFM compliance)
   Hard rules derived from CFM 2.454/2022 (Telemedicina) and related
   Brazilian regulations. These are NOT delegated to Guardrails AI.

3. Policy validators (per-clinic operational constraints)
   Configurable policies that vary by clinic deploy (e.g. allowed topics,
   working hours for automated responses, escalation thresholds).

Architecture principle:
    Guardrails AI handles STRUCTURE.
    Business rules handle ETHICS.
    Policy validators handle OPERATIONS.

    Never rely on a single layer alone.
"""

from .guards.output_guards import GuardResult, InjectionGuard, MedicalSafetyGuard
from .policies.medical_policies import CFMPolicy, PolicyRegistry, UrgencyPolicy
from .validators.response_validator import ResponseValidator

__all__ = [
    "GuardResult",
    "InjectionGuard",
    "MedicalSafetyGuard",
    "CFMPolicy",
    "UrgencyPolicy",
    "PolicyRegistry",
    "ResponseValidator",
]
