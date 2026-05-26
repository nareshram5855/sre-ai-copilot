"""
Synthetic demo services — configurable profiles for SRE Copilot testing.

Profiles (SERVICE_PROFILE env):
  payment       — intermittent 5xx / high error rate
  inventory     — slow responses / latency P99 spikes
  notification  — memory leak / OOM risk
  gateway       — rate limiting (429) + auth-service dependency
  user-profile  — log volume spike + structured ERROR logs

Failure modes: POST/GET /simulate/<mode>
"""
import gc
import hashlib
import json
import math
import os
import random
import signal
import sys
import threading
import time
import urllib.request
import uuid
from contextlib import nullcontext
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer

from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST

SERVICE   = os.getenv("SERVICE_NAME", "payment-api")
PROFILE   = os.getenv("SERVICE_PROFILE", "payment")
VERSION   = os.getenv("SERVICE_VERSION", "1.0.0")
ENV       = os.getenv("ENVIRONMENT", "production")
NAMESPACE = os.getenv("NAMESPACE", "synthetic")
PORT      = int(os.getenv("PORT", "5000"))
OTEL_EP   = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")
AUTH_URL  = os.getenv("AUTH_SERVICE_URL", "http://auth-service.synthetic.svc.cluster.local:5000/health")

HTTP_REQUESTS  = Counter("http_requests_total", "HTTP requests",
                         ["service", "env", "method", "endpoint", "status_code"])
HTTP_ERRORS    = Counter("http_errors_total", "HTTP errors",
                         ["service", "env", "error_type"])
HTTP_LATENCY   = Histogram("http_request_duration_ms", "Request latency ms",
                             ["service", "env", "endpoint"],
                             buckets=[5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000, 30000])
DB_ERRORS      = Counter("db_errors_total", "DB errors",
                         ["service", "env", "host", "error_type"])
MEMORY_HEAP    = Gauge("memory_heap_bytes", "Heap used bytes", ["service", "env"])
MEMORY_LEAK_OBJ = Gauge("memory_leak_objects_total", "Leaked object count", ["service"])
POOL_EXHAUSTION = Counter("db_pool_exhaustion_total", "Pool exhaustion events",
                          ["service", "env", "host"])
RATE_LIMIT_HITS = Counter("rate_limit_exceeded_total", "Rate limit 429 responses",
                           ["service", "env", "client_id"])
LOG_EVENTS     = Counter("log_events_total", "Structured log events emitted",
                         ["service", "env", "level"])

PROFILE_CONFIG = {
    "payment": {
        "endpoints": ["/api/payments/charge", "/api/payments/refund", "/api/payments/status",
                      "/api/payments/webhook", "/api/payments/settle"],
        "component": "PaymentController",
        "modes": ["normal", "high_error_rate", "db_timeout", "cpu_spike"],
    },
    "inventory": {
        "endpoints": ["/api/inventory/stock", "/api/inventory/reserve", "/api/inventory/release",
                      "/api/inventory/audit", "/api/inventory/sync"],
        "component": "InventoryService",
        "modes": ["normal", "slow_response", "cpu_spike", "db_timeout"],
    },
    "notification": {
        "endpoints": ["/api/notifications/send", "/api/notifications/batch",
                      "/api/notifications/status", "/api/notifications/templates"],
        "component": "NotificationDispatcher",
        "modes": ["normal", "memory_leak", "crash_loop", "cpu_spike"],
    },
    "gateway": {
        "endpoints": ["/api/gateway/proxy", "/api/gateway/routes", "/api/gateway/health-check"],
        "component": "GatewayRouter",
        "modes": ["normal", "rate_limit", "high_error_rate", "db_timeout"],
    },
    "user-profile": {
        "endpoints": ["/api/users/profile", "/api/users/preferences", "/api/users/avatar",
                      "/api/users/sessions", "/api/users/audit-log"],
        "component": "UserProfileService",
        "modes": ["normal", "log_flood", "high_error_rate", "slow_response"],
    },
}

