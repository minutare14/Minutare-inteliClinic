"""Clinic layer — everything that changes per deploy.

This package contains ONLY per-clinic configuration, assets, and data.
It contains NO core product logic.

What lives here:
    config/     Clinic identity, credentials, enabled features
    branding/   Name, logo, colors, tone of voice
    prompts/    Complementary prompts (appended to core system prompts)
    knowledge/  Local documents indexed into this clinic's RAG
    policies/   Per-clinic operational policies (extends core safety policies)
    seeds/      Initial data: professionals, schedules, patients (for first deploy)

What does NOT live here:
    - AI engine logic (→ core/ai_engine/)
    - RAG infrastructure (→ core/rag/)
    - Safety rules (→ core/safety/)
    - Analytics models (→ core/analytics/)
    - API routes (→ api/)

Deployment rule:
    "Nova clínica = novo deploy da mesma base, com nova configuração local.
     Não é permitido criar uma nova base de código por cliente."
"""
