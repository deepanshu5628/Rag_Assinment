# Implementation Plan — FastAPI HTTP API + single-page Web UI for the Vectra KB RAG assistant

## Scope & intent

Additive layer on top of the existing, working RAG assistant. The ONLY answering
entry point is `from rag import answer` → returns EXACTLY
`{"answer": str, "citations": list[str], "abstained": bool}`. Do NOT modify the
core logic in `rag.py`, `ingest.py`, `pii.py`, `evaluate.py` (import only).

Repo: `c:\Users\Admin_IT\Desktop\Rag poc` (git repo, branch `master`, tree clean
at HEAD `60763af`). Work directly on `master`; no worktree. Final result is one
commit on `master`. Never commit `.env` (already in `.gitignore`).

## Key design decisions (grounded in the code I read)

1. **Run `answer()` in a worker thread, route handler is `async def` + `await run_in_threadpool(answer, question)`.**
   Rationale: `rag.py` uses `langchain-postgres` `PGEngine`, which spins up a
   background event loop (on Windows a `ProactorEventLoop`) and `asyncpg`. If the
   synchronous `answer()` (which drives that engine) is called directly inside an
   `async def` handler it runs on uvicorn's running event loop and can raise
   "event loop is already running" / cross-loop errors. Offloading to a thread
   via `starlette.concurrency.run_in_threadpool` (FastAPI re-exports it) gives
   `answer()` a thread with no running loop, letting PGEngine use its own
   background loop safely. This is the exact mitigation called out in the brief
   and the project's existing Windows async note. (Alternative — define the route
   as plain `def` so Starlette auto-threads it — is equally valid; I chose the
   explicit `run_in_threadpool` form so the threadpool behavior is visible in the
   code. Either satisfies the contract; do not do both.)

2. **Load `.env` at import time with `python-dotenv`** (`load_dotenv()` at the top
   of `api.py`), same as `rag.py`/`ingest.py`. `rag.py` also calls `load_dotenv()`
   on import, so config is loaded regardless; doing it in `api.py` too makes host/
   port env vars available before `rag` is imported.

3. **Pydantic request model with a non-empty constraint.** `question: str` with
   `min_length=1` plus an explicit strip check so whitespace-only bodies and
   missing fields both yield FastAPI's native 422. Response is returned as a plain
   dict (the exact dict from `answer()`), NOT re-serialized through a response
   model, so the three-key contract passes through byte-for-byte.

4. **Error handling that never leaks secrets/paths.** Wrap the `answer()` call in
   try/except. On exception: `logging.exception(...)` server-side (full stack
   trace to the server log only), and return `JSONResponse(status_code=500,
   content={"error": "Internal error answering the question."})` — a fixed generic
   message, never the exception text (which could contain the OpenAI key, a DSN,
   or a filesystem path).

5. **Self-contained UI, no network deps.** A single HTML document with inline CSS
   and vanilla JS, served by `GET /`. I will put it in `static/index.html` and
   serve it with `FileResponse` (keeps `api.py` readable and the HTML
   syntax-highlightable). No CDN links, no fonts/scripts fetched remotely, so it
   works offline. The page calls `fetch('/answer', …)` on the same origin.

6. **Host/port from env.** `API_HOST` (default `127.0.0.1`), `API_PORT` (default
   `8000`). `if __name__ == "__main__":` runs `uvicorn.run("api:app", host=…,
   port=…)` so `python api.py` starts the server.

