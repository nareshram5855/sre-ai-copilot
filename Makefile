.PHONY: help setup setup-voice ollama-setup start-infra stop-infra \
        start-backend start-frontend ingest status logs wipe-data \
        test test-unit test-integration test-cov

PYTEST      := venv/bin/pytest
PYTHON      := venv/bin/python
PIP         := venv/bin/pip
UVICORN     := venv/bin/uvicorn
CHROMA_PID  := .chromadb.pid

help:
	@echo ""
	@echo "  SRE AI Copilot — Dev Commands"
	@echo ""
	@echo "  Initial setup (run once):"
	@echo "    make setup             Install Python deps + npm deps"
	@echo "    make setup-voice       Install voice module deps (Whisper + pyttsx3)"
	@echo "    make ollama-setup      Pull llama3.1:8b + nomic-embed-text"
	@echo ""
	@echo "  Daily dev (run in order):"
	@echo "    make start-infra       Start Ollama + ChromaDB on :8000"
	@echo "    make start-backend     FastAPI on :8080 (hot reload)"
	@echo "    make ingest            Load knowledge base into ChromaDB"
	@echo "    make start-frontend    React + Vite on :5173 (HMR)"
	@echo ""
	@echo "  Ops:"
	@echo "    make status            Health check all services"
	@echo "    make stop-infra        Stop ChromaDB"
	@echo "    make wipe-data         Delete ChromaDB data (full reset)"
	@echo ""
	@echo "  Tests:"
	@echo "    make test              Run full test suite (with coverage gate)"
	@echo "    make test-unit         Unit tests only (faster, no coverage)"
	@echo "    make test-integration  Integration tests only"
	@echo "    make test-cov          Full suite + HTML coverage report"
	@echo "    make test-e2e          E2E smoke (all services must be live)"
	@echo "    make test-e2e-full     E2E + webhook background triage (~2 min wait)"
	@echo ""

# ── One-time setup ────────────────────────────────────────────────────────────

setup:
	/opt/homebrew/bin/python3.11 -m venv venv
	$(PIP) install --upgrade pip
	$(PIP) install -r backend/requirements.txt
	cd frontend && npm install
	cp -n .env.example .env || true
	@echo "✓ Setup complete. Run 'make ollama-setup' next."

setup-voice:
	$(PIP) install -r backend/requirements-voice.txt
	@echo "✓ Voice deps installed. Set VOICE_VOICE_ENABLED=true in .env to enable."

ollama-setup:
	ollama pull llama3.1:8b
	ollama pull nomic-embed-text
	@echo "✓ Ollama models ready."

# ── Infrastructure (local — no Docker/Minikube needed for dev) ────────────────
# ChromaDB runs directly from the venv. Data persists in .chromadb-data/
# For production (Phase 4): infrastructure/k8s/chromadb.yaml → EKS/Helm

start-infra:
	@echo "→ Starting Ollama..."
	@pgrep -x ollama > /dev/null && echo "  Ollama already running" || \
		(ollama serve > /tmp/ollama.log 2>&1 & sleep 2 && echo "  Ollama started")
	@echo "→ Starting ChromaDB on :8000..."
	@mkdir -p .chromadb-data
	@venv/bin/chroma run --host localhost --port 8000 --path .chromadb-data \
		> /tmp/chromadb.log 2>&1 & echo $$! > $(CHROMA_PID)
	@sleep 2
	@curl -sf http://localhost:8000/api/v1/heartbeat > /dev/null && \
		echo "✓ ChromaDB live at http://localhost:8000" || \
		echo "⚠ ChromaDB starting — retry in a few seconds"

stop-infra:
	@-kill $$(cat $(CHROMA_PID) 2>/dev/null) 2>/dev/null || true
	@rm -f $(CHROMA_PID)
	@echo "✓ ChromaDB stopped. Data preserved in .chromadb-data/"

wipe-data:
	@-kill $$(cat $(CHROMA_PID) 2>/dev/null) 2>/dev/null || true
	@rm -f $(CHROMA_PID)
	rm -rf .chromadb-data
	@echo "✓ ChromaDB data wiped."

# ── App services ──────────────────────────────────────────────────────────────

start-backend:
	$(UVICORN) backend.main:app --host 0.0.0.0 --port 8080 --reload

start-frontend:
	cd frontend && npm run dev

ingest:
	@echo "→ Ingesting knowledge base..."
	@curl -s -X POST http://localhost:8080/api/v1/ingest/sync | $(PYTHON) -m json.tool

# ── Ops ───────────────────────────────────────────────────────────────────────

status:
	@echo "=== Backend (localhost:8080) ==="
	@curl -sf http://localhost:8080/health | $(PYTHON) -m json.tool || echo "  offline"
	@echo "=== ChromaDB (localhost:8000) ==="
	@curl -sf http://localhost:8000/api/v1/heartbeat > /dev/null && echo "  healthy" || echo "  offline"
	@echo "=== Ollama (localhost:11434) ==="
	@curl -sf http://localhost:11434/api/tags | $(PYTHON) -c \
		"import sys,json; m=[x['name'] for x in json.load(sys.stdin).get('models',[])]; print('  models:', m)" \
		|| echo "  offline"

logs:
	@tail -f /tmp/chromadb.log

# ── Tests ─────────────────────────────────────────────────────────────────────

test:
	$(PYTEST) tests/

test-unit:
	$(PYTEST) tests/unit/ --no-cov -v

test-integration:
	$(PYTEST) tests/integration/ --no-cov -v

test-cov:
	$(PYTEST) tests/ --cov=backend --cov-report=html --cov-report=term-missing
	@echo "✓ HTML report: htmlcov/index.html"

test-e2e:
	@echo "→ Running E2E smoke tests (requires all services live)..."
	@echo "  Backend  : http://localhost:8080"
	@echo "  Prometheus: http://localhost:9090"
	$(PYTEST) tests/e2e/ -v --no-cov --timeout=180 -k "not test_webhook_triage_runs_in_background"
	@echo "✓ E2E smoke passed"

test-e2e-full:
	@echo "→ Running full E2E suite incl. background triage wait (~2 min)..."
	$(PYTEST) tests/e2e/ -v --no-cov --timeout=300
	@echo "✓ Full E2E smoke passed"
