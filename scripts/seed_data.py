#!/usr/bin/env python3
"""
Seed the database with initial data for a new clinic deploy.

Works in two modes:
  --mode api    → Seeds via HTTP API (requires running server)
  --mode db     → Seeds directly to DB (requires DATABASE_URL in env)

Usage:
    python scripts/seed_data.py --mode db
    python scripts/seed_data.py --mode api --api-url http://localhost:8000

NOTE: RAG documents use CLINIC_NAME from environment.
All clinic-specific content (name, phone, address) must be configured via
the Admin panel or environment variables after the initial seed.
This script seeds demo data only. Replace with real clinic data before production.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path

# Support both local dev and Docker container contexts.
_script_dir = Path(__file__).resolve().parent
_project_root = _script_dir.parent
if (_project_root / "app").is_dir():
    sys.path.insert(0, str(_project_root))
else:
    sys.path.insert(0, str(_project_root / "apps" / "api"))


# ── Clinic name from env (no hardcodes) ───────────────────────
_CLINIC_NAME = os.environ.get("CLINIC_NAME", "nossa clínica")
_CLINIC_PHONE = os.environ.get("CLINIC_PHONE", "(00) 0000-0000")
_CLINIC_ADDRESS = os.environ.get("CLINIC_ADDRESS", "endereço a configurar no Admin")


# ── Data definitions ──────────────────────────────────────────
# DEMO DATA — Replace with real professionals before production deploy.

PROFESSIONALS = [
    {"full_name": "Dra. Maria Silva", "specialty": "Clínica Geral", "crm": "CRM/SP 123456"},
    {"full_name": "Dr. João Santos", "specialty": "Cardiologia", "crm": "CRM/SP 789012"},
    {"full_name": "Dra. Ana Oliveira", "specialty": "Dermatologia", "crm": "CRM/SP 345678"},
    {"full_name": "Dr. Pedro Costa", "specialty": "Ortopedia", "crm": "CRM/SP 901234"},
    {"full_name": "Dra. Beatriz Almeida", "specialty": "Ginecologia", "crm": "CRM/SP 567890"},
    {"full_name": "Dr. Ricardo Ferreira", "specialty": "Pediatria", "crm": "CRM/SP 112233"},
    {"full_name": "Dra. Camila Rodrigues", "specialty": "Endocrinologia", "crm": "CRM/SP 445566"},
    {"full_name": "Dr. Marcos Nunes", "specialty": "Neurologia", "crm": "CRM/SP 778899"},
]

PATIENTS = [
    {
        "full_name": "Carlos Eduardo Mendes",
        "cpf": "123.456.789-00",
        "phone": "+5511999990001",
        "email": "carlos@email.com",
        "convenio_name": "Unimed",
        "consented_ai": True,
    },
    {
        "full_name": "Ana Paula Ferreira",
        "cpf": "987.654.321-00",
        "phone": "+5511999990002",
        "email": "ana@email.com",
        "convenio_name": "Bradesco Saúde",
        "consented_ai": True,
    },
    {
        "full_name": "Roberto Lima",
        "cpf": "456.789.123-00",
        "phone": "+5511999990003",
        "convenio_name": "Particular",
        "consented_ai": True,
    },
]

# RAG documents use clinic name from env — no hardcoded clinic identity.
RAG_DOCUMENTS = [
    {
        "title": "Horário de Funcionamento",
        "category": "faq",
        "content": (
            f"A {_CLINIC_NAME} funciona de segunda a sexta-feira, das 7h às 20h, "
            "e aos sábados das 8h às 13h. Domingos e feriados não há atendimento presencial, "
            "mas nosso atendimento virtual via Telegram está disponível 24 horas para "
            "agendamentos, dúvidas e remarcações."
        ),
    },
    {
        "title": "Convênios Aceitos",
        "category": "convenio",
        "content": (
            f"A {_CLINIC_NAME} aceita os seguintes convênios: Unimed, Bradesco Saúde, "
            "SulAmérica, Amil, Notre Dame Intermédica, Porto Seguro Saúde, "
            "Hapvida, Prevent Senior, e Particular. "
            "Para verificar a cobertura do seu plano para procedimentos específicos, "
            "entre em contato com nossa equipe. Aceitamos também pacientes particulares "
            "com diversas opções de pagamento: cartão de crédito (até 6x), débito, PIX e boleto."
        ),
    },
    {
        "title": "Especialidades Disponíveis",
        "category": "especialidades",
        "content": (
            f"A {_CLINIC_NAME} oferece atendimento nas seguintes especialidades: "
            "Clínica Geral, Cardiologia, Dermatologia, Ortopedia, Ginecologia, "
            "Pediatria, Endocrinologia e Neurologia. "
            "Cada especialidade conta com profissionais experientes e "
            "agenda disponível para consultas e retornos."
        ),
    },
    {
        "title": "Como Agendar uma Consulta",
        "category": "agendamento",
        "content": (
            "Você pode agendar sua consulta de várias formas: "
            "1) Pelo nosso assistente virtual no Telegram — disponível 24h. "
            "2) Por telefone durante o horário comercial: (11) 3000-0000. "
            "3) Presencialmente na recepção da clínica. "
            "Para agendar, tenha em mãos: nome completo, CPF, dados do convênio "
            "(se houver) e preferência de data e horário. "
            "Consultas podem ser agendadas com até 60 dias de antecedência."
        ),
    },
    {
        "title": "Política de Cancelamento e Remarcação",
        "category": "agendamento",
        "content": (
            "Cancelamentos e remarcações devem ser feitos com pelo menos 24 horas de "
            "antecedência. Cancelamentos com menos de 24h podem gerar cobrança de "
            "taxa administrativa de R$ 50,00 para pacientes particulares. "
            "Para remarcar, basta enviar uma mensagem ao nosso Telegram ou ligar "
            "para a recepção. Nosso assistente virtual pode ajudar com remarcações "
            "a qualquer hora do dia. Faltas sem aviso são registradas e, após 3 faltas, "
            "o paciente precisará agendar apenas presencialmente."
        ),
    },
    {
        "title": "Preparo para Exames — Informações Gerais",
        "category": "faq",
        "content": (
            "Preparos para exames variam conforme o procedimento. Informações gerais: "
            "- Exames de sangue: jejum de 8 a 12 horas (água é permitida). "
            "- Ultrassonografia abdominal: jejum de 6 horas. "
            "- Ultrassonografia pélvica: bexiga cheia (beber 4 copos de água 1h antes). "
            "- Eletrocardiograma: sem preparo especial. "
            "- Teste ergométrico: usar roupas confortáveis e tênis. "
            "Para preparos específicos de outros exames, consulte nossa equipe."
        ),
    },
    {
        "title": "Endereço e Como Chegar",
        "category": "faq",
        "content": (
            f"A {_CLINIC_NAME} está localizada em: {_CLINIC_ADDRESS}. "
            "Verifique o endereço atualizado no painel Admin ou entre em contato "
            f"pelo telefone: {_CLINIC_PHONE}."
        ),
    },
    {
        "title": "Primeira Consulta — O que Trazer",
        "category": "faq",
        "content": (
            "Na primeira consulta, traga: "
            "1) Documento de identidade com foto (RG ou CNH). "
            "2) CPF. "
            "3) Carteirinha do convênio (se aplicável). "
            "4) Pedido médico ou guia de encaminhamento (se houver). "
            "5) Exames anteriores relacionados à consulta. "
            "6) Lista de medicamentos em uso. "
            "Chegue 15 minutos antes do horário agendado para cadastro na recepção."
        ),
    },
]


def generate_slots(professional_ids: list[uuid.UUID]) -> list[dict]:
    """Generate 2 weeks of available slots for all professionals."""
    slots = []
    now = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    for prof_id in professional_ids:
        for day_offset in range(1, 15):  # Next 14 days
            day = now + timedelta(days=day_offset)
            weekday = day.weekday()

            if weekday == 6:  # Sunday — no slots
                continue

            if weekday == 5:  # Saturday — morning only
                hours = [8, 9, 10, 11, 12]
            else:  # Weekdays — full day
                hours = [8, 9, 10, 11, 14, 15, 16, 17, 18, 19]

            for hour in hours:
                start = day.replace(hour=hour, minute=0)
                slots.append({
                    "id": uuid.uuid4(),
                    "professional_id": prof_id,
                    "start_at": start,
                    "end_at": start + timedelta(minutes=30),
                    "status": "available",
                    "slot_type": "first_visit",
                    "source": "manual",
                })

    return slots


# ── DB mode ───────────────────────────────────────────────────

async def seed_db(database_url: str, *, skip_embeddings: bool = False) -> None:
    """Seed directly to database."""
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.orm import sessionmaker
    from sqlmodel import SQLModel, select

    from app.models.patient import Patient
    from app.models.professional import Professional
    from app.models.schedule import ScheduleSlot
    from app.models.rag import RagDocument
    from app.models.conversation import Conversation, Message, Handoff  # noqa
    from app.models.audit import AuditEvent  # noqa
    from app.services.rag_service import RagService

    engine = create_async_engine(database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        rag_service = RagService(session)
        # 1. Professionals
        print("\n--- Professionals ---")
        prof_ids = []
        for p in PROFESSIONALS:
            # Check if CRM already exists
            existing = (await session.execute(
                select(Professional).where(Professional.crm == p["crm"])
            )).scalar_one_or_none()
            if existing:
                print(f"  = {p['full_name']} (already exists)")
                prof_ids.append(existing.id)
                continue
            prof = Professional(id=uuid.uuid4(), **p)
            session.add(prof)
            prof_ids.append(prof.id)
            print(f"  + {p['full_name']} ({p['specialty']})")
        await session.commit()

        # 2. Patients
        print("\n--- Patients ---")
        for p in PATIENTS:
            existing = (await session.execute(
                select(Patient).where(Patient.cpf == p["cpf"])
            )).scalar_one_or_none()
            if existing:
                print(f"  = {p['full_name']} (already exists)")
                continue
            patient = Patient(id=uuid.uuid4(), preferred_channel="telegram", **p)
            session.add(patient)
            print(f"  + {p['full_name']} ({p['convenio_name']})")
        await session.commit()

        # 3. Schedule slots — only generate if none exist (idempotent)
        print("\n--- Schedule Slots ---")
        from sqlalchemy import func
        slot_count_result = await session.execute(select(func.count()).select_from(ScheduleSlot))
        existing_slot_count = slot_count_result.scalar_one()
        if existing_slot_count > 0:
            print(f"  = Slots already exist ({existing_slot_count} total), skipping generation")
        else:
            slots = generate_slots(prof_ids)
            count = 0
            for s in slots:
                slot = ScheduleSlot(**s)
                session.add(slot)
                count += 1
            await session.commit()
            print(f"  + {count} slots for {len(prof_ids)} professionals (14 days)")

        # 4. RAG documents
        print("\n--- RAG Documents ---")
        for doc_data in RAG_DOCUMENTS:
            existing = (await session.execute(
                select(RagDocument).where(RagDocument.title == doc_data["title"])
            )).scalar_one_or_none()
            if existing:
                print(f"  = {doc_data['title']} (already exists)")
                continue

            result = await rag_service.ingest_document(
                title=doc_data["title"],
                content=doc_data["content"],
                category=doc_data["category"],
                skip_embeddings=skip_embeddings,
            )
            print(
                "  + {title} -> chunks={chunks} embedded={embedded} failed={failed}".format(
                    title=doc_data["title"],
                    chunks=result.chunks_created,
                    embedded=result.chunks_embedded,
                    failed=result.chunks_failed,
                )
            )

    await engine.dispose()
    print("\nSeed complete!")


# ── API mode ──────────────────────────────────────────────────

def seed_api(api_url: str) -> None:
    """Seed via HTTP API (requires running server)."""
    import httpx

    # Check health
    try:
        resp = httpx.get(f"{api_url}/health", timeout=5.0)
        if resp.status_code != 200:
            print("API not healthy. Start the server first.")
            sys.exit(1)
    except Exception:
        print("Cannot reach API. Start the server first.")
        sys.exit(1)

    # Patients
    print("\n--- Patients ---")
    for p in PATIENTS:
        try:
            resp = httpx.post(f"{api_url}/api/v1/patients", json=p, timeout=10.0)
            if resp.status_code in (200, 201):
                print(f"  + {p['full_name']}")
            else:
                print(f"  = {p['full_name']} (exists or error: {resp.status_code})")
        except Exception as e:
            print(f"  x {p['full_name']}: {e}")

    # RAG documents
    print("\n--- RAG Documents ---")
    for doc in RAG_DOCUMENTS:
        try:
            resp = httpx.post(f"{api_url}/api/v1/rag/ingest", json=doc, timeout=30.0)
            if resp.status_code in (200, 201):
                data = resp.json()
                print(f"  + {doc['title']} -> {data.get('chunks_created', '?')} chunks")
            else:
                print(f"  = {doc['title']} ({resp.status_code})")
        except Exception as e:
            print(f"  x {doc['title']}: {e}")

    print("\nSeed via API complete!")
    print("NOTE: Professionals and slots must be seeded via --mode db.")


# ── Main ──────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Seed database with production data")
    parser.add_argument(
        "--mode", choices=["api", "db"], default="db",
        help="Seed mode: 'db' (direct) or 'api' (via HTTP)",
    )
    parser.add_argument("--api-url", default="http://localhost:8000", help="API base URL")
    parser.add_argument(
        "--skip-embeddings",
        action="store_true",
        help="Seed RAG documents without generating embeddings during startup.",
    )
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/inteliclinic"),
        help="Database URL (for --mode db). Defaults to DATABASE_URL env var.",
    )
    args = parser.parse_args()

    print(f"Seeding data (mode: {args.mode})")

    if args.mode == "db":
        asyncio.run(seed_db(args.database_url, skip_embeddings=args.skip_embeddings))
    else:
        seed_api(args.api_url)


if __name__ == "__main__":
    main()
