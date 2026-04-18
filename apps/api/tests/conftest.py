"""
Shared test fixtures.

Uses a real async SQLite database for integration tests.
No mocks for DB — tests run against actual SQL.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

# Import all models so SQLModel.metadata knows about them
from app.models.patient import Patient
from app.models.professional import Professional
from app.models.schedule import ScheduleSlot, SlotStatus
from app.models.conversation import Conversation, Message, Handoff
from app.models.audit import AuditEvent
from app.models.rag import RagDocument, RagChunk
from app.models.admin import ClinicSettings


@pytest_asyncio.fixture
async def engine():
    """Create an async SQLite engine for testing."""
    eng = create_async_engine(
        "sqlite+aiosqlite:///",  # in-memory
        echo=False,
    )
    async with eng.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session(engine):
    """Create a test DB session."""
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as sess:
        yield sess


@pytest_asyncio.fixture
async def sample_patient(session: AsyncSession) -> Patient:
    """Create a sample patient in the DB."""
    patient = Patient(
        id=uuid.uuid4(),
        full_name="Maria Silva",
        cpf="123.456.789-00",
        phone="11999998888",
        email="maria@example.com",
        telegram_user_id="12345",
        telegram_chat_id="12345",
        convenio_name="Unimed",
        consented_ai=True,
    )
    session.add(patient)
    await session.commit()
    await session.refresh(patient)
    return patient


@pytest_asyncio.fixture
async def sample_professional(session: AsyncSession) -> Professional:
    """Create a sample professional in the DB."""
    prof = Professional(
        id=uuid.uuid4(),
        full_name="Dr. Carlos Mendes",
        specialty="Cardiologia",
        crm="CRM/SP 12345",
    )
    session.add(prof)
    await session.commit()
    await session.refresh(prof)
    return prof


@pytest_asyncio.fixture
async def sample_slots(session: AsyncSession, sample_professional: Professional) -> list[ScheduleSlot]:
    """Create available slots for the next 3 days."""
    slots = []
    base = datetime.utcnow().replace(hour=9, minute=0, second=0, microsecond=0) + timedelta(days=1)
    for i in range(5):
        start = base + timedelta(hours=i)
        slot = ScheduleSlot(
            id=uuid.uuid4(),
            professional_id=sample_professional.id,
            start_at=start,
            end_at=start + timedelta(minutes=30),
            status=SlotStatus.available,
        )
        session.add(slot)
        slots.append(slot)
    await session.commit()
    for s in slots:
        await session.refresh(s)
    return slots


@pytest_asyncio.fixture
async def sample_conversation(session: AsyncSession, sample_patient: Patient) -> Conversation:
    """Create a sample conversation."""
    conv = Conversation(
        id=uuid.uuid4(),
        patient_id=sample_patient.id,
        channel="telegram",
        status="active",
    )
    session.add(conv)
    await session.commit()
    await session.refresh(conv)
    return conv


@pytest_asyncio.fixture
async def sample_rag_data(session: AsyncSession) -> tuple[RagDocument, list[RagChunk]]:
    """Create sample RAG documents and chunks."""
    doc = RagDocument(
        id=uuid.uuid4(),
        clinic_id="clinic01",
        title="Informacoes da Clinica",
        category="operacional",
        status="active",
    )
    session.add(doc)
    await session.commit()
    await session.refresh(doc)

    chunks_data = [
        "A clinica funciona de segunda a sexta das 8h as 18h e sabados das 8h as 12h.",
        "Aceitamos os convenios Unimed, Bradesco Saude, SulAmerica e Amil. Consultas particulares tambem sao atendidas.",
        "Para exames de sangue, e necessario jejum de 8 horas. Trazer documento com foto e carteirinha do convenio.",
        "O endereco da clinica e Rua das Flores, 123, Centro. Telefone (11) 3456-7890.",
        "Politica de cancelamento: cancelamentos devem ser feitos com 24 horas de antecedencia. Faltas sem aviso podem gerar cobranca.",
    ]
    chunks = []
    for i, content in enumerate(chunks_data):
        chunk = RagChunk(
            id=uuid.uuid4(),
            document_id=doc.id,
            clinic_id="clinic01",
            chunk_index=i,
            content=content,
        )
        session.add(chunk)
        chunks.append(chunk)
    await session.commit()
    for c in chunks:
        await session.refresh(c)
    return doc, chunks
