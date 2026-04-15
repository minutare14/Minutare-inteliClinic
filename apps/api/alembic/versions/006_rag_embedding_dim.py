"""Alter rag_chunks.embedding vector dimension to match EMBEDDING_DIM env var.

Motivation:
  O provider padrão de embeddings passou a ser local/fastembed (384 dims).
  A coluna anterior era vector(1536) para OpenAI text-embedding-3-small.
  Esta migration nulifica embeddings existentes (precisam de reindexação)
  e altera a coluna para a dimensão configurada.

  Após executar esta migration, use POST /api/v1/rag/reindex para regenerar
  os embeddings de todos os documentos existentes.

EMBEDDING_DIM env var:
  384  → local/fastembed (padrão — gratuito, sem API key)
  768  → gemini/text-embedding-004
  1536 → openai/text-embedding-3-small

Revision ID: 006
Revises: 005
Create Date: 2026-04-15
"""
from __future__ import annotations

import os
from typing import Sequence, Union

from alembic import op

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    dim = int(os.environ.get("EMBEDDING_DIM", "384"))

    # 1. Nulificar todos os embeddings existentes (serão regenerados via /reindex)
    #    Isso é seguro porque:
    #    - Chunks sem embedding já estão NULL
    #    - Chunks com embedding de dim diferente precisam de regeneração mesmo assim
    op.execute("UPDATE rag_chunks SET embedding = NULL")

    # 2. Alterar a coluna para a nova dimensão configurada
    op.execute(
        f"ALTER TABLE rag_chunks ALTER COLUMN embedding TYPE vector({dim}) USING NULL"
    )


def downgrade() -> None:
    # Downgrade reverte para 1536 (OpenAI default)
    op.execute("UPDATE rag_chunks SET embedding = NULL")
    op.execute(
        "ALTER TABLE rag_chunks ALTER COLUMN embedding TYPE vector(1536) USING NULL"
    )
