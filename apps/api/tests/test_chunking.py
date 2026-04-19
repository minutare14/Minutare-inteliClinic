from __future__ import annotations

import pytest
from app.core.chunking import semantic_chunk, HARD_MAX, MIN_CHUNK, CHUNK_SIZE


class TestChunkingHeadings:
    def test_h1_generates_chunk_with_heading(self):
        text = "# Título Principal\n\nEste é o conteúdo do primeiro título com informação relevante."
        chunks = semantic_chunk(text)
        assert len(chunks) >= 1
        assert any("# Título Principal" in c.content for c in chunks)

    def test_h2_generates_chunk(self):
        text = "## Subtítulo Importante\n\nConteúdo do subtítulo que tem tamanho suficiente."
        chunks = semantic_chunk(text)
        assert len(chunks) >= 1

    def test_headings_create_distinct_chunks(self):
        text = "# Seção A\n\nConteúdo da seção A com tamanho suficiente para ser chunk.\n\n## Seção B\n\nConteúdo da seção B também com tamanho adequado."
        chunks = semantic_chunk(text)
        assert len(chunks) >= 2
        # Verify headings appear in content
        heading_texts = [c.content for c in chunks]
        assert any("Seção A" in t for t in heading_texts)
        assert any("Seção B" in t for t in heading_texts)


class TestChunkingHardLimit:
    def test_no_chunk_exceeds_1000_chars(self):
        text = "A" * 400 + ". " + "B" * 400 + ". " + "C" * 200
        chunks = semantic_chunk(text)
        for chunk in chunks:
            assert len(chunk.content) <= HARD_MAX

    def test_long_text_splits(self):
        text = "Primeira frase completa. " * 30 + "Segunda frase completa. " * 30
        chunks = semantic_chunk(text)
        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk.content) <= HARD_MAX

    def test_sentence_split_respected(self):
        text = "Primeira frase completa. Segunda frase. Terceira frase muito longa que pode precisar de split."
        chunks = semantic_chunk(text)
        for chunk in chunks:
            assert len(chunk.content) <= HARD_MAX


class TestChunkingMinimum:
    def test_chunks_below_minimum_are_discarded(self):
        text = "ABC" * 20  # 60 chars - should appear
        chunks = semantic_chunk(text)
        for chunk in chunks:
            assert len(chunk.content) >= MIN_CHUNK

    def test_very_small_content_discarded(self):
        text = "x"
        chunks = semantic_chunk(text)
        # No chunks because content < MIN_CHUNK
        for chunk in chunks:
            assert len(chunk.content) >= MIN_CHUNK


class TestChunkingOverlap:
    def test_heading_context_propagates(self):
        text = "# Título Principal\n\n" + ("x" * 100 + "\n") * 5
        chunks = semantic_chunk(text)
        if len(chunks) > 1:
            has_context = any("Título Principal" in c.content for c in chunks)
            assert has_context


class TestChunkingTables:
    def test_tables_preserved(self):
        text = "| Coluna 1 | Coluna 2 |\n|----------|----------|\n| Dado A   | Dado B   |"
        chunks = semantic_chunk(text)
        table_chunks = [c for c in chunks if "Coluna 1" in c.content]
        assert len(table_chunks) >= 1


class TestChunkingLists:
    def test_list_items_become_chunks(self):
        text = "- Item um com conteúdo suficiente para ser um chunk separado\n- Item dois também com conteúdo adequado para gerar um chunk"
        chunks = semantic_chunk(text)
        assert len(chunks) >= 2

    def test_single_list_item_chunk(self):
        text = "- Um item de lista com conteúdo muito longo que deveria formar um chunk próprio e significativo para teste"
        chunks = semantic_chunk(text)
        assert len(chunks) >= 1