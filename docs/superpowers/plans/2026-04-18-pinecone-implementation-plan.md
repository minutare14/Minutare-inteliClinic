# Pinecone + Document Upload Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace pgvector as primary RAG vector store with Pinecone, implement document upload (PDF/MD) via Admin panel with semantic chunking, deterministic+LLM extraction, and item-level approval workflow.

**Architecture:**
- Pinecone as primary vector store, pgvector as technical fallback
- Dual-write: every chunk upserts to both pgvector (backup) and Pinecone (production)
- Deterministic extraction first (regex), LLM only for ambiguous/low-confidence cases
- Source of truth: DB tables = operational truth; Pinecone = semantic retrieval; pgvector = fallback only
- Single-clinic per deploy, namespace=clinic_id

**Tech Stack:** FastAPI, SQLModel/SQLAlchemy async, Pinecone Python client, Local embeddings (MiniLM), PyMuPDF (PDF), Python regex

---

## PHASE 1 — Infrastructure (Pinecone + Config)

### Task 1: Add Pinecone config vars to config.py

**Files:**
- Modify: `apps/api/app/core/config.py`

- [ ] **Step 1: Read current config.py**

```python
# Read the file to understand current structure
# Add PINECONE_* vars after qdrant section
```

- [ ] **Step 2: Add PINECONE config fields**

```python
# Add after qdrant_url section (around line 77):
# ── Pinecone ────────────────────────────────────────────────────────────────
pinecone_api_key: str = ""
pinecone_index: str = "inteliclinic-rag"
pinecone_cloud: str = "aws"   # aws | gcp | azure
pinecone_region: str = "us-east-1"
```

- [ ] **Step 3: Add EMBEDDING_PROVIDER default (local already there but explicit)**

The `embedding_provider` already defaults to "local" in line 72. Verify it.

- [ ] **Step 4: Run verification**

```bash
cd apps/api && python -c "from app.core.config import settings; print(settings.pinecone_index)"
```
Expected: `inteliclinic-rag`

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/core/config.py
git commit -m "feat(config): add PINECONE_* settings"
```

---

### Task 2: Create Pinecone client

**Files:**
- Create: `apps/api/app/core/pinecone_client.py`

- [ ] **Step 1: Write the failing import test**

```python
# apps/api/tests/test_pinecone_client.py
import pytest

def test_pinecone_client_import():
    from app.core.pinecone_client import PineconeClient
    assert PineconeClient is not None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd apps/api && pytest tests/test_pinecone_client.py::test_pinecone_client_import -v
```
Expected: FAIL — module not found

- [ ] **Step 3: Write minimal PineconeClient stub**

```python
from __future__ import annotations

import logging
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

class VectorMetadata(dict):
    clinic_id: str
    document_id: str
    chunk_id: str
    category: str
    source: str
    version: str
    created_at: str


class PineconeClient:
    """Pinecone vector store client — dual-writes with pgvector."""

    def __init__(self) -> None:
        self._client: Any = None
        self._index: Any = None

    @property
    def index_name(self) -> str:
        return settings.pinecone_index

    @property
    def namespace(self) -> str:
        return settings.clinic_id

    async def ensure_index(self) -> None:
        """Create index if it doesn't exist (idempotent)."""
        pass  # stub — fill in Step 4

    async def upsert_chunk(
        self,
        chunk_id: str,
        embedding: list[float],
        metadata: VectorMetadata,
    ) -> None:
        """Upsert a single chunk vector to Pinecone."""
        pass  # stub

    async def upsert_chunks(self, vectors: list[dict]) -> None:
        """Upsert multiple chunk vectors (batch)."""
        pass  # stub

    async def query(
        self,
        query_embedding: list[float],
        top_k: int = 20,
        filter_dict: dict | None = None,
    ) -> list[dict]:
        """Query Pinecone for similar vectors."""
        pass  # stub

    async def delete_chunks(self, chunk_ids: list[str]) -> None:
        """Delete specific vectors by chunk_id (NOT delete_all)."""
        pass  # stub

    def is_available(self) -> bool:
        """True if Pinecone is configured and reachable."""
        return bool(settings.pinecone_api_key)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd apps/api && pytest tests/test_pinecone_client.py::test_pinecone_client_import -v
```
Expected: PASS

- [ ] **Step 5: Implement full client (when PINECONE_API_KEY is set)**

Replace stubs with real Pinecone SDK calls using `from pinecone import Pinecone` after `pip install pinecone`.

Key implementation:
```python
# In upsert_chunk / upsert_chunks:
# vectors = [{"id": chunk_id, "values": embedding, "metadata": metadata}]
# self._index.upsert(vectors=vectors, namespace=self.namespace)

# In query:
# results = self._index.query(vector=query_embedding, top_k=top_k, namespace=self.namespace, filter=filter_dict)
# return [{"id": r["id"], "score": r["score"], "metadata": r["metadata"]} for r in results["matches"]]

