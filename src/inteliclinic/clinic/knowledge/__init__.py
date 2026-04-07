"""Clinic knowledge base — local documents indexed into the RAG for this deploy.

This directory contains the documents specific to this clinic:
    - Insurance coverage tables (PDFs, Excel)
    - Internal FAQs and operational manuals
    - Medical protocols approved by the medical director
    - TISS/TUSS tables for this clinic's specialties
    - Pricing tables (particular and per-insurance)
    - Internal regulations and policies

How documents are indexed:
    Documents placed in this directory are processed by:
        IngestPipeline → Docling parser → SemanticChunker → LlamaIndex → Qdrant

    Run: python scripts/ingest_docs.py --source src/inteliclinic/clinic/knowledge/

Note:
    The Qdrant collection is EXCLUSIVE to this clinic (keyed by clinic_id).
    Documents from one clinic deploy are never mixed with another.

Global documents (common to all clinics):
    If a document applies to all clinic deploys (e.g. CFM regulations),
    place it in docs/knowledge/global/ and ingest separately.
"""
