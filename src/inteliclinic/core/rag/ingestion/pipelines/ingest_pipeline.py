"""Document ingestion pipeline: Parse → Clean → Chunk → Embed → Store.

Usage (per-clinic deploy):
    from inteliclinic.core.rag.ingestion.pipelines import IngestPipeline

    pipeline = IngestPipeline.from_config(clinic_config)

    # Ingest a single PDF
    result = await pipeline.ingest(Path("convenio_unimed.pdf"))

    # Ingest all docs in a clinic knowledge directory
    results = await pipeline.ingest_directory(Path("clinic/knowledge/"))

    # Reprocess an existing document (e.g. after parser upgrade)
    result = await pipeline.reingest(source_path="convenio_unimed.pdf")

Note:
    The engine is GLOBAL (core). The documents are LOCAL to each clinic deploy.
    Each clinic has its own collection in Qdrant, configured via clinic_id.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".pptx", ".html", ".adoc", ".md", ".txt"}


@dataclass
class IngestResult:
    """Result of ingesting a single document."""

    doc_id: str
    source_path: str
    chunks_created: int
    doc_type: str
    success: bool
    error: str | None = None
    metadata: dict = field(default_factory=dict)


class IngestPipeline:
    """Full document ingestion pipeline for a clinic deploy.

    Attributes:
        parsers:    Ordered list of BaseParser instances. First match wins.
        chunker:    TextChunker or SemanticChunker instance.
        store:      LlamaIndexStore (backed by Qdrant) for this clinic.
    """

    def __init__(
        self,
        parsers: list,
        chunker,
        store,
        metadata_enrichers: list | None = None,
        max_concurrent: int = 4,
    ):
        self.parsers = parsers
        self.chunker = chunker
        self.store = store
        self.metadata_enrichers = metadata_enrichers or []
        self.max_concurrent = max_concurrent
        self._semaphore = asyncio.Semaphore(max_concurrent)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def ingest(
        self,
        path: Path,
        doc_type: str | None = None,
        extra_metadata: dict | None = None,
    ) -> IngestResult:
        """Ingest a single document into the clinic knowledge base."""
        async with self._semaphore:
            return await self._ingest_one(path, doc_type, extra_metadata)

    async def ingest_directory(
        self,
        directory: Path,
        glob_pattern: str = "**/*",
        recursive: bool = True,
    ) -> list[IngestResult]:
        """Ingest all supported documents in a directory concurrently."""
        files = [
            f
            for f in directory.glob(glob_pattern)
            if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS
        ]
        if not files:
            logger.warning("No supported documents found in %s", directory)
            return []

        logger.info("Ingesting %d documents from %s", len(files), directory)
        tasks = [self._ingest_one(f) for f in files]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        out: list[IngestResult] = []
        for path, result in zip(files, results):
            if isinstance(result, Exception):
                out.append(
                    IngestResult(
                        doc_id="",
                        source_path=str(path),
                        chunks_created=0,
                        doc_type="unknown",
                        success=False,
                        error=str(result),
                    )
                )
            else:
                out.append(result)

        succeeded = sum(1 for r in out if r.success)
        logger.info("Ingestion complete: %d/%d succeeded", succeeded, len(out))
        return out

    async def reingest(self, source_path: str) -> IngestResult:
        """Re-parse and re-index an existing document (e.g. after parser upgrade)."""
        path = Path(source_path)
        if not path.exists():
            return IngestResult(
                doc_id="",
                source_path=source_path,
                chunks_created=0,
                doc_type="unknown",
                success=False,
                error=f"File not found: {source_path}",
            )
        logger.info("Re-ingesting %s", source_path)
        return await self._ingest_one(path)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _ingest_one(
        self,
        path: Path,
        doc_type: str | None = None,
        extra_metadata: dict | None = None,
    ) -> IngestResult:
        try:
            parser = self._select_parser(path)
            logger.debug("Parsing %s with %s", path.name, parser.name)

            parsed = await parser.parse(path)
            if doc_type:
                parsed.doc_type = doc_type
            if extra_metadata:
                parsed.metadata.update(extra_metadata)

            # Apply metadata enrichers (e.g. date extraction, clinic_id tagging)
            for enricher in self.metadata_enrichers:
                parsed.metadata = enricher.enrich(parsed.metadata, parsed.content)

            chunks = self.chunker.chunk_document(parsed)
            if not chunks:
                logger.warning("No chunks produced from %s", path.name)

            # TODO: embed chunks and upsert into self.store
            # from llama_index.core import Document as LIDocument
            # li_docs = [LIDocument(text=c.text, metadata=c.metadata) for c in chunks]
            # self.store.add_documents(li_docs)

            doc_id = _stable_id(str(path))
            logger.info("Ingested %s → %d chunks (id=%s)", path.name, len(chunks), doc_id)

            return IngestResult(
                doc_id=doc_id,
                source_path=str(path),
                chunks_created=len(chunks),
                doc_type=parsed.doc_type,
                success=True,
                metadata=parsed.metadata,
            )

        except Exception as exc:
            logger.exception("Failed to ingest %s: %s", path, exc)
            return IngestResult(
                doc_id="",
                source_path=str(path),
                chunks_created=0,
                doc_type=doc_type or "unknown",
                success=False,
                error=str(exc),
            )

    def _select_parser(self, path: Path):
        for parser in self.parsers:
            if parser.supports(path):
                return parser
        raise ValueError(
            f"No parser registered for '{path.suffix}'. "
            f"Available parsers: {[p.name for p in self.parsers]}"
        )

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_config(cls, config: dict) -> "IngestPipeline":
        """Build an IngestPipeline from a clinic configuration dict.

        Expected config keys:
            qdrant_url:        Qdrant server URL
            clinic_id:         Unique identifier for this clinic deploy
            chunk_size:        Target chunk character size (default 512)
            chunk_overlap:     Overlap between chunks (default 64)
            chunker_strategy:  "fixed" | "semantic" (default "semantic")
            ocr_enabled:       Enable OCR in Docling (default True)
        """
        from ..parsers.docling_parser import DoclingParser
        from ..parsers.markdown_parser import MarkdownParser
        from ..chunking.chunkers import SemanticChunker, TextChunker

        parsers = [
            DoclingParser(
                ocr_enabled=config.get("ocr_enabled", True),
                table_extraction=config.get("table_extraction", True),
            ),
            MarkdownParser(),
        ]

        strategy = config.get("chunker_strategy", "semantic")
        if strategy == "semantic":
            chunker = SemanticChunker(
                max_chunk_size=config.get("chunk_size", 800),
                min_chunk_size=config.get("min_chunk_size", 150),
            )
        else:
            chunker = TextChunker(
                chunk_size=config.get("chunk_size", 512),
                chunk_overlap=config.get("chunk_overlap", 64),
            )

        # Store is optional during dry-run / testing
        store = None
        if config.get("qdrant_url") and config.get("clinic_id"):
            from ...indexes.llamaindex_store import LlamaIndexStore

            store = LlamaIndexStore.from_config(config)

        return cls(parsers=parsers, chunker=chunker, store=store)


def _stable_id(path: str) -> str:
    """Generate a stable document ID from its path."""
    import hashlib

    return hashlib.sha256(path.encode()).hexdigest()[:16]
