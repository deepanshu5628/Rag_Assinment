"""FastAPI HTTP API + single-page web UI for the Vectra KB RAG assistant.

This is a thin, additive layer on top of the existing assistant. The ONLY
answering entry point is ``rag.answer(question) -> dict`` which returns EXACTLY
``{"answer": str, "citations": list[str], "abstained": bool}``. This module does
not touch the core logic; it only imports ``answer`` and exposes it over HTTP.

Endpoints
---------
- ``GET  /``        -> the self-contained browser UI (static/index.html).
- ``GET  /health``  -> ``{"status": "ok"}``.
- ``POST /answer``  -> body ``{"question": "<text>"}`` (422 if missing/empty);
  returns the exact three-key dict from ``answer()``.

Windows / asyncpg note
----------------------
``rag.py`` drives ``langchain-postgres`` ``PGEngine``, which runs its own
background event loop (a ``ProactorEventLoop`` on Windows) with ``asyncpg``.
Calling the synchronous ``answer()`` directly on uvicorn's running event loop
can raise cross-loop / "event loop is already running" errors. We therefore
offload ``answer()`` to a worker thread via ``run_in_threadpool`` so it executes
on a thread with no running loop and PGEngine can use its own loop safely.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

# Load .env before importing rag (which also loads it) so API_HOST/API_PORT and
# the OpenAI/DB config are available at startup.
load_dotenv()

from rag import answer  # noqa: E402  (import after load_dotenv, by design)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("vectra.api")

STATIC_DIR = Path(__file__).resolve().parent / "static"
INDEX_HTML = STATIC_DIR / "index.html"

app = FastAPI(title="Vectra IT Assistant (KB-only)")


class AskRequest(BaseModel):
    """Request body for POST /answer. Missing/empty question -> 422."""

    question: str = Field(..., min_length=1, description="The staff question.")


@app.get("/health")
def health() -> dict:
    """Liveness probe."""
    return {"status": "ok"}


@app.get("/")
def index() -> FileResponse:
    """Serve the single-page web UI."""
    return FileResponse(INDEX_HTML, media_type="text/html")


@app.post("/answer")
async def post_answer(request: AskRequest):
    """Answer a question via the KB-only assistant.

    Returns the exact dict from ``rag.answer()``. On any failure, logs the stack
    trace server-side and returns a generic 500 that never leaks the OpenAI key,
    the DB DSN, or internal paths.
    """
    question = request.question.strip()
    if not question:
        # Whitespace-only passes min_length=1 but is still an empty question.
        return JSONResponse(
            status_code=422,
            content={
                "detail": [
                    {
                        "type": "string_too_short",
                        "loc": ["body", "question"],
                        "msg": "question must not be empty",
                    }
                ]
            },
        )

    try:
        # Run the synchronous answer() off uvicorn's event loop (see module docstring).
        result = await run_in_threadpool(answer, question)
    except Exception:  # noqa: BLE001 - we deliberately swallow and genericize.
        logger.exception("answer() failed")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal error answering the question."},
        )

    # result is already the exact {"answer", "citations", "abstained"} dict.
    return result


if __name__ == "__main__":
    # Host/port resolution works both locally and on PaaS hosts (Railway,
    # Render, etc.). Those platforms inject the public port as $PORT and expect
    # the server to bind 0.0.0.0. Precedence:
    #   port: $PORT (platform) -> $API_PORT (local override) -> 8000
    #   host: $API_HOST if set -> 0.0.0.0 when $PORT is present (deployed)
    #         -> 127.0.0.1 locally (safer default for a dev machine)
    port = int(os.getenv("PORT") or os.getenv("API_PORT") or "8000")
    default_host = "0.0.0.0" if os.getenv("PORT") else "127.0.0.1"
    host = os.getenv("API_HOST", default_host)
    uvicorn.run("api:app", host=host, port=port)