7. **Dependency pins** (current stable, compatible with the pinned langchain
   stack — these are pure-Python ASGI libs with no conflicting constraints on
   langchain/pydantic; `pydantic` v2 is already pulled in transitively by
   langchain-core and is what FastAPI needs):
   - `fastapi==0.120.4`
   - `uvicorn[standard]==0.41.0`
   - `pydantic==2.12.3`  *(pin explicitly; confirm it matches the version already
     resolved in the environment during the install step — see item 6 — and adjust
     the pin to the resolved 2.x if pip reports a conflict with langchain-core).* 
   Rationale for pinning pydantic explicitly: FastAPI needs pydantic v2; the
   langchain stack also uses pydantic v2, so one shared pin avoids a silent
   resolver bump. If `pip install` reports a conflict, keep the langchain stack
   intact and relax the FastAPI/uvicorn pin instead (never downgrade langchain-core
   or pydantic below what the langchain stack requires).

## Environment gaps found during exploration (MUST handle in verification)

- **There is no `.venv` in the repo** right now, and **no `python`/`py` on PATH**
  (only the Microsoft Store alias stub). The brief assumes `.venv` exists with the
  stack installed; it does not in this environment. The prior `verification.md`
  shows the venv was previously created in a now-removed worktree
  (`.worktrees\rag-build`) via `python -m venv`.
  → The verification procedure below starts by locating a real Python 3.11+
  interpreter and creating `.venv`, then installing `requirements.txt`. If no
  system Python can be found, STOP and report this as a blocker (the code can be
  written and committed, but the mandatory live verification cannot run without a
  Python interpreter + a reachable OpenAI key).
- **Docker is available** (v29.8.1), so `docker compose up -d` for pgvector works.
- `.venv/` and `.env` are both gitignored, so neither can be swept into the commit.

## Build / test commands (discovered)

- No separate build step (pure Python). "Build" = successful import of `api.py`.
- Live check = start uvicorn and hit the endpoints with HTTP requests.
- Existing unit tests: `.venv\Scripts\python.exe -m pytest -q tests/` (should stay
  green; this change does not touch tested modules).

---

## Plan

