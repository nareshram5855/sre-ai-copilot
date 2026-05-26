# ── Stage 1: Build React frontend ────────────────────────────────────────────
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ── Stage 2: Python runtime ───────────────────────────────────────────────────
FROM python:3.11-slim-bookworm

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_ENV=production

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 --shell /usr/sbin/nologin appuser

# Python deps
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --upgrade pip \
    && pip install -r ./backend/requirements.txt

# Backend source
COPY backend/ ./backend/

# Built frontend static files
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# SQLite data: backend/data (audit/checkpoints) + /data volume (recruiter analytics on Railway)
RUN mkdir -p backend/data /data \
    && chown -R appuser:appuser backend/data /data

USER appuser

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8080/health || exit 1

# Railway injects $PORT — bind to it, 2 workers to stay within memory limits
CMD gunicorn backend.main:app \
    --worker-class uvicorn.workers.UvicornWorker \
    --workers 2 \
    --bind "0.0.0.0:${PORT:-8080}" \
    --timeout 120 \
    --keep-alive 5 \
    --access-logfile - \
    --error-logfile -
