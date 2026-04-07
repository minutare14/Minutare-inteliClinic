"""Docling-based document parser for medical and administrative documents.

Uses: https://github.com/docling-project/docling
Supports: PDF, DOCX, PPTX, HTML, AsciiDoc

Specialized for:
- Insurance (convenio) PDFs
- TISS/TUSS tables
- Medical protocols
- Administrative contracts
- Internal FAQs
- Operational manuals

Docling is lazily initialised on first use to avoid slow startup times.
Heavy parsing is always delegated to a thread executor to remain async-safe.
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from .base_parser import BaseParser, ParsedDocument

logger = logging.getLogger(__name__)

# Supported extensions for Docling
DOCLING_EXTENSIONS = {".pdf", ".docx", ".pptx", ".html", ".adoc"}


class DoclingParser(BaseParser):
    """Primary parser using Docling for rich document extraction.

    Capabilities:
        - Full-text extraction from PDF (including scanned pages via OCR)
        - Table structure recognition (for TISS/TUSS procedure tables)
        - Section detection for logical chunking downstream
        - Markdown export for clean LLM consumption
    """

    def __init__(
        self,
        ocr_enabled: bool = True,
        table_extraction: bool = True,
        ocr_lang: list[str] | None = None,
    ) -> None:
        self.ocr_enabled = ocr_enabled
        self.table_extraction = table_extraction
        self.ocr_lang = ocr_lang or ["por", "eng"]  # Portuguese + English
        self._pipeline: Any = None

    @property
    def name(self) -> str:
        return "docling"

    def supports(self, path: Path) -> bool:
        """Return True for all file types Docling can handle."""
        return path.suffix.lower() in DOCLING_EXTENSIONS

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_pipeline(self) -> Any:
        """Lazy-load the Docling DocumentConverter (expensive to initialise)."""
        if self._pipeline is None:
            from docling.document_converter import DocumentConverter
            from docling.datamodel.pipeline_options import PdfPipelineOptions

            options = PdfPipelineOptions(
                do_ocr=self.ocr_enabled,
                do_table_structure=self.table_extraction,
            )
            self._pipeline = DocumentConverter()
            logger.debug("DoclingParser: pipeline initialised (ocr=%s)", self.ocr_enabled)
        return self._pipeline

    def _extract_tables(self, doc: Any) -> list[dict]:
        """Extract tables from a Docling document object."""
        tables: list[dict] = []
        for i, table in enumerate(getattr(doc, "tables", [])):
            entry: dict = {
                "index": i,
                "caption": getattr(table, "caption", ""),
            }
            # Export to dict if possible (pandas DataFrame → dict)
            if hasattr(table, "export_to_dataframe"):
                try:
                    entry["data"] = table.export_to_dataframe().to_dict(orient="records")
                except Exception:
                    entry["data"] = {}
            tables.append(entry)
        return tables

    def _extract_sections(self, doc: Any) -> list[dict]:
        """Extract logical sections from document headings."""
        sections: list[dict] = []
        for item in getattr(doc, "body", []):
            label = getattr(item, "label", "")
            if label in ("section_header", "title"):
                sections.append(
                    {
                        "heading": getattr(item, "text", ""),
                        "level": getattr(item, "level", 1),
                    }
                )
        return sections

    def _detect_doc_type(self, path: Path, content: str) -> str:
        """Heuristic document type detection based on filename and content."""
        name_lower = path.stem.lower()
        content_lower = content.lower()

        if any(k in content_lower for k in ["tiss", "ans xml", "lote guid"]):
            return "tiss"
        if any(k in content_lower for k in ["tuss", "procedimento", "código tuss"]):
            return "tuss"
        if any(k in name_lower for k in ["convenio", "convênio", "plano", "operadora"]):
            return "insurance"
        if any(k in name_lower for k in ["protocolo", "protocol"]):
            return "protocol"
        if any(k in name_lower for k in ["contrato", "contract", "termo"]):
            return "contract"
        if any(k in name_lower for k in ["faq", "perguntas", "duvidas"]):
            return "faq"
        if any(k in name_lower for k in ["manual", "procedimento", "instrucao"]):
            return "manual"
        return "document"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def parse(self, path: Path) -> ParsedDocument:
        """Parse a document using Docling.

        Runs the synchronous Docling pipeline in a thread executor to
        avoid blocking the asyncio event loop.

        Args:
            path: Path to the file to parse.

        Returns:
            ParsedDocument with full content, tables, and metadata.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If Docling cannot convert the file.
        """
        if not path.exists():
            raise FileNotFoundError(f"Document not found: {path}")
        if not self.supports(path):
            raise ValueError(f"DoclingParser does not support '{path.suffix}' files")

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._sync_parse, path)

    def _sync_parse(self, path: Path) -> ParsedDocument:
        """Synchronous parsing — always call via run_in_executor."""
        logger.info("DoclingParser: parsing %s", path.name)
        converter = self._get_pipeline()

        result = converter.convert(str(path))
        doc = result.document

        # Export to Markdown for clean text representation
        content: str = doc.export_to_markdown()

        tables = self._extract_tables(doc)
        sections = self._extract_sections(doc)

        num_pages: int | None = getattr(doc, "num_pages", None)

        return ParsedDocument(
            content=content,
            title=path.stem.replace("_", " ").replace("-", " ").title(),
            source_path=str(path),
            doc_type=self._detect_doc_type(path, content),
            metadata={
                "parser": "docling",
                "ocr_enabled": self.ocr_enabled,
                "table_extraction": self.table_extraction,
                "filename": path.name,
                "file_size_bytes": path.stat().st_size,
            },
            pages=num_pages,
            tables=tables if tables else None,
            sections=sections if sections else None,
        )
