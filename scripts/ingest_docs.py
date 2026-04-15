#!/usr/bin/env python3
"""
Ingest markdown documents into the runtime RAG pipeline.

Modes:
  --mode api -> send sections to the HTTP ingest endpoint
  --mode db  -> write directly through RagService using the configured DB
"""
from __future__ import annotations

import argparse
import asyncio
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "apps" / "api"))

DEFAULT_DOCS_DIR = "GUIAS-DEV"

CATEGORY_PATTERNS = [
    ("faq", [r"FAQ", r"perguntas?\s+frequentes", r"duvidas?"]),
    ("agendamento", [r"agend\w+", r"horario", r"agenda", r"slot"]),
    ("convenio", [r"convenio", r"operadora", r"plano\s+de\s+saude", r"TISS", r"TUSS"]),
    ("atendimento", [r"atendimento", r"recepcao", r"acolhimento"]),
    ("financeiro", [r"financeiro", r"faturamento", r"glosa", r"receita"]),
    ("governanca", [r"governanca", r"auditoria", r"LGPD", r"CFM", r"compliance"]),
    ("especialidades", [r"especialidade", r"medico", r"CRM"]),
    ("fluxo_operacional", [r"fluxo", r"operacion\w+", r"processo"]),
    ("rag", [r"RAG", r"base\s+de\s+conhecimento", r"corpus"]),
    ("ia", [r"inteligencia\s+artificial", r"\bIA\b", r"LLM", r"chatbot"]),
]


def classify_section(title: str, content: str) -> str:
    text = f"{title} {content[:500]}".lower()
    for category, patterns in CATEGORY_PATTERNS:
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return category
    return "general"


def extract_sections(filepath: Path) -> list[dict]:
    text = filepath.read_text(encoding="utf-8")
    sections: list[dict] = []
    parts = re.split(r"^## ", text, flags=re.MULTILINE)

    for part in parts:
        if not part.strip():
            continue
        lines = part.strip().split("\n", 1)
        title = lines[0].strip().strip("#").strip()
        body = lines[1].strip() if len(lines) > 1 else ""
        if len(body) < 50:
            continue
        sections.append(
            {
                "title": f"{filepath.stem} - {title}",
                "content": body,
                "category": classify_section(title, body),
                "source_path": str(filepath),
            }
        )

    if not sections and len(text) > 100:
        sections.append(
            {
                "title": filepath.stem,
                "content": text,
                "category": classify_section(filepath.stem, text),
                "source_path": str(filepath),
            }
        )

    return sections


async def ingest_db(docs_dir: Path, database_url: str) -> None:
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.orm import sessionmaker

    from app.models.audit import AuditEvent  # noqa: F401
    from app.models.conversation import Conversation, Handoff, Message  # noqa: F401
    from app.models.patient import Patient  # noqa: F401
    from app.models.professional import Professional  # noqa: F401
    from app.models.schedule import ScheduleSlot  # noqa: F401
    from app.services.rag_service import RagService

    engine = create_async_engine(database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    md_files = sorted(docs_dir.glob("*.md"))
    if not md_files:
        print(f"No .md files found in {docs_dir}")
        return

    print(f"Found {len(md_files)} document(s) in {docs_dir}")
    total_sections = 0

    async with async_session() as session:
        rag_service = RagService(session)
        for filepath in md_files:
            print(f"\nProcessing: {filepath.name}")
            sections = extract_sections(filepath)
            print(f"  Extracted {len(sections)} section(s)")

            for section in sections:
                result = await rag_service.ingest_document(
                    title=section["title"],
                    content=section["content"],
                    category=section["category"],
                    source_path=section.get("source_path"),
                )
                total_sections += 1
                print(
                    "  + '{title}' -> chunks={chunks} embedded={embedded} failed={failed}".format(
                        title=section["title"],
                        chunks=result.chunks_created,
                        embedded=result.chunks_embedded,
                        failed=result.chunks_failed,
                    )
                )

    await engine.dispose()
    print(f"\nDone. Ingested {total_sections} section(s) from {len(md_files)} file(s).")


def ingest_api(docs_dir: Path, api_url: str) -> None:
    import httpx

    md_files = sorted(docs_dir.glob("*.md"))
    if not md_files:
        print(f"No .md files found in {docs_dir}")
        return

    print(f"Found {len(md_files)} document(s) in {docs_dir}")
    print(f"API URL: {api_url}\n")

    total_sections = 0
    total_ingested = 0

    for filepath in md_files:
        print(f"\nProcessing: {filepath.name}")
        sections = extract_sections(filepath)
        print(f"  Extracted {len(sections)} section(s)")

        for section in sections:
            total_sections += 1
            try:
                resp = httpx.post(
                    f"{api_url}/api/v1/rag/ingest",
                    json=section,
                    timeout=60.0,
                )
                resp.raise_for_status()
                data = resp.json()
                print(
                    "  + '{title}' -> chunks={chunks} embedded={embedded} failed={failed}".format(
                        title=section["title"],
                        chunks=data.get("chunks_created", "?"),
                        embedded=data.get("chunks_embedded", "?"),
                        failed=data.get("chunks_failed", "?"),
                    )
                )
                total_ingested += 1
            except Exception as exc:
                print(f"  x '{section['title']}': {exc}")

    print(
        f"\nDone. Ingested {total_ingested}/{total_sections} section(s) from {len(md_files)} file(s)."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest documents into RAG")
    parser.add_argument("--docs-dir", default=DEFAULT_DOCS_DIR, help="Path to docs directory")
    parser.add_argument("--mode", choices=["api", "db"], default="db")
    parser.add_argument("--api-url", default="http://localhost:8000")
    parser.add_argument(
        "--database-url",
        default="postgresql+asyncpg://minutare:minutare@localhost:5432/minutare_med",
    )
    args = parser.parse_args()

    docs_dir = Path(args.docs_dir)
    if not docs_dir.exists():
        print(f"Directory not found: {docs_dir}")
        sys.exit(1)

    if args.mode == "db":
        asyncio.run(ingest_db(docs_dir, args.database_url))
    else:
        ingest_api(docs_dir, args.api_url)


if __name__ == "__main__":
    main()