_cfg = PROFILE_CONFIG.get(PROFILE, PROFILE_CONFIG["payment"])
ENDPOINTS = _cfg["endpoints"]
VALID_MODES = _cfg["modes"]
DB_HOSTS = ["postgres-primary:5432", "postgres-replica-1:5432"]

state = {"mode": "normal", "leak_cache": [], "start_time": time.time(), "rate_counter": 0}
_lock = threading.Lock()
tracer = None


def _json_log(level: str, component: str, message: str, **extra):
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "service": SERVICE,
        "namespace": NAMESPACE,
        "env": ENV,
        "version": VERSION,
        "component": component,
        "msg": message,
    }
    record.update(extra)
    LOG_EVENTS.labels(service=SERVICE, env=ENV, level=level).inc()
    print(json.dumps(record), flush=True)


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
        resource = Resource.create({"service.name": SERVICE, "deployment.environment": ENV})
        provider = TracerProvider(resource=resource)
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=OTEL_EP, insecure=True)))
        otel_trace.set_tracer_provider(provider)
        tracer = otel_trace.get_tracer(SERVICE, VERSION)
        _json_log("INFO", "OTelInit", f"OTLP trace exporter → {OTEL_EP}")
    except Exception as e:
        _json_log("WARN", "OTelInit", f"OTel init failed (non-fatal): {e}")


def _span(name, **attrs):
    if tracer:
        return tracer.start_as_current_span(name, attributes=attrs)
    return nullcontext()


def _check_auth_health() -> tuple[bool, str]:
    try:
        with urllib.request.urlopen(AUTH_URL, timeout=2) as r:
            data = json.load(r)
            mode = data.get("mode", "unknown")
            ok = data.get("status") == "ok" and mode == "normal"
            return ok, mode
    except Exception as e:
        return False, str(e)[:80]


def gen_normal_request():
    ep = random.choice(ENDPOINTS)
    method = "POST" if random.random() < 0.4 else "GET"
    latency = max(5.0, random.gauss(40, 12))
    tid = uuid.uuid4().hex[:16]
    with _span("http.request", http_method=method, http_url=ep):
        HTTP_REQUESTS.labels(service=SERVICE, env=ENV, method=method,
                             endpoint=ep, status_code="200").inc()
        HTTP_LATENCY.labels(service=SERVICE, env=ENV, endpoint=ep).observe(latency)
    _json_log("INFO", _cfg["component"], f"{method} {ep} → 200",
              trace_id=tid, latency_ms=round(latency, 2))


def gen_high_error():
    ep = random.choice(ENDPOINTS)
    code = random.choice([500, 502, 503, 504])
    msgs = {
        500: "Payment processor returned internal error",
        502: "Upstream dependency unavailable",
        503: "Circuit breaker OPEN — failure_rate elevated",
        504: "Gateway timeout waiting for downstream",
    }
    HTTP_REQUESTS.labels(service=SERVICE, env=ENV, method="POST",
                         endpoint=ep, status_code=str(code)).inc()
    HTTP_ERRORS.labels(service=SERVICE, env=ENV, error_type=f"http_{code}").inc()
    HTTP_LATENCY.labels(service=SERVICE, env=ENV, endpoint=ep).observe(random.uniform(500, 8000))
    _json_log("ERROR", _cfg["component"], f"POST {ep} → {code}",
              trace_id=uuid.uuid4().hex[:16], status_code=code, reason=msgs.get(code, "error"))


def gen_db_timeout():
    host = random.choice(DB_HOSTS)
    DB_ERRORS.labels(service=SERVICE, env=ENV, host=host, error_type="connection_timeout").inc()
    POOL_EXHAUSTION.labels(service=SERVICE, env=ENV, host=host).inc()
    HTTP_ERRORS.labels(service=SERVICE, env=ENV, error_type="db_timeout").inc()
    _json_log("ERROR", "DatabasePool.acquire", "Connection timeout — pool exhausted",
              trace_id=uuid.uuid4().hex[:16], host=host, pool_used="20/20",
              error="HikariPool-1 - Connection not available")


