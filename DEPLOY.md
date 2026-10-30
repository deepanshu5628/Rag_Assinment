# Deploying for free: Render (app) + Neon (pgvector database)

This deploys the Vectra KB-only RAG assistant with **no credit card required**:

- **Neon** — free serverless Postgres with `pgvector` built in (the vector DB).
- **Render** — free Docker web service that runs the FastAPI app + web UI.

The app is a **long-running web service** (not serverless), which matches how it
runs locally. The database is a separate free Neon Postgres.

> Estimated time: ~20-30 minutes. GitHub repo:
> https://github.com/deepanshu5628/Rag_Assinment

> Free-tier note: a Render free web service **sleeps after ~15 min of inactivity**
> and takes ~30-60 s to wake on the first request. Before a demo, open the URL a
> minute early so it's warm.

---

## What's already prepared in the repo

No code changes are needed to deploy — these are in place:

- **`Dockerfile`** — builds on `python:3.12-slim`, starts `python api.py`.
- **`render.yaml`** — Render blueprint (Docker web service, `/health` check).
- **`.dockerignore`** — keeps `.env`, `.venv`, tests out of the image.
- **`api.py`** binds `$PORT` / `0.0.0.0` when deployed (Render injects `$PORT`).
- **`rag.py` / `ingest.py`** auto-normalize any `postgres://` / `postgresql://`
  URL to the async `asyncpg` driver **and strip a trailing `?sslmode=...`**, so
  you can paste Neon's connection string verbatim into `DATABASE_URL`.

---

## Step 1 — Create the free Neon database

1. Sign up at [neon.tech](https://neon.tech) (sign in with GitHub, no card).
2. Create a project (any name, e.g. `vectra-rag`). Neon creates a database.
3. Enable pgvector. In the Neon **SQL Editor**, run:
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```
4. Copy the **connection string**. In Neon: **Connect** -> copy the URL. It looks
   like:
   ```
   postgresql://<user>:<password>@<host>.neon.tech/<db>?sslmode=require
   ```
   Keep this — it's your `DATABASE_URL`. (The app strips `?sslmode=require`
   automatically; asyncpg negotiates SSL with Neon on its own.)

## Step 2 — Load the knowledge base into Neon (one time)

The database starts empty, so the app would abstain on everything until the KB
is ingested. Run `ingest.py` once from your laptop, pointed at Neon:

```powershell
# point the local run at Neon (use your copied URL)
$env:DATABASE_URL = "postgresql://<user>:<password>@<host>.neon.tech/<db>?sslmode=require"
.\.venv\Scripts\python.exe ingest.py
Remove-Item Env:\DATABASE_URL   # clear it so later local runs use localhost
```
Expect: `Ingested docs: 7`, `Total chunks stored: 14`, with KB-002 and KB-099
skipped. (Your local `.venv` and `OPENAI_API_KEY` in `.env` are used for this
one-off ingest.)

## Step 3 — Deploy the app on Render

1. Sign up at [render.com](https://render.com) with GitHub (no card for the
   free web service).
2. **New** -> **Web Service** -> connect the GitHub repo
   `deepanshu5628/Rag_Assinment`.
3. Render detects `render.yaml` (or choose **Docker** as the runtime manually).
   Confirm:
   - Runtime: **Docker**
   - Plan: **Free**
   - Health check path: **/health**
4. Add environment variables (**Environment** tab):
   | Key | Value |
   |-----|-------|
   | `OPENAI_API_KEY` | your OpenAI key |
   | `DATABASE_URL` | the Neon connection string from Step 1.4 |
5. **Create Web Service**. Render builds the Docker image and deploys. Watch the
   logs until it's live and `/health` passes.

## Step 4 — Open it

Render gives a public URL like `https://vectra-rag-assistant.onrender.com`.

- Web UI: open that URL in a browser.
- API:
  ```bash
  curl -X POST https://<your-app>.onrender.com/answer \
    -H "Content-Type: application/json" \
    -d '{"question":"What is the resolution target for a P2 ticket?"}'
  ```

---

## Troubleshooting

- **Everything abstains / no citations** — the KB wasn't ingested into Neon.
  Re-run Step 2 against the Neon `DATABASE_URL`.
- **`type "vector" does not exist`** — run `CREATE EXTENSION IF NOT EXISTS vector;`
  in Neon's SQL Editor (Step 1.3).
- **First request is slow / times out** — Render free tier woke from sleep; retry
  after ~30-60 s, then it's responsive.
- **App can't connect to DB** — re-check `DATABASE_URL` on Render matches Neon's
  string exactly (including user/password). The app handles the `sslmode` param.
- **Build too slow / fails on memory** — the langchain stack is large; Render's
  free build should still complete, just slowly. Re-trigger the deploy if it
  times out once.

---

## Alternatives (if you want options)

- **App host:** Koyeb and Fly.io also run Docker, but currently ask for a card or
  a hold. Hugging Face **Docker Spaces** is free and card-free, but its storage
  is ephemeral, so you'd still pair it with Neon for the DB. Render is the
  smoothest card-free pick.
- **Database:** Supabase also ships pgvector on its free tier and works the same
  way (paste its connection string into `DATABASE_URL`). Neon is used above
  because pgvector is on every plan and setup is one SQL command.

## Reminder

For the interview itself, the **local demo** (`python api.py` ->
`http://127.0.0.1:8000`) is the most reliable. Treat the Render URL as a bonus
"it's also live here" link, and warm it up before you present.
