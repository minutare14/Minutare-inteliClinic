# SPEC — RAG + Pinecone Integration + Document Upload Admin

**Date:** 2026-04-18
**Project:** IntelliClinic / Minutare Med
**Status:** Approved

---

## 1. Overview

Transformar o sistema RAG do IntelliClinic para usar **Pinecone como vector store principal**, implementar **upload de documentos (PDF/MD) via Admin panel** com ingestão automática, e **extração estruturada** de dados (médicos, preços, convênios, horários) com aprovação humana.

**Stack:** FastAPI, PostgreSQL/pgvector, Pinecone, Local embeddings (MiniLM)

---

## 2. Key Principles

### 2.1 Source of Truth — Formalized

| Layer | Purpose | Usage |
|-------|---------|-------|
| **Structured DB (PostgreSQL)** | Operational truth | professionals, services, service_prices, insurance_catalog, clinic_policies — chatbot uses these for structured questions |
| **Pinecone** | Semantic retrieval | Open questions about procedures, protocols, policies |
| **pgvector** | Technical fallback | Only if Pinecone is unavailable |

**Rule:** Structured lookup ALWAYS tries DB first. If not found, THEN queries Pinecone (never the reverse).

### 2.2 API Key

`PINECONE_API_KEY` lives in `.env` only. Never hardcoded in code, docs, specs, or memory.

### 2.3 Deterministic-First Extraction

Extraction has two layers:
1. **Deterministic (no LLM cost):** Regex patterns for CRM, currency, named lists, time slots, specialty matches
2. **LLM (ambiguous/low confidence cases):** Only if confidence < 0.7 or deterministic fails

---

## 3. Infrastructure

### 3.1 Pinecone Configuration

```
Index: inteliclinic-rag (created on first init if not exists)
Dimension: 384 (MiniLM)
Metric: cosine
Cloud: configurable via PINECONE_CLOUD env (default: aws)
Region: configurable via PINECONE_REGION env (default: us-east-1)
Namespace: clinic_id (single-clinic per deploy, but enables future multi-clinic)
```

### 3.2 Vector Metadata

Every vector in Pinecone carries:
```json
{
  "clinic_id": "clinic01",
  "document_id": "uuid",
  "chunk_id": "uuid",
  "category": "convenio|protocolo|faq|manual|tabela|outro",
  "source": "filename.pdf",
  "version": "1.0",
  "created_at": "ISO8601"
}
```

### 3.3 Dual-Write Strategy

Every chunk is written to both:
1. **pgvector** (`rag_chunks.embedding`) — backup/fallback
2. **Pinecone** — production vector store

Query falls back to pgvector if Pinecone fails.

---

## 4. Database Schema

### 4.1 Existing Tables (unchanged)

- `rag_documents` — document metadata, dual-write source
- `rag_chunks` — chunk data with embeddings, dual-write source
- `professionals` — doctors and specialists
- `insurance_catalog` — accepted insurance plans
- `clinic_specialties` — medical specialties offered
- `clinic_settings` — clinic configuration

### 4.2 New Tables

