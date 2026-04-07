"""Base parser interface — allows pluggable document parsers beyond Docling."""
from abc import ABC, abstractmethod
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class ParsedDocument:
    """Result of parsing a document."""

    content: str
    title: str
    source_path: str
    doc_type: str  # "pdf", "docx", "md", "txt", "tiss", "tuss", "contract", "protocol", "faq"
    metadata: dict
    pages: int | None = None
    tables: list[dict] | None = None  # Extracted tables (for TISS/TUSS)
    sections: list[dict] | None = None  # Logical sections

    def word_count(self) -> int:
        """Approximate word count of the parsed content."""
        return len(self.content.split())

    def is_empty(self) -> bool:
        """Return True if the document has no meaningful content."""
        return not self.content or not self.content.strip()

    def to_metadata_dict(self) -> dict:
        """Flat metadata dict suitable for embedding storage."""
        return {
            "title": self.title,
            "source_path": self.source_path,
            "doc_type": self.doc_type,
            "pages": self.pages,
            "has_tables": bool(self.tables),
            **self.metadata,
        }


class BaseParser(ABC):
    """Abstract base parser. Implement for each document type.

    All parsers must be async-safe. Heavy I/O (e.g., OCR) should be run
    in an executor to avoid blocking the event loop.
    """

    @abstractmethod
    async def parse(self, path: Path) -> ParsedDocument:
        """Parse a document and return structured content.

        Args:
            path: Absolute path to the document file.

        Returns:
            ParsedDocument with extracted content and metadata.

        Raises:
            FileNotFoundError: If the path does not exist.
            ValueError: If the file cannot be parsed by this parser.
        """
        ...

    @abstractmethod
    def supports(self, path: Path) -> bool:
        """Return True if this parser handles the given file type.

        Uses file extension to determine compatibility.
        """
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Parser name for logging and debugging."""
        ...

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r}>"
