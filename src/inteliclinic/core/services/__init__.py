"""Core services — business logic layer.

Existing service implementations live in apps/api/app/services/.
This package is the new home as the project migrates to src/inteliclinic/.

Services:
    PatientService, ProfessionalService
    ScheduleService, ConversationService
    RAGService, AuditService, HandoffService, TelegramService

All services follow the pattern:
    - Accept a database session (async SQLAlchemy)
    - Delegate data access to repositories in core/domain/
    - Contain business logic only (no HTTP, no LLM calls)
"""
