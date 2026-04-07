"""Clinic seed data — initial data for first deploy setup.

Contains seed scripts and data files for:
    - Professionals (name, CRM, specialty, schedule)
    - Schedule slots (initial availability)
    - Insurance plans accepted
    - Initial patients (for testing)
    - RAG documents to ingest on first run

These seeds are one-time setup artifacts.
After the first deploy, data is managed via the operational API.

How to run seeds:
    python scripts/seed_data.py --clinic-config clinic.yaml

See docs/clinic-onboarding/new-clinic.md for full onboarding steps.
"""
