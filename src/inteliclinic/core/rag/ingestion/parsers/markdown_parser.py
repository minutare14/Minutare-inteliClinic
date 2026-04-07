"""Lightweight parser for Markdown and plain-text documents.

Handles .md and .txt files by reading the raw content directly —
no heavy external dependencies required.

Sections are detected from Markdown headings (# / ## / ###).
This is used for internal knowledge bases, FAQs, and operational
procedures authored as Markdown files.
"""
from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path

from .base_parser import BaseParser, ParsedDocument

logger = logging.getLogger(__name__)

MARKDOWN_EXTENSIONS = {".md", ".markdown"}
TEXT_EXTENSIONS = {".txt"}
SUPPORTED_EXTENSIONS = MARKDOWN_EXTENSIONS | TEXT_EXTENSIONS

# Regex for Markdown headings: # H1, ## H2, ### H3 …
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)", re.MULTILINE)


class MarkdownParser(BaseParser):
    """Parser for Markdown (.md, .markdown) and plain-text (.txt) files.

    Does not require any external library. Reads files with UTF-8 encoding,
    falling back to latin-1 if necessary (common in older Brazilian documents).

    Section detection:
        Scans for Markdown headings and records them as structured sections
        so the chunker can split on logical boundaries.
    """

    def __init__(self, strip_html: bool = True) -> None:
        """
        Args:
            strip_html: If True, remove any inline HTML tags from the content.
        """
        self.strip_html = strip_html

    @property
    def name(self) -> str:
        return "markdown"

    def supports(self, path: Path) -> bool:
        """Return True for .md, .markdown, and .txt files."""
        return path.suffix.lower() in SUPPORTED_EXTENSIONS

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _read_file(self, path: Path) -> str:
        """Read text file with graceful encoding fallback."""
        try:
            return path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            logger.warning(
                "MarkdownParser: UTF-8 failed for %s, retrying with latin-1", path.name
            )
            return path.read_text(encoding="latin-1")

    def _strip_html_tags(self, text: str) -> str:
        """Remove HTML tags from text using a simple regex."""
        return re.sub(r"<[^>]+>", "", text)

    def _extract_sections(self, content: str) -> list[dict]:
        """Extract Markdown headings as document sections."""
        sections: list[dict] = []
        for match in _HEADING_RE.finditer(content):
            level = len(match.group(1))  # number of '#' chars
            heading = match.group(2).strip()
            sections.append(
                {
                    "heading": heading,
                    "level": level,
                    "char_offset": match.start(),
                }
            )
        return sections

    def _detect_doc_type(self, path: Path, content: str) -> str:
        """Infer document type from filename and content keywords."""
        name_lower = path.stem.lower()
        content_lower = content.lower()

        if any(k in name_lower for k in ["faq", "perguntas", "duvidas"]):
            return "faq"
        if any(k in name_lower for k in ["protocolo", "protocol"]):
            return "protocol"
        if any(k in name_lower for k in ["manual", "instrucao", "procedimento"]):
            return "manual"
        if any(k in name_lower for k in ["contrato", "contract", "termo"]):
            return "contract"
        if any(k in content_lower for k in ["convenio", "convênio", "operadora"]):
            return "insurance"
        return "md" if path.suffix.lower() in MARKDOWN_EXTENSIONS else "txt"

    def _infer_title(self, path: Path, content: str) -> str:
        """Try to extract title from the first H1 heading, else use filename."""
        first_h1 = _HEADING_RE.search(content)
        if first_h1 and len(first_h1.group(1)) == 1:
            return first_h1.group(2).strip()
        return path.stem.replace("_", " ").replace("-", " ").title()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def parse(self, path: Path) -> ParsedDocument:
        """Parse a Markdown or plain-text file.

        Reading is synchronous but fast (no OCR / ML), so we run it in
        an executor for consistency with other parsers.

        Args:
            path: Path to the .md or .txt file.

        Returns:
            ParsedDocument with content, sections, and metadata.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If the file extension is not supported.
        """
        if not path.exists():
            raise FileNotFoundError(f"Document not found: {path}")
        if not self.supports(path):
            raise ValueError(f"MarkdownParser does not support '{path.suffix}' files")

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._sync_parse, path)

    def _sync_parse(self, path: Path) -> ParsedDocument:
        """Synchronous parsing logic — call via run_in_executor."""
        logger.info("MarkdownParser: parsing %s", path.name)

        content = self._read_file(path)

        if self.strip_html and path.suffix.lower() in MARKDOWN_EXTENSIONS:
            content = self._strip_html_tags(content)

        sections = self._extract_sections(content)
        title = self._infer_title(path, content)

        return ParsedDocument(
            content=content,
            title=title,
            source_path=str(path),
            doc_type=self._detect_doc_type(path, content),
            metadata={
                "parser": "markdown",
                "encoding": "utf-8",
                "filename": path.name,
                "file_size_bytes": path.stat().st_size,
                "line_count": content.count("\n"),
            },
            pages=None,  # No page concept for markdown
            tables=None,
            sections=sections if sections else None,
        )
