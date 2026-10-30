# Dockerfile for the Vectra KB-only RAG assistant (FastAPI + web UI).
# Used by Railway (and any Docker host) to run the app as a long-running web
# service. The app binds $PORT / 0.0.0.0 (see api.py), which Railway injects.
#
# The vector database (pgvector) is NOT built here: on Railway it is a separate
# managed Postgres service. Set DATABASE_URL and OPENAI_API_KEY as environment
# variables on the service; never bake secrets into the image.

FROM python:3.12-slim

# Keep Python output unbuffered (logs appear immediately) and skip .pyc files.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install dependencies first (better layer caching).
COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy the application code.
COPY . .

# Documented default; Railway overrides with its own $PORT at runtime.
EXPOSE 8000

# Start the FastAPI server. api.py reads $PORT and binds 0.0.0.0 when deployed.
CMD ["python", "api.py"]
