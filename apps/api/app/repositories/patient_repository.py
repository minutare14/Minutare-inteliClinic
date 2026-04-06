from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.patient import Patient
from app.schemas.patient import PatientCreate, PatientUpdate


class PatientRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, data: PatientCreate) -> Patient:
        patient = Patient(**data.model_dump())
        self.session.add(patient)
        await self.session.commit()
        await self.session.refresh(patient)
        return patient

    async def get_by_id(self, patient_id: uuid.UUID) -> Patient | None:
        return await self.session.get(Patient, patient_id)

    async def get_by_telegram_user_id(self, telegram_user_id: str) -> Patient | None:
        stmt = select(Patient).where(Patient.telegram_user_id == telegram_user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_cpf(self, cpf: str) -> Patient | None:
        stmt = select(Patient).where(Patient.cpf == cpf)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update(self, patient_id: uuid.UUID, data: PatientUpdate) -> Patient | None:
        patient = await self.get_by_id(patient_id)
        if not patient:
            return None
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(patient, key, value)
        patient.updated_at = datetime.utcnow()
        self.session.add(patient)
        await self.session.commit()
        await self.session.refresh(patient)
        return patient

    async def list_all(self, limit: int = 100, offset: int = 0) -> list[Patient]:
        stmt = select(Patient).offset(offset).limit(limit).order_by(Patient.created_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
