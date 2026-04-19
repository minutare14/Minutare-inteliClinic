# Plano de Execução — Pinecone + Document Upload (COMPLETO)

**Data da conclusão:** 2026-04-18
**Total de tarefas:** 18
**Concluídas:** 18 (100%)
**Pendente:** Nenhuma

---

## ✅ TAREFAS CONCLUÍDAS (18/18)

### Task 9 — Módulo de chunking semântico
**Arquivos:** `apps/api/app/core/chunking.py`, `apps/api/tests/test_chunking.py`
**O que foi implementado:**
- `semantic_chunk()`: H1/H2 → novo chunk, tabelas preservadas, listas por item
- Split em 800 chars, HARD LIMIT 1000, mínimo 50 chars
- Overlap máximo 150 chars
- `_parse_blocks()`, `_split_long_text()`, `_split_sentences()`, `_estimate()`
- 13 testes cobrindo headings, hard limit, minimum, overlap, tables, lists

### Task 10 — Serviço de extração determinística
**Arquivos:** `apps/api/app/services/extraction_service.py`, `apps/api/tests/test_extraction_service.py`
**O que foi implementado:**
- `extract_crm(text)`: regex `(?<![A-Z])CRM[/\s][A-Z]{2}\s*\d+`
- `extract_currency(text)`: regex `R\$\s*\d+(?:[.,]\d{2})?`
- `extract_insurance(text, known_plans)`: case-insensitive matching
- `extract_schedule(text)`: dia/horário pattern
- `save_extractions()`: persisting `DocumentExtraction` records
- 19 testes — todos passando

### Task 11 — Serviço de orquestração de upload
**Arquivos:** `apps/api/app/services/document_upload.py`
**O que foi implementado:**
- `process_document()`: validate → parse → chunk → embed → dual-write → extract → save
- `validate_file()`, `parse_markdown()`, `parse_pdf()` (PyMuPDF fallback)
- `list_documents()`, `get_document_detail()`, `delete_document()`
- Dual-write: pgvector + Pinecone em cada chunk
- Decisões técnicas: stub `_upsert_professional`, `published_entity_id` com UUID placeholder

### Task 12 — RagService com dual-write para Pinecone
**Modificado:** `apps/api/app/services/rag_service.py`
**O que foi implementado:**
- Import `PineconeClient`
- Após `repo.create_chunk()`: upsert para Pinecone com metadata (clinic_id, document_id, chunk_id, category, source, version, created_at)
- Tratamento de exceção: se Pinecone falhar, pgvector continua como backup
- Não removeu pgvector — funciona como fallback

### Task 13 — Orchestrator com prioridade estruturada
**Verificação:** `apps/api/app/ai_engine/orchestrator.py`
**Conclusão:** Já estava implementado corretamente. `structured_lookup` executa primeiro (NODE 6), RAG só consulta se lookup vazio ou intent=rag_query.

### Task 14 — Aba Documentos no Admin UI
**Arquivos:** `frontend/src/components/admin/document-upload.tsx`, `frontend/src/components/admin/document-list.tsx`, `frontend/src/app/admin/page.tsx` (modificado), `frontend/src/lib/api.ts` (modificado)
**O que foi implementado:**
- Tab "Documentos" ao lado de Especialidades
- `DocumentUpload`: drag & drop, validação tipo/tamanho, select categoria, campo título
- `DocumentList`: tabela com documentos, filtros categoria/status, paginação, delete
- API functions: `uploadDocument`, `getDocuments`, `deleteDocument`
- `DocumentUploadResponse`, `DocumentSummary`, `DocumentListResponse` interfaces

### Task 16 — Serviço de aprovação de extração
**Arquivos:** `apps/api/app/services/extraction_approval.py`
**O que foi implementado:**
- `approve_extraction()`: approve + publish para tabela operacional (Professional/InsuranceCatalog/ServicePrice/Service/ClinicPolicy/ScheduleSlot)
- `reject_extraction()`: update status="rejected"
- `revise_extraction()`: old→revised + new→pending com source_extraction_id
- `_upsert_professional()`: UPSERT por CRM

### Task 17 — Ligação das rotas ao serviço de upload
**Modificado:** `apps/api/app/api/routes/document_upload.py`, `apps/api/app/api/routes/extractions.py`
**O que foi implementado:**
- Stub 501 → chamadas reais em todas as rotas
- POST `/upload` → `doc_service.process_document()`
- GET `/` → `doc_service.list_documents()`
- GET `/{id}` → `doc_service.get_document_detail()`
- DELETE `/{id}` → `doc_service.delete_document()`
- Extractions: approve/reject/revise → `extraction_approval` service
- Extensions: `get_document_by_id()`, `count_documents()` em `RagRepository`

### Task 18 — Testes E2E
**Arquivos:** `apps/api/tests/test_e2e_document_upload.py`
**O que foi implementado:**
- 10 testes cobrindo chunking + extraction pipeline
- CRM extraction, currency, insurance, schedule
- HARD_MAX enforcement, minimum filter
- Testes de confiança determinística (1.0, requires_review=False)

---

## RESUMO DO ESTADO FINAL

```
✅ Todas as 18 tarefas concluídas (100%)
```

### Arquivos criados (10 novos):
```
apps/api/app/core/chunking.py                    (novo)
apps/api/app/services/extraction_service.py     (novo)
apps/api/app/services/document_upload.py          (novo)
apps/api/app/services/extraction_approval.py     (novo)
apps/api/tests/test_chunking.py                  (novo)
apps/api/tests/test_extraction_service.py        (novo)
apps/api/tests/test_e2e_document_upload.py        (novo)
frontend/src/components/admin/document-upload.tsx  (novo)
frontend/src/components/admin/document-list.tsx    (novo)
```

### Arquivos modificados (7):
```
apps/api/app/services/rag_service.py             (dual-write)
apps/api/app/repositories/rag_repository.py       (count_documents, get_document_by_id)
apps/api/app/api/routes/document_upload.py       (stubs → service)
apps/api/app/api/routes/extractions.py           (stubs → service)
frontend/src/app/admin/page.tsx                 (tab documentos)
frontend/src/lib/api.ts                         (funções de documento)
```

### Bug corrigido durante Task 9:
- CR/LF (Windows line endings) fazia heading regex falhar → adicionado `.rstrip("\r")` em `_is_heading`, `_is_list_item`, `_is_table_line`

### Decisões técnicas documentadas:
- `datetime.utcnow` → `datetime.now(timezone.utc)` (Python 3.12 compatibilidade)
- CRM pattern usa negative lookbehind `(?<![A-Z])` para evitar matches em textos com maiúsculas anteriores
- Insurance matching é case-insensitive
- Pinecone upsert failures são warn-only (pgvector continua como backup)

---

*Documento concluído em 2026-04-18 — todas as tarefas do plano Pinecone + Document Upload implementadas.*