```sql
-- Service categories (e.g., "Consulta", "Exame", "Procedimento")
CREATE TABLE service_categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id VARCHAR(64) NOT NULL DEFAULT 'clinic01',
    name VARCHAR(128) NOT NULL,
    description TEXT,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Services offered (e.g., "Consulta Cardiologia", "Eletrocardiograma")
CREATE TABLE services (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id VARCHAR(64) NOT NULL DEFAULT 'clinic01',
    category_id UUID REFERENCES service_categories(id),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    duration_min INT DEFAULT 30,
    active BOOLEAN DEFAULT TRUE,
    version INT DEFAULT 1,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Prices (per service + insurance plan combination)
CREATE TABLE service_prices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id VARCHAR(64) NOT NULL DEFAULT 'clinic01',
    service_id UUID REFERENCES services(id),
    insurance_plan_id UUID REFERENCES insurance_catalog(id),
    price DECIMAL(10,2) NOT NULL,
    copay DECIMAL(10,2),
    active BOOLEAN DEFAULT TRUE,
    version INT DEFAULT 1,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Clinic policies (cancellation, privacy, etc.)
CREATE TABLE clinic_policies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id VARCHAR(64) NOT NULL DEFAULT 'clinic01',
    category VARCHAR(64) NOT NULL,  -- cancellation|privacy|terms|general
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    version INT DEFAULT 1,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Extraction log with full review trail
CREATE TABLE document_extractions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES rag_documents(id) ON DELETE SET NULL,
    chunk_id UUID,
    clinic_id VARCHAR(64) NOT NULL DEFAULT 'clinic01',
    entity_type VARCHAR(32) NOT NULL,  -- doctor|service|price|insurance|policy|schedule
    extracted_data JSONB NOT NULL,
    raw_text TEXT,
    extraction_method VARCHAR(32) NOT NULL,  -- deterministic|llm
    confidence FLOAT NOT NULL,  -- 0.0-1.0
    requires_review BOOLEAN DEFAULT FALSE,
    status VARCHAR(32) NOT NULL DEFAULT 'pending',  -- pending|approved|rejected|revised|orphaned|cancelled
    reviewed_by VARCHAR(64),
    reviewed_at TIMESTAMP,
    published_at TIMESTAMP,
    published_to VARCHAR(64),  -- professionals|services|service_prices|insurance_catalog|clinic_policies
    published_entity_id UUID,
    superseded_by UUID REFERENCES document_extractions(id) ON DELETE SET NULL,
    source_extraction_id UUID REFERENCES document_extractions(id) ON DELETE SET NULL,
    orphaned_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_service_prices_clinic ON service_prices(clinic_id);
CREATE INDEX idx_services_clinic ON services(clinic_id);
CREATE INDEX idx_services_category ON services(category_id);
CREATE INDEX idx_document_extractions_document ON document_extractions(document_id);
CREATE INDEX idx_document_extractions_clinic ON document_extractions(clinic_id);
CREATE INDEX idx_document_extractions_status ON document_extractions(status);
CREATE INDEX idx_document_extractions_entity ON document_extractions(entity_type);
CREATE INDEX idx_clinic_policies_clinic ON clinic_policies(clinic_id);
```

### 4.3 Versioning Rules (services/service_prices)

- Extraction approved with same (name + service_category) → UPDATE existing, version += 1
- Old record archived (active=false), new record active (active=true)
- `published_entity_id` in `document_extractions` always points to ACTIVE record
- If name changes (e.g., "Consulta Cardiológica" vs "Consulta Cardiologia"), treated as different service

---

## 5. Semantic Chunking Rules

### 5.1 Chunking Strategy

```
1. Parse document into structured_blocks (headings, paragraphs, tables, lists)
2. For each block:
   - If heading → new chunk with heading prefix
   - If table → chunk with table header preserved
   - If list → item-level chunks with list context
3. If chunk > 800 chars → split at sentence boundary
4. HARD LIMIT: no chunk exceeds 1000 chars (forced split even if breaks semantic)
5. Minimum chunk: 50 chars (merge with next or discard)
6. Overlap: 20% of chunk_size (100 chars for 500-char chunks), max 150 chars
   - Overlap shares previous chunk's heading/header
   - Maximum 3 overlap chunks per document
```

### 5.2 Configurable Parameters (Admin-exposed)

```
chunk_semantic_max_chars: 800   # split before this limit
chunk_hard_max_chars: 1000       # never exceeds
chunk_overlap_pct: 0.20          # 20% overlap
chunk_min_chars: 50              # minimum chunk size
```

### 5.3 Chunk Metadata

Each chunk carries:
- `chunk_index`: position in document
- `page`: page number (for PDF)
- `metadata_json`: source section info
- `parent_chunk_id`: previous chunk (for sibling linking)

---

## 6. Extraction Pipeline

### 6.1 Two-Layer Extraction

**Layer 1 — Deterministic (no LLM):**

