# FastAPI /answer + /health API and single-page KB assistant web UI

An additive HTTP layer over the existing Vectra KB RAG assistant. `api.py` wraps the unchanged `rag.answer()` behind three endpoints (`GET /`, `GET /health`, `POST /answer`) and serves a self-contained, build-free browser UI at `static/index.html`. The synchronous `answer()` is offloaded to a worker thread via `run_in_threadpool`, which is the correct mitigation for the Windows `PGEngine`/`asyncpg` background-loop collision. Validation, error genericization, env-configurable host/port, and the `__main__` uvicorn block are all present and match the contract. The coder's verification evidence records real HTTP responses for every required case.

Watch for: nothing blocking. One minor UI behavior (chip 422 message wording) and one cosmetic requirements.txt comment are noted below, neither gating. (confirmed)

**Verdict**: APPROVED

## High-level view

The answering path is correct and this is the thing most likely to break on this stack. `POST /answer` is an `async def` handler that awaits `run_in_threadpool(answer, question)`, so the synchronous `answer()` — which drives `PGEngine`'s own background `ProactorEventLoop` and `asyncpg` — runs on a thread with no running loop instead of colliding with uvicorn's. The verification evidence's VPN call returning `abstained=false`, `citations=["KB-007"]`, and the `zt-gw.vectralogistics.example` address is the concrete proof this offload works end to end.

The API surface matches the contract exactly. `GET /health` returns `{"status":"ok"}`, `GET /` serves the HTML by `FileResponse` resolved relative to `__file__`, and `POST /answer` returns the `answer()` dict verbatim (no response model re-serialization), so the three-key shape passes through untouched. Validation is layered: Pydantic `min_length=1` catches missing/empty for a native 422, and an explicit `.strip()` guard returns a 422 for whitespace-only.

Secrets posture is sound. On any `answer()` exception the handler logs the stack trace server-side and returns a fixed `{"error":"Internal error..."}` with status 500 — the exception text, OpenAI key, and DB DSN never reach the client. `.env` stays gitignored and untracked, and no key material is in any committed file.

The core logic is untouched. The commit adds six files and modifies none of `rag.py`, `ingest.py`, `pii.py`, or `evaluate.py`. The new FastAPI/uvicorn/pydantic pins install clean against the langchain stack per the recorded `pip check`.

<details>
<summary>Issues (2)</summary>

1. **Chip-triggered 422 wording** — a clicked example chip always carries a non-empty question, so the 422 branch is unreachable from chips; the generic "Please enter a valid question." message on 422 is slightly misleading but harmless since valid questions never hit it. No action required; noted for awareness. (confirmed)
2. **requirements.txt header comment** — the top comment says pins are "verified installed in .venv", but the verification ran in a Docker container because no host Python exists. Cosmetic; update the comment wording if desired. (confirmed)

</details>

<details>
<summary>Details</summary>

### answer() offloaded off uvicorn's loop

The one real risk on this stack is calling the synchronous `answer()` from inside an async handler, which would run it on uvicorn's event loop and collide with `PGEngine`'s background `ProactorEventLoop` + `asyncpg`. The handler avoids this:

```python
@app.post("/answer")
async def post_answer(request: AskRequest):
    ...
    result = await run_in_threadpool(answer, question)
```

`run_in_threadpool` hands `answer()` a thread with no running loop, so `PGEngine` drives its own loop undisturbed. The plan called for exactly this (and warned against combining it with a plain `def` route — the code uses only the `run_in_threadpool` form). The verification evidence's VPN POST returning HTTP 200 with `abstained=false`, `citations=["KB-007"]`, and an answer naming `zt-gw.vectralogistics.example` (not the deprecated `vpn.vectralogistics.example`/KB-002) is the proof the offload works through the full request path, with the server log showing the embeddings + chat completion calls succeeding. (confirmed)

### Validation: two layers to 422

