"""Tests for Schedule Actions — real DB operations."""
from __future__ import annotations

import sys
import os
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_engine.actions import ScheduleActions
from app.models.schedule import ScheduleSlot, SlotStatus
from app.models.professional import Professional
from app.models.patient import Patient


@pytest.mark.asyncio
class TestSearchSlots:
    async def test_search_by_doctor_name(
        self, session: AsyncSession, sample_professional: Professional, sample_slots
    ):
        actions = ScheduleActions(session)
        result = await actions.search_slots(doctor_name="Carlos")
        assert result.success is True
        assert result.slots is not None
        assert len(result.slots) > 0
        assert "Carlos" in result.slots[0].professional_name

    async def test_search_by_specialty(
        self, session: AsyncSession, sample_professional: Professional, sample_slots
    ):
        actions = ScheduleActions(session)
        result = await actions.search_slots(specialty="Cardiologia")
        assert result.success is True
        assert len(result.slots) > 0

    async def test_search_no_results(self, session: AsyncSession):
        actions = ScheduleActions(session)
        result = await actions.search_slots(doctor_name="NaoExiste")
        assert result.success is False
        assert "Não encontrei" in result.message

    async def test_search_no_criteria(self, session: AsyncSession, sample_professional, sample_slots):
        actions = ScheduleActions(session)
        result = await actions.search_slots()
        assert result.success is True  # returns all available


@pytest.mark.asyncio
class TestBookSlot:
    async def test_book_available_slot(
        self, session: AsyncSession, sample_patient: Patient, sample_slots
    ):
        actions = ScheduleActions(session)
        slot = sample_slots[0]
        result = await actions.book_slot(slot.id, sample_patient.id)
        assert result.success is True
        assert "agendada com sucesso" in result.message
        assert result.booked_slot is not None

        # Verify in DB
        updated = await session.get(ScheduleSlot, slot.id)
        assert updated.status == SlotStatus.booked
        assert updated.patient_id == sample_patient.id

    async def test_book_already_booked(
        self, session: AsyncSession, sample_patient: Patient, sample_slots
    ):
        actions = ScheduleActions(session)
        slot = sample_slots[0]
        # Book it first
        await actions.book_slot(slot.id, sample_patient.id)
        # Try to book again
        result = await actions.book_slot(slot.id, sample_patient.id)
        assert result.success is False
        assert "não está mais disponível" in result.message


@pytest.mark.asyncio
class TestCancelSlot:
    async def test_cancel_booked_slot(
        self, session: AsyncSession, sample_patient: Patient, sample_slots
    ):
        actions = ScheduleActions(session)
        slot = sample_slots[0]
        # Book it first
        await actions.book_slot(slot.id, sample_patient.id)
        # Now cancel
        result = await actions.cancel_slot(sample_patient.id, slot_id=slot.id)
        assert result.success is True
        assert "cancelada com sucesso" in result.message

        # Verify in DB
        updated = await session.get(ScheduleSlot, slot.id)
        assert updated.status == SlotStatus.cancelled

    async def test_cancel_nonexistent(self, session: AsyncSession, sample_patient: Patient):
        actions = ScheduleActions(session)
        result = await actions.cancel_slot(sample_patient.id, date_str="2099-01-01")
        assert result.success is False

    async def test_cancel_wrong_patient(
        self, session: AsyncSession, sample_patient: Patient, sample_slots
    ):
        actions = ScheduleActions(session)
        slot = sample_slots[0]
        await actions.book_slot(slot.id, sample_patient.id)

        other_patient_id = uuid.uuid4()
        result = await actions.cancel_slot(other_patient_id, slot_id=slot.id)
        assert result.success is False


@pytest.mark.asyncio
class TestRescheduleSlot:
    async def test_reschedule_finds_options(
        self, session: AsyncSession, sample_patient: Patient, sample_slots, sample_professional
    ):
        actions = ScheduleActions(session)
        slot = sample_slots[0]
        # Book first slot
        await actions.book_slot(slot.id, sample_patient.id)
        # Reschedule
        result = await actions.reschedule_slot(
            patient_id=sample_patient.id,
            old_slot_id=slot.id,
        )
        # Should find remaining available slots
        assert result.success is True
        assert "Remarcação" in result.message or result.slots is not None


@pytest.mark.asyncio
class TestListAppointments:
    async def test_no_appointments(self, session: AsyncSession, sample_patient: Patient):
        actions = ScheduleActions(session)
        result = await actions.list_patient_appointments(sample_patient.id)
        assert result.success is True
        assert "não tem consultas" in result.message

    async def test_with_appointments(
        self, session: AsyncSession, sample_patient: Patient, sample_slots
    ):
        actions = ScheduleActions(session)
        await actions.book_slot(sample_slots[0].id, sample_patient.id)
        result = await actions.list_patient_appointments(sample_patient.id)
        assert result.success is True
        assert result.slots is not None
        assert len(result.slots) == 1
