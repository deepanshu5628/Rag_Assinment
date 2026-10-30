# Deploying to Railway

This guide deploys the Vectra KB-only RAG assistant (FastAPI + web UI) to
[Railway](https://railway.app) with a managed pgvector Postgres database.

The app is deployed as a **long-running web service** (not serverless), which
matches how it runs locally. The database is a **separate managed Postgres**
service in the same Railway project.

> Estimated time: ~20-30 minutes.

---

## What's already prepared in the repo

These were added so the app is deploy-ready with no code edits on your part:

- **`Dockerfile`** — builds the app on `python:3.12-slim` and starts it with
  `python api.py`.
- **`railway.json`** — tells Railway to build from the Dockerfile, start with
  `python api.py`, and health-check `/health`.
- **`.dockerignore`** — keeps `.env`, `.venv`, tests, and local Docker files out
  of the image.
- **`api.py`** already binds `$PORT` / `0.0.0.0` when deployed (Railway injects
  `$PORT`), and `127.0.0.1:8000` locally.
- **`rag.py` / `ingest.py`** auto-normalize any standard `postgres://` or
  `postgresql://` connection string to the async `asyncpg` driver, so you can
  paste Railway's database URL verbatim — no editing.

---

## Prerequisites

1. A [Railway account](https://railway.app) (sign in with GitHub).
2. Your code pushed to a **GitHub repo** (Railway deploys from GitHub).
   - If it isn't on GitHub yet: create a new empty GitHub repo, then from the
     project root run:
     ```powershell
     git remote add origin https://github.com/<you>/<repo>.git
     git push -u origin master
     ```
   - `.env` is gitignored and will NOT be pushed — good.
3. Your `OPENAI_API_KEY` (the same one in your local `.env`).

---

## Step 1 — Create the project and database

1. On Railway, click **New Project** -> **Deploy PostgreSQL**. This creates a
   managed Postgres service.
2. Open the Postgres service -> **Variables** tab. Note the value of
   **`DATABASE_URL`** (looks like `postgresql://postgres:...@...rlwy.net:1234/railway`).
3. Enable the pgvector extension. Open the Postgres service -> **Data** tab (or
   the **Query** / connect console) and run:
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```
   (Railway's Postgres images include pgvector; this just turns it on. The app
   also attempts this at ingest time, but running it now avoids surprises.)

## Step 2 — Deploy the app service

1. In the same project, click **New** -> **GitHub Repo** and pick your repo.
   Railway detects `railway.json` + `Dockerfile` and builds the image.
2. Open the new app service -> **Variables** tab and add:
   | Variable | Value |
   |----------|-------|
   | `OPENAI_API_KEY` | your OpenAI key |
   | `DATABASE_URL` | reference the Postgres service's `DATABASE_URL` |

   For `DATABASE_URL`, use Railway's **variable reference** so it always points
   at the DB: set the value to `${{Postgres.DATABASE_URL}}` (adjust `Postgres`
   to your DB service's name). This uses Railway's private network.
3. The app service needs a public URL: **Settings** -> **Networking** ->
   **Generate Domain**. Railway assigns the public `$PORT` automatically; the
   app already binds it.
4. Railway redeploys on save. Watch **Deployments** -> logs until it's live and
   `/health` passes.

## Step 3 — Load the knowledge base (one time)

The database starts empty, so the app will abstain on everything until the KB
is ingested. Run `ingest.py` once against the Railway database. Two options:

**Option A — from your laptop (simplest):**
```powershell
# Temporarily point your local run at the Railway DB. Use the PUBLIC URL from
# the Postgres service's "Connect" tab (the proxy host, e.g. *.rlwy.net).
$env:DATABASE_URL = "postgresql://postgres:<pw>@<host>.rlwy.net:<port>/railway"
.\.venv\Scripts\python.exe ingest.py
Remove-Item Env:\DATABASE_URL   # clear it so local runs use localhost again
```
You should see `Ingested docs: 7` and `Total chunks stored: 14`, with KB-002
and KB-099 skipped.

**Option B — from Railway (one-off command):**
In the app service, open a shell / one-off command (Railway "Run a command" or
`railway run`) and execute `python ingest.py`. Here `DATABASE_URL` is already
set, so no extra args are needed.

## Step 4 — Open it

Visit the generated domain (e.g. `https://<your-app>.up.railway.app`). You get
the web UI. The API is at `/answer` and `/health`:

```bash
curl -X POST https://<your-app>.up.railway.app/answer \
  -H "Content-Type: application/json" \
  -d '{"question":"What is the resolution target for a P2 ticket?"}'
```

---

## Troubleshooting

- **Everything abstains / no citations** — the KB wasn't ingested into the
  cloud DB. Re-run Step 3 against the Railway `DATABASE_URL`.
- **App can't connect to DB** — confirm `DATABASE_URL` on the app service
  references the Postgres service (`${{Postgres.DATABASE_URL}}`) and both are in
  the same project.
- **`vector` type does not exist** — run `CREATE EXTENSION IF NOT EXISTS vector;`
  on the Postgres service (Step 1.3).
- **Health check failing on first deploy** — the app needs the DB reachable at
  startup only when a request arrives (the store is lazily created), so a failing
  health check usually means a crash in build/startup; check the deploy logs.
- **SSL / connection string** — paste Railway's URL as-is. The app strips a
  trailing `?sslmode=...` automatically; asyncpg negotiates SSL for managed DBs.

## Cost note

Railway's free trial credit covers a small demo. The app service is always-on
(not free-tier-sleeping like Render), so for a long-lived public link you may
need a paid plan. For a short interview demo, the trial credit is typically
enough.

## Render (alternative)

Render works the same way for the app (Dockerfile web service) but its **free**
Postgres does not reliably support the `vector` extension — you'd use a paid
Render Postgres or an external pgvector DB (Neon / Supabase). For pgvector
simplicity, Railway is the smoother path.