def gen_slow_response():
    ep = random.choice(ENDPOINTS)
    latency = random.uniform(3000, 12000)
    HTTP_REQUESTS.labels(service=SERVICE, env=ENV, method="GET",
                         endpoint=ep, status_code="200").inc()
    HTTP_LATENCY.labels(service=SERVICE, env=ENV, endpoint=ep).observe(latency)
    _json_log("WARN", _cfg["component"], f"GET {ep} → 200 (slow)",
              trace_id=uuid.uuid4().hex[:16], latency_ms=round(latency, 2),
              threshold_ms=2000, action="investigate_db_query")


def gen_memory_leak():
    with _lock:
        state["leak_cache"].extend(
            hashlib.sha256(uuid.uuid4().bytes).hexdigest() for _ in range(800))
        obj_count = len(state["leak_cache"])
    heap_bytes = obj_count * 64 + random.randint(55_000_000, 95_000_000)
    MEMORY_HEAP.labels(service=SERVICE, env=ENV).set(heap_bytes)
    MEMORY_LEAK_OBJ.labels(service=SERVICE).set(obj_count)
    pct = min(99.9, (heap_bytes / 1_048_576) / 128 * 100)
    level = "ERROR" if pct > 85 else "WARN"
    _json_log(level, "HealthMonitor",
              f"Heap usage rising: {heap_bytes/1_048_576:.1f}MB ({pct:.1f}%)",
              heap_bytes=heap_bytes, leaked_objects=obj_count,
              action="OOM_IMMINENT" if pct > 90 else "GC_TRIGGERED")


def gen_rate_limit():
    client = f"client_{random.randint(1, 20):03d}"
    ep = random.choice(ENDPOINTS)
    RATE_LIMIT_HITS.labels(service=SERVICE, env=ENV, client_id=client).inc()
    HTTP_REQUESTS.labels(service=SERVICE, env=ENV, method="GET",
                         endpoint=ep, status_code="429").inc()
    HTTP_ERRORS.labels(service=SERVICE, env=ENV, error_type="rate_limit").inc()
    _json_log("WARN", _cfg["component"], f"GET {ep} → 429 Too Many Requests",
              trace_id=uuid.uuid4().hex[:16], client_id=client,
              limit_rps=100, current_rps=random.randint(120, 350))


def gen_gateway_upstream_error(auth_mode: str):
    ep = random.choice(ENDPOINTS)
    HTTP_REQUESTS.labels(service=SERVICE, env=ENV, method="GET",
                         endpoint=ep, status_code="502").inc()
    HTTP_ERRORS.labels(service=SERVICE, env=ENV, error_type="upstream_auth_failure").inc()
    _json_log("ERROR", _cfg["component"],
              f"GET {ep} → 502 — auth-service unhealthy (mode={auth_mode})",
              trace_id=uuid.uuid4().hex[:16], upstream="auth-service",
              upstream_mode=auth_mode)


def gen_log_flood():
    errors = [
        "Disk write quota exceeded on /var/log/app",
        "Failed to rotate audit log — no space left on device",
        "Structured log buffer overflow — dropping events",
        "Profile sync failed: storage backend unreachable",
        "Avatar upload failed: temp directory full",
    ]
    for _ in range(random.randint(5, 15)):
        msg = random.choice(errors)
        _json_log("ERROR", _cfg["component"], msg,
                  trace_id=uuid.uuid4().hex[:16],
                  disk_usage_pct=random.randint(92, 99),
                  log_volume_mb=random.randint(500, 2000))


def gen_cpu_spike():
    _ = sum(math.sin(i) * math.cos(i) for i in range(25000))
    _json_log("WARN", "ResourceMonitor", "CPU throttling detected",
              cpu_pct=round(random.uniform(80, 99), 2))


