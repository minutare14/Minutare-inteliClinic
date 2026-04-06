#!/usr/bin/env python3
"""
Ingest documents from GUIAS-DEV into the RAG system.

Modes:
  --mode api    → Send sections to RAG ingest endpoint
  --mode db     → Write directly to database

Usage:
    python scripts/ingest_docs.py --mode db
    python scripts/ingest_docs.py --mode api --api-url http://localhost:8000
    python scripts/ingest_docs.py --mode db --docs-dir GUIAS-DEV
"""
from __future__ import annotations

import argparse
import asyncio
import re
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "apps" / "api"))

DEFAULT_DOCS_DIR = "GUIAS-DEV"

# Category mapping based on content patterns
CATEGORY_PATTERNS = [
    ("faq", [r"FAQ", r"perguntas?\s+frequentes", r"dúvidas?"]),
    ("agendamento", [r"agend\w+", r"horário", r"agenda", r"slot"]),
    ("convenio", [r"convênio", r"convenio", r"operadora", r"plano\s+de\s+saúde", r"TISS", r"TUSS"]),
    ("atendimento", [r"atendimento", r"recepção", r"recepcao", r"acolhimento"]),
    ("financeiro", [r"financeiro", r"faturamento", r"glosa", r"receita"]),
    ("governanca", [r"governança", r"auditoria", r"LGPD", r"CFM", r"compliance"]),
    ("especialidades", [r"especialidade", r"médico", r"medico", r"CRM"]),
    ("fluxo_operacional", [r"fluxo", r"operacion\w+", r"processo"]),
    ("rag", [r"RAG", r"base\s+de\s+conhecimento", r"corpus"]),
    ("ia", [r"inteligência\s+artificial", r"\bIA\b", r"LLM", r"chatbot"]),
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
        category = classify_section(title, body)
        sections.append({
            "title": f"{filepath.stem} — {title}",
            "content": body,
            "category": category,
            "source_path": str(filepath),
        })

    if not sections and len(text) > 100:
        sections.append({
            "title": filepath.stem,
            "content": text,
            "category": classify_section(filepath.stem, text),
            "source_path": str(filepath),
        })

    return sections


# ── DB mode ───────────────────────────────────────────────────

async def ingest_db(docs_dir: Path, database_url: str) -> None:
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.orm import sessionmaker

    from app.models.rag import RagDocument, RagChunk
    from app.models.patient import Patient  # noqa — metadata
    from app.models.professional import Professional  # noqa
    from app.models.schedule import ScheduleSlot  # noqa
    from app.models.conversation import Conversation, Message, Handoff  # noqa
    from app.models.audit import AuditEvent  # noqa
    from app.services.rag_service import chunk_text

    engine = create_async_engine(database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    md_files = sorted(docs_dir.glob("*.md"))
    if not md_files:
        print(f"No .md files found in {docs_dir}")
        return

    print(f"Found {len(md_files)} document(s) in {docs_dir}")
    total = 0

    async with async_session() as session:
        for filepath in md_files:
            print(f"\nProcessing: {filepath.name}")
            sections = extract_sections(filepath)
            print(f"  Extracted {len(sections)} section(s)")

            for section in sections:
                doc = RagDocument(
                    id=uuid.uuid4(),
                    title=section["title"],
                    category=section["category"],
                    source_path=section.get("source_path"),
                    status="active",
                )
                session.add(doc)
                await session.flush()

                chunks = chunk_text(section["content"], chunk_size=500, overlap=100)
                for idx, chunk_content in enumerate(chunks):
                    chunk = RagChunk(
                        id=uuid.uuid4(),
                        document_id=doc.id,
                        chunk_index=idx,
                        content=chunk_content,
                    )
                    session.add(chunk)

                total += 1
                print(f"  + '{section['title']}' -> {len(chunks)} chunks ({section['category']})")

        await session.commit()

    await engine.dispose()
    print(f"\nDone. Ingested {total} sections from {len(md_files)} files.")


# ── API mode ──────────────────────────────────────────────────

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
                    f"{api_url}/api/v1/rag/ingest", json=section, timeout=60.0
                )
                resp.raise_for_status()
                data = resp.json()
                print(f"  + '{section['title']}' -> {data['chunks_created']} chunks")
                total_ingested += 1
            except Exception as e:
                print(f"  x '{section['title']}': {e}")

    print(f"\nDone. Ingested {total_ingested}/{total_sections} sections from {len(md_files)} files.")


# ── Main ──────────────────────────────────────────────────────

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
