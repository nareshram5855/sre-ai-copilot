.PHONY: help setup setup-voice ollama-setup start-infra stop-infra \
        start-backend start-frontend start-all stop-all ingest ingest-profile status logs wipe-data \
        test test-unit test-integration test-cov \
        deploy-kafka kafka-port-forward kafka-status \
        deploy-observability deploy-synthetic observability-port-forward \
        observability-port-forward-watch observability-pf-daemon dev-up \
        observability-status deploy-all smoke-test-minikube \
        nginx-install nginx-reload nginx-start nginx-stop serve-backend serve-all build-frontend

PYTEST      := venv/bin/pytest
PYTHON      := venv/bin/python
PIP         := venv/bin/pip
UVICORN     := venv/bin/uvicorn
CHROMA_PID  := .chromadb.pid
OBS_PF_PROM := 19090
OBS_PF_LOKI := 13100

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
	@echo "    make dev-up              Start PF daemon + verify Prom/Loki (run after sleep/restart)"
	@echo "    make start-infra       Start Ollama + ChromaDB on :8000"
	@echo "    make deploy-all        Minikube: full stack (observability, Kafka, Redis, ChromaDB, synthetic)"
	@echo "    make smoke-test-minikube  Post-deploy health checks for Minikube stack"
	@echo "    make observability-port-forward  One-shot PF refresh (daemon preferred: make dev-up)"
	@echo "    make observability-pf-daemon     PF watchdog daemon (start|stop|status|restart)"
	@echo "    make kafka-port-forward  Forward Kafka :9092 to localhost (separate terminal)"
	@echo "    make start-backend     FastAPI on :8080 (hot reload)"
	@echo "    make ingest            Load knowledge base into ChromaDB"
	@echo "    make ingest-profile    Index resume for recruiter profile RAG"
	@echo "    make start-frontend    React + Vite on :5173 (HMR)"
	@echo ""
	@echo "  Ops:"
	@echo "    make status            Health check all services"
	@echo "    make observability-status  Prometheus/Loki/synthetic stack checks"
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
	$(PIP) install --no-build-isolation 'openai-whisper==20240930' || true
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

# ── Kafka (Minikube) ──────────────────────────────────────────────────────────

deploy-kafka:
	chmod +x infrastructure/k8s/kafka/install.sh
	infrastructure/k8s/kafka/install.sh

kafka-port-forward:
	@echo "→ Forwarding Kafka to localhost:9092 (Ctrl+C to stop)"
	kubectl port-forward svc/kafka -n kafka 9092:9092

kafka-status:
	@kubectl get pods,svc -n kafka 2>/dev/null || echo "Kafka namespace not deployed"
	@curl -sf http://localhost:8080/api/v1/events/health 2>/dev/null | $(PYTHON) -m json.tool || true

# ── Observability (Minikube) ──────────────────────────────────────────────────

deploy-observability:
	chmod +x infrastructure/k8s/observability/install.sh
	infrastructure/k8s/observability/install.sh

deploy-synthetic:
	chmod +x infrastructure/k8s/observability/deploy-synthetic.sh
	infrastructure/k8s/observability/deploy-synthetic.sh

observability-port-forward:
	chmod +x scripts/ensure-port-forwards.sh
	scripts/ensure-port-forwards.sh

observability-port-forward-watch:
	chmod +x scripts/ensure-port-forwards.sh
	scripts/ensure-port-forwards.sh --loop

observability-pf-daemon:
	chmod +x scripts/observability-pf-daemon.sh
	scripts/observability-pf-daemon.sh start

dev-up:
	@echo "→ Starting observability port-forward daemon (auto-restarts after sleep)…"
	chmod +x scripts/observability-pf-daemon.sh scripts/ensure-port-forwards.sh
	scripts/observability-pf-daemon.sh start
	@echo "→ Verifying Prometheus :$(OBS_PF_PROM) and Loki :$(OBS_PF_LOKI)…"
	scripts/ensure-port-forwards.sh
	@echo ""
	@echo "=== Dev stack health ==="
	@curl -sf http://localhost:$(OBS_PF_PROM)/-/healthy >/dev/null && \
		echo "  Prometheus :$(OBS_PF_PROM) ✓" || echo "  Prometheus :$(OBS_PF_PROM) ✗"
	@curl -sf http://localhost:$(OBS_PF_LOKI)/ready >/dev/null && \
		echo "  Loki       :$(OBS_PF_LOKI) ✓" || echo "  Loki       :$(OBS_PF_LOKI) ✗"
	@curl -sf http://localhost:8080/health >/dev/null && \
		echo "  Backend    :8080 ✓" || echo "  Backend    :8080 ✗  → run: make start-backend"
	@echo ""
	@echo "✓ Port-forward daemon running (.observability-pf.pid) — no manual PF needed."
	@echo "  Next: make start-backend && make start-frontend"
	@echo "  Command Center: http://localhost:5173"