def background_emitter():
    while True:
        mode = state["mode"]
        try:
            if mode == "normal":
                gen_normal_request()
                time.sleep(random.uniform(0.3, 0.7))

            elif mode == "high_error_rate":
                gen_normal_request()
                for _ in range(random.randint(3, 8)):
                    gen_high_error()
                if random.random() < 0.3:
                    gen_db_timeout()
                time.sleep(random.uniform(0.1, 0.25))

            elif mode == "db_timeout":
                gen_normal_request()
                gen_db_timeout()
                if random.random() < 0.5:
                    gen_db_timeout()
                time.sleep(random.uniform(0.4, 1.0))

            elif mode == "slow_response":
                for _ in range(random.randint(2, 5)):
                    gen_slow_response()
                time.sleep(random.uniform(0.2, 0.5))

            elif mode == "memory_leak":
                with _lock:
                    state["leak_cache"].extend(
                        hashlib.sha256(uuid.uuid4().bytes).hexdigest() for _ in range(600))
                gen_memory_leak()
                if len(state["leak_cache"]) > 150_000:
                    _json_log("ERROR", "HealthMonitor", "OOM imminent — heap near limit",
                              action="OOM_KILLER_LIKELY")
                time.sleep(0.25)

            elif mode == "rate_limit":
                for _ in range(random.randint(4, 10)):
                    gen_rate_limit()
                auth_ok, auth_mode = _check_auth_health()
                if not auth_ok:
                    gen_gateway_upstream_error(auth_mode)
                time.sleep(random.uniform(0.1, 0.3))

            elif mode == "log_flood":
                gen_log_flood()
                gen_normal_request()
                time.sleep(random.uniform(0.15, 0.4))

            elif mode == "cpu_spike":
                gen_cpu_spike()
                gen_normal_request()
                time.sleep(0.08)

            elif mode == "crash_loop":
                _json_log("ERROR", "App", "Fatal error — process exiting", exit_code=1)
                time.sleep(0.5)
                os._exit(1)

        except Exception as exc:
            _json_log("ERROR", "Emitter", f"Emitter error: {exc}")
            time.sleep(1)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, ct, body):
        if isinstance(body, str):
            body = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ct)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self._handle(self.command)

    def do_POST(self):
        self._handle(self.command)

    def _handle(self, method):
        path = self.path.split("?")[0]

        if path == "/health":
            auth_ok, auth_mode = _check_auth_health() if PROFILE == "gateway" else (True, "n/a")
            uptime = int(time.time() - state["start_time"])
            status = "ok"
            if PROFILE == "gateway" and not auth_ok and state["mode"] in ("rate_limit", "high_error_rate"):
                status = "degraded"
            self._send(200, "application/json", json.dumps({
                "status": status, "mode": state["mode"], "service": SERVICE,
                "profile": PROFILE, "uptime_s": uptime,
                "auth_dependency": {"healthy": auth_ok, "mode": auth_mode} if PROFILE == "gateway" else None,
            }))

        elif path == "/metrics":
            self._send(200, CONTENT_TYPE_LATEST, generate_latest())

        elif path.startswith("/simulate/"):
            issue = path.split("/simulate/", 1)[-1]
            if issue in VALID_MODES:
                with _lock:
                    state["mode"] = issue
                    if issue == "normal":
                        state["leak_cache"].clear()
                        gc.collect()
                        MEMORY_HEAP.labels(service=SERVICE, env=ENV).set(0)
                        MEMORY_LEAK_OBJ.labels(service=SERVICE).set(0)
                _json_log("INFO", "SimulationController", f"Mode switched to '{issue}'", operator="api")
                self._send(200, "application/json",
                           json.dumps({"mode": issue, "status": "activated", "service": SERVICE}))
            else:
                self._send(400, "application/json",
                           json.dumps({"error": "unknown issue", "valid": VALID_MODES, "profile": PROFILE}))
        else:
            self._send(404, "application/json", '{"error":"not found"}')


if __name__ == "__main__":
    _json_log("INFO", "App", f"{SERVICE} v{VERSION} starting",
              profile=PROFILE, port=PORT, namespace=NAMESPACE, pid=os.getpid())
    _init_otel()
    threading.Thread(target=background_emitter, daemon=True, name="emitter").start()
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    _json_log("INFO", "App", f"HTTP server listening on :{PORT}")
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    server.serve_forever()