Applied in order:
1. CRM pattern `(?<![A-Z])CRM[/\s][A-Z]{2}\s*\d+` → doctor entity
2. Currency pattern `R\$\s*\d+(?:[.,]\d{2})?` → price entity
3. Named list (matching insurance_catalog names) → insurance entity
4. Time slot pattern `(?:Seg|Segunda|Ter|Terceira|Qua|Quarta|Qui|Quinta|Sex|Sexta)[^,\n]{0,50}` → schedule entity
5. Specialty exact match against clinic_specialties → specialty entity

**Layer 2 — LLM (only if confidence < 0.7 or deterministic failed):**

```
Trigger: confidence < 0.7 OR extraction_method == null
Provider: configurable via Admin (same as chat LLM)
Model: configurable via Admin (default: same as chat model)
Prompt: structured_extraction_prompt from PromptRegistry
```

### 6.2 DocumentExtraction Creation

Each extraction creates a record with:
- `status = pending`
- `requires_review = True` if extraction_method == "llm" OR confidence < 0.7
- `entity_type` based on what was detected

### 6.3 Workflow

```
1. Extraction generates DocumentExtraction (status=pending)
2. Admin reviews (approve/reject/revise)
3. If approved:
   - published_to = target table (professionals, services, etc.)
   - published_at = NOW
   - published_entity_id = created/updated record ID
   - If same entity exists → UPDATE + version increment
4. If rejected:
   - status = rejected
   - reviewed_by + reviewed_at filled
5. If revised:
   - superseded_by = new_extraction.id
   - New extraction created with status=pending
```

---

## 7. API Endpoints

### 7.1 Document Upload

```
POST /api/v1/admin/documents/upload
  Content-Type: multipart/form-data
  Fields:
    - file: PDF or MD (required, max 10MB)
    - title: string (optional, auto-filled from filename if empty)
    - category: enum (convenio|protocolo|faq|manual|tabela|outro)
  Auth: requires_roles(admin)
  Response 201:
    {
      document_id: uuid,
      title: string,
      category: string,
      status: "processing",
      chunks_created: 0,
      message: "Document uploaded. Processing started."
    }
  Errors:
    - 400: unsupported file type
    - 413: file > 10MB
    - 422: invalid document structure
```

### 7.2 Document List & Detail

```
GET /api/v1/admin/documents
  Query: ?category=&status=&page=&limit=
  Response: { items: [DocumentSummary], total, page }

GET /api/v1/admin/documents/{id}
  Response: DocumentDetail with chunks[] and extractions[]

DELETE /api/v1/admin/documents/{id}
  Soft delete (status=archived), remove from Pinecone, orphan approved extractions
  Response: 204

GET /api/v1/admin/documents/{id}/chunks
  Response: [ChunkInfo]

GET /api/v1/admin/documents/{id}/extractions
  Query: ?status=pending|approved|rejected|revised
  Response: [ExtractionItem]
```

### 7.3 Extraction Operations (item-level)

```
PATCH /api/v1/admin/documents/extractions/{extraction_id}/approve
  Body: { notes?: string }
  Response: ExtractionItem (status=approved, published_to, published_entity_id)

PATCH /api/v1/admin/documents/extractions/{extraction_id}/reject
  Body: { reason: string }
  Response: ExtractionItem (status=rejected, reviewed_by, reviewed_at)

PATCH /api/v1/admin/documents/extractions/{extraction_id}/revise
  Body: { corrected_data: dict }
  Response: NEW ExtractionItem (status=pending, source_extraction_id=parent)
```

### 7.4 Chunk Inspection

```
GET /api/v1/admin/documents/{id}/chunks
  Response: [{ id, chunk_index, content, page, metadata_json }]
```

---

## 8. Delete Behavior

