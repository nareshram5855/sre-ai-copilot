# ── Stage 1: Build React frontend ────────────────────────────────────────────
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ── Stage 2: Build Stackport demo at /stackport/ ─────────────────────────────
FROM node:20-alpine AS stackport-builder
# Bump INFRA_VER to force re-clone of infra-platform on next build
ARG INFRA_VER=7
RUN apk add --no-cache git
WORKDIR /stackport
RUN git clone --depth 1 --branch admin/org-bootstrap \
    https://github.com/nareshram5855/infra-platform.git .
# Apply local patches — overrides cloned files so Docker cache never stales these
COPY stackport-patches/components/ ./ui/frontend/src/components/
# Patch pages: fixes Blueprints render (GET→POST), MyTeam API base URL, ArchitectureDiagram SVG
COPY stackport-patches/pages/      ./ui/frontend/src/pages/
WORKDIR /stackport/ui/frontend
RUN npm ci
RUN npx vite build --mode demo

# ── Stage 2: Python runtime ───────────────────────────────────────────────────
FROM python:3.11-slim-bookworm

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_ENV=production

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl gosu \
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
# Stackport demo served at /stackport/ via the portfolio backend
COPY --from=stackport-builder /stackport/ui/frontend/dist ./frontend/dist/stackport

# SQLite data: backend/data (audit/checkpoints) + /data volume (recruiter analytics on Railway)
RUN mkdir -p backend/data /data \
    && chown -R appuser:appuser backend/data /data

# Entrypoint fixes /data ownership after Railway mounts the volume (root-owned at start)
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8080/health || exit 1

# Runs as root → entrypoint chowns /data → su-exec drops to appuser → starts gunicorn
ENTRYPOINT ["/docker-entrypoint.sh"]
