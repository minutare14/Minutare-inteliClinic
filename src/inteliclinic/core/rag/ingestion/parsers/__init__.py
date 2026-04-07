"""Document parsers — pluggable interface for extracting structured content from files.

Available parsers:
    - BaseParser      : Abstract base class all parsers must implement
    - DoclingParser   : Primary parser using Docling (PDF, DOCX, PPTX, HTML)
    - MarkdownParser  : Lightweight parser for .md and .txt files

Parser selection is automatic based on file extension via BaseParser.supports().
The IngestPipeline iterates registered parsers and picks the first match.
"""

from .base_parser import BaseParser, ParsedDocument
from .docling_parser import DoclingParser
from .markdown_parser import MarkdownParser

__all__ = [
    "BaseParser",
    "ParsedDocument",
    "DoclingParser",
    "MarkdownParser",
]
