"""Ingestion pipelines — orchestrate parse → clean → chunk → embed → store."""

from .ingest_pipeline import IngestPipeline, IngestResult

__all__ = ["IngestPipeline", "IngestResult"]
