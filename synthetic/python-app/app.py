"""
Synthetic Auth Service — proper observability-grade log/trace/metric generator.

Instrumentation stack:
  Prometheus  → prometheus_client Counter/Histogram/Gauge exposed on /metrics
  OpenTelemetry → OTLP gRPC to OTel Collector (traces with real spans)
  Loki        → JSON structured logs on stdout; Promtail scrapes and ships them

Failure modes: /simulate/<mode>
  normal | high_error_rate | db_timeout | memory_leak | cpu_spike
  connection_exhaust | crash_loop
"""
import gc
import hashlib
import json
import logging
import math
import os
import random
import signal
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer

# ── Prometheus metrics ─────────────────────────────────────────────────────────
from prometheus_client import (
    Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST,
    CollectorRegistry, REGISTRY,
)

SERVICE = os.getenv("SERVICE_NAME", "auth-service")
VERSION = os.getenv("SERVICE_VERSION", "2.4.1")
ENV     = os.getenv("ENVIRONMENT", "production")
PORT    = int(os.getenv("PORT", "5000"))
OTEL_EP = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")   # e.g. http://otel-collector:4317

LABELS = {"service": SERVICE, "env": ENV}

HTTP_REQUESTS   = Counter("http_requests_total",       "HTTP requests",
                           ["service", "env", "method", "endpoint", "status_code"])
HTTP_ERRORS     = Counter("http_errors_total",          "HTTP errors",
                           ["service", "env", "error_type"])
HTTP_LATENCY    = Histogram("http_request_duration_ms", "Request latency ms",
                             ["service", "env", "endpoint"],
                             buckets=[5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000])
DB_ERRORS       = Counter("db_errors_total",            "DB errors",
                           ["service", "env", "host", "error_type"])
AUTH_FAILURES   = Counter("auth_failures_total",        "Auth failures",
                           ["service", "env", "reason"])
MEMORY_HEAP     = Gauge("memory_heap_bytes",             "Heap used bytes",    ["service", "env"])
MEMORY_LEAK_OBJ = Gauge("memory_leak_objects_total",     "Leaked object count", ["service"])
POOL_EXHAUSTION = Counter("db_pool_exhaustion_total",   "Pool exhaustion events",
                           ["service", "env", "host"])

# ── OpenTelemetry tracing ─────────────────────────────────────────────────────
tracer = None

def _init_otel():
    global tracer
    if not OTEL_EP:
        return
    try:
        from opentelemetry import trace as otel_trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        resource  = Resource.create({"service.name": SERVICE, "deployment.environment": ENV})
        provider  = TracerProvider(resource=resource)
        exporter  = OTLPSpanExporter(endpoint=OTEL_EP, insecure=True)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        otel_trace.set_tracer_provider(provider)
        tracer = otel_trace.get_tracer(SERVICE, VERSION)
        _json_log("INFO", "OTelInit", f"OTLP trace exporter → {OTEL_EP}")
    except Exception as e:
        _json_log("WARN", "OTelInit", f"OTel init failed (non-fatal): {e}")

# ── JSON structured logging (Loki-ready) ──────────────────────────────────────
def _json_log(level: str, component: str, message: str, **extra):
    record = {
        "ts":        datetime.now(timezone.utc).isoformat(),
        "level":     level,
        "service":   SERVICE,
        "env":       ENV,
        "version":   VERSION,
        "component": component,
        "msg":       message,
    }
    record.update(extra)
    print(json.dumps(record), flush=True)

# ── Shared state ──────────────────────────────────────────────────────────────
state = {
    "mode":       "normal",
    "leak_cache": [],
    "start_time": time.time(),
}
_lock = threading.Lock()

ENDPOINTS   = ["/api/auth/login", "/api/auth/refresh", "/api/auth/validate",
               "/api/users/profile", "/api/tokens/revoke"]
DB_HOSTS    = ["postgres-primary:5432", "postgres-replica-1:5432"]
USERS       = [f"user_{i:04d}@corp.internal" for i in range(1, 50)]
HTTP_ERRORS_500 = [500, 502, 503, 504]

# ── Scenario generators ───────────────────────────────────────────────────────

def _span(name, **attrs):
    """Context manager returning an OTel span, or a no-op if OTel not configured."""
    if tracer:
        return tracer.start_as_current_span(name, attributes=attrs)
    import contextlib
    return contextlib.nullcontext()