- [ ] 1. Add pinned API dependencies to `requirements.txt`.
      Append `fastapi==0.120.4`, `uvicorn[standard]==0.41.0`, and
      `pydantic==2.12.3` under a new comment line (e.g. `# --- Web UI / API ---`).
      Keep every existing langchain pin unchanged.
      Files: `requirements.txt`
      Verify (done together with step 5's install): after creating `.venv` and
      running `.venv\Scripts\python.exe -m pip install -r requirements.txt`, pip
      reports no dependency conflicts and the langchain versions
      (`langchain==1.4.7`, `langchain-core==1.7.1`, `langchain-postgres==0.0.19`,
      `langchain-openai==1.7.3`, `langgraph==1.2.18`) are unchanged in
      `pip freeze`. If pip reports a conflict on `pydantic`, change only the
      FastAPI/uvicorn/pydantic pins to the versions pip resolves while keeping the
      langchain stack intact, then re-run.

- [ ] 2. Create the web UI page `static/index.html` — one self-contained document.
      Title/`<h1>` "Vectra IT Assistant (KB-only)". A `<textarea>` + an "Ask"
      `<button>`; submit on Enter (Enter submits, Shift+Enter newline). Six
      clickable example-question chips prefilled EXACTLY with:
      "My account got locked. How long until it unlocks by itself?",
      "What VPN server address should I use when working from home?",
      "What is the resolution target for a P2 ticket?",
      "How do I get a parking pass for the Gurugram office?",
      "Does ZenTunnel work on Linux?",
      "ZenTunnel shows ZT-401, what do I do?".
      Clicking a chip fills the textarea and submits. On submit: `fetch('/answer',
      {method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify({question})})`. Render: a loading state while awaiting;
      the `answer` text; `citations` as badge pills (e.g. "KB-007"); when
      `abstained === true` show an amber banner "No KB match — raise a ticket";
      on non-OK HTTP or network error show a red error box using the server's
      `{"error": …}` message when present, otherwise a generic message. All CSS
      inline in a `<style>` block; all JS inline in a `<script>` block; NO external
      CDN/font/script URLs (must work offline).
      Files: `static/index.html`
      Verify: deferred to the live HTTP checks in step 6 (`GET /` returns the page;
      manual/automated POST shows correct rendering). Opening the file has no build
      step.

- [ ] 3. Create `api.py` — the FastAPI app.
      Contents (one cohesive module):
      - `load_dotenv()` at top; `logging` configured; `from rag import answer`.
      - `app = FastAPI(title="Vectra IT Assistant (KB-only)")`.
      - Pydantic `AskRequest(BaseModel)` with `question: str = Field(min_length=1)`.
      - `GET /health` → `{"status": "ok"}`.
      - `GET /` → `FileResponse` of `static/index.html` (resolve path relative to
        `__file__`, not CWD).
      - `POST /answer` as `async def`: reject empty/whitespace question (rely on
        the `min_length=1` model for missing/empty → 422; add an explicit
        `question.strip()` guard that raises `HTTPException(422)` for
        whitespace-only). Call `result = await run_in_threadpool(answer,
        request.question)` inside try/except. On success return `result` (the exact
        three-key dict) as-is. On exception: `logging.exception("answer() failed")`
        and return `JSONResponse(status_code=500, content={"error": "Internal error
        answering the question."})`. Never include exception text, the OpenAI key,
        or paths in the response.
      - Mount or reference `static/` only as needed for `GET /` (a direct
        `FileResponse` is enough; a `StaticFiles` mount is optional).
      - `if __name__ == "__main__":` → read `API_HOST`/`API_PORT` env (defaults
        `127.0.0.1`/`8000`) and `uvicorn.run("api:app", host=host, port=port)`.
      Files: `api.py`
      Verify: `.venv\Scripts\python.exe -c "import api; print(type(api.app))"`
      imports without error and prints the FastAPI app type (confirms the module
      and the `from rag import answer` import resolve). Full behavior verified live
      in step 6.

- [ ] 4. Update `README.md` — add a "Web UI / API" section.
      Document: prerequisites recap (`docker compose up -d`, create/activate
      `.venv`, `pip install -r requirements.txt`, run `python ingest.py` ONCE so the
      KB is embedded before the API can answer); start the server with
      `python api.py`; the URL `http://127.0.0.1:8000` (browser UI at the root);
      the endpoints `GET /health`, `GET /`, `POST /answer`; a PowerShell + a
      `curl` example for `POST /answer`, e.g.
      `curl -s -X POST http://127.0.0.1:8000/answer -H "Content-Type: application/json" -d "{\"question\": \"What VPN server address should I use when working from home?\"}"`;
      note the `API_HOST`/`API_PORT` env overrides.
      Files: `README.md`
      Verify: section renders as valid markdown and the documented commands match
      what step 6 actually runs.

- [ ] 5. Create `.venv` and install dependencies (environment prep — this produces
      no committed files since `.venv/` is gitignored).
      Locate a Python 3.11+ interpreter (try `python`, `py -3`, common install
      paths such as `C:\Program Files\Python312\python.exe` or
      `%LocalAppData%\Programs\Python\Python312\python.exe`). Create the venv:
      `<python> -m venv "c:\Users\Admin_IT\Desktop\Rag poc\.venv"`. Then
      `c:\Users\Admin_IT\Desktop\Rag poc\.venv\Scripts\python.exe -m pip install -r requirements.txt`.
      If no interpreter can be found, STOP and report the blocker (code is written
      but live verification cannot run).
      Files: none committed (`.venv/` is gitignored).
      Verify: `.venv\Scripts\python.exe -m pip check` reports no broken
      requirements, and `pip freeze` shows the unchanged langchain pins alongside
      the new fastapi/uvicorn/pydantic.

- [ ] 6. MANDATORY live verification (run in order; use the absolute venv python
      `c:\Users\Admin_IT\Desktop\Rag poc\.venv\Scripts\python.exe`). This is the
      acceptance gate for the whole task.
      a. `docker compose up -d` (from repo root); wait for the `vectra-rag-pgvector`
         container to be healthy (`docker compose ps`).
      b. `...\.venv\Scripts\python.exe ingest.py` — expect the 7 current docs
         ingested (KB-001,003,004,005,006,007,008), KB-002 & KB-099 skipped, total
         14 chunks. This must succeed before the API can answer. (Requires a valid
         `OPENAI_API_KEY` in `.env`.)
      c. Start the API in the BACKGROUND: run
         `...\.venv\Scripts\python.exe api.py` as a background process (capture its
         PID/handle so it can be stopped in step g). Wait until it is listening on
         `127.0.0.1:8000`.
      d. `GET /health` → HTTP 200, body `{"status": "ok"}`.
      e. `GET /` → HTTP 200, `Content-Type: text/html`, body contains the title
         "Vectra IT Assistant (KB-only)" and at least one example chip string.
      f. `POST /answer` checks (use `Invoke-RestMethod`/`curl` with
         `Content-Type: application/json`):
         - VPN question `{"question": "What VPN server address should I use when working from home?"}`
           → HTTP 200, `abstained == false`, `citations` contains `"KB-007"`, and
           `answer` mentions `zt-gw.vectralogistics.example`. **This is the primary
           proof that `answer()` runs correctly through the API without an event-loop
           error.** If this raises a 500 with an event-loop error in the server log,
           the `run_in_threadpool` offload is missing/incorrect — fix `api.py`
           (ensure `answer()` runs in a worker thread, not on uvicorn's loop) and
           re-test.
         - Parking question `{"question": "How do I get a parking pass for the Gurugram office?"}`
           → HTTP 200, `abstained == true`, `citations == []`.
         - Empty body `{"question": ""}` → HTTP 422.
         - Whitespace body `{"question": "   "}` → HTTP 422.
         - Missing field `{}` → HTTP 422.
      g. STOP the background API process (kill the captured PID/handle). Leave the
         pgvector container UP (do NOT `docker compose down`).
      Files: none.
      Verify: every expectation in a–f holds; record the actual HTTP statuses and
      JSON bodies as evidence. If f's VPN case failed on an event-loop error and
      was fixed, re-run f end-to-end and confirm it now passes.

- [ ] 7. Secrets / hygiene check, then commit on `master`.
      Confirm `.env` is still gitignored and NOT staged (`git status`,
      `git check-ignore .env`), and that no `OPENAI_API_KEY` / `sk-` key value
      appears in any file to be committed (`api.py`, `static/index.html`,
      `requirements.txt`, `README.md`) — grep the staged diff for `sk-` and
      `OPENAI_API_KEY`. Stage ONLY the intended files by name:
      `git add api.py static/index.html requirements.txt README.md` (plus the plan
      file if the workflow wants it tracked — otherwise leave `.agents/` as-is).
      Do NOT use `git add -A`. Commit with a clear message, e.g.
      `feat: add FastAPI /answer + /health API and single-page KB assistant web UI`.
      Files: git index / commit.
      Verify: `git status` shows a clean tree with the new commit on `master`;
      `git show --stat HEAD` lists exactly the intended files and NOT `.env` or
      `.venv/`; the grep for key material in the committed diff returns nothing.

## Notes / assumptions

- Assumed the OpenAI key in `.env` is valid and the machine can reach the OpenAI
  API; `ingest.py` and the live VPN check both require it. If the key is
  missing/invalid, ingestion/answering will fail — report that rather than
  silently skipping the live gate.
- Chose `static/index.html` + `FileResponse` over an inline HTML string so the
  markup stays maintainable; the brief allows either.
- Chose explicit `await run_in_threadpool(answer, …)` over a plain `def` handler;
  both are acceptable per the brief. Do not combine them.
- Pydantic is pinned explicitly but must track whatever 2.x the langchain stack
  resolves; the install step is the authority if the pin needs nudging.
