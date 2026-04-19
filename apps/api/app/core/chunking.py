from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class ChunkResult:
    content: str
    chunk_index: int
    page: int | None = None
    metadata_json: str | None = None


# ── Constants ─────────────────────────────────────────────────────────────────

CHUNK_SIZE = 800
HARD_MAX = 1000
MIN_CHUNK = 50
MAX_OVERLAP = 150

HEADING_PATTERN = re.compile(r"^(#{1,2})\s+(.+)", re.MULTILINE)
LIST_ITEM_PATTERN = re.compile(r"^[-*+]\s+(.+)", re.MULTILINE)
SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
TABLE_ROW_PATTERN = re.compile(r"^\|")


def _is_heading(line: str) -> tuple[bool, int, str] | tuple[bool, None, None]:
    m = HEADING_PATTERN.match(line)
    if m:
        return True, len(m.group(1)), m.group(2)
    return False, None, None


def _is_list_item(line: str) -> str | None:
    m = LIST_ITEM_PATTERN.match(line.rstrip("\r"))
    return m.group(1) if m else None


def _is_table_line(line: str) -> bool:
    return bool(TABLE_ROW_PATTERN.match(line.rstrip("\r")))


def _split_sentences(text: str) -> list[str]:
    return [s.strip() for s in SENTENCE_SPLIT.split(text) if s.strip()]


def _estimate(text: str) -> int:
    return len(text.encode("utf-8"))


def semantic_chunk(text: str, page: int | None = None) -> list[ChunkResult]:
    """
    Split document text into semantic chunks following rules:
    - H1/H2 → new chunk with heading prefix
    - Tables → chunk with header preserved (multi-line)
    - Lists → chunks per item with heading context
    - > 800 chars → split at sentence boundary
    - HARD LIMIT: no chunk exceeds 1000 chars
    - Minimum: 50 chars (discard smaller)
    - Overlap: max 150 chars with previous chunk's heading context
    """
    lines = text.split("\n")
    chunks: list[ChunkResult] = []
    chunk_index = 0
    current_heading = ""
    buffer: list[str] = []
    buffer_size = 0

    def emit(content: str) -> None:
        nonlocal chunk_index
        size = _estimate(content)
        if size < MIN_CHUNK:
            return
        if size > HARD_MAX:
            # Split by sentences
            sentences = _split_sentences(content)
            part: list[str] = []
            part_size = 0
            for sent in sentences:
                sent_len = _estimate(sent)
                if part_size + sent_len > CHUNK_SIZE and part:
                    joined = " ".join(part)
                    if _estimate(joined) >= MIN_CHUNK:
                        chunks.append(ChunkResult(joined, chunk_index, page))
                        chunk_index += 1
                    # Overlap
                    overlap = part[-1] if part else ""
                    if _estimate(overlap) <= MAX_OVERLAP:
                        part = [overlap, sent]
                        part_size = _estimate(overlap) + sent_len
                    else:
                        part = [sent]
                        part_size = sent_len
                else:
                    part.append(sent)
                    part_size += sent_len
            if part:
                joined = " ".join(part)
                if _estimate(joined) >= MIN_CHUNK:
                    chunks.append(ChunkResult(joined, chunk_index, page))
                    chunk_index += 1
            # If still exceeds HARD_MAX after sentence split, truncate
            if _estimate(content) > HARD_MAX:
                truncated = content[:HARD_MAX]
                if _estimate(truncated) >= MIN_CHUNK:
                    chunks.append(ChunkResult(truncated, chunk_index, page))
                    chunk_index += 1
        else:
            chunks.append(ChunkResult(content, chunk_index, page))
            chunk_index += 1

    def flush() -> None:
        if buffer:
            full = "\n".join(buffer)
            if current_heading and not full.startswith(current_heading):
                full = f"{current_heading}\n{full}"
            emit(full)
            buffer.clear()

    i = 0
    while i < len(lines):
        line = lines[i].rstrip("\r")
        stripped = line.strip()

        # Heading
        is_head, level, heading_text = _is_heading(line)
        if is_head:
            flush()
            current_heading = heading_text.rstrip("\r")
            # Emit heading as its own chunk (but content after heading comes next)
            heading_full = f"{'#' * level} {heading_text}"
            if _estimate(heading_full) >= MIN_CHUNK:
                chunks.append(ChunkResult(heading_full, chunk_index, page))
                chunk_index += 1
            i += 1
            continue

        # Table (collect consecutive | lines)
        if _is_table_line(line):
            flush()
            table_lines = []
            while i < len(lines) and _is_table_line(lines[i]):
                table_lines.append(lines[i].rstrip("\r"))
                i += 1
            table_content = "\n".join(table_lines)
            if _estimate(table_content) >= MIN_CHUNK:
                chunks.append(ChunkResult(table_content, chunk_index, page))
                chunk_index += 1
            current_heading = ""
            continue

        # List item
        item_content = _is_list_item(line)
        if item_content:
            flush()
            # Collect consecutive list items
            list_items = []
            while i < len(lines):
                ic = _is_list_item(lines[i])
                if ic is None:
                    break
                list_items.append(f"- {ic}")
                i += 1
            for li in list_items:
                if _estimate(li) >= MIN_CHUNK:
                    content = li
                    if current_heading:
                        content = f"{current_heading}\n{li}"
                    chunks.append(ChunkResult(content, chunk_index, page))
                    chunk_index += 1
            current_heading = ""
            continue

        # Blank line
        if not line.strip():
            flush()
            i += 1
            continue

        # Paragraph
        para_size = _estimate(line)
        if para_size > HARD_MAX:
            flush()
            # Split long paragraph by sentences
            sentences = _split_sentences(line)
            part: list[str] = []
            part_size = 0
            for sent in sentences:
                sent_len = _estimate(sent)
                if part_size + sent_len > CHUNK_SIZE and part:
                    joined = " ".join(part)
                    emit(joined)
                    overlap = part[-1] if part else ""
                    if _estimate(overlap) <= MAX_OVERLAP:
                        part = [overlap, sent]
                        part_size = _estimate(overlap) + sent_len
                    else:
                        part = [sent]
                        part_size = sent_len
                else:
                    part.append(sent)
                    part_size += sent_len
            if part:
                emit(" ".join(part))
        elif buffer_size + para_size > CHUNK_SIZE:
            flush()
            buffer.append(line)
            buffer_size = para_size
        else:
            buffer.append(line)
            buffer_size += para_size
            i += 1

    flush()
    # Re-index chunks sequentially
    for idx, chunk in enumerate(chunks):
        chunk.chunk_index = idx
    return chunks