def gen_normal_request():
    ep      = random.choice(ENDPOINTS)
    method  = "POST" if "login" in ep or "refresh" in ep else "GET"
    latency = max(5.0, random.gauss(45, 15))
    tid     = uuid.uuid4().hex[:16]

    with _span("http.request", http_method=method, http_url=ep):
        HTTP_REQUESTS.labels(service=SERVICE, env=ENV, method=method,
                              endpoint=ep, status_code="200").inc()
        HTTP_LATENCY.labels(service=SERVICE, env=ENV, endpoint=ep).observe(latency)

    _json_log("INFO", "AuthController",
              f"{method} {ep} → 200",
              trace_id=tid, latency_ms=round(latency, 2),
              user=random.choice(USERS))

def gen_auth_failure():
    reason = random.choice(["invalid_password", "account_locked", "mfa_failed"])
    AUTH_FAILURES.labels(service=SERVICE, env=ENV, reason=reason).inc()
    HTTP_ERRORS.labels(service=SERVICE, env=ENV, error_type="auth_failure").inc()
    _json_log("WARN", "AuthController.validate",
              "Authentication failed",
              trace_id=uuid.uuid4().hex[:16],
              user=random.choice(USERS),
              reason=reason, attempts=random.randint(1, 5),
              ip=f"10.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}")

def gen_db_timeout():
    host    = random.choice(DB_HOSTS)
    wait_ms = random.randint(4500, 15000)
    pool    = random.randint(18, 20)
    queue   = random.randint(40, 120)
    DB_ERRORS.labels(service=SERVICE, env=ENV, host=host, error_type="connection_timeout").inc()
    POOL_EXHAUSTION.labels(service=SERVICE, env=ENV, host=host).inc()
    HTTP_ERRORS.labels(service=SERVICE, env=ENV, error_type="db_timeout").inc()

    _json_log("ERROR", "DatabasePool.acquire",
              "Connection timeout — pool exhausted",
              trace_id=uuid.uuid4().hex[:16],
              host=host, pool_used=f"{pool}/20", queue_depth=queue,
              timeout_ms=wait_ms,
              error="HikariPool-1 - Connection not available")
    _json_log("ERROR", "AuthRepository.findUser",
              "Query failed: no DB connection available",
              trace_id=uuid.uuid4().hex[:16],
              query="SELECT * FROM users WHERE email=? AND active=true",
              error_class="SQLTransientConnectionException")

def gen_high_error():
    ep   = random.choice(ENDPOINTS)
    code = random.choice(HTTP_ERRORS_500)
    msgs = {
        500: "Unhandled NullPointerException in token validation",
        502: "Upstream auth-provider returned 502 Bad Gateway",
        503: "Circuit breaker OPEN — failure_rate=72.3%",
        504: "Upstream did not respond within 30s",
    }
    HTTP_REQUESTS.labels(service=SERVICE, env=ENV, method="POST",
                          endpoint=ep, status_code=str(code)).inc()
    HTTP_ERRORS.labels(service=SERVICE, env=ENV, error_type=f"http_{code}").inc()
    HTTP_LATENCY.labels(service=SERVICE, env=ENV, endpoint=ep).observe(
        random.uniform(500, 30000))
    _json_log("ERROR", "RequestDispatcher",
              f"POST {ep} → {code}",
              trace_id=uuid.uuid4().hex[:16],
              status_code=code, reason=msgs[code],
              error_id=uuid.uuid4().hex[:12])

def gen_memory_warn():
    with _lock:
        obj_count = len(state["leak_cache"])
    heap_bytes = obj_count * 64 + random.randint(50_000_000, 80_000_000)
    heap_mb    = heap_bytes / 1_048_576
    MEMORY_HEAP.labels(service=SERVICE, env=ENV).set(heap_bytes)
    MEMORY_LEAK_OBJ.labels(service=SERVICE).set(obj_count)
    pct = min(99.9, (heap_mb / 128) * 100)

    level = "ERROR" if pct > 90 else "WARN"
    _json_log(level, "HealthMonitor",
              f"High heap usage: {heap_mb:.1f}MB/128MB ({pct:.1f}%)",
              heap_bytes=heap_bytes, leaked_objects=obj_count,
              gc_pressure="CRITICAL" if pct > 90 else "HIGH",
              action="OOM_IMMINENT" if pct > 95 else "GC_TRIGGERED")

def gen_cpu_spike():
    pct = random.uniform(85, 100)
    _json_log("WARN", "ResourceMonitor",
              "CPU throttling detected",
              cpu_pct=round(pct, 2),
              throttle_periods=random.randint(50, 500),
              cfs_quota_us=100000, cfs_period_us=100000)

def gen_connection_exhaust():
    used = random.randint(980, 1024)
    _json_log("ERROR", "NetworkManager",
              "Ephemeral port exhaustion",
              connections_in_time_wait=used, max_connections=1024,
              fix="sysctl net.ipv4.tcp_tw_reuse=1")