```
When document is deleted (soft delete, status=archived):

1. All DocumentExtractions with status=approved:
   - status → "orphaned"
   - orphaned_at = NOW
   - published_to + published_entity_id = PRESERVED (point to operational data)

2. All DocumentExtractions with status=pending/rejected:
   - status → "cancelled"

3. Pinecone vectors deleted by chunk_id (NOT delete_all):
   - Query all chunk_ids for document from DB
   - pinecone.delete(ids=[chunk_ids], namespace=clinic_id, delete_all=False)

4. pgvector entries: embedding set to NULL, embedded=false

5. Audit log: "document_id={id} deleted, N orphaned, M cancelled"

Rationale: Approved extractions created operational records (professionals, services, etc.)
which should NOT be deleted when the source document is removed.
```

**NEVER uses `delete_all=True` on Pinecone.**

---

## 9. Query Pipeline

### 9.1 Intent Classification

```
User message → intent classification:
  - structured_query: médico|preço|horário|convênio|especialidade
  - rag_query: procedimento|protocolo|política|regra|como fazer
  - handoff_query: reclamação|urgência|bloqueio
```

### 9.2 Structured Lookup Priority

```
IF user asks about:
  - "médicos", "doutores", "especialistas" → professionals table ONLY
  - "preço", "valor", "custa", "quanto" → service_prices table ONLY
  - "horário", "funciona", "aberto", "fecha" → clinic_settings.working_hours + schedule_slots
  - "convênio", "plano", "aceita" → insurance_catalog table ONLY
  - "especialidade" → clinic_specialties table ONLY

THEN: do NOT query Pinecone. DB only.
```

### 9.3 RAG Query Flow

```
IF structured not found OR intent == rag_query:
  1. Generate query embedding (local MiniLM, 384 dims)
  2. Pinecone query (top_k=20, filter by clinic_id)
  3. If Pinecone fails → pgvector fallback
  4. Results → response_composer
```

### 9.4 Fallback Chain

```
PRIMARY: Pinecone
  ↓ fail
SECONDARY: pgvector (local RagChunk.search_similar)
  ↓ fail
TERTIARY: text search (RagRepo.text_search)
  ↓ fail
FINAL:
  {
    answer: "Desculpe, não consegui acessar a base de conhecimento agora.",
    source: "unavailable",
    error_id: uuid
  }
  → Full error logged
  → Never returns empty to user
```

---

## 10. Environment Variables

```bash
# Pinecone (required for RAG production)
PINECONE_API_KEY=${PINECONE_API_KEY}  # read from environment, never hardcoded
PINECONE_INDEX=inteliclinic-rag
PINECONE_CLOUD=aws
PINECONE_REGION=us-east-1

# Embedding (local is default)
EMBEDDING_PROVIDER=local
EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
EMBEDDING_DIM=384

# Extraction LLM (configurable per clinic via Admin)
EXTRACTION_LLM_PROVIDER=  # inherits from llm_provider if empty
EXTRACTION_LLM_MODEL=      # specific model for extraction, overrides chat model
```

---

## 11. Admin Panel UI

### 11.1 New Tab: "Documentos"

```
Admin Navigation:
├── Clínica          (existing)
├── Branding         (existing)
├── IA               (existing — expanded)
├── Convênios        (existing)
├── Especialidades   (existing)
├── Documentos       (NEW TAB)
│   ├── Upload        (drag & drop zone)
│   ├── Lista         (table with status)
│   └── Aprovar       (detail view + extraction cards)
└── ...existing...
```

### 11.2 Upload Section

```
┌─────────────────────────────────────────────────────────────┐
│  DRAG & DROP or CLICK TO SELECT                            │
│  PDF or Markdown • Max 10MB                                 │
│                                                              │
│  Category: [ dropdown ]                                      │
│  Title: [ auto-filled ]                                      │
│                                                              │
│  [Upload and Process]                                        │
└─────────────────────────────────────────────────────────────┘
```

### 11.3 Extraction Review Cards

```
┌─────────────────────────────────────────────────────────────┐
│ Dr. Marcos Nunes - CRM/SP 123456                      [Pending]
│ Speciality: Neurologia                                       │
│ Confidence: deterministic 100%                              │
│ [Approve] [Reject] [Revise]                                 │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ Consulta Neurológica: R$ 350,00                       [Pending]
│ Confidence: llm 82%                                         │
│ [Approve] [Reject] [Revise]                                 │
└─────────────────────────────────────────────────────────────┘
```

