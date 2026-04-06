from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.patient import Patient
from app.repositories.patient_repository import PatientRepository
from app.schemas.patient import PatientCreate, PatientUpdate
from app.services.audit_service import AuditService


class PatientService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = PatientRepository(session)
        self.audit = AuditService(session)

    async def create_patient(self, data: PatientCreate) -> Patient:
        patient = await self.repo.create(data)
        await self.audit.log_event(
            actor_type="system",
            actor_id="patient_service",
            action="patient.created",
            resource_type="patient",
            resource_id=str(patient.id),
        )
        return patient

    async def get_patient(self, patient_id: uuid.UUID) -> Patient | None:
        return await self.repo.get_by_id(patient_id)

    async def list_patients(self, limit: int = 100, offset: int = 0) -> list[Patient]:
        return await self.repo.list_all(limit=limit, offset=offset)

    async def get_by_telegram(self, telegram_user_id: str) -> Patient | None:
        return await self.repo.get_by_telegram_user_id(telegram_user_id)

    async def get_or_create_from_telegram(
        self, telegram_user_id: str, telegram_chat_id: str, first_name: str
    ) -> Patient:
        """Find patient by Telegram user ID, or create a stub record."""
        patient = await self.repo.get_by_telegram_user_id(telegram_user_id)
        if patient:
            return patient
        data = PatientCreate(
            full_name=first_name,
            telegram_user_id=telegram_user_id,
            telegram_chat_id=telegram_chat_id,
            preferred_channel="telegram",
        )
        return await self.create_patient(data)

    async def update_patient(self, patient_id: uuid.UUID, data: PatientUpdate) -> Patient | None:
        patient = await self.repo.update(patient_id, data)
        if patient:
            await self.audit.log_event(
                actor_type="system",
                actor_id="patient_service",
                action="patient.updated",
                resource_type="patient",
                resource_id=str(patient.id),
            )
        return patient
