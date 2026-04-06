# Database Schema — Minutare Med

PostgreSQL 16 + pgvector

## Tabelas

### patients
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK |
| full_name | VARCHAR(255) | NOT NULL |
| cpf | VARCHAR(14) | UNIQUE, INDEX |
| birth_date | DATE | |
| phone | VARCHAR(20) | |
| email | VARCHAR(255) | |
| telegram_user_id | VARCHAR(64) | UNIQUE, INDEX |
| telegram_chat_id | VARCHAR(64) | |
| convenio_name | VARCHAR(128) | |
| insurance_card_number | VARCHAR(64) | |
| consented_ai | BOOLEAN | DEFAULT false |
| preferred_channel | VARCHAR(32) | DEFAULT 'telegram' |
| operational_notes | TEXT | |
| created_at | TIMESTAMP | DEFAULT now() |
| updated_at | TIMESTAMP | DEFAULT now() |

### professionals
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK |
| full_name | VARCHAR(255) | NOT NULL |
| specialty | VARCHAR(128) | NOT NULL |
| crm | VARCHAR(20) | UNIQUE, INDEX, NOT NULL |
| active | BOOLEAN | DEFAULT true |
| created_at | TIMESTAMP | DEFAULT now() |

### schedule_slots
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK |
| professional_id | UUID | FK → professionals.id, INDEX |
| patient_id | UUID | FK → patients.id, INDEX |
| start_at | TIMESTAMP | NOT NULL |
| end_at | TIMESTAMP | NOT NULL |
| status | VARCHAR(20) | DEFAULT 'available' |
| slot_type | VARCHAR(32) | DEFAULT 'first_visit' |
| source | VARCHAR(20) | DEFAULT 'manual' |
| notes | TEXT | |
| created_at | TIMESTAMP | DEFAULT now() |
| updated_at | TIMESTAMP | DEFAULT now() |

**Status enum:** available, booked, confirmed, cancelled, completed, no_show
**Slot type enum:** first_visit, follow_up, exam, procedure
**Source enum:** manual, telegram, whatsapp, web, phone

### conversations
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK |
| patient_id | UUID | FK → patients.id, INDEX |
| channel | VARCHAR(32) | DEFAULT 'telegram' |
| status | VARCHAR(20) | DEFAULT 'active' |
| current_intent | VARCHAR(64) | |
| confidence_score | FLOAT | |
| human_assignee | VARCHAR(128) | |
| last_message_at | TIMESTAMP | |
| created_at | TIMESTAMP | DEFAULT now() |
| updated_at | TIMESTAMP | DEFAULT now() |

**Status enum:** active, waiting_input, escalated, closed

### messages
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK |
| conversation_id | UUID | FK → conversations.id, INDEX, NOT NULL |
| direction | VARCHAR(10) | NOT NULL (inbound/outbound) |
| content | TEXT | NOT NULL |
| raw_payload | TEXT | |
| created_at | TIMESTAMP | DEFAULT now() |

### handoffs
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK |
| conversation_id | UUID | FK → conversations.id, INDEX, NOT NULL |
| reason | VARCHAR(255) | NOT NULL |
| priority | VARCHAR(20) | DEFAULT 'normal' |
| context_summary | TEXT | |
| status | VARCHAR(20) | DEFAULT 'open' |
| created_at | TIMESTAMP | DEFAULT now() |

### audit_events
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK |
| actor_type | VARCHAR(20) | NOT NULL (user/ai/system) |
| actor_id | VARCHAR(128) | NOT NULL |
| action | VARCHAR(128) | NOT NULL |
| resource_type | VARCHAR(64) | NOT NULL |
| resource_id | VARCHAR(128) | NOT NULL |
| payload | TEXT | JSON string |
| created_at | TIMESTAMP | DEFAULT now() |

### rag_documents
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK |
| title | VARCHAR(512) | NOT NULL |
| category | VARCHAR(64) | DEFAULT 'general' |
| source_path | VARCHAR(1024) | |
| version | VARCHAR(20) | DEFAULT '1.0' |
| status | VARCHAR(20) | DEFAULT 'active' |
| created_at | TIMESTAMP | DEFAULT now() |

### rag_chunks
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK |
| document_id | UUID | FK → rag_documents.id, INDEX, NOT NULL |
| chunk_index | INTEGER | DEFAULT 0 |
| content | TEXT | NOT NULL |
| embedding | VECTOR(1536) | pgvector |
| page | INTEGER | |
| metadata_json | TEXT | JSON string |
| created_at | TIMESTAMP | DEFAULT now() |

## Extensões
- `pgvector` — busca vetorial por similaridade de cosseno

## Diagrama de Relacionamentos
```
patients ─┬── schedule_slots
           ├── conversations ─┬── messages
           │                  └── handoffs
professionals ── schedule_slots

rag_documents ── rag_chunks

audit_events (standalone — trilha transversal)
```