observability-status:
	chmod +x infrastructure/k8s/observability/status.sh
	infrastructure/k8s/observability/status.sh

deploy-all:
	chmod +x infrastructure/k8s/deploy-all.sh
	infrastructure/k8s/deploy-all.sh

smoke-test-minikube:
	chmod +x infrastructure/k8s/smoke-test.sh
	infrastructure/k8s/smoke-test.sh

wipe-data:
	@-kill $$(cat $(CHROMA_PID) 2>/dev/null) 2>/dev/null || true
	@rm -f $(CHROMA_PID)
	rm -rf .chromadb-data
	@echo "✓ ChromaDB data wiped."

# ── App services ──────────────────────────────────────────────────────────────

start-backend:
	@chmod +x scripts/observability-pf-daemon.sh scripts/ensure-port-forwards.sh
	@scripts/observability-pf-daemon.sh start
	@scripts/ensure-port-forwards.sh || echo "⚠  Observability port-forwards failed — run: make dev-up"
	$(UVICORN) backend.main:app --host 0.0.0.0 --port 8080

start-frontend:
	cd frontend && npm run dev -- --port 5173

start-all:
	@echo "→ Starting backend + frontend as background daemons…"
	@pkill -f "uvicorn backend.main" 2>/dev/null || true
	@pkill -f "vite" 2>/dev/null || true
	@sleep 1
	@chmod +x scripts/observability-pf-daemon.sh scripts/ensure-port-forwards.sh
	@scripts/observability-pf-daemon.sh start
	@scripts/ensure-port-forwards.sh || echo "⚠  Port-forwards failed — run: make dev-up"
	@nohup $(UVICORN) backend.main:app --host 0.0.0.0 --port 8080 >> /tmp/uv.log 2>&1 & echo $$! > .backend.pid
	@sleep 4
	@curl -sf http://localhost:8080/health > /dev/null && echo "  Backend  :8080 ✓" || echo "  Backend  :8080 ✗ — see /tmp/uv.log"
	@cd frontend && nohup npm run dev -- --port 5173 >> /tmp/vite.log 2>&1 & echo $$! > ../.frontend.pid
	@sleep 4
	@curl -sf http://localhost:5173 > /dev/null && echo "  Frontend :5173 ✓" || echo "  Frontend :5173 ✗ — see /tmp/vite.log"
	@echo ""
	@echo "✓ All services running in background."
	@echo "  Logs: backend=/tmp/uv.log  frontend=/tmp/vite.log"
	@echo "  Stop: make stop-all"

stop-all:
	@echo "→ Stopping backend + frontend…"
	@pkill -f "uvicorn backend.main" 2>/dev/null && echo "  Backend stopped" || true
	@pkill -f "gunicorn" 2>/dev/null && echo "  Gunicorn stopped" || true
	@pkill -f "vite" 2>/dev/null && echo "  Frontend stopped" || true
	@rm -f .backend.pid .frontend.pid

# ── Nginx + Gunicorn (production-style) ──────────────────────────────────────

build-frontend:
	@echo "→ Building React app…"
	cd frontend && npm run build
	@echo "  Build output: frontend/dist/"

nginx-install: build-frontend
	@echo "→ Installing nginx config + starting nginx…"
	chmod +x scripts/install-nginx.sh
	scripts/install-nginx.sh
	@echo "  App: http://localhost:8090  (nginx → gunicorn)"
	@echo "  Next: make serve-backend"

nginx-reload:
	@nginx -t && (nginx -s reload 2>/dev/null || nginx)
	@echo "nginx reloaded"

nginx-start:
	@nginx -t
	@if lsof -i :8090 -sTCP:LISTEN >/dev/null 2>&1; then \
		echo "nginx already listening on :8090"; \
		nginx -s reload 2>/dev/null || true; \
	else \
		nginx && echo "nginx started on :8090"; \
	fi