### 11.4 AI Config — Extraction LLM

```
┌─────────────────────────────────────────────────────────────┐
│ EXTRACTION LLM                                               │
│ Provider: [Groq ▼]    Model: [llama-3.3-70b ▼]             │
│                                                             │
│ Note: Used only for ambiguous extractions.                  │
│ Deterministic regex is tried first.                          │
│ [Test Extraction]                                           │
└─────────────────────────────────────────────────────────────┘
```

---

## 12. Files to Create/Modify

### New Files

```
apps/api/app/core/pinecone_client.py       # Pinecone connection + upsert/delete
apps/api/app/services/document_upload.py   # Upload orchestration
apps/api/app/services/extraction_service.py # Structured extraction
apps/api/app/repositories/ pinecone_repository.py # Pinecone CRUD
apps/api/app/repositories/service_repository.py # New DB tables
apps/api/app/models/service.py             # service_categories, services, service_prices
apps/api/app/models/policy.py              # clinic_policies
apps/api/app/schemas/document.py           # Upload request/response
apps/api/app/schemas/extraction.py         # Extraction schemas
apps/api/app/api/routes/document_upload.py # Upload endpoints
apps/api/app/api/routes/extractions.py    # Extraction approval endpoints
migrations/xxx_add_services_and_policies.py # DB migration
frontend/src/app/admin/documents/page.tsx  # Admin UI
frontend/src/components/admin/document-upload.tsx
frontend/src/components/admin/extraction-card.tsx
```

### Modify

```
apps/api/app/core/config.py               # Add PINECONE_* vars
apps/api/app/services/rag_service.py      # Add Pinecone dual-write
apps/api/app/ai_engine/orchestrator.py    # Structured priority before RAG
apps/api/app/ai_engine/structured_lookup.py # Use new service tables
apps/api/app/api/routes/admin.py           # Add document routes
apps/api/app/api/routes/__init__.py        # Register new routes
frontend/src/app/admin/page.tsx            # Add Documents tab
frontend/src/lib/api.ts                    # Add document API calls
```

---

## 13. Acceptance Criteria

### Upload
- [ ] PDF upload succeeds with status=processing
- [ ] MD upload succeeds with status=processing
- [ ] File > 10MB returns 413
- [ ] Invalid type returns 400

### Ingestion
- [ ] Chunks created with semantic rules (heading-aware, table-aware)
- [ ] Chunks ≤ 1000 chars, minimum 50 chars
- [ ] 20% overlap between adjacent chunks
- [ ] Embeddings generated (384 dim local)
- [ ] Dual-write: pgvector + Pinecone

### Extraction
- [ ] CRM detected via deterministic regex
- [ ] Currency detected via deterministic regex
- [ ] LLM called only if confidence < 0.7
- [ ] DocumentExtraction records created with status=pending
- [ ] requires_review=True for LLM extractions

### Approval
- [ ] Approve item → published_to populated, record in DB table
- [ ] Reject item → status=rejected, reviewed_by/at filled
- [ ] Revise item → new extraction created, superseded_by linked
- [ ] Re-approve same entity → UPDATE (version incremented)

### Query
- [ ] "médicos" → DB professionals (NOT Pinecone)
- [ ] "preço" → DB service_prices (NOT Pinecone)
- [ ] "protocolo" → Pinecone query
- [ ] Pinecone down → pgvector fallback
- [ ] All fallbacks fail → graceful error message

### Delete
- [ ] Document deleted (archived) → Pinecone vectors removed
- [ ] Approved extractions → orphaned status (data preserved)
- [ ] Pending extractions → cancelled status
- [ ] delete_all=True NEVER used

---

## 14. Out of Scope

- Multi-tenant (one index per clinic, single-clinic per deploy)
- Async background workers (sync pipeline for MVP)
- S3 storage (local filesystem for uploads)
- Real-time sync from external systems
- GraphRAG / LlamaIndex / Docling (Phase 5 — future)

---

*Spec approved 2026-04-18*