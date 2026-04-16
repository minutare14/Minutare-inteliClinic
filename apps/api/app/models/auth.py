"""
Auth models — Users and RBAC roles.

One deploy = one clinic. Users are clinic staff with role-based access.
Passwords are bcrypt-hashed, never stored in plain text.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from sqlmodel import Field, SQLModel


class UserRole(str, Enum):
    admin = "admin"                   # Full access — clinic owner/manager
    manager = "manager"               # Operational management, no destructive actions
    reception = "reception"           # Scheduling, patients, conversations
    handoff_operator = "handoff_operator"  # Handoff queue only


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    email: str = Field(unique=True, index=True, max_length=255)
    full_name: str = Field(max_length=255)
    hashed_password: str = Field(max_length=255)
    role: UserRole = Field(default=UserRole.reception)
    active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_login_at: datetime | None = Field(default=None)