nginx-stop:
	@nginx -s quit 2>/dev/null && echo "nginx stopped" || brew services stop nginx 2>/dev/null || true

serve-backend:
	@echo "→ Starting gunicorn ($(shell venv/bin/python -c 'import min,multiprocessing; print(min(4,multiprocessing.cpu_count()))' 2>/dev/null || echo 2) uvicorn workers) on :8080…"
	@chmod +x scripts/observability-pf-daemon.sh scripts/ensure-port-forwards.sh
	@scripts/observability-pf-daemon.sh start
	@scripts/ensure-port-forwards.sh || echo "⚠  Port-forwards failed — run: make dev-up"
	venv/bin/gunicorn backend.main:app -c gunicorn.conf.py

serve-all: build-frontend nginx-install
	@echo "→ Starting gunicorn backend in background…"
	@pkill -f "gunicorn.*backend.main" 2>/dev/null || true
	@sleep 1
	@chmod +x scripts/observability-pf-daemon.sh scripts/ensure-port-forwards.sh
	@scripts/observability-pf-daemon.sh start
	@scripts/ensure-port-forwards.sh || echo "⚠  Port-forwards failed — run: make dev-up"
	@nohup venv/bin/gunicorn backend.main:app -c gunicorn.conf.py >> /tmp/sre-ai-gunicorn-error.log 2>&1 & echo $$! > .backend.pid
	@sleep 5
	@curl -sf http://localhost:8080/health > /dev/null && echo "  Backend  :8080 ✓ (gunicorn)" || echo "  Backend  :8080 ✗ — see /tmp/sre-ai-gunicorn-error.log"
	@curl -sf http://localhost:8090 > /dev/null && echo "  Frontend :8090 ✓ (nginx)" || echo "  Frontend :8090 ✗ — see /tmp/sre-ai-nginx-error.log"
	@echo ""
	@echo "✓ Production stack running."
	@echo "  App:  http://localhost:8090"
	@echo "  Logs: /tmp/sre-ai-gunicorn-*.log  /tmp/sre-ai-nginx-*.log"
	@echo "  Stop: make stop-all"

ingest:
	@echo "→ Ingesting knowledge base..."
	@curl -s -X POST http://localhost:8080/api/v1/ingest/sync | $(PYTHON) -m json.tool

ingest-profile:
	@echo "→ Ingesting candidate profile for recruiter RAG..."
	@$(PYTHON) -c "from backend.knowledge.profile_ingest import ingest_profile; n=ingest_profile(force=True); print(f'Indexed {n} profile chunks into sre_candidate_profile')"

# ── Ops ───────────────────────────────────────────────────────────────────────

status:
	@echo "=== Backend (localhost:8080) ==="
	@curl -sf http://localhost:8080/health | $(PYTHON) -m json.tool || echo "  offline"
	@echo "=== Events SSE / Kafka (localhost:8080) ==="
	@curl -sf http://localhost:8080/api/v1/events/health | $(PYTHON) -m json.tool || echo "  offline"
	@echo "=== Observability stack (localhost:8080) ==="
	@curl -sf http://localhost:8080/api/v1/observability/stack | $(PYTHON) -c \
		"import sys,json; d=json.load(sys.stdin); \
[print(' ', t['name']+':', t['status'], t.get('stats',{})) for t in d.get('tools',[])]; \
prom=next((t for t in d.get('tools',[]) if t['name']=='Prometheus'),{}); \
pf_ok=prom.get('status')=='up' and prom.get('stats',{}).get('total_targets',0)>0; \
print('  hint: make observability-port-forward' if not pf_ok else '  port-forwards OK')" \
		|| echo "  offline"
	@echo "=== Prometheus (localhost:$(OBS_PF_PROM)) ==="
	@curl -sf http://localhost:$(OBS_PF_PROM)/-/healthy >/dev/null && echo "  healthy" || echo "  offline — stale PF? run: make observability-port-forward"
	@echo "=== Loki (localhost:$(OBS_PF_LOKI)) ==="
	@curl -sf http://localhost:$(OBS_PF_LOKI)/ready >/dev/null && echo "  ready" || echo "  offline — stale PF? run: make observability-port-forward"
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
