"""
Seed script for services, categories, prices, rules, and professional links.

Usage:
    python scripts/seed_services.py           # dry run (default)
    python scripts/seed_services.py --force  # actually write to DB

Run from apps/api/:
    python ../../scripts/seed_services.py --force

Data source: medicos_servicos.md — IntelliClinic doctors + services specification.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Add apps/api to path
_project_root = Path(__file__).parent.parent
sys.path.insert(0, str(_project_root / "apps" / "api"))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.core.config import settings


# ─── Seed data from medicos_servicos.md ──────────────────────────────────────

CATEGORIES = [
    {"name": "Consulta", "description": "Consultas médicas gerais e especializadas"},
    {"name": "Procedimento", "description": "Procedimentos diagnósticos e estéticos"},
    {"name": "Teleconsulta", "description": "Atendimento remoto"},
    {"name": "Retorno", "description": "Visitas de retorno"},
    {"name": "Triagem", "description": "Triagem e orientação administrativa"},
    {"name": "Suporte", "description": "Suporte administrativo"},
]

INSURANCE_PLANS = [
    {"name": "Unimed", "code": "UNIMED", "plan_types": "Basic, Standard, Premium"},
    {"name": "Bradesco Saúde", "code": "BRADESCO", "plan_types": "Essential, Exclusivo, Premium"},
    {"name": "SulAmérica", "code": "SULAMERICA", "plan_types": "Fit, Plus, Top"},
    {"name": "Amil", "code": "AMIL", "plan_types": "S2000, S500, S750"},
    {"name": "Hapvida", "code": "HAPVIDA", "plan_types": "Basic, Premium"},
]

# 8 doctors from medicos_servicos.md
PROFESSIONALS = [
    {
        "full_name": "Dra. Ana Paula Ribeiro",
        "specialty": "Neurologia",
        "specialties_secondary": "Cefaleia, Distúrbios do Sono",
        "crm": "CRM-BA 15421",
        "allows_teleconsultation": False,
        "accepts_insurance": True,
        "insurance_plans": "Unimed, Bradesco Saúde, SulAmérica, Particular",
        "notes": "Atende adultos. Primeira consulta com tempo ampliado.",
    },
    {
        "full_name": "Dr. João Santos Lima",
        "specialty": "Ortopedia",
        "specialties_secondary": "Joelho, Ombro, Dor Articular",
        "crm": "CRM-BA 16203",
        "allows_teleconsultation": False,
        "accepts_insurance": True,
        "insurance_plans": "Unimed, Hapvida, Particular",
        "notes": "Consulta presencial. Pode solicitar retorno em janela reduzida.",
    },
    {
        "full_name": "Dra. Maria Clara Nunes",
        "specialty": "Dermatologia",
        "specialties_secondary": "Dermatologia Clínica, Acne, Melasma",
        "crm": "CRM-BA 14877",
        "allows_teleconsultation": True,
        "accepts_insurance": False,
        "insurance_plans": "Particular",
        "notes": "Procedimentos estéticos em agenda separada.",
    },
    {
        "full_name": "Dr. Carlos Henrique Menezes",
        "specialty": "Cardiologia",
        "specialties_secondary": "Hipertensão, Check-up Cardiológico",
        "crm": "CRM-BA 13902",
        "allows_teleconsultation": True,
        "accepts_insurance": True,
        "insurance_plans": "Unimed, Bradesco Saúde, Amil, Particular",
        "notes": "Teleconsulta apenas para retorno e acompanhamento.",
    },
    {
        "full_name": "Dra. Juliana Ferreira Costa",
        "specialty": "Ginecologia",
        "specialties_secondary": "Saúde da Mulher, Preventivo, Planejamento Reprodutivo",
        "crm": "CRM-BA 17111",
        "allows_teleconsultation": False,
        "accepts_insurance": True,
        "insurance_plans": "Unimed, Particular",
        "notes": "Procedimentos ginecológicos vinculados a agenda própria.",
    },
    {
        "full_name": "Dr. Ricardo Almeida Barros",
        "specialty": "Pediatria",
        "specialties_secondary": "Puericultura, Infecções Respiratórias, Acompanhamento Infantil",
        "crm": "CRM-BA 14365",
        "allows_teleconsultation": True,
        "accepts_insurance": True,
        "insurance_plans": "Hapvida, Unimed, Particular",
        "notes": "Teleconsulta apenas para casos elegíveis definidos em regra.",
    },
    {
        "full_name": "Dra. Fernanda Oliveira Prado",
        "specialty": "Endocrinologia",
        "specialties_secondary": "Diabetes, Tireoide, Obesidade",
        "crm": "CRM-BA 16744",
        "allows_teleconsultation": True,
        "accepts_insurance": True,
        "insurance_plans": "Bradesco Saúde, SulAmérica, Particular",
        "notes": "Primeira consulta preferencialmente presencial.",
    },
    {
        "full_name": "Dr. Marcelo Tavares Rocha",
        "specialty": "Gastroenterologia",
        "specialties_secondary": "Refluxo, Gastrite, Intestino Irritável",
        "crm": "CRM-BA 15198",
        "allows_teleconsultation": False,
        "accepts_insurance": True,
        "insurance_plans": "Amil, Unimed, Particular",
        "notes": "Exames e procedimentos devem ser ofertados conforme protocolo.",
    },
]

# 16 services from medicos_servicos.md
SERVICES = [
    # SVC-001
    {
        "service_code": "SVC-001",
        "name": "CONSULTA NEUROLÓGICA",
        "description": "Avaliação neurológica completa para queixas neurológicas, cefaleias e distúrbios do sono",
        "category": "Consulta",
        "duration_min": 50,
        "requires_specific_doctor": True,
        "ai_summary": "Consulta de neurologia para avaliação de queixas neurológicas, cefaleias e distúrbios do sono",
        "base_price": 320.0,
        "insurance_prices": [("Unimed", 256.0), ("Bradesco Saúde", 272.0), ("SulAmérica", 240.0), ("Particular", 320.0)],
        "doctor": "Dra. Ana Paula Ribeiro",
        "rules": [
            ("scheduling", "Primeira consulta sempre presencial"),
            ("scheduling", "Retorno pode ser marcado conforme avaliação médica"),
            ("return_window", "30 dias"),
        ],
    },
    # SVC-002
    {
        "service_code": "SVC-002",
        "name": "RETORNO NEUROLÓGICO",
        "description": "Retorno de neurologia vinculado ao mesmo médico",
        "category": "Retorno",
        "duration_min": 30,
        "requires_specific_doctor": True,
        "ai_summary": "Retorno de neurologia vinculado ao mesmo médico quando aplicável",
        "base_price": 220.0,
        "insurance_prices": [("Unimed", 176.0), ("Bradesco Saúde", 187.0), ("SulAmérica", 165.0), ("Particular", 220.0)],
        "doctor": "Dra. Ana Paula Ribeiro",
        "rules": [
            ("scheduling", "Retorno deve preferir o mesmo médico da consulta inicial"),
            ("scheduling", "Só pode ser vendido como retorno se estiver dentro da regra configurada da clínica"),
            ("return_window", "30 dias"),
        ],
    },
    # SVC-003
    {
        "service_code": "SVC-003",
        "name": "CONSULTA ORTOPÉDICA",
        "description": "Avaliação ortopédica de ossos e articulações",
        "category": "Consulta",
        "duration_min": 40,
        "requires_specific_doctor": True,
        "ai_summary": "Consulta ortopédica para avaliação de dores articulares, joelho e ombro",
        "base_price": 290.0,
        "insurance_prices": [("Unimed", 232.0), ("Hapvida", 232.0), ("Particular", 290.0)],
        "doctor": "Dr. João Santos Lima",
        "rules": [
            ("scheduling", "Preferir presencial"),
            ("scheduling", "Casos de dor aguda podem ser marcados com prioridade"),
            ("return_window", "20 dias"),
        ],
    },
    # SVC-004
    {
        "service_code": "SVC-004",
        "name": "RETORNO ORTOPÉDICO",
        "description": "Retorno ortopédico para continuidade",
        "category": "Retorno",
        "duration_min": 25,
        "requires_specific_doctor": True,
        "ai_summary": "Retorno de ortopedia com prioridade para continuidade do mesmo médico",
        "base_price": 180.0,
        "insurance_prices": [("Unimed", 144.0), ("Hapvida", 144.0), ("Particular", 180.0)],
        "doctor": "Dr. João Santos Lima",
        "rules": [
            ("scheduling", "Manter o mesmo ortopedista quando houver histórico prévio"),
            ("return_window", "20 dias"),
        ],
    },
    # SVC-005
    {
        "service_code": "SVC-005",
        "name": "CONSULTA DERMATOLÓGICA",
        "description": "Avaliação dermatológica para pele, acne e melasma",
        "category": "Consulta",
        "duration_min": 35,
        "requires_specific_doctor": True,
        "ai_summary": "Consulta dermatológica clínica para pele, acne e melasma",
        "base_price": 260.0,
        "insurance_prices": [("Particular", 260.0)],
        "doctor": "Dra. Maria Clara Nunes",
        "rules": [
            ("scheduling", "Avaliação clínica dermatológica"),
            ("scheduling", "Procedimentos estéticos são serviços separados"),
            ("return_window", "30 dias"),
        ],
    },
    # SVC-006
    {
        "service_code": "SVC-006",
        "name": "PEELING QUÍMICO FACIAL",
        "description": "Procedimento de rejuvenescimento facial",
        "category": "Procedimento",
        "duration_min": 60,
        "requires_specific_doctor": True,
        "ai_summary": "Peeling químico para rejuvenescimento",
        "base_price": 450.0,
        "insurance_prices": [("Particular", 450.0)],
        "doctor": "Dra. Maria Clara Nunes",
        "rules": [
            ("scheduling", "Exige avaliação dermatológica prévia"),
            ("scheduling", "Não oferecer direto sem triagem"),
            ("return_window", "15 dias"),
        ],
    },
    # SVC-007
    {
        "service_code": "SVC-007",
        "name": "CONSULTA CARDIOLÓGICA",
        "description": "Avaliação cardiológica com eletrocardiograma",
        "category": "Consulta",
        "duration_min": 45,
        "requires_specific_doctor": True,
        "ai_summary": "Consulta cardiológica para avaliação clínica e acompanhamento cardiovascular",
        "base_price": 340.0,
        "insurance_prices": [("Unimed", 272.0), ("Bradesco Saúde", 289.0), ("Amil", 255.0), ("Particular", 340.0)],
        "doctor": "Dr. Carlos Henrique Menezes",
        "rules": [
            ("scheduling", "Teleconsulta apenas para retorno e acompanhamento elegível"),
            ("return_window", "30 dias"),
        ],
    },
    # SVC-008
    {
        "service_code": "SVC-008",
        "name": "RETORNO CARDIOLÓGICO POR TELECONSULTA",
        "description": "Retorno cardiológico remoto sob critérios definidos",
        "category": "Teleconsulta",
        "duration_min": 25,
        "requires_specific_doctor": True,
        "ai_summary": "Retorno cardiológico remoto sob critérios definidos",
        "base_price": 210.0,
        "insurance_prices": [("Particular", 210.0), ("Bradesco Saúde", 178.0)],
        "doctor": "Dr. Carlos Henrique Menezes",
        "rules": [
            ("scheduling", "Só pode ser ofertado se o paciente já tiver passado em consulta anterior"),
            ("teleconsult", "Apenas para retorno e acompanhamento elegível"),
            ("return_window", "30 dias"),
        ],
    },
    # SVC-009
    {
        "service_code": "SVC-009",
        "name": "CONSULTA GINECOLÓGICA",
        "description": "Avaliação ginecológica e preventivo",
        "category": "Consulta",
        "duration_min": 40,
        "requires_specific_doctor": True,
        "ai_summary": "Consulta ginecológica para prevenção e acompanhamento da saúde da mulher",
        "base_price": 280.0,
        "insurance_prices": [("Unimed", 224.0), ("Particular", 280.0)],
        "doctor": "Dra. Juliana Ferreira Costa",
        "rules": [
            ("scheduling", "Primeira consulta preferencialmente presencial"),
            ("return_window", "30 dias"),
        ],
    },
    # SVC-010
    {
        "service_code": "SVC-010",
        "name": "PREVENTIVO GINECOLÓGICO",
        "description": "Procedimento ginecológico vinculado à avaliação ou acompanhamento",
        "category": "Procedimento",
        "duration_min": 30,
        "requires_specific_doctor": True,
        "ai_summary": "Procedimento ginecológico vinculado à avaliação ou acompanhamento",
        "base_price": 190.0,
        "insurance_prices": [("Particular", 190.0)],
        "doctor": "Dra. Juliana Ferreira Costa",
        "rules": [
            ("scheduling", "Pode exigir consulta associada conforme protocolo"),
        ],
    },
    # SVC-011
    {
        "service_code": "SVC-011",
        "name": "CONSULTA PEDIÁTRICA",
        "description": "Avaliação pediátrica para crianças e adolescentes",
        "category": "Consulta",
        "duration_min": 35,
        "requires_specific_doctor": True,
        "ai_summary": "Consulta pediátrica para avaliação e acompanhamento infantil",
        "base_price": 250.0,
        "insurance_prices": [("Hapvida", 200.0), ("Unimed", 200.0), ("Particular", 250.0)],
        "doctor": "Dr. Ricardo Almeida Barros",
        "rules": [
            ("scheduling", "Teleconsulta infantil só em casos elegíveis"),
            ("teleconsult", "Teleconsulta apenas para casos elegíveis"),
            ("return_window", "30 dias"),
        ],
    },
    # SVC-012
    {
        "service_code": "SVC-012",
        "name": "TELECONSULTA PEDIÁTRICA DE RETORNO",
        "description": "Retorno pediátrico remoto mediante elegibilidade",
        "category": "Teleconsulta",
        "duration_min": 20,
        "requires_specific_doctor": True,
        "ai_summary": "Retorno pediátrico remoto mediante elegibilidade",
        "base_price": 170.0,
        "insurance_prices": [("Particular", 170.0)],
        "doctor": "Dr. Ricardo Almeida Barros",
        "rules": [
            ("scheduling", "Somente retorno e casos previamente orientados"),
            ("teleconsult", "Apenas para retorno e casos previamente orientados"),
            ("return_window", "15 dias"),
        ],
    },
    # SVC-013
    {
        "service_code": "SVC-013",
        "name": "CONSULTA ENDOCRINOLÓGICA",
        "description": "Avaliação de glândulas e metabolismo",
        "category": "Consulta",
        "duration_min": 45,
        "requires_specific_doctor": True,
        "ai_summary": "Consulta endocrinológica para diabetes, tireoide e obesidade",
        "base_price": 330.0,
        "insurance_prices": [("Bradesco Saúde", 280.0), ("SulAmérica", 264.0), ("Particular", 330.0)],
        "doctor": "Dra. Fernanda Oliveira Prado",
        "rules": [
            ("scheduling", "Primeira consulta preferencialmente presencial"),
            ("return_window", "30 dias"),
        ],
    },
    # SVC-014
    {
        "service_code": "SVC-014",
        "name": "RETORNO ENDOCRINOLÓGICO",
        "description": "Retorno endocrinológico de acompanhamento clínico",
        "category": "Retorno",
        "duration_min": 25,
        "requires_specific_doctor": True,
        "ai_summary": "Retorno endocrinológico de acompanhamento clínico",
        "base_price": 210.0,
        "insurance_prices": [("Bradesco Saúde", 178.0), ("SulAmérica", 168.0), ("Particular", 210.0)],
        "doctor": "Dra. Fernanda Oliveira Prado",
        "rules": [
            ("scheduling", "Retorno idealmente com o mesmo médico"),
            ("return_window", "30 dias"),
        ],
    },
    # SVC-015
    {
        "service_code": "SVC-015",
        "name": "CONSULTA GASTROENTEROLÓGICA",
        "description": "Avaliação gastroenterológica para queixas digestivas",
        "category": "Consulta",
        "duration_min": 40,
        "requires_specific_doctor": True,
        "ai_summary": "Consulta gastroenterológica para queixas digestivas e acompanhamento clínico",
        "base_price": 310.0,
        "insurance_prices": [("Amil", 248.0), ("Unimed", 248.0), ("Particular", 310.0)],
        "doctor": "Dr. Marcelo Tavares Rocha",
        "rules": [
            ("scheduling", "Sintomas persistentes podem gerar prioridade de encaixe"),
            ("return_window", "30 dias"),
        ],
    },
    # SVC-016
    {
        "service_code": "SVC-016",
        "name": "RETORNO GASTROENTEROLÓGICO",
        "description": "Retorno gastroenterológico para continuidade do tratamento",
        "category": "Retorno",
        "duration_min": 25,
        "requires_specific_doctor": True,
        "ai_summary": "Retorno gastroenterológico para continuidade do tratamento",
        "base_price": 200.0,
        "insurance_prices": [("Amil", 160.0), ("Unimed", 160.0), ("Particular", 200.0)],
        "doctor": "Dr. Marcelo Tavares Rocha",
        "rules": [
            ("scheduling", "Continuidade preferencial com o mesmo médico"),
            ("return_window", "20 dias"),
        ],
    },
    # SVC-017 — shared (no specific doctor)
    {
        "service_code": "SVC-017",
        "name": "TRIAGEM ADMINISTRATIVA DE PRIMEIRA RESPOSTA",
        "description": "Fluxo administrativo inicial para classificar demanda",
        "category": "Triagem",
        "duration_min": 10,
        "requires_specific_doctor": False,
        "ai_summary": "Fluxo administrativo inicial para classificar demanda",
        "base_price": 0.0,
        "insurance_prices": [],
        "doctor": None,
        "rules": [
            ("scheduling", "Usado para organizar intenção antes do agendamento definitivo"),
            ("general", "Não caracteriza consulta médica"),
        ],
    },
    # SVC-018 — shared (no specific doctor)
    {
        "service_code": "SVC-018",
        "name": "ORIENTAÇÃO DE CONVÊNIO E COBERTURA",
        "description": "Atendimento para dúvidas de cobertura, regras e documentos",
        "category": "Suporte",
        "duration_min": 10,
        "requires_specific_doctor": False,
        "ai_summary": "Atendimento para dúvidas de cobertura, regras e documentos",
        "base_price": 0.0,
        "insurance_prices": [],
        "doctor": None,
        "rules": [
            ("scheduling", "Apenas suporte administrativo"),
            ("general", "Não caracteriza consulta médica"),
        ],
    },
]


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _now():
    return datetime.now(timezone.utc)


async def _fetchone(session, sql_str, params=None):
    result = await session.execute(text(sql_str), params or {})
    row = result.fetchone()
    if row is None:
        return None
    return {k: v for k, v in zip(result.keys(), row)}


async def _exec(session, sql_str, params=None):
    await session.execute(text(sql_str), params or {})
    await session.commit()


# ─── Main ─────────────────────────────────────────────────────────────────────

async def run_seed(dry_run: bool = True):
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with async_session() as session:
        if dry_run:
            print("=== DRY RUN — nenhuma alteração será gravada ===\n")

        clinic_id = settings.clinic_id
        now = _now()

        print(f"Clinic ID: {clinic_id}")
        print(f"Modo: {'DRY RUN' if dry_run else 'EXECUTE'}\n")

        # ── 1. Categories ─────────────────────────────────────────────────────
        print("[1] Service Categories...")
        cat_ids = {}
        for cat in CATEGORIES:
            row = await _fetchone(
                session,
                "SELECT id FROM service_categories WHERE clinic_id = :cid AND name = :name",
                {"cid": clinic_id, "name": cat["name"]},
            )
            if row:
                cat_ids[cat["name"]] = row["id"]
                print(f"  ✓ {cat['name']} — já existe (skip)")
            else:
                cat_id = str(uuid.uuid4())
                if not dry_run:
                    await _exec(
                        session,
                        """INSERT INTO service_categories (id, clinic_id, name, description, active, created_at)
                           VALUES (:id, :cid, :name, :desc, true, :created_at)""",
                        {"id": cat_id, "cid": clinic_id, "name": cat["name"],
                         "desc": cat.get("description"), "created_at": now},
                    )
                cat_ids[cat["name"]] = cat_id
                print(f"  + {cat['name']} — seria criado" if dry_run else f"  ✓ {cat['name']} — criado")

        # ── 2. Professionals ────────────────────────────────────────────────
        print("\n[2] Professionals...")
        prof_ids = {}
        for prof in PROFESSIONALS:
            existing = await _fetchone(
                session,
                "SELECT id FROM professionals WHERE crm = :crm",
                {"crm": prof["crm"]},
            )
            if existing:
                prof_ids[prof["full_name"]] = existing["id"]
                # Update secondary specialties and other fields if they differ
                print(f"  ✓ {prof['full_name']} — já existe (CRM {prof['crm']})")
            else:
                prof_id = str(uuid.uuid4())
                if not dry_run:
                    await _exec(
                        session,
                        """INSERT INTO professionals
                           (id, full_name, specialty, specialties_secondary, crm, active,
                            allows_teleconsultation, accepts_insurance, insurance_plans, notes,
                            created_at, updated_at)
                           VALUES (:id, :name, :spec, :specs_sec, :crm, true,
                                   :tele, :accepts_ins, :ins_plans, :notes,
                                   :created_at, :updated_at)""",
                        {"id": prof_id, "name": prof["full_name"], "spec": prof["specialty"],
                         "specs_sec": prof.get("specialties_secondary"), "crm": prof["crm"],
                         "tele": prof.get("allows_teleconsultation", False),
                         "accepts_ins": prof.get("accepts_insurance", True),
                         "ins_plans": prof.get("insurance_plans"),
                         "notes": prof.get("notes"),
                         "created_at": now, "updated_at": now},
                    )
                prof_ids[prof["full_name"]] = prof_id
                print(f"  + {prof['full_name']} — seria criado" if dry_run else f"  ✓ {prof['full_name']} — criado (CRM {prof['crm']})")

        # ── 3. Insurance Plans ──────────────────────────────────────────────
        print("\n[3] Insurance Plans...")
        ins_plan_ids = {}
        for plan in INSURANCE_PLANS:
            row = await _fetchone(
                session,
                "SELECT id FROM insurance_catalog WHERE clinic_id = :cid AND name = :name",
                {"cid": clinic_id, "name": plan["name"]},
            )
            if row:
                ins_plan_ids[plan["name"]] = row["id"]
                print(f"  ✓ {plan['name']} — já existe (skip)")
            else:
                ins_id = str(uuid.uuid4())
                if not dry_run:
                    await _exec(
                        session,
                        """INSERT INTO insurance_catalog (id, clinic_id, name, code, plan_types, active, created_at)
                           VALUES (:id, :cid, :name, :code, :plan_types, true, :created_at)""",
                        {"id": ins_id, "cid": clinic_id, "name": plan["name"],
                         "code": plan["code"], "plan_types": plan["plan_types"], "created_at": now},
                    )
                ins_plan_ids[plan["name"]] = ins_id
                print(f"  + {plan['name']} — seria criado" if dry_run else f"  ✓ {plan['name']} — criado")

        # ── 4. Services + Prices + Insurance Rules ──────────────────────────
        print("\n[4] Services + Prices...")
        svc_ids = {}

        for svc in SERVICES:
            cat_id = cat_ids.get(svc["category"])
            existing = await _fetchone(
                session,
                "SELECT id FROM services WHERE clinic_id = :cid AND service_code = :code",
                {"cid": clinic_id, "code": svc["service_code"]},
            )
            if existing:
                svc_ids[svc["name"]] = existing["id"]
                print(f"  ✓ {svc['service_code']} {svc['name']} — já existe (skip)")
                # Still seed missing prices
            else:
                svc_id = str(uuid.uuid4())
                svc_ids[svc["name"]] = svc_id
                if not dry_run:
                    await _exec(
                        session,
                        """INSERT INTO services
                           (id, clinic_id, category_id, service_code, name, description,
                            duration_min, requires_specific_doctor, ai_summary, active, version,
                            created_at, updated_at)
                           VALUES (:id, :cid, :cat_id, :code, :name, :desc,
                                   :dur, :req_doc, :ai_sum, true, 1, :created_at, :updated_at)""",
                        {"id": svc_id, "cid": clinic_id, "cat_id": cat_id,
                         "code": svc["service_code"], "name": svc["name"],
                         "desc": svc.get("description"),
                         "dur": svc["duration_min"],
                         "req_doc": svc.get("requires_specific_doctor", True),
                         "ai_sum": svc.get("ai_summary"),
                         "created_at": now, "updated_at": now},
                    )
                print(f"  + {svc['service_code']} {svc['name']} — seria criado" if dry_run else f"  ✓ {svc['service_code']} {svc['name']} — criado")

            sid = svc_ids[svc["name"]]

            # Base price (particular — insurance_plan_id = NULL)
            base_price_row = await _fetchone(
                session,
                """SELECT id FROM service_prices
                   WHERE service_id = :sid AND insurance_plan_id IS NULL AND active = true""",
                {"sid": sid},
            )
            if not base_price_row:
                price_id = str(uuid.uuid4())
                if not dry_run:
                    await _exec(
                        session,
                        """INSERT INTO service_prices
                           (id, clinic_id, service_id, insurance_plan_id, price, active, version, created_at)
                           VALUES (:id, :cid, :sid, NULL, :price, true, 1, :created_at)""",
                        {"id": price_id, "cid": clinic_id, "sid": sid,
                         "price": svc["base_price"], "created_at": now},
                    )
                print(f"    + Particular: R$ {svc['base_price']:,.2f} — seria criado" if dry_run else f"    ✓ Particular: R$ {svc['base_price']:,.2f} — criado")
            else:
                print(f"    ✓ Particular: já existe (skip)")

            # Insurance prices
            for ins_name, price in svc.get("insurance_prices", []):
                ins_plan_id = ins_plan_ids.get(ins_name)
                if not ins_plan_id:
                    print(f"    ! Convênio '{ins_name}' não encontrado — pulando")
                    continue
                ins_row = await _fetchone(
                    session,
                    """SELECT id FROM service_prices
                       WHERE service_id = :sid AND insurance_plan_id = :ins_id AND active = true""",
                    {"sid": sid, "ins_id": ins_plan_id},
                )
                if ins_row:
                    print(f"    ✓ {ins_name}: R$ {price:,.2f} — já existe (skip)")
                else:
                    price_id = str(uuid.uuid4())
                    if not dry_run:
                        await _exec(
                            session,
                            """INSERT INTO service_prices
                               (id, clinic_id, service_id, insurance_plan_id, price, active, version, created_at)
                               VALUES (:id, :cid, :sid, :ins_id, :price, true, 1, :created_at)""",
                            {"id": price_id, "cid": clinic_id, "sid": sid,
                             "ins_id": ins_plan_id, "price": price, "created_at": now},
                        )
                    print(f"    + {ins_name}: R$ {price:,.2f} — seria criado" if dry_run else f"    ✓ {ins_name}: R$ {price:,.2f} — criado")

            # Service Insurance Rules
            svc_insurance_names = [p[0] for p in svc.get("insurance_prices", [])]
            for ins_name in svc_insurance_names:
                ins_plan_id = ins_plan_ids.get(ins_name)
                if not ins_plan_id:
                    continue
                allowed = True
                rule_row = await _fetchone(
                    session,
                    """SELECT id FROM service_insurance_rules
                       WHERE service_id = :sid AND insurance_name = :ins_name AND active = true""",
                    {"sid": sid, "ins_name": ins_name},
                )
                if not rule_row:
                    rule_id = str(uuid.uuid4())
                    if not dry_run:
                        await _exec(
                            session,
                            """INSERT INTO service_insurance_rules
                               (id, clinic_id, service_id, insurance_name, allowed, active, created_at, updated_at)
                               VALUES (:id, :cid, :sid, :ins_name, :allowed, true, :created_at, :updated_at)""",
                            {"id": rule_id, "cid": clinic_id, "sid": sid,
                             "ins_name": ins_name, "allowed": allowed,
                             "created_at": now, "updated_at": now},
                        )
                    print(f"    + Regra convênio {ins_name}: allow={allowed} — seria criada" if dry_run else f"    ✓ Regra convênio {ins_name}: allow={allowed} — criada")

            # Operational rules
            for rule_type, rule_text in svc.get("rules", []):
                rule_row = await _fetchone(
                    session,
                    """SELECT id FROM service_operational_rules
                       WHERE service_id = :sid AND rule_type = :rtype AND active = true""",
                    {"sid": sid, "rtype": rule_type},
                )
                if rule_row:
                    print(f"    ✓ Regra [{rule_type}]: já existe (skip)")
                else:
                    rule_id = str(uuid.uuid4())
                    if not dry_run:
                        await _exec(
                            session,
                            """INSERT INTO service_operational_rules
                               (id, clinic_id, service_id, rule_type, rule_text, active, version, created_at, updated_at)
                               VALUES (:id, :cid, :sid, :rtype, :rtext, true, 1, :created_at, :updated_at)""",
                            {"id": rule_id, "cid": clinic_id, "sid": sid,
                             "rtype": rule_type, "rtext": rule_text,
                             "created_at": now, "updated_at": now},
                        )
                    print(f"    + Regra [{rule_type}]: '{rule_text[:50]}...' — seria criada" if dry_run else f"    ✓ Regra [{rule_type}]: '{rule_text[:50]}...' — criada")

        # ── 5. Professional → Service Links ─────────────────────────────────
        print("\n[5] Professional → Service Links...")
        for svc in SERVICES:
            doctor_name = svc.get("doctor")
            if not doctor_name:
                continue
            prof_id = prof_ids.get(doctor_name)
            svc_id = svc_ids.get(svc["name"])
            if not prof_id:
                print(f"  ! Profissional '{doctor_name}' não encontrado — pulando link")
                continue
            if not svc_id:
                print(f"  ! Serviço '{svc['name']}' não encontrado — pulando link")
                continue

            existing = await _fetchone(
                session,
                """SELECT id FROM professional_service_links
                   WHERE professional_id = :pid AND service_id = :sid AND active = true""",
                {"pid": prof_id, "sid": svc_id},
            )
            if existing:
                print(f"  ✓ {doctor_name} → {svc['name']} — já existe (skip)")
            else:
                link_id = str(uuid.uuid4())
                if not dry_run:
                    await _exec(
                        session,
                        """INSERT INTO professional_service_links
                           (id, clinic_id, professional_id, service_id, active, priority_order, created_at, updated_at)
                           VALUES (:id, :cid, :pid, :sid, true, 0, :created_at, :updated_at)""",
                        {"id": link_id, "cid": clinic_id, "pid": prof_id, "sid": svc_id,
                         "created_at": now, "updated_at": now},
                    )
                print(f"  + {doctor_name} → {svc['name']} — seria criado" if dry_run else f"  ✓ {doctor_name} → {svc['name']} — criado")

        print(f"\n{'='*50}")
        if dry_run:
            print("DRY RUN concluído. Execute com --force para gravar.")
        else:
            print("Seed concluído com sucesso!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed services, preços, regras e vínculos do medicos_servicos.md")
    parser.add_argument("--force", action="store_true", help="Gravar alterações no banco (sem --force é dry-run)")
    args = parser.parse_args()
    asyncio.run(run_seed(dry_run=not args.force))
