"""Per-clinic operational policies — extend core safety policies.

Core policies (always active, not overridable):
    CFMPolicy, UrgencyPolicy, DataPrivacyPolicy → core/safety/policies/

Per-clinic policies (configured here):
    - Topic restrictions (e.g. don't discuss competitor clinics)
    - Business hours enforcement for automated responses
    - Specific escalation triggers for this clinic
    - Approved responses for common local questions

How to add a clinic policy:
    1. Create a class inheriting from core.safety.policies.medical_policies.BasePolicy
    2. Register it in your clinic startup code:
        registry = PolicyRegistry.default()
        registry.register(MyClinicPolicy())
"""