# ── Background emitter ────────────────────────────────────────────────────────

def background_emitter():
    crash_n = [0]
    crash_after = int(os.getenv("CRASH_AFTER", "0"))

    while True:
        mode = state["mode"]
        crash_n[0] += 1
        if crash_after and crash_n[0] >= crash_after:
            _json_log("ERROR", "App", "Crash threshold reached — exiting",
                      crash_after=crash_after)
            time.sleep(0.5)
            os._exit(1)

        try:
            if mode == "normal":
                gen_normal_request()
                if random.random() < 0.08: gen_auth_failure()
                time.sleep(random.uniform(0.3, 0.8))

            elif mode == "high_error_rate":
                gen_normal_request()
                for _ in range(random.randint(3, 7)):
                    gen_high_error()
                if random.random() < 0.4: gen_db_timeout()
                time.sleep(random.uniform(0.1, 0.3))

            elif mode == "db_timeout":
                gen_normal_request()
                gen_db_timeout()
                if random.random() < 0.6: gen_db_timeout()
                time.sleep(random.uniform(0.5, 1.5))

            elif mode == "memory_leak":
                with _lock:
                    state["leak_cache"].extend(
                        [hashlib.sha256(uuid.uuid4().bytes).hexdigest()
                         for _ in range(500)])
                gen_memory_warn()
                if len(state["leak_cache"]) > 200_000:
                    _json_log("ERROR", "HealthMonitor",
                              "OOM imminent — heap 127MB/128MB (99.2%)",
                              action="OOM_KILLER_LIKELY",
                              heap_bytes=133169152)
                time.sleep(0.3)

            elif mode == "cpu_spike":
                _ = sum(math.sin(i) * math.cos(i) for i in range(30000))
                gen_cpu_spike()
                gen_normal_request()
                time.sleep(0.08)

            elif mode == "connection_exhaust":
                gen_connection_exhaust()
                gen_normal_request()
                if random.random() < 0.3: gen_db_timeout()
                time.sleep(0.4)

            elif mode == "crash_loop":
                _json_log("ERROR", "App",
                          "Fatal RuntimeError — shutting down", exit_code=1)
                time.sleep(1)
                os._exit(1)

        except Exception as exc:
            _json_log("ERROR", "Emitter", f"Emitter error: {exc}")
            time.sleep(1)

# ── HTTP handler ──────────────────────────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def _send(self, code, ct, body):
        if isinstance(body, str):
            body = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ct)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?")[0]

        if path == "/health":
            uptime = int(time.time() - state["start_time"])
            self._send(200, "application/json",
                       json.dumps({"status": "ok", "mode": state["mode"],
                                   "service": SERVICE, "uptime_s": uptime}))

        elif path == "/metrics":
            # prometheus_client generates the full scrape page
            self._send(200, CONTENT_TYPE_LATEST, generate_latest())

        elif path.startswith("/simulate/"):
            issue = path.split("/simulate/", 1)[-1]
            valid = ["normal", "high_error_rate", "db_timeout", "memory_leak",
                     "cpu_spike", "connection_exhaust", "crash_loop"]
            if issue in valid:
                with _lock:
                    state["mode"] = issue
                    if issue == "normal":
                        state["leak_cache"].clear()
                        gc.collect()
                        MEMORY_HEAP.labels(service=SERVICE, env=ENV).set(0)
                        MEMORY_LEAK_OBJ.labels(service=SERVICE).set(0)
                _json_log("INFO", "SimulationController",
                          f"Mode switched to '{issue}'", operator="api")
                self._send(200, "application/json",
                           json.dumps({"mode": issue, "status": "activated"}))
            else:
                self._send(400, "application/json",
                           json.dumps({"error": "unknown issue", "valid": valid}))
        else:
            self._send(404, "application/json", '{"error":"not found"}')

# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    _json_log("INFO", "App", f"{SERVICE} v{VERSION} starting",
              port=PORT, env=ENV, pid=os.getpid(),
              otel_endpoint=OTEL_EP or "disabled")
    _init_otel()

    t = threading.Thread(target=background_emitter, daemon=True, name="emitter")
    t.start()

    server = HTTPServer(("0.0.0.0", PORT), Handler)
    _json_log("INFO", "App", f"HTTP server listening on :{PORT}",
              metrics_path="/metrics", health_path="/health")

    def _shutdown(sig, frame):
        _json_log("INFO", "App", "SIGTERM received — exiting gracefully")
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    server.serve_forever()
