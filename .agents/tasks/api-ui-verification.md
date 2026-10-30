# Live verification — FastAPI API + web UI

This records the exact commands run and the ACTUAL outputs for the additive
FastAPI/UI layer (`api.py`, `static/index.html`). The reviewer can read this
without re-running anything.

## Environment note (important)

There is **no Python interpreter installed on the host** (only the Microsoft
Store alias stubs at `...\WindowsApps\python.exe`, which do not execute) and the
`py` launcher is absent, so the `.venv` the brief/plan assumed could not be
created on the host. Docker **is** available (`Docker version 29.8.1`), so the
mandatory live verification was performed inside a `python:3.12-slim` container
attached to the compose network `ragpoc_default`, talking to the same pgvector
container the user will use.

- The container used the OpenAI key and config from the repo `.env`
  (`--env-file .env`).
- Inside the container the DB is reached as `db:5432` on the compose network
  (`DATABASE_URL=postgresql+asyncpg://rag:rag@db:5432/ragdb`). From the host the
  same DB is `localhost:5433` (the default in `rag.py`) — only the host/port
  differ; the data and behaviour are identical.
- `api.py` was imported and served **unmodified**; the only extra file used was a
  throwaway `_verify_runner.py` that started uvicorn in a background thread and
  hit the real HTTP endpoints with `httpx`. That runner and the temp logs were
  deleted after verification (not committed).

The Python version in the container: `Python 3.12.16`.

## 1. pgvector up and healthy

Command (host):

```
docker compose up -d
docker ps --filter "name=vectra-rag-pgvector" --format "{{.Names}} :: {{.Status}}"
```

Output:

```
vectra-rag-pgvector :: Up (healthy)
```

## 2. Install new deps + dependency-conflict check

Command (in the container, repo mounted at `/app`):

```
pip install --no-input -r requirements.txt
pip check
pip freeze | grep -iE "^(langchain|langchain-core|langchain-postgres|langchain-openai|langgraph|fastapi|uvicorn|pydantic)=="
```

Output (tail):

```
PIP_INSTALL_OK
===== PIP CHECK =====
No broken requirements found.
===== LANGCHAIN PINS =====
fastapi==0.120.4
langchain==1.4.7
langchain-core==1.7.1
langchain-openai==1.7.3
langchain-postgres==0.0.19
langgraph==1.2.18
pydantic==2.12.3
uvicorn==0.41.0
```

`pip check` reports **no broken requirements**: the new `fastapi==0.120.4`,
`uvicorn[standard]==0.41.0`, and `pydantic==2.12.3` install alongside the pinned
langchain stack with no conflict, and every langchain pin is unchanged.

## 3. Ingest the KB (idempotent)

Command:

```
python ingest.py
```

Output:

```
=== Vectra KB ingestion ===
INGEST KB-001 (KB-001_password_reset.md): 4 chunk(s)
SKIP  KB-002 (KB-002_vpn_securelink.md): status=deprecated, superseded_by KB-007
INGEST KB-003 (KB-003_priority_sla.md): 1 chunk(s)
INGEST KB-004 (KB-004_email_mobile.md): 1 chunk(s)
INGEST KB-005 (KB-005_warehouse_devices.md): 3 chunk(s)
INGEST KB-006 (KB-006_security_incidents.md): 1 chunk(s)
INGEST KB-007 (KB-007_vpn_zentunnel.md): 3 chunk(s)
INGEST KB-008 (KB-008_software_requests.md): 1 chunk(s)
SKIP  KB-099 (KB-099_community_tips.md): status=unverified (...contains a prompt-injection)
Ingested docs: 7 (expected 7 current articles)
Total chunks stored: 14
```

7 current docs ingested (KB-001,003,004,005,006,007,008), KB-002 & KB-099
skipped, 14 chunks total — exactly as expected.

## 4. Start the API server (background) + boot log

`api.py` was imported and served with uvicorn in a background thread. Boot log:

```
INFO:     Started server process [31]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

## 5. Real HTTP requests + ACTUAL responses

### GET /health

```
status=200  content-type=application/json
body={"status": "ok"}
```

### GET /

```
status=200  content-type=text/html; charset=utf-8
[html 8926 chars]  title_present=True  chip_present=True
head='<!DOCTYPE html>\n<html lang="en">\n...<title>Vectra IT A...'
```

(The page title "Vectra IT Assistant (KB-only)" and the VPN example chip string
are both present in the returned HTML.)

### POST /answer — VPN question  (primary event-loop proof)

Request body: `{"question": "What VPN server address should I use when working from home?"}`

```
status=200  content-type=application/json
body={"answer": "You should use the gateway address **zt-gw.vectralogistics.example** when connecting to the VPN with ZenTunnel. This address is selected automatically after you sign in.", "citations": ["KB-007"], "abstained": false}
```

Server-side retrieval log for this call:

```
[retrieve] q='What VPN server address should I use when working from home?' hits=4 top_sim=0.474
POST https://api.openai.com/v1/embeddings "HTTP/1.1 200 OK"
POST https://api.openai.com/v1/chat/completions "HTTP/1.1 200 OK"
INFO:     127.0.0.1:... - "POST /answer HTTP/1.1" 200 OK
```

`abstained=false`, `citations` contains `"KB-007"`, and the answer mentions
`zt-gw.vectralogistics.example` (NOT the deprecated `vpn.vectralogistics.example`
/ KB-002). **This proves `answer()` runs correctly THROUGH the API with no
event-loop error** — the `run_in_threadpool(answer, ...)` offload from the async
handler works.

### POST /answer — parking pass (abstain)

Request body: `{"question": "How do I get a parking pass for the Gurugram office?"}`

```
status=200  content-type=application/json
body={"answer": "I don't have information about that in the Vectra IT knowledge base, so I can't answer reliably. Please raise a ticket with the service desk and the right team will help you.", "citations": [], "abstained": true}
```

`abstained=true`, `citations` empty — correct.

### POST /answer — empty question

Request body: `{"question": ""}`

```
status=422  content-type=application/json
body={"detail": [{"type": "string_too_short", "loc": ["body", "question"], "msg": "String should have at least 1 character", "input": "", "ctx": {"min_length": 1}}]}
```

### POST /answer — whitespace-only question

Request body: `{"question": "   "}`

```
status=422  content-type=application/json
body={"detail": [{"type": "string_too_short", "loc": ["body", "question"], "msg": "question must not be empty"}]}
```

### POST /answer — missing field

Request body: `{}`

```
status=422  content-type=application/json
body={"detail": [{"type": "missing", "loc": ["body", "question"], "msg": "Field required", "input": {}}]}
```

All three invalid-input cases return **422** as required.

## 6. Server stopped; Docker state

The verification process (uvicorn in the throwaway container) exited when the
container finished; nothing is left listening. The **pgvector container is left
UP and healthy** (not torn down) so the user can immediately run `python api.py`
and demo. To stop it later: `docker compose down`.

## 7. Secrets / hygiene

- `.env` is gitignored (`git check-ignore .env` → `.env`) and was NOT staged.
- No `OPENAI_API_KEY` value or `sk-` key material appears in any committed file
  (`api.py`, `static/index.html`, `requirements.txt`, `README.md`) — checked via
  grep of the staged diff.
- `.venv/` does not exist on the host and is gitignored regardless.

## Result

Every acceptance check in the plan passed: deps install with no conflict, KB
ingests, and all HTTP endpoints behave correctly through the API — including the
VPN case that proves `answer()` runs through the async handler without an
event-loop error.
