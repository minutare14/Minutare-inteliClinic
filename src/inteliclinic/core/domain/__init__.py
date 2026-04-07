"""Domain models — ORM models, repositories, and domain schemas.

The existing SQLModel models in apps/api/app/models/ are the canonical
implementation. This package provides the new home for those models
as the project migrates to the src/inteliclinic/ structure.

Current models (from apps/api/app/models/):
    Patient, Professional, ScheduleSlot
    Conversation, Message, Handoff
    AuditEvent, RagDocument, RagChunk

Migration path:
    Phase 1: models remain in apps/api/app/models/ (backwards compatible)
    Phase 2: move here and update imports throughout

Imports from this package will eventually supersede apps/api/app/models/.
"""
