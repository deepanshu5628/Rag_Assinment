"""Unit tests for the table-safe chunker in ingest.py (no DB, no network)."""

from pathlib import Path

from ingest import chunk_article, parse_front_matter

KB_DIR = Path(__file__).parent.parent / "vectra_kb_articles" / "kb"


def _load(doc_file: str):
    raw = (KB_DIR / doc_file).read_text(encoding="utf-8")
    meta, body = parse_front_matter(raw)
    return meta, body


def _find_chunk_with(chunks, needle):
    for c in chunks:
        if needle in c:
            return c
    return None


def test_kb003_sla_table_not_split():
    meta, body = _load("KB-003_priority_sla.md")
    chunks = chunk_article(meta["doc_id"], meta["title"], body)
    chunk = _find_chunk_with(chunks, "| P1 |")
    assert chunk is not None
    # Full table header through last data row must live in ONE chunk.
    assert "| Priority | Definition |" in chunk
    assert "| P1 |" in chunk
    assert "| P2 |" in chunk
    assert "| P3 |" in chunk
    assert "| P4 |" in chunk


def test_kb007_error_table_not_split():
    meta, body = _load("KB-007_vpn_zentunnel.md")
    chunks = chunk_article(meta["doc_id"], meta["title"], body)
    chunk = _find_chunk_with(chunks, "ZT-401")
    assert chunk is not None
    # The whole error-code table (ZT-401 row through the last row) stays whole.
    assert "ZT-401" in chunk
    assert "ZT-503" in chunk
    assert "Negotiating" in chunk
    assert "Refresh profile" in chunk


def test_kb005_splits_on_headings():
    meta, body = _load("KB-005_warehouse_devices.md")
    chunks = chunk_article(meta["doc_id"], meta["title"], body)
    # KB-005 has two ## sections and no tables -> more than one chunk.
    assert len(chunks) >= 2
    scanners = _find_chunk_with(chunks, "Handheld scanners")
    printers = _find_chunk_with(chunks, "Label printers")
    assert scanners is not None and printers is not None
    assert scanners is not printers