`AskRequest.question` is `Field(..., min_length=1)`, so a missing field or empty string produces FastAPI's native 422 before the handler body runs. Whitespace-only strings pass `min_length=1`, so the handler adds an explicit `request.question.strip()` guard that returns a hand-built 422 payload. The evidence records all three invalid cases (`""`, `"   "`, `{}`) returning 422. The whitespace branch returns a `JSONResponse(status_code=422, ...)` rather than raising `HTTPException`; the resulting body differs slightly in shape from the native validation error, but both are 422 and the UI treats any `detail` as a validation failure, so the contract holds. (confirmed)

### Error handling never leaks secrets or paths

```python
except Exception:
    logger.exception("answer() failed")
    return JSONResponse(status_code=500, content={"error": "Internal error answering the question."})
```

The full stack trace goes to the server log via `logger.exception`; the client gets a fixed generic string. No exception text, OpenAI key, DSN, or filesystem path can reach the response. The grep of the committed diff found no `sk-` key material, and `.env` is gitignored and untracked — the only `OPENAI_API_KEY`/`sk-` string matches in the repo are prose references inside the plan/verification markdown, not real values. (confirmed)

### Self-contained UI

`static/index.html` is one document: inline `<style>`, inline vanilla `<script>`, no CDN/font/script URLs, so it works offline with no build step. The title and `<h1>` are "Vectra IT Assistant (KB-only)". The six example chips are prefilled with the exact required prompts (account-lock, VPN address, P2 SLA, parking pass, ZenTunnel on Linux, ZT-401). Enter submits and Shift+Enter inserts a newline. The render path shows a spinner while awaiting, the answer text (HTML-escaped, so citations/answers can't inject markup), citation badge pills, an amber "No KB match — raise a ticket" banner when `abstained === true`, and a red error box that prefers the server's `{"error":...}` message. (confirmed)

One minor note: when a 422 comes back, the UI maps any `detail` to "Please enter a valid question." Because every example chip carries a non-empty question and the manual Ask path blocks empty input client-side before fetching, the 422 branch is effectively unreachable in normal use — the wording is slightly generic but never surfaces misleadingly. Not gating. (confirmed)

### Dependencies install clean against the langchain stack

`requirements.txt` adds `fastapi==0.120.4`, `uvicorn[standard]==0.41.0`, and `pydantic==2.12.3` under a `# --- Web UI / API ---` block, with every existing langchain pin unchanged. The verification evidence's `pip check` reports "No broken requirements found", and `pip freeze` confirms the langchain pins (`langchain==1.4.7`, `langchain-core==1.7.1`, `langchain-postgres==0.0.19`, `langchain-openai==1.7.3`, `langgraph==1.2.18`) are intact alongside the new pins. The header comment claims the pins were "verified installed in .venv", but the evidence shows verification ran in a `python:3.12-slim` container because the host has no usable Python. Cosmetic wording mismatch only. (confirmed)

### Core logic untouched

`git show --stat HEAD` lists exactly six added files — the two task markdown docs, `README.md`, `api.py`, `requirements.txt`, and `static/index.html`. None of `rag.py`, `ingest.py`, `pii.py`, or `evaluate.py` appears in the commit, so the answering logic is import-only as required. (confirmed)

</details>

<details>
<summary>File map</summary>

- `api.py` — new FastAPI app: `/`, `/health`, `/answer`; `run_in_threadpool(answer)`; 422/500 handling; `__main__` uvicorn block with env host/port.
- `static/index.html` — new self-contained UI: title, textarea + Ask, Enter-submit, six example chips, answer/citation/abstain/loading/error states.
- `requirements.txt` — adds pinned `fastapi`, `uvicorn[standard]`, `pydantic`; langchain pins unchanged.
- `README.md` — adds the "Web UI / API" section.
- `.agents/tasks/api-ui-plan.md`, `.agents/tasks/api-ui-verification.md` — plan and verification evidence.

Full diff: `git show HEAD` (commit `fb74760`).

</details>
