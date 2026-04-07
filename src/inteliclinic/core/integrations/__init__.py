"""External integrations — adapters for third-party services.

All integrations follow the Adapter pattern:
    - Define an abstract interface in this package
    - Implement concrete adapters per provider
    - Swap providers by changing configuration, not code

Current integrations:
    telegram/   Telegram Bot API (primary patient channel)

Planned integrations:
    whatsapp/   WhatsApp Business API (Phase 2)
    voice/      LiveKit Agents for phone channel (Phase 2)
    calendar/   Google Calendar / Outlook sync (Phase 2)
    pms/        Practice Management System integrations (Phase 3)

Integration rule:
    Integration code belongs here in CORE — it's reusable across deploys.
    Per-clinic credentials (tokens, API keys) live in clinic/config/.
"""
