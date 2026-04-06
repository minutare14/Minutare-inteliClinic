from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class AuditEventRead(BaseModel):
    id: uuid.UUID
    actor_type: str
    actor_id: str
    action: str
    resource_type: str
    resource_id: str
    payload: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
