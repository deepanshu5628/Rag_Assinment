"""Ingestion for the Vectra Logistics KB-only RAG assistant.

Responsibilities
----------------
1. Discover ``vectra_kb_articles/kb/KB-*.md``.
2. Parse YAML front-matter (doc_id, title, status, effective_date, and the
   optional superseded_by / supersedes / owner fields).
3. Ingest ONLY ``status == "current"`` articles. Skip everything else and LOG
   each skip with the reason (KB-002 deprecated->KB-007, KB-099 unverified +
   prompt-injection).
4. Table-safe chunking: keep short articles whole, otherwise split on ``##``
   headings, but NEVER split a markdown ``| ... |`` table across chunks
   (KB-003 SLA table and KB-007 error-code table must each stay intact).
5. Embed with text-embedding-3-small and store in pgvector via the modern
   langchain-postgres PGVectorStore (NOT the deprecated PGVector class), with
   doc_id/status/title/effective_date as real, filterable metadata columns.
6. Report chunks per doc; mask PII in every log line.

Run:  python ingest.py   (DB must be up: docker compose up -d)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_postgres import Column, PGEngine, PGVectorStore
from langchain_postgres.v2.indexes import DistanceStrategy

from pii import mask_pii

load_dotenv()

# --- Configuration (env with sensible defaults) -----------------------------
KB_DIR = Path(__file__).parent / "vectra_kb_articles" / "kb"


def _normalize_db_url(url: str) -> str:
    """Coerce any standard Postgres URL to the async (asyncpg) driver form.

    Managed providers (Railway, Neon, Supabase, Render) hand out a plain
    ``postgres://`` / ``postgresql://`` DSN. PGEngine needs an async SQLAlchemy
    driver URL; asyncpg is used (not psycopg3-async) because on Windows
    PGEngine's background event loop is a ProactorEventLoop that psycopg3's
    async mode rejects while asyncpg works on either. This lets you paste a
    provider's connection string verbatim into DATABASE_URL.
    """
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://"):]
    if "+asyncpg://" in url and "?" in url:
        url = url.split("?", 1)[0]
    return url


# Async driver URL. We use asyncpg (not psycopg3-async) because on Windows the
# default asyncio ProactorEventLoop that PGEngine's background thread runs is
# not compatible with psycopg3's async mode; asyncpg works on either loop.
DATABASE_URL = _normalize_db_url(
    os.getenv("DATABASE_URL", "postgresql+asyncpg://rag:rag@localhost:5433/ragdb")
)
TABLE_NAME = os.getenv("TABLE_NAME", "kb_chunks")
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536  # text-embedding-3-small dimensionality

# Metadata columns promoted to real (indexed, filterable) table columns.
METADATA_COLUMN_NAMES = ["doc_id", "status", "title", "effective_date"]


def _log(msg: str) -> None:
    """Print a log line with any user/PII text masked."""
    print(mask_pii(msg), flush=True)


# --- Front-matter parsing ----------------------------------------------------
def parse_front_matter(raw: str) -> tuple[dict, str]:
    """Split a ``---`` fenced YAML front-matter block from the markdown body.

    Returns (metadata_dict, body_text). If there is no front-matter the first
    element is an empty dict and the body is the whole text.
    """
    if raw.startswith("---"):
        parts = raw.split("---", 2)
        if len(parts) == 3:
            meta = yaml.safe_load(parts[1]) or {}
            body = parts[2].lstrip("\n")
            return meta, body
    return {}, raw


# --- Table-safe chunking -----------------------------------------------------
def _is_table_line(line: str) -> bool:
    return line.lstrip().startswith("|")


def _split_sections(body: str) -> list[str]:
    """Split a markdown body into sections on top-level ``##`` headings.

    The text before the first ``##`` (intro + the ``#`` H1) is its own section.
    A ``##`` heading starts a new section. Crucially, a markdown table block is
    never split: table lines always stay attached to the section they belong
    to (we only break on ``##`` lines, and a ``##`` never appears mid-table).
    """
    lines = body.splitlines()
    sections: list[list[str]] = []
    current: list[str] = []
    in_table = False

    for line in lines:
        if _is_table_line(line):
            in_table = True
        elif line.strip() == "":
            in_table = False  # blank line ends a table block

        is_heading = line.startswith("## ") and not in_table
        if is_heading and current:
            sections.append(current)
            current = [line]
        else:
            current.append(line)
    if current:
        sections.append(current)

    return [("\n".join(s)).strip() for s in sections if "\n".join(s).strip()]


def chunk_article(doc_id: str, title: str, body: str) -> list[str]:
    """Return table-safe chunks for one article.

    - No ``##`` headings -> keep the WHOLE article as one chunk. This keeps a
      short article whole and, critically, keeps a heading-less article that is
      mostly a markdown table (e.g. KB-003's SLA table) intact in one chunk.
    - Has ``##`` headings -> split on those headings; each section is one chunk.
      Because a ``##`` heading never appears in the middle of a markdown table,
      any table stays wholly inside the one section it belongs to (e.g. KB-007's
      error-code table lives entirely in its "## Common errors" section).

    Each chunk is prefixed with a ``doc_id: KB-00N - <title>`` header line to
    make grounding/citation easy; the authoritative doc_id still lives in the
    vector metadata. The presence of ``##`` headings is the deciding factor so
    that structured articles always split into their natural sections.
    """
    body = body.strip()
    header = f"doc_id: {doc_id} - {title}"

    has_headings = any(ln.startswith("## ") for ln in body.splitlines())
    if not has_headings:
        chunks = [body]
    else:
        chunks = _split_sections(body)

    return [f"{header}\n\n{c}" for c in chunks]


# --- Loading & filtering -----------------------------------------------------
def _skip_reason(meta: dict) -> str:
    status = meta.get("status")
    doc_id = meta.get("doc_id", "?")
    if status == "deprecated":
        sb = meta.get("superseded_by")
        extra = f", superseded_by {sb}" if sb else ""
        return f"status=deprecated{extra}"
    if status == "unverified":
        return "status=unverified (unreviewed community content; contains a prompt-injection)"
    return f"status={status!r} (not 'current')"


def load_documents() -> tuple[list[Document], list[tuple[str, int]], list[tuple[str, str]]]:
    """Load, filter and chunk all KB files.

    Returns (documents, per_doc_chunk_counts, skipped) where skipped is a list
    of (doc_id, reason).
    """
    documents: list[Document] = []
    per_doc: list[tuple[str, int]] = []
    skipped: list[tuple[str, str]] = []

    for path in sorted(KB_DIR.glob("KB-*.md")):
        raw = path.read_text(encoding="utf-8")
        meta, body = parse_front_matter(raw)
        doc_id = meta.get("doc_id", path.stem)
        status = meta.get("status")
        title = meta.get("title", "")

        if status != "current":
            reason = _skip_reason(meta)
            skipped.append((doc_id, reason))
            _log(f"SKIP  {doc_id} ({path.name}): {reason}")
            continue

        chunks = chunk_article(doc_id, title, body)
        for chunk_text in chunks:
            documents.append(
                Document(
                    page_content=chunk_text,
                    metadata={
                        "doc_id": doc_id,
                        "status": status,
                        "title": title,
                        "effective_date": str(meta.get("effective_date", "")),
                    },
                )
            )
        per_doc.append((doc_id, len(chunks)))
        _log(f"INGEST {doc_id} ({path.name}): {len(chunks)} chunk(s)")

    return documents, per_doc, skipped


# --- Store setup -------------------------------------------------------------
def build_store(embeddings: OpenAIEmbeddings) -> tuple[PGEngine, PGVectorStore]:
    """Create the engine, (re)create the vector table, and return the store."""
    engine = PGEngine.from_connection_string(DATABASE_URL)
    # init_vectorstore_table also runs CREATE EXTENSION IF NOT EXISTS vector.
    engine.init_vectorstore_table(
        table_name=TABLE_NAME,
        vector_size=EMBEDDING_DIM,
        metadata_columns=[
            Column("doc_id", "TEXT"),
            Column("status", "TEXT"),
            Column("title", "TEXT"),
            Column("effective_date", "TEXT"),
        ],
        overwrite_existing=True,  # idempotent: re-running ingest rebuilds the table
        store_metadata=True,
    )
    store = PGVectorStore.create_sync(
        engine=engine,
        embedding_service=embeddings,
        table_name=TABLE_NAME,
        metadata_columns=METADATA_COLUMN_NAMES,
        distance_strategy=DistanceStrategy.COSINE_DISTANCE,
        k=4,
    )
    return engine, store


def main() -> int:
    if not os.getenv("OPENAI_API_KEY"):
        _log("ERROR: OPENAI_API_KEY is not set. Put it in .env.")
        return 2

    _log("=== Vectra KB ingestion ===")
    documents, per_doc, skipped = load_documents()

    if not documents:
        _log("ERROR: no 'current' documents found to ingest.")
        return 1

    embeddings = OpenAIEmbeddings(model=EMBEDDING_MODEL)
    engine, store = build_store(embeddings)
    store.add_documents(documents)

    # --- Report --------------------------------------------------------------
    _log("")
    _log("--- Ingestion report ---")
    _log(f"Ingested docs: {len(per_doc)} (expected 7 current articles)")
    for doc_id, n in per_doc:
        _log(f"  {doc_id}: {n} chunk(s)")
    _log(f"Skipped docs: {len(skipped)}")
    for doc_id, reason in skipped:
        _log(f"  {doc_id}: {reason}")
    _log(f"Total chunks stored: {len(documents)}")

    # Clean up the background engine connection pool.
    import asyncio

    try:
        asyncio.run_coroutine_threadsafe(
            engine._pool.dispose(), engine._loop
        ).result()
    except Exception:  # pragma: no cover - best-effort cleanup
        pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