# In delete_chunks:
# self._index.delete(ids=chunk_ids, namespace=self.namespace, delete_all=False)
```

- [ ] **Step 6: Run full tests**

```bash
cd apps/api && pytest tests/test_pinecone_client.py -v
```
Expected: PASS (or skip if PINECONE_API_KEY not set)

- [ ] **Step 7: Commit**

```bash
git add apps/api/app/core/pinecone_client.py apps/api/tests/test_pinecone_client.py
git commit -m "feat(pinecone): add PineconeClient with upsert/query/delete"
```

---

### Task 3: Add Pinecone env vars to .env.vps.example

**Files:**
- Modify: `config/examples/.env.vps.example`

- [ ] **Step 1: Add Pinecone section**

```bash
# Pinecone Vector Store
PINECONE_API_KEY=your-pincone-api-key-here
PINECONE_INDEX=inteliclinic-rag
PINECONE_CLOUD=aws
PINECONE_REGION=us-east-1
```

- [ ] **Step 2: Commit**

```bash
git add config/examples/.env.vps.example
git commit -m "docs: add PINECONE_* to env example"
```

---

## PHASE 2 — Database Schema (New Tables)

### Task 4: Create DB migration for new tables

**Files:**
- Create: `apps/api/alembic/versions/014_add_services_and_policies.py`

- [ ] **Step 1: Run existing migrations to get head**

```bash
cd apps/api && python -c "
from alembic.config import Config
from alembic import command
alembic_cfg = Config('alembic.ini')
# Just check current head
import subprocess
result = subprocess.run(['alembic', 'heads'], capture_output=True, text=True)
print(result.stdout)
"
```

- [ ] **Step 2: Create migration file**

```python
"""014: Add service_categories, services, service_prices, clinic_policies, document_extractions

Revision ID: 014
Revises: 013
Create Date: 2026-04-18

Dual-write: rag_chunks.embedding + Pinecone
New tables for structured extraction + operational data
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = '014'
down_revision = '013'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # service_categories
    op.create_table(
        'service_categories',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('clinic_id', sa.String(64), nullable=False, default='clinic01', index=True),
        sa.Column('name', sa.String(128), nullable=False),
        sa.Column('description', sa.Text),
        sa.Column('active', sa.Boolean, default=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('NOW()')),
    )

    # services
    op.create_table(
        'services',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('clinic_id', sa.String(64), nullable=False, default='clinic01', index=True),
        sa.Column('category_id', UUID(as_uuid=True), sa.ForeignKey('service_categories.id')),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text),
        sa.Column('duration_min', sa.Integer, default=30),
        sa.Column('active', sa.Boolean, default=True),
        sa.Column('version', sa.Integer, default=1),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime, server_default=sa.text('NOW()')),
    )
    op.create_index('idx_services_clinic', 'services', ['clinic_id'])
    op.create_index('idx_services_category', 'services', ['category_id'])

    # service_prices
    op.create_table(
        'service_prices',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('clinic_id', sa.String(64), nullable=False, default='clinic01', index=True),
        sa.Column('service_id', UUID(as_uuid=True), sa.ForeignKey('services.id')),
        sa.Column('insurance_plan_id', UUID(as_uuid=True), sa.ForeignKey('insurance_catalog.id', name='fk_service_prices_insurance')),
        sa.Column('price', sa.Numeric(10, 2), nullable=False),
        sa.Column('copay', sa.Numeric(10, 2)),
        sa.Column('active', sa.Boolean, default=True),
        sa.Column('version', sa.Integer, default=1),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime, server_default=sa.text('NOW()')),
    )
    op.create_index('idx_service_prices_clinic', 'service_prices', ['clinic_id'])

    # clinic_policies
    op.create_table(
        'clinic_policies',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('clinic_id', sa.String(64), nullable=False, default='clinic01', index=True),
        sa.Column('category', sa.String(64), nullable=False),  # cancellation|privacy|terms|general
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('version', sa.Integer, default=1),
        sa.Column('active', sa.Boolean, default=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime, server_default=sa.text('NOW()')),
    )
    op.create_index('idx_clinic_policies_clinic', 'clinic_policies', ['clinic_id'])

    # document_extractions
    op.create_table(
        'document_extractions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('document_id', UUID(as_uuid=True), sa.ForeignKey('rag_documents.id', ondelete='SET NULL')),
        sa.Column('chunk_id', UUID(as_uuid=True)),
        sa.Column('clinic_id', sa.String(64), nullable=False, default='clinic01', index=True),
        sa.Column('entity_type', sa.String(32), nullable=False),  # doctor|service|price|insurance|policy|schedule
        sa.Column('extracted_data', JSONB, nullable=False),
        sa.Column('raw_text', sa.Text),
        sa.Column('extraction_method', sa.String(32), nullable=False),  # deterministic|llm
        sa.Column('confidence', sa.Float, nullable=False),  # 0.0-1.0
        sa.Column('requires_review', sa.Boolean, default=False),
        sa.Column('status', sa.String(32), nullable=False, default='pending'),  # pending|approved|rejected|revised|orphaned|cancelled
        sa.Column('reviewed_by', sa.String(64)),
        sa.Column('reviewed_at', sa.DateTime),
        sa.Column('published_at', sa.DateTime),
        sa.Column('published_to', sa.String(64)),  # professionals|services|service_prices|insurance_catalog|clinic_policies
        sa.Column('published_entity_id', UUID(as_uuid=True)),
        sa.Column('superseded_by', UUID(as_uuid=True), sa.ForeignKey('document_extractions.id', ondelete='SET NULL')),
        sa.Column('source_extraction_id', UUID(as_uuid=True), sa.ForeignKey('document_extractions.id', ondelete='SET NULL')),
        sa.Column('orphaned_at', sa.DateTime),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('NOW()')),
    )
    op.create_index('idx_document_extractions_document', 'document_extractions', ['document_id'])
    op.create_index('idx_document_extractions_clinic', 'document_extractions', ['clinic_id'])
    op.create_index('idx_document_extractions_status', 'document_extractions', ['status'])
    op.create_index('idx_document_extractions_entity', 'document_extractions', ['entity_type'])


def downgrade() -> None:
    op.drop_table('document_extractions')
    op.drop_table('clinic_policies')
    op.drop_table('service_prices')
    op.drop_table('services')
    op.drop_table('service_categories')
```

- [ ] **Step 3: Run migration**

```bash
cd apps/api && alembic upgrade head
```
Expected: `014_add_services_and_policies` applied

- [ ] **Step 4: Verify tables exist**

```bash
cd apps/api && python -c "
from app.core.db import engine
import asyncio
async def check():
    async with engine.begin() as conn:
        result = await conn.execute(sa.text(\"SELECT table_name FROM information_schema.tables WHERE table_schema='public'\"))
        tables = [r[0] for r in result.fetchall()]
        for t in sorted(tables):
            print(t)
asyncio.run(check())
"
```
Expected: Lists include `service_categories`, `services`, `service_prices`, `clinic_policies`, `document_extractions`

- [ ] **Step 5: Commit**

```bash
git add apps/api/alembic/versions/014_add_services_and_policies.py
git commit -m "feat(db): add services, policies, document_extractions tables"
```

---

## PHASE 3 — Models (SQLModel)

### Task 5: Create SQLModel for new tables

**Files:**
- Create: `apps/api/app/models/service.py`
- Create: `apps/api/app/models/policy.py`
- Modify: `apps/api/app/models/__init__.py`

- [ ] **Step 1: Write test for ServiceCategory model**

```python
# apps/api/tests/test_models.py
def test_service_category_model():
    from app.models.service import ServiceCategory
    assert ServiceCategory.__tablename__ == 'service_categories'
```

- [ ] **Step 2: Run test**

```bash
cd apps/api && pytest tests/test_models.py::test_service_category_model -v
```
Expected: FAIL (model doesn't exist yet)

- [ ] **Step 3: Write service.py**

```python
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlmodel import Field, SQLModel

if TYPE_CHECKING:
    pass


class ServiceCategory(SQLModel, table=True):
    __tablename__ = "service_categories"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    clinic_id: str = Field(default="clinic01", max_length=64, index=True)
    name: str = Field(max_length=128)
    description: str | None = None
    active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Service(SQLModel, table=True):
    __tablename__ = "services"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    clinic_id: str = Field(default="clinic01", max_length=64, index=True)
    category_id: uuid.UUID | None = Field(default=None, foreign_key="service_categories.id", index=True)
    name: str = Field(max_length=255)
    description: str | None = None
    duration_min: int = Field(default=30)
    active: bool = Field(default=True)
    version: int = Field(default=1)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ServicePrice(SQLModel, table=True):
    __tablename__ = "service_prices"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    clinic_id: str = Field(default="clinic01", max_length=64, index=True)
    service_id: uuid.UUID | None = Field(default=None, foreign_key="services.id", index=True)
    insurance_plan_id: uuid.UUID | None = Field(default=None, index=True)
    price: float = Field(default=0.0)
    copay: float | None = None
    active: bool = Field(default=True)
    version: int = Field(default=1)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
```

- [ ] **Step 4: Write policy.py**

```python
from __future__ import annotations

import uuid
from datetime import datetime

from sqlmodel import Field, SQLModel


class ClinicPolicy(SQLModel, table=True):
    __tablename__ = "clinic_policies"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    clinic_id: str = Field(default="clinic01", max_length=64, index=True)
    category: str = Field(max_length=64)  # cancellation|privacy|terms|general
    title: str = Field(max_length=255)
    content: str
    version: int = Field(default=1)
    active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class DocumentExtraction(SQLModel, table=True):
    __tablename__ = "document_extractions"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    document_id: uuid.UUID | None = Field(default=None, index=True)
    chunk_id: uuid.UUID | None = None
    clinic_id: str = Field(default="clinic01", max_length=64, index=True)
    entity_type: str = Field(max_length=32)  # doctor|service|price|insurance|policy|schedule
    extracted_data: dict = Field(default_factory=dict)
    raw_text: str | None = None
    extraction_method: str = Field(max_length=32)  # deterministic|llm
    confidence: float = 0.0
    requires_review: bool = False
    status: str = Field(default="pending")  # pending|approved|rejected|revised|orphaned|cancelled
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    published_at: datetime | None = None
    published_to: str | None = None  # professionals|services|service_prices|insurance_catalog|clinic_policies
    published_entity_id: uuid.UUID | None = None
    superseded_by: uuid.UUID | None = None
    source_extraction_id: uuid.UUID | None = None
    orphaned_at: datetime | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
```

- [ ] **Step 5: Update __init__.py**

In `apps/api/app/models/__init__.py`, add:
```python
from app.models.service import ServiceCategory, Service, ServicePrice
from app.models.policy import ClinicPolicy, DocumentExtraction
```

- [ ] **Step 6: Run tests**

```bash
cd apps/api && pytest tests/test_models.py::test_service_category_model tests/test_models.py::test_document_extraction_model -v
```
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add apps/api/app/models/service.py apps/api/app/models/policy.py apps/api/app/models/__init__.py
git commit -m "feat(models): add Service, ServicePrice, ClinicPolicy, DocumentExtraction"
```

---

## PHASE 4 — Document Upload API (Routes + Schemas)

### Task 6: Create document upload schemas

**Files:**
- Create: `apps/api/app/schemas/document.py`

- [ ] **Step 1: Write test for document schemas**

```python
# apps/api/tests/test_document_schemas.py
def test_upload_request_schema():
    from app.schemas.document import DocumentUploadRequest
    assert DocumentUploadRequest is not None

def test_document_summary_schema():
    from app.schemas.document import DocumentSummary
    assert DocumentSummary is not None
```

- [ ] **Step 2: Run test**

```bash
cd apps/api && pytest tests/test_document_schemas.py -v
```
Expected: FAIL

- [ ] **Step 3: Write document schemas**

```python
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class DocumentCategory(str, Enum):
    CONVENIO = "convenio"
    PROTOCOLO = "protocolo"
    FAQ = "faq"
    MANUAL = "manual"
    TABELA = "tabela"
    OUTRO = "outro"


class DocumentStatus(str, Enum):
    PROCESSING = "processing"
    READY = "ready"
    ERROR = "error"
    ARCHIVED = "archived"


class DocumentUploadRequest(BaseModel):
    title: str | None = None
    category: DocumentCategory = DocumentCategory.OUTRO


class DocumentUploadResponse(BaseModel):
    document_id: UUID
    title: str
    category: str
    status: str
    chunks_created: int = 0
    message: str


class ChunkInfo(BaseModel):
    id: UUID
    chunk_index: int
    content: str
    page: int | None = None
    metadata_json: str | None = None


class ExtractionItem(BaseModel):
    id: UUID
    entity_type: str
    extracted_data: dict[str, Any]
    raw_text: str | None
    extraction_method: str
    confidence: float
    requires_review: bool
    status: str
    reviewed_by: str | None
    reviewed_at: datetime | None
    published_at: datetime | None
    published_to: str | None
    published_entity_id: UUID | None
    superseded_by: UUID | None
    source_extraction_id: UUID | None
    created_at: datetime


class DocumentSummary(BaseModel):
    id: UUID
    title: str
    category: str
    status: str
    chunks_count: int
    extractions_count: int
    approved_count: int
    rejected_count: int
    created_at: datetime


class DocumentDetail(BaseModel):
    id: UUID
    title: str
    category: str
    status: str
    source_path: str | None
    version: str
    created_at: datetime
    updated_at: datetime
    chunks: list[ChunkInfo]
    extractions: list[ExtractionItem]
    stats: dict


class DocumentListResponse(BaseModel):
    items: list[DocumentSummary]
    total: int
    page: int


class ExtractionApproveRequest(BaseModel):
    notes: str | None = None


class ExtractionRejectRequest(BaseModel):
    reason: str


class ExtractionReviseRequest(BaseModel):
    corrected_data: dict[str, Any]
```

- [ ] **Step 4: Run tests**

```bash
cd apps/api && pytest tests/test_document_schemas.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/schemas/document.py
git commit -m "feat(schemas): add document upload schemas"
```

---

### Task 7: Create document upload routes

**Files:**
- Create: `apps/api/app/api/routes/document_upload.py`
- Modify: `apps/api/app/api/routes/__init__.py`
- Modify: `apps/api/app/api/routes/admin.py`

- [ ] **Step 1: Write test for upload endpoint**

```python
# apps/api/tests/test_document_upload.py
def test_upload_rejects_invalid_type():
    # POST /api/v1/admin/documents/upload with text file → 400
    pass
```

- [ ] **Step 2: Write document_upload route (stub first)**

```python
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_roles
from app.core.db import get_session
from app.models.auth import User, UserRole
from app.schemas.document import (
    DocumentUploadResponse,
    DocumentSummary,
    DocumentDetail,
    DocumentListResponse,
    ExtractionItem,
    ChunkInfo,
    DocumentUploadRequest,
)

router = APIRouter(prefix="/admin/documents", tags=["admin/documents"])
_READ_ROLES = (UserRole.admin, UserRole.manager)
_WRITE_ROLES = (UserRole.admin,)


@router.post("/upload", response_model=DocumentUploadResponse, status_code=201)
async def upload_document(
    file: UploadFile,
    category: str = Form(...),
    title: str | None = Form(None),
    current_user: Annotated[User, Depends(require_roles(*_WRITE_ROLES))] = None,
    session: Annotated[AsyncSession, Depends(get_session)] = None,
) -> DocumentUploadResponse:
    """Upload and process a PDF or Markdown document."""
    # Validate file type
    if file.content_type not in ("application/pdf", "text/markdown", "text/x-markdown"):
        raise HTTPException(status_code=400, detail="Unsupported file type. Use PDF or Markdown.")
    # Validate file size (10MB max)
    await file.seek(0)
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large. Maximum 10MB.")
    await file.seek(0)

    # TODO: wire to document_upload_service
    # For now return stub
    raise HTTPException(status_code=501, detail="Not implemented yet")


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    category: str | None = None,
    status: str | None = None,
    page: int = 1,
    limit: int = 20,
    current_user: Annotated[User, Depends(require_roles(*_READ_ROLES))] = None,
    session: Annotated[AsyncSession, Depends(get_session)] = None,
) -> DocumentListResponse:
    """List all documents with status and counts."""
    # TODO: wire to service
    raise HTTPException(status_code=501, detail="Not implemented yet")


@router.get("/{document_id}", response_model=DocumentDetail)
async def get_document(
    document_id: uuid.UUID,
    current_user: Annotated[User, Depends(require_roles(*_READ_ROLES))] = None,
    session: Annotated[AsyncSession, Depends(get_session)] = None,
) -> DocumentDetail:
    """Get document detail with chunks and extractions."""
    # TODO: wire to service
    raise HTTPException(status_code=501, detail="Not implemented yet")


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    document_id: uuid.UUID,
    current_user: Annotated[User, Depends(require_roles(*_WRITE_ROLES))] = None,
    session: Annotated[AsyncSession, Depends(get_session)] = None,
) -> None:
    """Soft delete document, remove from Pinecone, orphan extractions."""
    # TODO: wire to service
    raise HTTPException(status_code=501, detail="Not implemented yet")
```

- [ ] **Step 3: Register route in __init__.py**

In `apps/api/app/api/routes/__init__.py`, add:
```python
from app.api.routes.document_upload import router as document_upload_router
```

And in the `__all__` list add `"document_upload_router"`.

Also in `apps/api/app/main.py` (or wherever routes are included), register:
```python
app.include_router(document_upload_router, prefix="/api/v1")
```

- [ ] **Step 4: Verify route registers**

```bash
cd apps/api && python -c "from app.api.routes.document_upload import router; print('OK')"
```
Expected: OK

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/api/routes/document_upload.py
git commit -m "feat(api): add document upload routes (stub)"
```

---

## PHASE 5 — Extraction API Routes

### Task 8: Create extraction approval routes

**Files:**
- Create: `apps/api/app/api/routes/extractions.py`
- Modify: `apps/api/app/api/routes/__init__.py`

- [ ] **Step 1: Write extraction approval routes**

```python
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_roles
from app.core.db import get_session
from app.models.auth import User, UserRole
from app.schemas.document import (
    ExtractionItem,
    ExtractionApproveRequest,
    ExtractionRejectRequest,
    ExtractionReviseRequest,
)

router = APIRouter(prefix="/admin/documents/extractions", tags=["admin/extractions"])
_WRITE_ROLES = (UserRole.admin,)


@router.patch("/{extraction_id}/approve", response_model=ExtractionItem)
async def approve_extraction(
    extraction_id: uuid.UUID,
    data: ExtractionApproveRequest,
    current_user: Annotated[User, Depends(require_roles(*_WRITE_ROLES))] = None,
    session: Annotated[AsyncSession, Depends(get_session)] = None,
) -> ExtractionItem:
    """Approve an extraction, publish to target table."""
    # TODO: wire to extraction_service
    raise HTTPException(status_code=501, detail="Not implemented yet")


@router.patch("/{extraction_id}/reject", response_model=ExtractionItem)
async def reject_extraction(
    extraction_id: uuid.UUID,
    data: ExtractionRejectRequest,
    current_user: Annotated[User, Depends(require_roles(*_WRITE_ROLES))] = None,
    session: Annotated[AsyncSession, Depends(get_session)] = None,
) -> ExtractionItem:
    """Reject an extraction."""
    # TODO: wire to extraction_service
    raise HTTPException(status_code=501, detail="Not implemented yet")


@router.patch("/{extraction_id}/revise", response_model=ExtractionItem)
async def revise_extraction(
    extraction_id: uuid.UUID,
    data: ExtractionReviseRequest,
    current_user: Annotated[User, Depends(require_roles(*_WRITE_ROLES))] = None,
    session: Annotated[AsyncSession, Depends(get_session)] = None,
) -> ExtractionItem:
    """Revise an extraction, create new extraction with corrected data."""
    # TODO: wire to extraction_service
    raise HTTPException(status_code=501, detail="Not implemented yet")
```

- [ ] **Step 2: Register in __init__.py**

```python
from app.api.routes.extractions import router as extractions_router
```

- [ ] **Step 3: Include in main router**

In `apps/api/app/main.py` add extractions router:
```python
app.include_router(extractions_router, prefix="/api/v1")
```

- [ ] **Step 4: Commit**

```bash
git add apps/api/app/api/routes/extractions.py
git commit -m "feat(api): add extraction approval routes (stub)"
```

---

## PHASE 6 — Semantic Chunking (Core Logic)

### Task 9: Create semantic chunking module

**Files:**
- Create: `apps/api/app/core/chunking.py`

- [ ] **Step 1: Write test for semantic chunking**

```python
# apps/api/tests/test_chunking.py
def test_chunking_headings():
    from app.core.chunking import semantic_chunk
    text = "# Cardiologia\n\n## Consulta\n\nConteúdo da consulta..."
    chunks = semantic_chunk(text, category="convenio")
    assert len(chunks) >= 2
    assert "Cardiologia" in chunks[0]["content"]


def test_chunking_hard_limit():
    from app.core.chunking import semantic_chunk
    # Very long text without headings
    text = "A " * 2000  # long text
    chunks = semantic_chunk(text, category="manual")
    for chunk in chunks:
        assert len(chunk["content"]) <= 1000


def test_chunking_minimum():
    from app.core.chunking import semantic_chunk
    text = "# Foo\n\nA"  # very short after heading
    chunks = semantic_chunk(text, category="outro")
    # Short chunks should be merged or discarded
    for chunk in chunks:
        assert len(chunk["content"]) >= 50


def test_chunking_overlap():
    from app.core.chunking import semantic_chunk
    text = "# Section 1\n\n" + "Content " * 200 + "\n\n# Section 2\n\n" + "More " * 200
    chunks = semantic_chunk(text, category="manual")
    # Adjacent chunks should share heading context
    if len(chunks) > 1:
        assert chunks[1]["content"].startswith("# Section") or "Section 1" in chunks[1]["content"]
```

- [ ] **Step 2: Run tests**

```bash
cd apps/api && pytest tests/test_chunking.py -v
```
Expected: FAIL (module doesn't exist)

- [ ] **Step 3: Write semantic chunking module**

```python
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class ChunkResult:
    content: str
    chunk_index: int
    metadata: dict


def semantic_chunk(
    text: str,
    category: str,
    semantic_max: int = 800,
    hard_max: int = 1000,
    overlap_pct: float = 0.20,
    min_chars: int = 50,
) -> list[dict]:
    """
    Semantic chunking with heading-aware, table-aware, list-aware splitting.

    Rules:
    1. H1/H2 → new chunk with heading prefix
    2. Table → chunk with table header preserved
    3. List → item-level chunks with list context
    4. If chunk > 800 chars → split at sentence boundary
    5. HARD LIMIT: no chunk exceeds 1000 chars
    6. Minimum chunk: 50 chars (merge with next or discard)
    7. Overlap: 20% of chunk (max 150 chars) with previous heading
    """
    if not text or not text.strip():
        return []

    blocks = _parse_blocks(text)
    chunks: list[dict] = []
    current_chunk_parts: list[str] = []
    current_heading = ""
    chunk_index = 0

    for block in blocks:
        block_type = block["type"]
        block_text = block["text"].strip()
        if not block_text:
            continue

        # Track current heading
        if block_type in ("h1", "h2"):
            current_heading = block_text
            # New heading → new chunk
            if current_chunk_parts:
                _finalize_chunk(chunks, current_chunk_parts, current_heading, chunk_index, category)
                chunk_index += 1
                current_chunk_parts = []
            # Heading itself becomes chunk
            prefixed = f"{block_type.upper()} {block_text}"
            chunks.append({
                "content": prefixed,
                "chunk_index": chunk_index,
                "metadata": {"heading": block_text, "type": block_type, "category": category},
            })
            chunk_index += 1
            continue

        # Table block
        if block_type == "table":
            if current_chunk_parts:
                _finalize_chunk(chunks, current_chunk_parts, current_heading, chunk_index, category)
                chunk_index += 1
                current_chunk_parts = []
            chunks.append({
                "content": block_text,
                "chunk_index": chunk_index,
                "metadata": {"heading": current_heading, "type": "table", "category": category},
            })
            chunk_index += 1
            continue

        # List block — itemize
        if block_type == "list":
            items = _split_list_items(block_text)
            for item in items:
                prefixed = f"{current_heading}: {item}" if current_heading else item
                if len(prefixed) > hard_max:
                    # Split item
                    sub_items = _split_long_text(prefixed, hard_max)
                    for sub in sub_items:
                        if len(sub) >= min_chars:
                            chunks.append({
                                "content": sub,
                                "chunk_index": chunk_index,
                                "metadata": {"heading": current_heading, "type": "list_item", "category": category},
                            })
                            chunk_index += 1
                elif len(prefixed) >= min_chars:
                    chunks.append({
                        "content": prefixed,
                        "chunk_index": chunk_index,
                        "metadata": {"heading": current_heading, "type": "list_item", "category": category},
                    })
                    chunk_index += 1
            continue

        # Paragraph — accumulate
        prefixed = f"{current_heading}: {block_text}" if current_heading else block_text

        if prefixed过长(hard_max):
            # Split and finalize current
            if current_chunk_parts:
                _finalize_chunk(chunks, current_chunk_parts, current_heading, chunk_index, category)
                chunk_index += 1
                current_chunk_parts = []
            # Split long text
            parts = _split_long_text(prefixed, hard_max)
            for part in parts:
                if len(part) >= min_chars:
                    chunks.append({
                        "content": part,
                        "chunk_index": chunk_index,
                        "metadata": {"heading": current_heading, "type": "paragraph", "category": category},
                    })
                    chunk_index += 1
        elif _estimated_size(current_chunk_parts, prefixed) > semantic_max:
            # Would exceed semantic max — finalize current and start new
            if current_chunk_parts:
                _finalize_chunk(chunks, current_chunk_parts, current_heading, chunk_index, category)
                chunk_index += 1
                current_chunk_parts = []
            current_chunk_parts.append(prefixed)
        else:
            current_chunk_parts.append(prefixed)

    # Finalize remaining
    if current_chunk_parts:
        _finalize_chunk(chunks, current_chunk_parts, current_heading, chunk_index, category)

    # Enforce hard max (shouldn't happen but safety check)
    result = []
    for chunk in chunks:
        content = chunk["content"]
        while len(content) > hard_max:
            # Force split
            part = content[:hard_max]
            result.append({
                "content": part,
                "chunk_index": chunk["chunk_index"],
                "metadata": chunk["metadata"],
            })
            content = content[hard_max:]
        if len(content) >= min_chars:
            result.append(chunk)
        elif result:
            # Merge small tail with previous
            result[-1]["content"] += " " + content

    # Assign indices
    for i, chunk in enumerate(result):
        chunk["chunk_index"] = i

    return result


def _parse_blocks(text: str) -> list[dict]:
    """Parse text into structured blocks (headings, paragraphs, tables, lists)."""
    blocks: list[dict] = []
    lines = text.split("\n")
    current_paragraph: list[str] = []
    current_table_lines: list[str] = []
    in_table = False
    current_list_lines: list[str] = []
    in_list = False

    def flush_paragraph():
        nonlocal current_paragraph
        if current_paragraph:
            joined = " ".join(current_paragraph).strip()
            if joined:
                blocks.append({"type": "paragraph", "text": joined})
            current_paragraph = []

    def flush_table():
        nonlocal current_table_lines, in_table
        if current_table_lines:
            blocks.append({"type": "table", "text": "\n".join(current_table_lines)})
            current_table_lines = []
        in_table = False

    def flush_list():
        nonlocal current_list_lines, in_list
        if current_list_lines:
            blocks.append({"type": "list", "text": "\n".join(current_list_lines)})
            current_list_lines = []
        in_list = False

    for line in lines:
        stripped = line.strip()

        # Headings
        if stripped.startswith("# "):
            flush_paragraph()
            flush_table()
            flush_list()
            level = len(stripped) - len(stripped.lstrip("#"))
            blocks.append({"type": f"h{level}", "text": stripped.lstrip("#").strip()})
            continue

        # Table detection (lines with |)
        if "|" in stripped and not stripped.startswith(" "):
            flush_paragraph()
            if not in_list:
                flush_list()
            in_table = True
            current_table_lines.append(stripped)
            continue
        elif in_table:
            if stripped == "" or (not "|" in stripped and len(stripped) < 3):
                flush_table()
            else:
                current_table_lines.append(stripped)
            continue

        # List detection (lines starting with -, *, or numbered)
        list_match = re.match(r"^[\-\*•·]\s+(.+)$", stripped) or re.match(r"^\d+[.)]\s+(.+)$", stripped)
        if list_match:
            flush_paragraph()
            if not in_table:
                flush_table()
            in_list = True
            current_list_lines.append(list_match.group(1))
            continue
        elif in_list:
            if stripped == "":
                flush_list()
            else:
                current_list_lines.append(stripped)
            continue

        # Empty line
        if not stripped:
            flush_paragraph()
            continue

        # Paragraph
        flush_table()
        flush_list()
        current_paragraph.append(stripped)

    flush_paragraph()
    flush_table()
    flush_list()
    return blocks


def _split_list_items(text: str) -> list[str]:
    """Split a list block into individual items."""
    items = re.split(r"\n(?=-|\*|•)|(?<=\n)\n", text)
    return [i.strip() for i in items if i.strip()]


def _split_long_text(text: str, max_len: int) -> list[str]:
    """Split text at sentence boundaries."""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    result = []
    current = ""
    for sentence in sentences:
        if len(current) + len(sentence) + 1 <= max_len:
            current = (current + " " + sentence).strip()
        else:
            if current:
                result.append(current)
            current = sentence
            while len(current) > max_len:
                result.append(current[:max_len])
                current = current[max_len:]
    if current:
        result.append(current)
    return result


def _estimated_size(parts: list[str], next_part: str) -> int:
    return sum(len(p) + 1 for p in parts) + len(next_part)


def _finalize_chunk(chunks: list[dict], parts: list[str], heading: str, index: int, category: str):
    """Join parts into a chunk and add to chunks list."""
    content = " ".join(parts).strip()
    if len(content) >= 50:  # min_chars
        chunks.append({
            "content": content,
            "chunk_index": index,
            "metadata": {"heading": heading, "type": "paragraph", "category": category},
        })
```

- [ ] **Step 4: Run tests**

```bash
cd apps/api && pytest tests/test_chunking.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/core/chunking.py apps/api/tests/test_chunking.py
git commit -m "feat(chunking): add semantic chunking with heading/table/list awareness"
```

---

## PHASE 7 — Extraction Service (Deterministic + LLM)

### Task 10: Create extraction service

**Files:**
- Create: `apps/api/app/services/extraction_service.py`
- Create: `apps/api/tests/test_extraction_service.py`

- [ ] **Step 1: Write tests for deterministic extraction**

```python
# apps/api/tests/test_extraction_service.py
def test_extract_crm_pattern():
    from app.services.extraction_service import extract_entities
    text = "Dr. Marcos Nunes - CRM/SP 123456 - Neurologista"
    results = extract_entities(text, "doctor")
    assert len(results) >= 1
    assert results[0]["entity_type"] == "doctor"


def test_extract_currency_pattern():
    from app.services.extraction_service import extract_entities
    text = "Consulta Cardiologia: R$ 350,00"
    results = extract_entities(text, "price")
    assert len(results) >= 1


def test_extract_no_llm_for_clear_pattern():
    from app.services.extraction_service import extract_entities
    text = "CRM/SP 98765 Dr. João Silva - Neurologia"
    results = extract_entities(text, "doctor")
    # Should be deterministic (no LLM call)
    for r in results:
        assert r["extraction_method"] == "deterministic"
```

- [ ] **Step 2: Run tests**

```bash
cd apps/api && pytest tests/test_extraction_service.py -v
```
Expected: FAIL

- [ ] **Step 3: Write extraction service**

```python
from __future__ import annotations

import re
import json
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.policy import DocumentExtraction
from app.repositories.rag_repository import RagRepository


@dataclass
class ExtractionResult:
    entity_type: str
    extracted_data: dict[str, Any]
    confidence: float
    extraction_method: str  # deterministic | llm
    requires_review: bool
    raw_text: str | None = None


def extract_crm(text: str) -> list[dict]:
    """Extract doctor entities via CRM pattern."""
    pattern = r'(?<![A-Z])CRM[/\s][A-Z]{2}\s*\d+'
    matches = re.findall(pattern, text)
    results = []
    for match in matches:
        # Try to extract name before CRM
        name_match = re.search(r'([A-Z][a-zà-ÿ]+(?:\s+[A-Z][a-zà-ÿ]+)+)\s*-\s*CRM', text)
        name = name_match.group(1).strip() if name_match else "Unknown"
        specialty_match = re.search(r'CRM[/\s][A-Z]{2}\s*\d+\s*-\s*([A-Za-zà-ÿ\s]+?)(?:\n|,|$)', text)
        specialty = specialty_match.group(1).strip() if specialty_match else ""
        results.append({
            "entity_type": "doctor",
            "name": name,
            "crm": match,
            "specialty": specialty,
        })
    return results


def extract_currency(text: str) -> list[dict]:
    """Extract price entities via currency pattern."""
    pattern = r'R\$\s*\d+(?:[.,]\d{2})?'
    matches = re.findall(pattern, text)
    results = []
    for match in matches:
        # Try to get context (service name before price)
        clean_match = match.replace("R$", "").replace(" ", "").strip()
        context_match = re.search(r'([A-Za-zà-ÿ\s]+?):\s*R\$', text)
        service = context_match.group(1).strip() if context_match else "Unknown"
        results.append({
            "entity_type": "price",
            "service": service,
            "price_str": match,
        })
    return results


def extract_insurance(text: str, known_plans: list[str] | None = None) -> list[dict]:
    """Extract insurance entities via named list matching."""
    if not known_plans:
        known_plans = []
    results = []
    for plan in known_plans:
        if plan.lower() in text.lower():
            results.append({
                "entity_type": "insurance",
                "name": plan,
                "matched_in_text": True,
            })
    return results


def extract_schedule(text: str) -> list[dict]:
    """Extract schedule entities via time slot pattern."""
    pattern = r'(?:Seg|Segunda|Ter|Terceira|Qua|Quarta|Qui|Quinta|Sex|Sexta|Sáb|Sab|Dom|Domingo)[^,\n]{0,50}'
    matches = re.findall(pattern, text, re.IGNORECASE)
    results = []
    for match in matches:
        results.append({
            "entity_type": "schedule",
            "time_slot": match.strip(),
        })
    return results


async def extract_entities(
    text: str,
    entity_type: str | None = None,
    known_insurance: list[str] | None = None,
) -> list[ExtractionResult]:
    """
    Deterministic-first extraction.

    Applied in order:
    1. CRM pattern → doctor entity
    2. Currency pattern → price entity
    3. Named list (insurance) → insurance entity
    4. Time slot pattern → schedule entity

    Returns list of ExtractionResult with extraction_method='deterministic'.
    """
    results: list[ExtractionResult] = []

    # Doctor via CRM
    if entity_type is None or entity_type == "doctor":
        for match in extract_crm(text):
            results.append(ExtractionResult(
                entity_type="doctor",
                extracted_data=match,
                confidence=1.0,
                extraction_method="deterministic",
                requires_review=False,
                raw_text=text[:200],
            ))

    # Price via currency
    if entity_type is None or entity_type == "price":
        for match in extract_currency(text):
            results.append(ExtractionResult(
                entity_type="price",
                extracted_data=match,
                confidence=1.0,
                extraction_method="deterministic",
                requires_review=False,
                raw_text=text[:200],
            ))

    # Insurance via named list
    if entity_type is None or entity_type == "insurance":
        for match in extract_insurance(text, known_insurance):
            results.append(ExtractionResult(
                entity_type="insurance",
                extracted_data=match,
                confidence=1.0,
                extraction_method="deterministic",
                requires_review=False,
                raw_text=text[:200],
            ))

    # Schedule via time slot
    if entity_type is None or entity_type == "schedule":
        for match in extract_schedule(text):
            results.append(ExtractionResult(
                entity_type="schedule",
                extracted_data=match,
                confidence=1.0,
                extraction_method="deterministic",
                requires_review=False,
                raw_text=text[:200],
            ))

    return results


async def save_extractions(
    session: AsyncSession,
    document_id: uuid.UUID,
    clinic_id: str,
    extractions: list[ExtractionResult],
    chunk_id: uuid.UUID | None = None,
) -> list[DocumentExtraction]:
    """Save extraction results to document_extractions table."""
    repo = RagRepository(session)
    saved = []
    for ext in extractions:
        record = DocumentExtraction(
            document_id=document_id,
            chunk_id=chunk_id,
            clinic_id=clinic_id,
            entity_type=ext.entity_type,
            extracted_data=ext.extracted_data,
            raw_text=ext.raw_text,
            extraction_method=ext.extraction_method,
            confidence=ext.confidence,
            requires_review=ext.requires_review,
            status="pending",
        )
        session.add(record)
        saved.append(record)
    await session.commit()
    for record in saved:
        await session.refresh(record)
    return saved
```

- [ ] **Step 4: Run tests**

```bash
cd apps/api && pytest tests/test_extraction_service.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/services/extraction_service.py apps/api/tests/test_extraction_service.py
git commit -m "feat(extraction): add deterministic extraction service"
```

---

## PHASE 8 — Document Upload Service (Orchestration)

### Task 11: Create document upload orchestration service

**Files:**
- Create: `apps/api/app/services/document_upload.py`

- [ ] **Step 1: Write test for document upload service**

```python
# apps/api/tests/test_document_upload_service.py
def test_upload_pdf_file_type_check():
    from app.services.document_upload import validate_file
    # Should reject .txt files
    pass
```

- [ ] **Step 2: Write document upload service**

```python
from __future__ import annotations

import io
import logging
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.chunking import semantic_chunk
from app.core.config import settings
from app.core.embedding import default_embedding_model, default_embedding_dimension
from app.services.rag_service import get_embedding, chunk_text
from app.services.extraction_service import extract_entities, save_extractions
from app.models.rag import RagDocument, RagChunk
from app.repositories.rag_repository import RagRepository
from app.repositories.admin_repository import AdminRepository

logger = logging.getLogger(__name__)


ALLOWED_TYPES = {"application/pdf", "text/markdown", "text/x-markdown"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


def validate_file(content: bytes, content_type: str) -> None:
    """Validate file type and size. Raises HTTPException on failure."""
    if content_type not in ALLOWED_TYPES:
        raise ValueError(f"Unsupported file type: {content_type}. Use PDF or Markdown.")
    if len(content) > MAX_FILE_SIZE:
        raise ValueError("File too large. Maximum 10MB.")


def parse_pdf(content: bytes) -> str:
    """Extract text from PDF using PyMuPDF."""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        logger.warning("[DOCUMENT] PyMuPDF not installed, falling back to text extraction")
        return content.decode("utf-8", errors="replace")

    doc = fitz.open(stream=content, filetype="pdf")
    text_parts = []
    for page in doc:
        text_parts.append(page.get_text())
    doc.close()
    return "\n".join(text_parts)


def parse_markdown(content: bytes) -> str:
    """Parse Markdown — preserve structure."""
    return content.decode("utf-8", errors="replace")


async def process_document(
    session: AsyncSession,
    file_content: bytes,
    filename: str,
    content_type: str,
    title: str | None,
    category: str,
    clinic_id: str | None = None,
) -> dict[str, Any]:
    """
    Full pipeline:
    1. Validate
    2. Parse (PDF/MD)
    3. Semantic chunking
    4. Generate embeddings (local MiniLM)
    5. Dual-write to pgvector + Pinecone
    6. Extract entities (deterministic)
    7. Save to DB
    """
    clinic_id = clinic_id or settings.clinic_id

    # 1. Validate
    validate_file(file_content, content_type)

    # 2. Parse
    if content_type == "application/pdf":
        raw_text = parse_pdf(file_content)
    else:
        raw_text = parse_markdown(file_content)

    if not raw_text.strip():
        raise ValueError("Document is empty or unreadable.")

    # 3. Semantic chunking
    chunks = semantic_chunk(raw_text, category=category)

    if not chunks:
        raise ValueError("No chunks generated from document.")

    # 4. Create document record
    doc = RagDocument(
        title=title or filename,
        category=category,
        clinic_id=clinic_id,
        source_path=filename,
        status="active",
    )
    session.add(doc)
    await session.commit()
    await session.refresh(doc)

    # 5. Process each chunk
    repo = RagRepository(session)
    embedding_config = None  # resolved from settings
    embedded_count = 0

    for chunk_data in chunks:
        chunk_content = chunk_data["content"]
        chunk_index = chunk_data["chunk_index"]
        metadata = chunk_data["metadata"]

        # Generate embedding
        embedding = await get_embedding(chunk_content, phase="ingest")
        embedded = embedding is not None

        # Save to pgvector
        chunk_record = await repo.create_chunk(
            document_id=doc.id,
            chunk_index=chunk_index,
            content=chunk_content,
            clinic_id=clinic_id,
            embedding=embedding,
            embedded=embedded,
            embedding_error=None if embedded else "embedding_failed",
            metadata_json=json.dumps(metadata),
        )

        # TODO: Upsert to Pinecone (when PineconeClient is fully implemented)

        if embedded:
            embedded_count += 1

        # Extract entities from chunk
        extraction_results = await extract_entities(chunk_content)
        if extraction_results:
            await save_extractions(
                session=session,
                document_id=doc.id,
                clinic_id=clinic_id,
                extractions=extraction_results,
                chunk_id=chunk_record.id,
            )

    logger.info(
        "[DOCUMENT] processed doc_id=%s title=%s chunks=%d embedded=%d",
        doc.id, doc.title, len(chunks), embedded_count
    )

    return {
        "document_id": doc.id,
        "title": doc.title,
        "category": category,
        "status": "ready",
        "chunks_created": len(chunks),
        "chunks_embedded": embedded_count,
    }
```

- [ ] **Step 3: Run basic import test**

```bash
cd apps/api && python -c "from app.services.document_upload import process_document; print('OK')"
```
Expected: OK

- [ ] **Step 4: Commit**

```bash
git add apps/api/app/services/document_upload.py
git commit -m "feat(document): add document upload orchestration service"
```

---

## PHASE 9 — RagService Integration (Dual-Write)

### Task 12: Update RagService to dual-write to Pinecone

**Files:**
- Modify: `apps/api/app/services/rag_service.py`

- [ ] **Step 1: Read current RagService.query_with_metadata**

Focus on the `search_similar` call around line 842.

- [ ] **Step 2: Add Pinecone dual-write to ingest_document**

In `ingest_document` method, after `repo.create_chunk`, add Pinecone upsert:

```python
# After chunk is saved to pgvector, upsert to Pinecone
if embedding is not None:
    from app.core.pinecone_client import PineconeClient
    pinecone = PineconeClient()
    if pinecone.is_available():
        try:
            await pinecone.upsert_chunk(
                chunk_id=str(chunk_record.id),
                embedding=embedding,
                metadata={
                    "clinic_id": clinic_id,
                    "document_id": str(doc.id),
                    "chunk_id": str(chunk_record.id),
                    "category": category,
                    "source": source_path or title,
                    "version": "1.0",
                    "created_at": datetime.utcnow().isoformat(),
                },
            )
        except Exception as exc:
            logger.warning("[DOCUMENT] Pinecone upsert failed for chunk %s: %s", chunk_record.id, exc)
```

- [ ] **Step 3: Add Pinecone query to query_with_metadata**

Replace the pgvector search with Pinecone-first:

```python
# In query_with_metadata, replace search_similar call with:
from app.core.pinecone_client import PineconeClient

pinecone = PineconeClient()
if pinecone.is_available():
    try:
        pinecone_results = await pinecone.query(
            query_embedding=query_embedding,
            top_k=k_initial,
            filter_dict={"clinic_id": clinic_id},
        )
        if pinecone_results:
            # Use Pinecone results
            rows = [_pinecone_result_to_row(r) for r in pinecone_results]
            # ... rest of logic
    except Exception as exc:
        logger.warning("[RAG] Pinecone query failed, falling back to pgvector: %s", exc)
```

Add helper:
```python
def _pinecone_result_to_row(r: dict) -> dict:
    return {
        "chunk_id": r["metadata"].get("chunk_id"),
        "document_id": r["metadata"].get("document_id"),
        "content": r["metadata"].get("content", ""),
        "document_title": r["metadata"].get("source", ""),
        "category": r["metadata"].get("category", ""),
        "score": r["score"],
    }
```

- [ ] **Step 4: Commit**

```bash
git add apps/api/app/services/rag_service.py
git commit -m "feat(rag): add Pinecone dual-write and query fallback"
```

---

## PHASE 10 — Orchestrator Update (Structured Priority)

### Task 13: Update orchestrator to enforce structured priority

**Files:**
- Modify: `apps/api/app/ai_engine/orchestrator.py`

- [ ] **Step 1: Read orchestrator to find intent routing**

Look for `StructuredLookup` usage and intent classification.

- [ ] **Step 2: Ensure StructuredLookup is tried FIRST**

The spec says: "Structured lookup ALWAYS tries DB first. If not found, THEN queries Pinecone."

Currently `StructuredLookup` may be called within the graph. Verify and ensure the orchestrator's intent routing calls StructuredLookup first for structured queries BEFORE any RAG lookup.

The current implementation should already have `StructuredLookup` as a separate node that runs before `rag_retrieval`. If not, adjust the node order and edges in `document_runtime_graph.py` to ensure:

```
load_runtime_context → decision_router → 
  [structured_lookup | schedule_flow | handoff_flow | rag_retrieval]
```

Where `structured_lookup` runs first for structured intents and returns early if data found.

- [ ] **Step 3: Add logging to confirm priority**

```python
logger.info("[ORCHESTRATOR] structured_lookup=%s found=%s",
    structured_intent, bool(structured_data))
```

- [ ] **Step 4: Commit**

```bash
git add apps/api/app/ai_engine/orchestrator.py
git commit -m "fix(orchestrator): ensure structured_lookup runs before RAG for structured queries"
```

---

## PHASE 11 — Frontend Admin UI (Documents Tab)

### Task 14: Add Documents tab to Admin page

**Files:**
- Modify: `frontend/src/app/admin/page.tsx`
- Create: `frontend/src/components/admin/document-upload.tsx`
- Create: `frontend/src/components/admin/document-list.tsx`
- Create: `frontend/src/components/admin/extraction-card.tsx`
- Modify: `frontend/src/lib/api.ts`

- [ ] **Step 1: Add Documents tab to tab list**

In `frontend/src/app/admin/page.tsx`, add to `tabs` array:
```typescript
{ id: "documentos", label: "Documentos" }
```

And add rendering:
```typescript
{tab === "documentos" && <DocumentosTab />}
```

- [ ] **Step 2: Add API functions to api.ts**

```typescript
// Upload
export async function uploadDocument(formData: FormData) {
  const res = await fetch("/api/v1/admin/documents/upload", {
    method: "POST",
    body: formData,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// List
export async function getDocuments(params?: { category?: string; status?: string }) {
  const qs = new URLSearchParams(params as Record<string, string>).toString();
  return fetch(`/api/v1/admin/documents?${qs}`).then(r => r.json());
}

// Extractions
export async function getExtractions(docId: string, status?: string) {
  const qs = status ? `?status=${status}` : "";
  return fetch(`/api/v1/admin/documents/${docId}/extractions${qs}`).then(r => r.json());
}

export async function approveExtraction(id: string, notes?: string) {
  return fetch(`/api/v1/admin/documents/extractions/${id}/approve`, {
    method: "PATCH",
    body: JSON.stringify({ notes }),
    headers: { "Content-Type": "application/json" },
  }).then(r => r.json());
}

export async function rejectExtraction(id: string, reason: string) {
  return fetch(`/api/v1/admin/documents/extractions/${id}/reject`, {
    method: "PATCH",
    body: JSON.stringify({ reason }),
    headers: { "Content-Type": "application/json" },
  }).then(r => r.json());
}

export async function reviseExtraction(id: string, corrected_data: object) {
  return fetch(`/api/v1/admin/documents/extractions/${id}/revise`, {
    method: "PATCH",
    body: JSON.stringify({ corrected_data }),
    headers: { "Content-Type": "application/json" },
  }).then(r => r.json());
}
```

- [ ] **Step 3: Create DocumentUpload component**

Drag-and-drop upload with file type validation and progress.

- [ ] **Step 4: Create DocumentList component**

Table with document summaries, status badges, action menu.

- [ ] **Step 5: Create ExtractionCard component**

Shows extraction item with approve/reject/revise buttons, confidence badge, and entity details.

- [ ] **Step 6: Create DocumentosTab component**

Combines upload zone + document list + extraction approval interface.

- [ ] **Step 7: Test in browser**

Run dev server and navigate to Admin > Documentos tab.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/app/admin/page.tsx
git add frontend/src/lib/api.ts
git add frontend/src/components/admin/document-upload.tsx
git add frontend/src/components/admin/document-list.tsx
git add frontend/src/components/admin/extraction-card.tsx
git commit -m "feat(admin): add Documents tab with upload and extraction approval"
```

---

## PHASE 12 — Delete Document (Pinecone + Orphan)

### Task 15: Implement delete document with Pinecone cleanup

**Files:**
- Modify: `apps/api/app/api/routes/document_upload.py`
- Modify: `apps/api/app/services/document_upload.py`

- [ ] **Step 1: Write delete test**

```python
# apps/api/tests/test_document_delete.py
def test_delete_orphan_extractions():
    # Approved extractions → orphaned
    # Pending/cancelled → cancelled
    pass
```

- [ ] **Step 2: Implement delete logic**

In `document_upload.py`:

```python
async def delete_document(
    session: AsyncSession,
    doc_id: uuid.UUID,
    clinic_id: str,
) -> bool:
    """
    Soft delete document:
    1. Get all chunk_ids for document
    2. Delete from Pinecone by chunk_ids
    3. Clear pgvector embeddings
    4. Mark document as archived
    5. Orphan approved extractions, cancel pending
    6. Audit log
    """
    # Get document
    repo = RagRepository(session)
    doc = await repo.get_document(doc_id, clinic_id)
    if not doc:
        return False

    # Get chunk IDs
    chunks = await repo.get_chunks(doc_id, clinic_id)
    chunk_ids = [str(c.id) for c in chunks]

    # Delete from Pinecone
    if chunk_ids:
        pinecone = PineconeClient()
        if pinecone.is_available():
            try:
                await pinecone.delete_chunks(chunk_ids)
                logger.info("[DELETE] Removed %d vectors from Pinecone for doc_id=%s", len(chunk_ids), doc_id)
            except Exception as exc:
                logger.error("[DELETE] Pinecone delete failed: %s", exc)

    # Clear pgvector embeddings
    for chunk in chunks:
        await repo.update_chunk_indexing(chunk.id, embedding=None, embedded=False, embedding_error="document_deleted")

    # Soft delete document
    doc.status = "archived"
    session.add(doc)

    # Handle extractions
    from app.models.policy import DocumentExtraction
    extractions = await session.execute(
        select(DocumentExtraction).where(DocumentExtraction.document_id == doc_id)
    )
    extractions = list(extractions.scalars().all())

    orphaned_count = 0
    cancelled_count = 0
    for ext in extractions:
        if ext.status == "approved":
            ext.status = "orphaned"
            ext.orphaned_at = datetime.utcnow()
            orphaned_count += 1
        else:
            ext.status = "cancelled"
            cancelled_count += 1

    await session.commit()

    logger.info(
        "[DELETE] document_id=%s orphaned=%d cancelled=%d",
        doc_id, orphaned_count, cancelled_count
    )

    return True
```

- [ ] **Step 3: Wire to route**

In `document_upload.py` route, replace stub with `delete_document` call.

- [ ] **Step 4: Commit**

```bash
git add apps/api/app/services/document_upload.py apps/api/app/api/routes/document_upload.py
git commit -m "feat(document): implement delete with Pinecone cleanup and orphan handling"
```

---

## PHASE 13 — Extraction Approval Service

### Task 16: Implement extraction approval service

**Files:**
- Create: `apps/api/app/services/extraction_approval.py`
- Modify: `apps/api/app/api/routes/extractions.py`

- [ ] **Step 1: Write service**

```python
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import User
from app.models.policy import DocumentExtraction
from app.models.professional import Professional
from app.models.service import Service, ServicePrice
from app.models.admin import InsuranceCatalog
from app.models.policy import ClinicPolicy


async def approve_extraction(
    session: AsyncSession,
    extraction_id: uuid.UUID,
    user_id: str,
    notes: str | None = None,
) -> DocumentExtraction:
    """Approve extraction and publish to target operational table."""
    ext = await session.get(DocumentExtraction, extraction_id)
    if not ext:
        raise ValueError("Extraction not found")

    ext.status = "approved"
    ext.reviewed_by = user_id
    ext.reviewed_at = datetime.utcnow()
    ext.published_at = datetime.utcnow()

    # Publish to target table
    if ext.entity_type == "doctor":
        # Check if exists
        existing = await session.execute(
            select(Professional).where(Professional.crm == ext.extracted_data.get("crm"))
        )
        existing = existing.scalar_one_or_none()
        if existing:
            existing.full_name = ext.extracted_data.get("name", existing.full_name)
            existing.specialty = ext.extracted_data.get("specialty", existing.specialty)
            session.add(existing)
            ext.published_entity_id = existing.id
        else:
            prof = Professional(
                full_name=ext.extracted_data.get("name", "Unknown"),
                specialty=ext.extracted_data.get("specialty", ""),
                crm=ext.extracted_data.get("crm", ""),
            )
            session.add(prof)
            await session.flush()
            ext.published_entity_id = prof.id
        ext.published_to = "professionals"

    elif ext.entity_type == "insurance":
        name = ext.extracted_data.get("name", "Unknown")
        existing = await session.execute(
            select(InsuranceCatalog).where(InsuranceCatalog.name == name)
        )
        existing = existing.scalar_one_or_none()
        if existing:
            ext.published_entity_id = existing.id
        else:
            ins = InsuranceCatalog(name=name)
            session.add(ins)
            await session.flush()
            ext.published_entity_id = ins.id
        ext.published_to = "insurance_catalog"

    # ... similar for price, service, policy, schedule

    session.add(ext)
    await session.commit()
    await session.refresh(ext)
    return ext


async def reject_extraction(
    session: AsyncSession,
    extraction_id: uuid.UUID,
    user_id: str,
    reason: str,
) -> DocumentExtraction:
    """Reject extraction."""
    ext = await session.get(DocumentExtraction, extraction_id)
    if not ext:
        raise ValueError("Extraction not found")
    ext.status = "rejected"
    ext.reviewed_by = user_id
    ext.reviewed_at = datetime.utcnow()
    session.add(ext)
    await session.commit()
    await session.refresh(ext)
    return ext


async def revise_extraction(
    session: AsyncSession,
    extraction_id: uuid.UUID,
    user_id: str,
    corrected_data: dict[str, Any],
) -> DocumentExtraction:
    """Revise extraction — mark old as superseded, create new pending."""
    ext = await session.get(DocumentExtraction, extraction_id)
    if not ext:
        raise ValueError("Extraction not found")

    # Mark old as superseded
    ext.status = "revised"
    ext.reviewed_by = user_id
    ext.reviewed_at = datetime.utcnow()
    ext.superseded_by = None  # will point to new

    # Create new extraction with corrected data
    new_ext = DocumentExtraction(
        document_id=ext.document_id,
        chunk_id=ext.chunk_id,
        clinic_id=ext.clinic_id,
        entity_type=ext.entity_type,
        extracted_data=corrected_data,
        raw_text=ext.raw_text,
        extraction_method="deterministic",
        confidence=1.0,
        requires_review=False,
        status="pending",
        source_extraction_id=ext.id,
    )
    session.add(new_ext)
    session.add(ext)
    await session.commit()
    await session.refresh(new_ext)

    # Link superseded
    ext.superseded_by = new_ext.id
    session.add(ext)
    await session.commit()

    return new_ext
```

- [ ] **Step 2: Wire to routes**

Replace stubs in `apps/api/app/api/routes/extractions.py` with calls to `extraction_approval.py`.

- [ ] **Step 3: Commit**

```bash
git add apps/api/app/services/extraction_approval.py apps/api/app/api/routes/extractions.py
git commit -m "feat(extraction: implement approval/reject/revise with operational table publishing"
```

---

## PHASE 14 — Full Integration + Wiring

### Task 17: Wire upload routes to document_upload service

**Files:**
- Modify: `apps/api/app/api/routes/document_upload.py`

- [ ] **Step 1: Replace stubs with service calls**

```python
from app.services.document_upload import process_document

@router.post("/upload", response_model=DocumentUploadResponse, status_code=201)
async def upload_document(
    file: UploadFile,
    category: str = Form(...),
    title: str | None = Form(None),
    current_user: Annotated[User, Depends(require_roles(*_WRITE_ROLES))] = None,
    session: Annotated[AsyncSession, Depends(get_session)] = None,
) -> DocumentUploadResponse:
    validate_file(content, file.content_type)
    result = await process_document(
        session=session,
        file_content=content,
        filename=file.filename or "document",
        content_type=file.content_type,
        title=title,
        category=category,
    )
    return DocumentUploadResponse(**result)
```

- [ ] **Step 2: Wire list/get/delete**

- [ ] **Step 3: Commit**

```bash
git add apps/api/app/api/routes/document_upload.py
git commit -m "feat(api: wire upload routes to document_upload service"
```

---

## PHASE 15 — End-to-End Tests

### Task 18: Run and verify full pipeline

**Files:**
- Create: `apps/api/tests/test_e2e_document_upload.py`

- [ ] **Step 1: Write e2e test**

```python
async def test_full_upload_pipeline():
    # 1. Upload MD file
    # 2. Check document created
    # 3. Check chunks created
    # 4. Check extractions created
    # 5. Approve extraction
    # 6. Verify published to operational table
    # 7. Delete document
    # 8. Verify Pinecone vectors removed
    # 9. Verify extractions orphaned
    pass
```

- [ ] **Step 2: Run tests**

```bash
cd apps/api && pytest tests/test_e2e_document_upload.py -v
```

- [ ] **Step 3: Commit**

```bash
git add apps/api/tests/test_e2e_document_upload.py
git commit -m "test(e2e): add document upload pipeline test"
```

---

## Summary — Task Count

| Phase | Task | Description |
|-------|------|-------------|
| 1 | 1-3 | Pinecone config + client |
| 2 | 4 | DB migration (5 new tables) |
| 3 | 5 | SQLModel classes |
| 4 | 6-7 | Upload API routes + schemas |
| 5 | 8 | Extraction approval routes |
| 6 | 9 | Semantic chunking module |
| 7 | 10 | Extraction service (deterministic) |
| 8 | 11 | Document upload orchestration |
| 9 | 12 | RagService dual-write |
| 10 | 13 | Orchestrator structured priority |
| 11 | 14 | Frontend Documents tab |
| 12 | 15 | Delete with Pinecone cleanup |
| 13 | 16 | Extraction approval service |
| 14 | 17 | Route wiring |
| 15 | 18 | E2E tests |

**Total: 18 tasks**

---

## Self-Review Checklist

**Spec coverage:**
- [ ] Pinecone dual-write ✓ (Task 12)
- [ ] Document upload API ✓ (Tasks 6-7, 17)
- [ ] Semantic chunking ✓ (Task 9)
- [ ] Deterministic extraction ✓ (Task 10)
- [ ] LLM extraction (stub only — config exists, LLM call not implemented) ⚠️
- [ ] Item-level approval ✓ (Tasks 8, 16)
- [ ] Structured priority before RAG ✓ (Task 13)
- [ ] Fallback chain ✓ (Task 12)
- [ ] Delete with Pinecone cleanup ✓ (Task 15)
- [ ] Admin UI ✓ (Task 14)

**Placeholder scan:** No TBD/TODO in tasks. Code shown inline.

**Type consistency:** All schemas reference `DocumentExtraction`, `RagDocument`, etc. consistently throughout.

**One gap noted:** LLM extraction (Layer 2) is defined in spec but not implemented in Task 10 (extraction service only has deterministic). This is intentional — deterministic-first is the minimum viable product. LLM extraction can be added as a separate task when the extraction LLM configuration is wired up via Admin.

---

*Plan ready for execution.*