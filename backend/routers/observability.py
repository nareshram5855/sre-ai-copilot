"""
Live Observability API — queries Prometheus and Loki directly,
returns structured telemetry for the SRE dashboard.

Endpoints:
  GET  /api/v1/observability/services           — discover active services
  GET  /api/v1/observability/metrics/{service}  — live SLI metrics
  GET  /api/v1/observability/watch              — aggregated anomaly watch (all services)
  GET  /api/v1/observability/logs/{service}     — recent ERROR/WARN logs
  POST /api/v1/observability/analyze-live       — collect + stream AI analysis
"""
import json
import re
import threading
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import httpx
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse, StreamingResponse

from backend.config import settings
from backend.agents.analysis_agent import AnalysisAgent
from backend.utils.fleet_health import fleet_health_pct

# ── Live-analysis prompt (telemetry-specific, not the code-analysis prompt) ───

_LIVE_PROMPT = """\
You are a senior Site Reliability Engineer performing live incident triage.

The Incident Assessment section is ALREADY written. Do NOT output it again.
The OTel Pipeline Status, Cascade Analysis, Risk Assessment, and Validation Checklist
sections will be appended automatically. Do NOT write them.

Your task: write exactly TWO sections using ONLY the data provided below.

## 🔍 Root Cause Analysis

Use the ROOT CAUSE CANDIDATES and DETECTED CASCADE sections from the data to anchor
your analysis. For each candidate, write an explicit causal chain:
  **[ROOT CAUSE]** → **[SYMPTOM]** → **[USER IMPACT]**

Rules:
- Start with the highest-confidence candidate first
- Quote exact metric values: `error_rate=3.7593/s`, `latency_p99=10000ms`
- Quote verbatim log lines as inline code: `[HH:MM:SS] LEVEL [component] message`
- Reference OTel signals if OPENTELEMETRY SIGNALS section shows anomalies
- Reference cascade chain from DETECTED CASCADE if present
- If ISSUE MODE TRIGGERED appears, use it as the primary root cause
- If no anomalies: write "No active anomalies — service within normal parameters."

## 🛠️ Remediation Actions

### Immediate Actions (< 5 minutes)
```bash
# Diagnostics first — read-only, safe to run immediately
kubectl describe pod -n synthetic -l app=<service>
kubectl logs -n synthetic -l app=<service> --tail=100 | grep -E "ERROR|WARN"
kubectl top pod -n synthetic -l app=<service>

# Fix commands — one per line with inline comment explaining why
```

### Short-term Actions (< 1 hour)
- [kubectl command] — [why this fixes the root cause]
- [config change] — [what threshold to adjust and why]
- [scaling decision] — [when to trigger and target replica count]

### Long-term Recommendations
- [architectural improvement with specific technology/pattern]
- [capacity planning action with metric target]
- [runbook or SLO threshold update]

FORMAT:
• Start with "## 🔍 Root Cause Analysis" — nothing before it.
• Use ## for main sections, ### for sub-sections.
• bash code blocks for shell commands only — never ```markdown or ```text.
• No filler: no "Based on the data", no "In conclusion", no greetings.\
"""

router = APIRouter(prefix="/api/v1/observability", tags=["observability"])

NAMESPACE = "synthetic"


def _prom_url() -> str:
    return settings.prometheus_url


def _loki_url() -> str:
    return settings.loki_url


def _prom_ui() -> str:
    return settings.prometheus_ui_url


def _loki_ui() -> str:
    return settings.loki_ui_url
_MINIKUBE_IP_DEFAULT = settings.minikube_ip

# Registry of synthetic demo services (ports for NodePort simulate/trigger endpoints).
# list_services() auto-discovers live targets from Prometheus; this is fallback + metadata.
_SYNTHETIC_SERVICES: dict[str, dict] = {
    "auth-service": {
        "port": 30500,
        "issues": ["high_error_rate", "db_timeout", "memory_leak", "cpu_spike", "connection_exhaust", "crash_loop"],
    },
    "order-service": {
        "port": 30800,
        "issues": ["npe", "db_timeout", "cpu_spike", "memory_leak", "deadlock"],
    },
    "payment-api": {
        "port": 30510,
        "issues": ["high_error_rate", "db_timeout", "cpu_spike"],
    },
    "inventory-service": {
        "port": 30520,
        "issues": ["slow_response", "cpu_spike", "db_timeout"],
    },
    "notification-service": {
        "port": 30530,
        "issues": ["memory_leak", "crash_loop", "cpu_spike"],
    },
    "gateway-api": {
        "port": 30540,
        "issues": ["rate_limit", "high_error_rate", "db_timeout"],
    },
    "user-profile-service": {
        "port": 30550,
        "issues": ["log_flood", "high_error_rate", "slow_response"],
    },
}
_KNOWN = list(_SYNTHETIC_SERVICES.keys())

# ── Shared HTTP helpers ────────────────────────────────────────────────────────

# Thread-local httpx clients — httpx.Client is NOT thread-safe, so each thread
# in ThreadPoolExecutor gets its own instance to avoid concurrent-access races.
_tls = threading.local()
_LOKI_TIMEOUT_S = 8.0

# Keep a single client for use on the main FastAPI thread (non-parallel calls).
_HTTP = httpx.Client(timeout=httpx.Timeout(10.0, connect=3.0))


def _thread_http() -> httpx.Client:
    if not hasattr(_tls, "http"):
        _tls.http = httpx.Client(timeout=httpx.Timeout(10.0, connect=3.0))
    return _tls.http


# Core SLIs exported by demo-service / python-app; default to 0 when Prometheus
# has no series yet (healthy service with no errors in window).
_CORE_SLI = frozenset({
    "error_rate", "request_rate", "latency_p99_ms", "latency_p50_ms",
    "db_errors", "pool_exhaustion",
})


def _get(url: str, timeout=10, *, _client: httpx.Client | None = None) -> dict:
    client = _client or _HTTP
    try:
        r = client.get(url, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"error": str(e)}


def _prom(expr: str, timeout=10) -> list:
    url = f"{_prom_url()}/api/v1/query?" + urllib.parse.urlencode({"query": expr})
    d = _get(url, timeout)
    return d.get("data", {}).get("result", []) if "error" not in d else []


def _loki(logql: str, start_ns: int, end_ns: int, limit=50, timeout=_LOKI_TIMEOUT_S) -> dict:
    url = f"{_loki_url()}/loki/api/v1/query_range?" + urllib.parse.urlencode({
        "query": logql, "start": start_ns, "end": end_ns,
        "limit": limit, "direction": "backward",
    })
    return _get(url, timeout=timeout)


def _scalar(results: list) -> float | None:
    for r in results:
        v = r.get("value", [])
        if v and v[1] not in ("NaN", "+Inf", "-Inf"):
            try:
                return float(v[1])
            except (ValueError, TypeError):
                pass
    return None


# ── /services ─────────────────────────────────────────────────────────────────

def _service_from_labels(labels: dict) -> str:
    return labels.get("service") or labels.get("app") or ""


def _aggregate_up(raw: list) -> dict[str, dict]:
    """Build service map from instant ``up`` results (one row per scrape target)."""
    seen: dict[str, dict] = {}
    for r in raw:
        labels = r.get("metric", {})
        svc = _service_from_labels(labels)
        if not svc:
            continue
        is_up = r.get("value", [0, "0"])[1] == "1"
        if svc not in seen:
            seen[svc] = {"name": svc, "namespace": NAMESPACE,
                         "status": "up" if is_up else "down", "instances": 0}
        seen[svc]["instances"] += 1
        if is_up:
            seen[svc]["status"] = "up"
        elif seen[svc]["status"] == "unknown":
            seen[svc]["status"] = "down"
    return seen


def _aggregate_count_by_service(raw: list) -> dict[str, dict]:
    """Build service map from ``count by (service) (...)`` vector results."""
    seen: dict[str, dict] = {}
    for r in raw:
        labels = r.get("metric", {})
        svc = _service_from_labels(labels)
        if not svc:
            continue
        try:
            count = max(0, int(float(r.get("value", [0, "0"])[1])))
        except (ValueError, TypeError):
            count = 0
        seen[svc] = {
            "name": svc,
            "namespace": NAMESPACE,
            "status": "up" if count > 0 else "down",
            "instances": count,
        }
    return seen


def _prometheus_reachable() -> bool:
    try:
        r = _HTTP.get(f"{_prom_url()}/-/healthy", timeout=3.0)
        return r.status_code == 200
    except Exception:
        return False


def _loki_reachable() -> bool:
    try:
        r = _HTTP.get(f"{_loki_url()}/ready", timeout=3.0)
        return r.status_code == 200
    except Exception:
        return False


_OBS_DEV_UP_CMD = "make dev-up"


def observability_remediation() -> dict | None:
    """Return fix instructions when Prometheus/Loki are unreachable from the host."""
    return _remediation_if_down(_prometheus_reachable(), _loki_reachable())


def _remediation_if_down(prom_ok: bool, loki_ok: bool) -> dict | None:
    if prom_ok and loki_ok:
        return None
    down = [n for n, ok in (("Prometheus", prom_ok), ("Loki", loki_ok)) if not ok]
    return {
        "issue": "stale_or_missing_port_forward",
        "message": (
            f"{', '.join(down)} unreachable from the host backend — "
            "kubectl port-forwards are likely stale after Mac sleep or minikube restart."
        ),
        "command": _OBS_DEV_UP_CMD,
        "alt_command": "make observability-port-forward",
        "prometheus_url": _prom_url(),
        "loki_url": _loki_url(),
        "hint": "Run make dev-up once — it starts a background daemon that auto-restarts port-forwards.",
    }


@router.get("/services")
def list_services():
    """Discover active services scrapped by Prometheus in the synthetic namespace."""
    prom_ok = _prometheus_reachable()
    seen: dict[str, dict] = {}
    if prom_ok:
        seen = _aggregate_up(_prom(f'up{{kubernetes_namespace="{NAMESPACE}"}}', timeout=5))
        if not seen:
            seen = _aggregate_count_by_service(
                _prom(f'count by (service) (up{{kubernetes_namespace="{NAMESPACE}"}})', timeout=5)
            )
        if not seen:
            seen = _aggregate_count_by_service(
                _prom(
                    f'count by (service) (http_requests_total{{kubernetes_namespace="{NAMESPACE}"}})',
                    timeout=5,
                )
            )

    default_status = "unknown" if not prom_ok else "down"

    # Ensure registry services appear even when Prometheus is unreachable or not scraping yet.
    for svc in _KNOWN:
        if svc not in seen:
            seen[svc] = {"name": svc, "namespace": NAMESPACE,
                         "status": default_status, "instances": 0}

    return {"services": list(seen.values())}


# ── /metrics/{service} ────────────────────────────────────────────────────────

_METRIC_DEFS = {
    # name: (expr_template, unit, warn_thresh, crit_thresh)
    "error_rate":      ('sum(rate(http_errors_total{{service="{s}"}}[{m}m]))',                          "/s",   0.05,  0.5),
    "request_rate":    ('sum(rate(http_requests_total{{service="{s}"}}[{m}m]))',                        "/s",   None,  None),
    "latency_p99_ms":  ('histogram_quantile(0.99,sum by(le)(rate(http_request_duration_ms_bucket{{service="{s}"}}[{m}m])))', "ms", 500, 2000),
    "latency_p50_ms":  ('histogram_quantile(0.50,sum by(le)(rate(http_request_duration_ms_bucket{{service="{s}"}}[{m}m])))', "ms", 200, 1000),
    "db_errors":       ('sum(increase(db_errors_total{{service="{s}"}}[{m}m]))',                        "",     1,     10),
    "pool_exhaustion": ('sum(increase(db_pool_exhaustion_total{{service="{s}"}}[{m}m]))',               "",     1,     5),
    "memory_bytes":    ('memory_heap_bytes{{service="{s}"}}',                                           "bytes",80e6, 100e6),
    "jvm_heap_used":   ('sum(jvm_memory_used_bytes{{service="{s}",jvm_memory_type="heap"}})',           "bytes",60e6,  80e6),
    "jvm_heap_limit":  ('sum(jvm_memory_limit_bytes{{service="{s}",jvm_memory_type="heap"}})',          "bytes",None,  None),
    "jvm_cpu":         ('avg(jvm_cpu_recent_utilization_ratio{{service="{s}"}})',                       "ratio",0.6,   0.8),
    "jvm_threads":     ('avg(jvm_thread_count{{service="{s}"}})',                                       "",     None,  None),
    "jvm_gc_count":    ('sum(increase(jvm_gc_duration_seconds_count{{service="{s}"}}[{m}m]))',          "",     10,    20),
}

_ANOMALY_RULES = {
    "error_rate":      ("HIGH_ERROR_RATE",   "critical", lambda v: f"{v:.4f} errors/s"),
    "latency_p99_ms":  ("HIGH_LATENCY",      "critical", lambda v: f"{v:.0f}ms P99"),
    "db_errors":       ("DB_ERRORS",         "warning",  lambda v: f"{v:.0f} DB errors"),
    "pool_exhaustion": ("POOL_EXHAUSTION",   "critical", lambda v: f"{v:.0f} pool exhaustion events"),
    "memory_bytes":    ("HIGH_HEAP",         "warning",  lambda v: f"{v/1_048_576:.1f}MB heap"),
    "jvm_heap_used":   ("JVM_HIGH_HEAP",     "warning",  lambda v: f"{v/1_048_576:.1f}MB JVM heap"),
    "jvm_cpu":         ("JVM_HIGH_CPU",      "critical", lambda v: f"{v*100:.0f}% JVM CPU"),
    "jvm_gc_count":    ("EXCESSIVE_GC",      "warning",  lambda v: f"{v:.0f} GC collections"),
}


def _fetch_metric(name: str, tmpl: str, unit, warn, crit, service: str, minutes: int):
    expr = tmpl.format(s=service, m=minutes)
    url = f"{_prom_url()}/api/v1/query?" + urllib.parse.urlencode({"query": expr})
    d = _get(url, timeout=4, _client=_thread_http())
    results = d.get("data", {}).get("result", []) if "error" not in d else []
    return name, _scalar(results), warn, crit


@router.get("/metrics/{service}")
def get_metrics(service: str, minutes: int = Query(10, ge=1, le=60)):
    """Live SLI metrics from Prometheus, with anomaly detection."""
    metrics: dict[str, float] = {}
    anomalies: list[dict]     = []

    with ThreadPoolExecutor(max_workers=len(_METRIC_DEFS)) as pool:
        futures = {
            pool.submit(_fetch_metric, name, tmpl, unit, warn, crit, service, minutes): name
            for name, (tmpl, unit, warn, crit) in _METRIC_DEFS.items()
        }
        for future in as_completed(futures):
            name, val, warn, crit = future.result()
            if val is None:
                if service in _KNOWN and name in _CORE_SLI:
                    val = 0.0
                else:
                    continue
            metrics[name] = round(val, 6)

            if crit is not None and val >= crit and name in _ANOMALY_RULES:
                atype, severity, fmt = _ANOMALY_RULES[name]
                anomalies.append({"type": atype, "severity": severity, "label": fmt(val)})
            elif warn is not None and val >= warn and name in _ANOMALY_RULES:
                atype, _, fmt = _ANOMALY_RULES[name]
                anomalies.append({"type": atype, "severity": "warning", "label": fmt(val)})

    return {
        "service":    service,
        "minutes":    minutes,
        "metrics":    metrics,
        "anomalies":  anomalies,
        "fetched_at": datetime.now(tz=timezone.utc).isoformat(),
    }


# ── /logs/{service} ───────────────────────────────────────────────────────────

@router.get("/logs/{service}")
def get_logs(
    service: str,
    minutes: int = Query(10, ge=1, le=60),
    limit:   int = Query(50, ge=1, le=200),
):
    """Recent ERROR/WARN log entries from Loki."""
    now_ns   = int(time.time() * 1e9)
    start_ns = int((time.time() - minutes * 60) * 1e9)
    logql    = f'{{service="{service}",namespace="{NAMESPACE}",level=~"ERROR|WARN"}}'

    raw = _loki(logql, start_ns, now_ns, limit)
    if "error" in raw:
        return JSONResponse(
            {"service": service, "error": raw["error"], "entries": [], "total": 0},
            status_code=502,
        )

    entries: list[dict] = []
    for stream in raw.get("data", {}).get("result", []):
        for ts_ns, line in stream.get("values", []):
            try:
                rec = json.loads(line)
                entries.append({
                    "ts":        rec.get("ts", ""),
                    "level":     rec.get("level", "?"),
                    "component": rec.get("component", "?"),
                    "msg":       rec.get("msg", line[:200]),
                    "trace_id":  rec.get("trace_id", ""),
                    "extra":     {k: v for k, v in rec.items()
                                  if k not in ("ts","level","service","env","version",
                                               "component","msg","trace_id","span_id")},
                })
            except json.JSONDecodeError:
                entries.append({"ts": "", "level": "?", "component": "?",
                                 "msg": line[:200], "trace_id": "", "extra": {}})

    entries.sort(key=lambda x: x.get("ts", ""), reverse=True)
    return {"service": service, "entries": entries[:limit], "total": len(entries)}


# ── /stack ────────────────────────────────────────────────────────────────────

@router.get("/stack")
def stack_health():
    """Health and key stats for each observability component."""

    # ── Prometheus ──────────────────────────────────────────────────────────
    prom_ok, prom_targets, prom_series = False, 0, 0
    up_count = 0
    try:
        td = _get(f"{_prom_url()}/api/v1/targets", timeout=5)
        if "error" not in td:
            active = td.get("data", {}).get("activeTargets", [])
            prom_ok = True
            prom_targets = len(active)
            up_count = sum(1 for t in active if t.get("health") == "up")
            # rough series count
            sd = _get(
                f"{_prom_url()}/api/v1/query?"
                + urllib.parse.urlencode({"query": 'count({__name__=~".+"})'}),
                timeout=5,
            )
            if "error" not in sd:
                r = sd.get("data", {}).get("result", [])
                prom_series = int(float(r[0]["value"][1])) if r else 0
    except Exception:
        pass

    # ── Loki ────────────────────────────────────────────────────────────────
    loki_ok, loki_streams, loki_labels = False, 0, []
    svc_shipping: list = []
    try:
        r = _HTTP.get(f"{_loki_url()}/ready", timeout=5)
        loki_ok = r.status_code == 200
        if loki_ok:
            ld = _get(f"{_loki_url()}/loki/api/v1/labels", timeout=5)
            if "error" not in ld:
                loki_labels = ld.get("data", [])
            # Active streams: instant queries often return empty in Loki 3.x — use
            # service label cardinality (same signal Promtail health uses).
            vd = _get(f"{_loki_url()}/loki/api/v1/label/service/values", timeout=5)
            if "error" not in vd:
                svc_shipping = vd.get("data", [])
                loki_streams = len(svc_shipping)
    except Exception:
        pass

    # ── OTel Collector — check via Prometheus target OR via Loki streams ────
    # If Loki has any non-namespace label other than the basics, OTel/Promtail
    # ConfigMap is shipping. We treat any active scrape target whose job/name
    # contains "otel" OR a labeled stream named "trace_id" as evidence of OTel.
    otel_ok = False
    try:
        td2 = _get(f"{_prom_url()}/api/v1/targets", timeout=5)
        for t in td2.get("data", {}).get("activeTargets", []):
            labels = t.get("labels", {}) or {}
            job = (labels.get("job") or "").lower()
            instance = (labels.get("instance") or "").lower()
            if "otel" in job or "otel" in instance or "collector" in job:
                otel_ok = t.get("health") == "up"
                if otel_ok:
                    break
    except Exception:
        pass
    if not otel_ok and loki_labels:
        # Fallback: any of these labels means OTel logs/traces are flowing
        otel_ok = any(lbl in loki_labels for lbl in ("trace_id", "span_id", "service_name"))

    # ── Promtail (check Loki has logs from synthetic namespace) ─────────────
    # Treat Promtail as up when service streams are visible OR namespace=synthetic
    # is among Loki labels (some Loki versions return labels but no values).
    promtail_ok = bool(svc_shipping) or ("namespace" in loki_labels and loki_ok)

    remediation = _remediation_if_down(prom_ok, loki_ok)

    if not prom_ok and not loki_ok:
        return {
            "tools": _MOCK_STACK_TOOLS,
            "namespace": NAMESPACE,
            "remediation": remediation,
            "mock": True,
            "fetched_at": datetime.now(tz=timezone.utc).isoformat(),
        }

    return {
        "tools": [
            {
                "name":     "Prometheus",
                "role":     "Metrics scraper & TSDB",
                "endpoint": _prom_ui(),
                "status":   "up" if prom_ok else "down",
                "stats":    {"targets_up": up_count, "total_targets": prom_targets, "series": prom_series},
                "ui_path":  "/graph",
            },
            {
                "name":     "Loki",
                "role":     "Log aggregation",
                "endpoint": _loki_ui(),
                "status":   "up" if loki_ok else "down",
                "stats":    {"active_streams": loki_streams, "labels": len(loki_labels)},
                "ui_path":  "/loki/api/v1/labels",
            },
            {
                "name":     "OTel Collector",
                "role":     "Traces & metrics pipeline",
                "endpoint": "otel-collector.observability:4317",
                "status":   "up" if otel_ok else "unknown",
                "stats":    {},
                "ui_path":  None,
            },
            {
                "name":     "Promtail",
                "role":     "Log shipping (DaemonSet)",
                "endpoint": "promtail.observability:9080",
                "status":   "up" if promtail_ok else "unknown",
                "stats":    {"services_shipping": len(svc_shipping)},
                "ui_path":  None,
            },
        ],
        "namespace": NAMESPACE,
        "remediation": remediation,
        "fetched_at": datetime.now(tz=timezone.utc).isoformat(),
    }


# ── /timeseries ───────────────────────────────────────────────────────────────

_TS_QUERIES = {
    "error_rate":      'sum(rate(http_errors_total{{service="{s}"}}[2m]))',
    "request_rate":    'sum(rate(http_requests_total{{service="{s}"}}[2m]))',
    "latency_p99_ms":  'histogram_quantile(0.99,sum by(le)(rate(http_request_duration_ms_bucket{{service="{s}"}}[2m])))',
    "latency_p50_ms":  'histogram_quantile(0.50,sum by(le)(rate(http_request_duration_ms_bucket{{service="{s}"}}[2m])))',
    "db_errors":       'sum(rate(db_errors_total{{service="{s}"}}[2m]))',
    "pool_exhaustion": 'sum(rate(db_pool_exhaustion_total{{service="{s}"}}[2m]))',
    "memory_bytes":    'memory_heap_bytes{{service="{s}"}}',
    "jvm_heap_used":   'sum(jvm_memory_used_bytes{{service="{s}",jvm_memory_type="heap"}})',
    "jvm_cpu":         'avg(jvm_cpu_recent_utilization_ratio{{service="{s}"}})',
    "jvm_gc_count":    'sum(rate(jvm_gc_duration_seconds_count{{service="{s}"}}[2m]))',
}


def _fetch_timeseries(name: str, expr: str, start: float, now: float, step: str):
    url = f"{_prom_url()}/api/v1/query_range?" + urllib.parse.urlencode({
        "query": expr, "start": start, "end": now, "step": step,
    })
    d = _get(url, timeout=4, _client=_thread_http())
    results = d.get("data", {}).get("result", [])
    if not results:
        return name, []
    pts = [
        [float(ts), float(v)]
        for ts, v in results[0].get("values", [])
        if v not in ("NaN", "+Inf", "-Inf")
    ]
    return name, pts


@router.get("/timeseries/{service}")
def get_timeseries(
    service: str,
    minutes: int = Query(30, ge=5, le=120),
    step:    str  = Query("60s"),
):
    """Prometheus range query — returns [timestamp, value] arrays for sparkline charts."""
    now   = time.time()
    start = now - minutes * 60

    series: dict[str, list] = {}
    with ThreadPoolExecutor(max_workers=len(_TS_QUERIES)) as pool:
        futures = {
            pool.submit(_fetch_timeseries, name, tmpl.format(s=service), start, now, step): name
            for name, tmpl in _TS_QUERIES.items()
        }
        for future in as_completed(futures):
            name, pts = future.result()
            if pts:
                series[name] = pts

    if not series and not _prometheus_reachable():
        series = _mock_timeseries(service)
        return {
            "service": service,
            "minutes": minutes,
            "step": step,
            "series": series,
            "mock": True,
        }

    return {"service": service, "minutes": minutes, "step": step, "series": series}


def _service_health(anomalies: list[dict]) -> str:
    if any(a.get("severity") == "critical" for a in anomalies):
        return "critical"
    if anomalies:
        return "warning"
    return "healthy"


# ── Cached demo telemetry (auth-service) when Prometheus/Loki unreachable ─────

_DEMO_OBSERVE_SERVICES = ("auth-service", "payment-api")

_MOCK_AUTH_METRICS = {
    "error_rate": 0.042,
    "request_rate": 128.4,
    "latency_p99_ms": 842.0,
    "latency_p50_ms": 94.0,
    "db_errors": 0.0,
    "pool_exhaustion": 0.0,
}

_MOCK_PAYMENT_METRICS = {
    "error_rate": 0.008,
    "request_rate": 64.2,
    "latency_p99_ms": 312.0,
    "latency_p50_ms": 48.0,
    "db_errors": 0.0,
    "pool_exhaustion": 0.0,
}

_MOCK_AUTH_ANOMALIES = [
    {"type": "HIGH_LATENCY", "severity": "warning", "label": "842ms P99"},
]

_MOCK_STACK_TOOLS = [
    {
        "name": "Prometheus",
        "role": "Metrics scraper & TSDB",
        "endpoint": _prom_ui(),
        "status": "down",
        "stats": {"targets_up": 0, "total_targets": 0, "series": 0},
        "ui_path": "/graph",
    },
    {
        "name": "Loki",
        "role": "Log aggregation",
        "endpoint": _loki_ui(),
        "status": "down",
        "stats": {"active_streams": 0, "labels": 0},
        "ui_path": "/loki/api/v1/labels",
    },
    {
        "name": "OTel Collector",
        "role": "Traces & metrics pipeline",
        "endpoint": "otel-collector.observability:4317",
        "status": "unknown",
        "stats": {},
        "ui_path": None,
    },
    {
        "name": "Promtail",
        "role": "Log shipping (DaemonSet)",
        "endpoint": "promtail.observability:9080",
        "status": "unknown",
        "stats": {"services_shipping": 0},
        "ui_path": None,
    },
]


def _mock_sparkline(base: float, spread: float, points: int = 12) -> list[list[float]]:
    now = time.time()
    step = 60.0
    out: list[list[float]] = []
    for i in range(points):
        ts = now - (points - 1 - i) * step
        jitter = spread * (0.5 - (i % 5) * 0.1)
        out.append([ts, round(max(0.0, base + jitter), 4)])
    return out


def _mock_watch_summary(minutes: int) -> dict:
    auth_anomalies = list(_MOCK_AUTH_ANOMALIES)
    auth_svc = {
        "name": "auth-service",
        "status": "up",
        "instances": 2,
        "namespace": NAMESPACE,
        "health": _service_health(auth_anomalies),
        "metrics": dict(_MOCK_AUTH_METRICS),
        "anomalies": auth_anomalies,
        "anomaly_count": len(auth_anomalies),
    }
    pay_svc = {
        "name": "payment-api",
        "status": "up",
        "instances": 2,
        "namespace": NAMESPACE,
        "health": "healthy",
        "metrics": dict(_MOCK_PAYMENT_METRICS),
        "anomalies": [],
        "anomaly_count": 0,
    }
    services_out = [auth_svc, pay_svc]
    all_anomalies = [{**a, "service": "auth-service", "metric": a.get("type", "")} for a in auth_anomalies]

    return {
        "overall_health": "warning",
        "services": services_out,
        "anomalies": all_anomalies,
        "minutes": minutes,
        "service_count": len(services_out),
        "healthy_count": 1,
        "fleet_health_pct": 50.0,
        "prometheus_reachable": False,
        "anomaly_count": len(all_anomalies),
        "mock": True,
        "fetched_at": datetime.now(tz=timezone.utc).isoformat(),
    }


def _mock_timeseries(service: str) -> dict[str, list]:
    if service == "payment-api":
        metrics = _MOCK_PAYMENT_METRICS
    else:
        metrics = _MOCK_AUTH_METRICS
    series: dict[str, list] = {}
    for name, val in metrics.items():
        if name.endswith("_ms"):
            series[name] = _mock_sparkline(val, val * 0.08)
        elif name.endswith("_rate") or name == "jvm_cpu":
            series[name] = _mock_sparkline(val, val * 0.12)
        elif isinstance(val, (int, float)) and val > 0:
            series[name] = _mock_sparkline(val, max(val * 0.05, 0.01))
    return series


# ── SLO / error-budget endpoint (used by Command Center widget) ──────────────

@router.get("/slo")
def slo_summary(window_hours: int = Query(24, ge=1, le=168)):
    """
    Approximate SLO + burn rate per service over an N-hour window.

    SLO target = 99.9% availability (configurable). Burn rate > 1 means the
    error budget is being burned faster than allowed for the window.

    Computed from Prometheus rate of http_errors_total / http_requests_total.
    Falls back to ``status: \"no_data\"`` when Prometheus is unreachable.
    """
    target = 0.999
    services_out: list[dict] = []
    svc_list = list_services().get("services", [])
    for svc in svc_list:
        name = svc["name"]
        err_rate = _scalar(_prom(f'sum(rate(http_errors_total{{service="{name}"}}[{window_hours}h]))'))
        total_rate = _scalar(_prom(f'sum(rate(http_requests_total{{service="{name}"}}[{window_hours}h]))'))
        if err_rate is None or total_rate is None or total_rate == 0:
            services_out.append({
                "service": name,
                "status": "no_data",
                "target": target,
                "availability": None,
                "error_budget_remaining_pct": None,
                "burn_rate": None,
                "window_hours": window_hours,
            })
            continue
        availability = max(0.0, 1.0 - (err_rate / total_rate))
        bad_budget = 1.0 - target
        actual_bad = 1.0 - availability
        budget_remaining = max(0.0, 1.0 - (actual_bad / bad_budget)) if bad_budget else 1.0
        burn_rate = (actual_bad / bad_budget) if bad_budget else 0.0
        status = "ok"
        if burn_rate >= 2.0:
            status = "critical"
        elif burn_rate >= 1.0:
            status = "warning"
        services_out.append({
            "service": name,
            "status": status,
            "target": target,
            "availability": round(availability, 5),
            "error_budget_remaining_pct": round(budget_remaining * 100, 2),
            "burn_rate": round(burn_rate, 2),
            "window_hours": window_hours,
        })
    return {
        "services": services_out,
        "window_hours": window_hours,
        "target": target,
        "fetched_at": datetime.now(tz=timezone.utc).isoformat(),
    }


def _fetch_one_sli(mname: str, tmpl: str, warn, crit, service: str, minutes: int):
    url = f"{_prom_url()}/api/v1/query?" + urllib.parse.urlencode(
        {"query": tmpl.format(s=service, m=minutes)}
    )
    d = _get(url, timeout=4, _client=_thread_http())
    results = d.get("data", {}).get("result", []) if "error" not in d else []
    return mname, _scalar(results), warn, crit


def _fetch_service_metrics(svc: dict, minutes: int, prom_ok: bool) -> dict:
    """Fetch core SLIs in parallel for the watch summary."""
    name = svc["name"]
    metrics: dict[str, float] = {}
    anomalies: list[dict] = []

    if prom_ok:
        core_defs = [(mn, tmpl, warn, crit) for mn, (tmpl, unit, warn, crit) in _METRIC_DEFS.items() if mn in _CORE_SLI]
        with ThreadPoolExecutor(max_workers=len(core_defs)) as pool:
            futs = [pool.submit(_fetch_one_sli, mn, tmpl, warn, crit, name, minutes) for mn, tmpl, warn, crit in core_defs]
            for fut in as_completed(futs):
                mname, val, warn, crit = fut.result()
                if val is None:
                    val = 0.0
                metrics[mname] = round(val, 6)
                if crit is not None and val >= crit and mname in _ANOMALY_RULES:
                    atype, severity, fmt = _ANOMALY_RULES[mname]
                    anomalies.append({"type": atype, "severity": severity, "label": fmt(val)})
                elif warn is not None and val >= warn and mname in _ANOMALY_RULES:
                    atype, _, fmt = _ANOMALY_RULES[mname]
                    anomalies.append({"type": atype, "severity": "warning", "label": fmt(val)})

    health = _service_health(anomalies)
    if not prom_ok or svc.get("status") in ("unknown", "down"):
        health = "unknown"
    return {
        "name": name,
        "status": svc.get("status", "unknown"),
        "instances": svc.get("instances", 0),
        "namespace": svc.get("namespace", NAMESPACE),
        "health": health,
        "metrics": metrics,
        "anomalies": anomalies,
        "anomaly_count": len(anomalies),
    }


@router.get("/watch")
def watch_summary(minutes: int = Query(10, ge=1, le=60)):
    """
    Aggregated proactive watch — all services, metrics, and anomalies in one poll.
    Powers the Anomaly Watch dashboard.
    """
    prom_ok = _prometheus_reachable()
    if not prom_ok:
        return _mock_watch_summary(minutes)

    svc_list = list_services().get("services", [])
    all_anomalies: list[dict] = []

    # Fetch all services in parallel — each get_metrics call is already parallel internally
    with ThreadPoolExecutor(max_workers=len(svc_list) or 1) as pool:
        futures = [pool.submit(_fetch_service_metrics, svc, minutes, prom_ok) for svc in svc_list]
        services_out = [f.result() for f in futures]

    for svc_data in services_out:
        for a in svc_data["anomalies"]:
            all_anomalies.append({**a, "service": svc_data["name"], "metric": a.get("type", "")})

    severity_rank = {"critical": 0, "warning": 1}
    all_anomalies.sort(
        key=lambda x: (severity_rank.get(x.get("severity", "warning"), 9), x.get("service", ""))
    )

    healthy_count = sum(1 for s in services_out if s["health"] == "healthy")
    total = len(services_out)
    pct = None if not prom_ok else fleet_health_pct(healthy_count, total)

    if not prom_ok:
        overall = "unknown"
    elif any(s["health"] == "critical" for s in services_out):
        overall = "critical"
    elif any(s["health"] == "warning" for s in services_out):
        overall = "warning"
    else:
        overall = "healthy"

    return {
        "overall_health": overall,
        "services": services_out,
        "anomalies": all_anomalies,
        "minutes": minutes,
        "service_count": total,
        "healthy_count": healthy_count,
        "fleet_health_pct": pct,
        "prometheus_reachable": prom_ok,
        "anomaly_count": len(all_anomalies),
        "fetched_at": datetime.now(tz=timezone.utc).isoformat(),
    }


REPORTS_DIR = Path(__file__).parent.parent.parent / "synthetic" / "reports"

_ISSUE_MODES = {name: meta["issues"] for name, meta in _SYNTHETIC_SERVICES.items()}


def _fix_markdown_headers(text: str) -> str:
    """Ensure every emoji section header has the ## prefix the model may have skipped."""
    emoji_to_level = {"🚨": "##", "🔍": "##", "🛠️": "##", "⚠️": "##", "🔁": "##"}
    lines, out = text.split("\n"), []
    for line in lines:
        stripped = line.lstrip()
        for emoji, level in emoji_to_level.items():
            if stripped.startswith(emoji) and not stripped.startswith("#"):
                line = f"{level} {stripped}"
                break
        for sub in ["Immediate Actions", "Short-term Actions", "Long-term Recommendations"]:
            if stripped.startswith(sub) and not stripped.startswith("#"):
                line = f"### {stripped}"
                break
        out.append(line)
    return "\n".join(out)


def _compute_severity(anomalies: list) -> str:
    if any(a.get("severity") == "critical" for a in anomalies):
        return "P1"
    if anomalies:
        return "P2"
    return "P3"


def _build_report_header(
    service: str, environment: str, minutes: int,
    metrics: dict, anomalies: list,
) -> str:
    """Generate a guaranteed-correct markdown Incident Assessment block in Python."""
    now_utc  = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    severity = _compute_severity(anomalies)
    sev_icon = {"P1": "🔴", "P2": "🟡", "P3": "🟢"}[severity]
    status   = "🔴 INCIDENT IN PROGRESS" if anomalies else "🟢 HEALTHY"

    lines: list[str] = [
        "## 🚨 Incident Assessment",
        "",
        "| Field | Value |",
        "|-------|-------|",
        f"| **Service** | `{service}` |",
        f"| **Environment** | {environment} |",
        f"| **Namespace** | `{NAMESPACE}` |",
        f"| **Severity** | {sev_icon} **{severity}** |",
        f"| **Window** | Last {minutes} minutes |",
        f"| **Generated** | {now_utc} |",
        f"| **Status** | {status} |",
        "",
    ]

    if anomalies:
        lines += [
            "### Active Anomalies",
            "",
            "| Severity | Signal | Value |",
            "|----------|--------|-------|",
        ]
        for a in anomalies:
            badge = "🔴 CRITICAL" if a.get("severity") == "critical" else "🟡 WARNING"
            lines.append(f"| {badge} | `{a['type']}` | {a['label']} |")
        lines.append("")
    else:
        lines += ["*No anomalies detected — service within normal operating parameters.*", ""]

    _display: dict[str, tuple] = {
        "error_rate":      ("Error Rate",      lambda v: f"{v:.4f}/s",      0.5,   0.05),
        "request_rate":    ("Request Rate",    lambda v: f"{v:.2f}/s",      None,  None),
        "latency_p99_ms":  ("P99 Latency",     lambda v: f"{v:.0f} ms",     2000,  500),
        "latency_p50_ms":  ("P50 Latency",     lambda v: f"{v:.0f} ms",     1000,  200),
        "db_errors":       ("DB Errors",       lambda v: f"{v:.0f}",        10,    1),
        "pool_exhaustion": ("Pool Exhaustion", lambda v: f"{v:.0f} events", 5,     1),
        "memory_bytes":    ("Heap Memory",     lambda v: f"{v/1e6:.1f} MB", 100e6, 80e6),
        "jvm_heap_used":   ("JVM Heap",        lambda v: f"{v/1e6:.1f} MB", 80e6,  60e6),
        "jvm_cpu":         ("JVM CPU",         lambda v: f"{v*100:.1f}%",   0.8,   0.6),
        "jvm_threads":     ("JVM Threads",     lambda v: f"{v:.0f}",        None,  None),
        "jvm_gc_count":    ("GC Collections",  lambda v: f"{v:.0f}",        20,    10),
    }

    if metrics:
        lines += [
            "### Metrics Snapshot",
            "",
            "| Metric | Value | Status |",
            "|--------|-------|--------|",
        ]
        for k, v in metrics.items():
            if k not in _display:
                continue
            label, fmt, crit, warn = _display[k]
            if crit is not None and v >= crit:
                cell = "🔴 CRITICAL"
            elif warn is not None and v >= warn:
                cell = "🟡 WARNING"
            else:
                cell = "🟢 normal"
            lines.append(f"| {label} | `{fmt(v)}` | {cell} |")
        lines.append("")

    lines += ["---", ""]
    return "\n".join(lines)


def _build_user_message(service: str, environment: str, minutes: int,
                        metrics: dict, anomalies: list, entries: list,
                        issue_triggered: str | None) -> str:
    """Grounded user message — the ## 🚨 Incident Assessment block is pre-emitted, LLM starts at Root Cause."""

    metric_fmt = {
        "error_rate":      lambda v: f"{v:.4f} errors/s  {'⚠ CRITICAL' if v >= 0.5 else '⚠ elevated' if v > 0.05 else '✓ normal'}",
        "request_rate":    lambda v: f"{v:.2f} req/s",
        "latency_p99_ms":  lambda v: f"{v:.0f} ms  {'⚠ CRITICAL' if v >= 2000 else '⚠ elevated' if v >= 500 else '✓ normal'}",
        "latency_p50_ms":  lambda v: f"{v:.0f} ms",
        "db_errors":       lambda v: f"{v:.0f} events  {'⚠ DETECTED' if v > 0 else '✓ none'}",
        "pool_exhaustion": lambda v: f"{v:.0f} events  {'⚠ EXHAUSTED' if v > 0 else '✓ none'}",
        "memory_bytes":    lambda v: f"{v/1_048_576:.1f} MB",
        "jvm_heap_used":   lambda v: f"{v/1_048_576:.1f} MB  {'⚠ HIGH' if v > 60e6 else '✓ normal'}",
        "jvm_heap_limit":  lambda v: f"{v/1_048_576:.1f} MB (max)",
        "jvm_cpu":         lambda v: f"{v*100:.1f}%  {'⚠ HIGH' if v > 0.6 else '✓ normal'}",
        "jvm_threads":     lambda v: f"{v:.0f} threads",
        "jvm_gc_count":    lambda v: f"{v:.0f} GC events in window",
    }

    prom_block = [f"PROMETHEUS METRICS (last {minutes}m):", f"  {'Metric':<22} Value", f"  {'-'*52}"]
    for k, v in metrics.items():
        fmt = metric_fmt.get(k, lambda x: str(round(x, 4)))
        prom_block.append(f"  {k:<22} {fmt(v)}")

    if anomalies:
        prom_block += ["", "ACTIVE ANOMALIES — cite every one in Root Cause Analysis:"]
        for a in anomalies:
            prom_block.append(f"  ❌ [{a['severity'].upper()}] {a['type']}: {a['label']}")
    else:
        prom_block += ["", "NO ANOMALIES — service appears healthy."]

    log_block = [f"LOKI ERROR/WARN LOGS (last {minutes}m) — {len(entries)} entries:"]
    for e in entries[:20]:
        ts = e["ts"][11:19] if len(e.get("ts", "")) > 19 else e.get("ts", "?")
        ex = " | ".join(f"{k}={v}" for k, v in (e.get("extra") or {}).items() if v)
        log_block.append(
            f"  [{ts}] {e['level']:5s} [{e['component']}] {e['msg']}"
            + (f" | trace={e['trace_id']}" if e.get("trace_id") else "")
            + (f" | {ex}" if ex else "")
        )
    if not entries:
        log_block.append("  (no ERROR/WARN logs in this window)")

    issue_hint = ""
    if issue_triggered:
        issue_hint = f"\nISSUE MODE TRIGGERED: {issue_triggered}\n"

    return (
        f"Service: {service} | Env: {environment} | Namespace: {NAMESPACE} | Window: {minutes}m\n"
        f"{issue_hint}"
        f"\n{'='*60}\n"
        f"{chr(10).join(prom_block)}\n"
        f"\n{'='*60}\n"
        f"{chr(10).join(log_block)}\n"
        f"{'='*60}\n\n"
        "TASK: Incident Assessment is already displayed. Begin immediately with:\n"
        "## 🔍 Root Cause Analysis\n"
        "Then ## 🛠️ Remediation Actions. Stop after Long-term Recommendations.\n"
        "Quote exact metric values and exact log lines from the data above."
    )


def _build_risk_section(service: str, anomalies: list, metrics: dict, issue: str | None) -> str:
    """Generate Risk Assessment table from metrics data (no LLM needed)."""
    severity = _compute_severity(anomalies)

    # Impact scope
    if any(a.get("type") in ("HIGH_ERROR_RATE", "POOL_EXHAUSTION") for a in anomalies):
        scope = f"All authenticated users of `{service}` — estimated 100% of active sessions"
    elif any(a.get("type") == "HIGH_LATENCY" for a in anomalies):
        scope = f"All API consumers of `{service}` — degraded response times"
    elif anomalies:
        scope = f"`{service}` internal — elevated resource usage, risk of user impact"
    else:
        scope = "No users currently affected — proactive monitoring only"

    # Data risk
    if any(a.get("type") in ("POOL_EXHAUSTION", "DB_ERRORS") for a in anomalies):
        data_risk = "Write — failed DB transactions may leave partial state; verify idempotency"
    elif anomalies:
        data_risk = "Read-Only — service errors are on query path; no write risk detected"
    else:
        data_risk = "None — service is healthy"

    # MTTR estimate
    if severity == "P1":
        mttr = "15–30 minutes with immediate action; longer if DB pool config change requires restart"
    elif severity == "P2":
        mttr = "30–60 minutes — config tuning + validation"
    else:
        mttr = "No action required — within SLO"

    # Rollback
    issue_rollback = {
        "high_error_rate":   f"`kubectl rollout undo deployment/{service} -n {NAMESPACE}`",
        "connection_exhaust": f"`kubectl set env deployment/{service} DB_POOL_SIZE=10 -n {NAMESPACE}` then restart",
        "cpu_spike":         f"`kubectl rollout undo deployment/{service} -n {NAMESPACE}` or scale down then back",
        "memory_leak":       f"`kubectl rollout restart deployment/{service} -n {NAMESPACE}`",
        "db_timeout":        f"`kubectl set env deployment/{service} DB_TIMEOUT_MS=5000 -n {NAMESPACE}`",
        "npe":               f"`kubectl rollout undo deployment/{service} -n {NAMESPACE}`",
    }
    rollback = issue_rollback.get(issue or "", f"`kubectl rollout undo deployment/{service} -n {NAMESPACE}`")

    lines = [
        "",
        "## ⚠️ Risk Assessment",
        "",
        "| Factor | Assessment |",
        "|--------|------------|",
        f"| **Impact Scope** | {scope} |",
        f"| **Data Risk** | {data_risk} |",
        f"| **Severity** | {severity} |",
        f"| **Estimated MTTR** | {mttr} |",
        f"| **Rollback Path** | {rollback} |",
        "",
    ]
    return "\n".join(lines)


def _build_validation_section(service: str, anomalies: list, metrics: dict) -> str:
    """Generate Validation Checklist derived from the actual anomalies detected."""
    checks: list[str] = [
        "- [ ] `error_rate` below `0.05/s` for 5 consecutive Prometheus scrapes",
        "- [ ] `latency_p99` below `2000ms` — confirm via Prometheus query",
        f"- [ ] Zero new `ERROR` or `WARN` entries in Loki for `service=\"{service}\"`",
        "- [ ] All `up` targets reporting `1` in Prometheus scrape health",
    ]

    anom_types = {a.get("type") for a in anomalies}
    if "POOL_EXHAUSTION" in anom_types or "DB_ERRORS" in anom_types:
        checks.append("- [ ] `db_pool_exhaustion_total` rate returns to `0` — DB pool fully recovered")
        checks.append("- [ ] `db_errors_total` rate at `0` — no new DB connection failures")
    if "HIGH_LATENCY" in anom_types:
        checks.append("- [ ] `latency_p50` below `200ms` — median response time healthy")
    if "JVM_HIGH_HEAP" in anom_types or "HIGH_HEAP" in anom_types:
        checks.append("- [ ] JVM heap below 60% of max — no GC pressure")
    if "JVM_HIGH_CPU" in anom_types:
        checks.append("- [ ] `jvm_cpu_recent_utilization_ratio` below `0.60` for 3 minutes")

    checks.append(f"- [ ] Load test `{service}` with baseline traffic — confirm healthy responses")

    lines = ["", "## 🔁 Validation Checklist", ""] + checks + [""]
    return "\n".join(lines)


# Enterprise lane definitions — mirrors typical large-bank SDLC pipeline
_LANES = [
    # (display_name, k8s_namespace,      k8s_context,        purpose,                        change_control)
    ("DEV",     "synthetic-dev",     "dev-k8s-context",  "Developer sandbox",            "None — self-service"),
    ("SIT",     "synthetic-sit",     "sit-k8s-context",  "System Integration Testing",   "Peer review + team lead"),
    ("UAT",     "synthetic-uat",     "uat-k8s-context",  "User Acceptance Testing",      "Business sign-off + QA lead"),
    ("PREPROD", "synthetic-preprod", "preprod-k8s-ctx",  "Pre-Production mirror",        "CAB approval required"),
    ("PROD",    "synthetic",         "prod-k8s-context", "Production",                   "Emergency CAB + on-call SRE"),
]

_SERVICE_PORTS = {name: meta["port"] for name, meta in _SYNTHETIC_SERVICES.items()}

_ISSUE_SIMULATE_DESCRIPTION = {
    "high_error_rate":   "Simulates upstream dependency failures — triggers HTTP 500/502/503 error cascade and DB pool exhaustion",
    "connection_exhaust":"Simulates DB connection pool exhaustion — all pool slots acquired, queue depth grows, HikariCP timeouts",
    "db_timeout":        "Simulates slow DB queries — each query takes 10 000ms, driving P99 latency to timeout threshold",
    "cpu_spike":         "Simulates CPU saturation — background threads consume all cores, causing scheduling latency",
    "memory_leak":       "Simulates heap growth — allocates memory without releasing, drives GC pressure then OOM",
    "crash_loop":        "Simulates pod crash loop — process exits unexpectedly, triggers Kubernetes restart backoff",
    "npe":               "Simulates NullPointerException in request handler — returns 500 for all write-path requests",
    "deadlock":          "Simulates thread deadlock — request threads hang indefinitely, pool exhaustion follows",
    "slow_response":     "Simulates slow DB/API responses — P99 latency spikes to 3–12s via sleep-based delays",
    "rate_limit":        "Simulates rate limiting — sustained HTTP 429 responses and upstream auth dependency failures",
    "log_flood":         "Simulates disk/log volume spike — bursts of structured ERROR logs for Loki ingestion stress",
}

_ISSUE_METRIC_EXPECTATION = {
    "high_error_rate":   "`error_rate` ≥ 0.5/s · `latency_p99` ≥ 2000ms · `pool_exhaustion` > 0",
    "connection_exhaust":"`pool_exhaustion` > 0 · `db_errors` > 0 · `latency_p99` ≥ 5000ms",
    "db_timeout":        "`latency_p99` ≥ 10 000ms · `db_errors` > 0 · `error_rate` > 0",
    "cpu_spike":         "`jvm_cpu` ≥ 0.8 (JVM) or pod CPU near limit · `latency_p99` elevated",
    "memory_leak":       "`jvm_heap_used` growing · GC collections increasing · eventual OOMKilled",
    "crash_loop":        "Pod restarts > 0 in `kubectl get pods` · `up` metric flapping 0/1",
    "npe":               "`error_rate` > 0 · HTTP 500 in Loki for write endpoints",
    "deadlock":          "`jvm_threads` high and not decreasing · `latency_p99` → max timeout",
    "slow_response":     "`latency_p99` ≥ 3000ms · `latency_p50` elevated · error_rate normal",
    "rate_limit":        "`error_rate` elevated (429) · `rate_limit_exceeded_total` increasing · gateway 502 if auth unhealthy",
    "log_flood":         "Many ERROR logs in Loki · `log_events_total` spike · metrics may appear healthy",
}


def _build_replicate_section(
    service: str, anomalies: list, metrics: dict,
    issue: str | None, minikube_ip: str = "192.168.105.3",
) -> str:
    """
    Enterprise-grade replication and lane promotion guide.
    Designed for multi-environment SDLC pipelines (Citi-style DEV→SIT→UAT→PREPROD→PROD).
    """
    port        = _SERVICE_PORTS.get(service, 30500)
    issue_desc  = _ISSUE_SIMULATE_DESCRIPTION.get(issue or "", "Current production state — no issue mode active")
    metric_exp  = _ISSUE_METRIC_EXPECTATION.get(issue or "", "Anomalies matching the production incident")
    severity    = _compute_severity(anomalies)
    anom_types  = {a.get("type") for a in anomalies}

    # ── Environment matrix ────────────────────────────────────────────────────
    env_rows = "\n".join(
        f"| **{lane}** | `{ns}` | `{ctx}` | {purpose} | {cc} |"
        for lane, ns, ctx, purpose, cc in _LANES
    )

    # ── Issue-specific simulate command ───────────────────────────────────────
    sim_cmd = (
        f"curl -s -X POST http://{minikube_ip}:{port}/simulate/{issue}"
        if issue else
        f"# No issue mode — analyze current state\ncurl -s http://{minikube_ip}:{port}/health"
    )

    # ── Fix commands per issue type ───────────────────────────────────────────
    fix_cmds = {
        "high_error_rate": (
            f"# Restart pods to clear error mode\n"
            f"kubectl rollout restart deployment/{service} -n <NAMESPACE>\n"
            f"# OR reset via simulate endpoint\n"
            f"curl -s -X POST http://{minikube_ip}:{port}/simulate/normal"
        ),
        "connection_exhaust": (
            f"# Increase DB pool size\n"
            f"kubectl set env deployment/{service} DB_POOL_SIZE=25 -n <NAMESPACE>\n"
            f"kubectl rollout restart deployment/{service} -n <NAMESPACE>"
        ),
        "db_timeout": (
            f"# Lower DB timeout to fail fast instead of waiting\n"
            f"kubectl set env deployment/{service} DB_TIMEOUT_MS=3000 -n <NAMESPACE>\n"
            f"kubectl rollout restart deployment/{service} -n <NAMESPACE>"
        ),
        "cpu_spike": (
            f"# Reset simulation + add CPU limits\n"
            f"curl -s -X POST http://{minikube_ip}:{port}/simulate/normal\n"
            f"kubectl patch deployment/{service} -n <NAMESPACE> \\\n"
            f"  -p '{{\"spec\":{{\"template\":{{\"spec\":{{\"containers\":[{{\"name\":\"{service}\",\"resources\":{{\"limits\":{{\"cpu\":\"500m\"}}}}}}]}}}}}}}}'"
        ),
        "memory_leak": (
            f"# Force pod restart to reclaim heap\n"
            f"kubectl rollout restart deployment/{service} -n <NAMESPACE>\n"
            f"# Add memory limit to prevent OOM cascade\n"
            f"kubectl set resources deployment/{service} --limits=memory=512Mi -n <NAMESPACE>"
        ),
        "crash_loop": (
            f"# Check crash reason\n"
            f"kubectl describe pod -n <NAMESPACE> -l app={service}\n"
            f"kubectl logs -n <NAMESPACE> -l app={service} --previous\n"
            f"# Roll back to last stable image\n"
            f"kubectl rollout undo deployment/{service} -n <NAMESPACE>"
        ),
        "npe": (
            f"# Roll back to last stable version\n"
            f"kubectl rollout undo deployment/{service} -n <NAMESPACE>"
        ),
        "deadlock": (
            f"# Force restart to clear deadlocked threads\n"
            f"kubectl rollout restart deployment/{service} -n <NAMESPACE>"
        ),
    }
    fix_block = fix_cmds.get(issue or "", f"kubectl rollout restart deployment/{service} -n <NAMESPACE>")

    # ── Anomaly-specific recovery verification ────────────────────────────────
    verify_metrics: list[str] = [
        f'curl -s "http://localhost:8080/api/v1/observability/metrics/{service}?minutes=5" \\',
        "  | python3 -c \"import json,sys; d=json.load(sys.stdin); print('Anomalies:', d['anomalies'] or 'NONE — recovered')\"",
    ]
    if "POOL_EXHAUSTION" in anom_types or "DB_ERRORS" in anom_types:
        verify_metrics += [
            "# Confirm DB pool recovered",
            f"curl -s \"http://localhost:8080/api/v1/observability/metrics/{service}?minutes=2\" \\",
            "  | python3 -c \"import json,sys; d=json.load(sys.stdin); print('pool_exhaustion:', d['metrics'].get('pool_exhaustion', 0))\"",
        ]

    # ── Promotion gates ───────────────────────────────────────────────────────
    gate_rows = [
        "| **Unit Tests pass** | ✅ Required | ✅ Required | ✅ Required | ✅ Required |",
        "| **Integration Tests pass** | Recommended | ✅ Required | ✅ Required | ✅ Required |",
        "| **Regression suite clean** | Optional | ✅ Required | ✅ Required | ✅ Required |",
        "| **Performance baseline met** | Optional | Optional | ✅ Required | ✅ Required |",
        "| **Security / SAST scan** | Optional | ✅ Required | ✅ Required | ✅ Required |",
        "| **Fix reproduced in lane** | ✅ Required | ✅ Required | ✅ Required | ✅ Required |",
        "| **Rollback tested in lane** | Optional | ✅ Required | ✅ Required | ✅ Required |",
        "| **Peer code review** | ✅ Required | ✅ Required | ✅ Required | ✅ Required |",
        "| **Team lead sign-off** | Optional | ✅ Required | ✅ Required | ✅ Required |",
        "| **QA / Business sign-off** | Not Required | Not Required | ✅ Required | ✅ Required |",
        "| **CAB / Change ticket** | Not Required | Not Required | Advisory CAB | **Emergency CAB** |",
        "| **On-call SRE approval** | Not Required | Not Required | Not Required | **Required** |",
    ]

    lines: list[str] = [
        "",
        "## 🔬 Replication & Lane Promotion Guide",
        "",
        f"> **Incident Reference:** `{service}` · Severity {severity}"
        + (f" · Failure mode `{issue}`" if issue else "")
        + "  ",
        f"> **Purpose:** Reproduce this failure in a lower lane, validate the fix, then promote through DEV → SIT → UAT → PREPROD → PROD.",
        "",
        "---",
        "",
        "### Environment Matrix",
        "",
        "| Lane | Namespace | K8s Context | Purpose | Change Control |",
        "|------|-----------|-------------|---------|----------------|",
        env_rows,
        "",
        "---",
        "",
        "### Failure Mode Description",
        "",
        f"| Field | Value |",
        f"|-------|-------|",
        f"| **Issue Mode** | `{issue or 'none (baseline)'}` |",
        f"| **Description** | {issue_desc} |",
        f"| **Expected Metrics** | {metric_exp} |",
        f"| **Simulate Endpoint** | `POST http://<minikube-ip>:{port}/simulate/{issue or 'normal'}` |",
        "",
        "---",
        "",
        "### Step-by-Step Reproduction (Lower Lane)",
        "",
        "Replace `<NAMESPACE>` with the target lane namespace and `<CONTEXT>` with the k8s context.",
        "",
        "**Step 1 — Switch context and verify service health**",
        "```bash",
        "kubectl config use-context <CONTEXT>",
        f"kubectl get pods -n <NAMESPACE> -l app={service}",
        f"# Expected: 1/1 Running",
        f"curl -s http://{minikube_ip}:{port}/health",
        f"# Expected: {{\"status\":\"ok\",\"mode\":\"normal\"}}",
        "```",
        "",
        "**Step 2 — Start observability port-forwards** *(skip if already running)*",
        "```bash",
        "kubectl port-forward svc/prometheus  19090:9090 -n observability &",
        "kubectl port-forward svc/loki        13100:3100 -n observability &",
        "# Verify",
        "curl -s http://localhost:19090/-/healthy && echo 'Prometheus OK'",
        "curl -s http://localhost:13100/ready   && echo 'Loki OK'",
        "```",
        "",
        "**Step 3 — Trigger the failure mode**",
        "```bash",
        sim_cmd,
        f"# Expected response: {{\"mode\":\"{issue or 'normal'}\",\"status\":\"activated\"}}",
        "sleep 30  # wait one full Prometheus scrape interval",
        "```",
        "",
        "**Step 4 — Confirm anomalies are detected**",
        "```bash",
        f"curl -s 'http://localhost:8080/api/v1/observability/metrics/{service}?minutes=5' \\",
        "  | python3 -c \"import json,sys; d=json.load(sys.stdin); [print(a['severity'].upper(), a['type'], '→', a['label']) for a in d['anomalies']]\"",
        f"# Expected signals: {metric_exp}",
        "```",
        "",
        "**Step 5 — Generate incident report for the lane**",
        "```bash",
        f"curl -s -X POST http://localhost:8080/api/v1/observability/analyze-live \\",
        f"  -H 'Content-Type: application/json' \\",
        f"  -d '{{",
        f"    \"service\":     \"{service}\",",
        f"    \"environment\": \"<LANE>\",",
        f"    \"minutes\":     10,",
        f"    \"issue\":       \"{issue or ''}\"",
        f"  }}' \\",
        "  | grep '^data: ' | python3 -c \\",
        "    \"import sys,json; [print(json.loads(l[6:]).get('text',''),end='') for l in sys.stdin if json.loads(l[6:]).get('type')=='token']\"",
        "# Report auto-saved to synthetic/reports/<service>_<issue>_<timestamp>.md",
        "```",
        "",
        "**Step 6 — Apply fix**",
        "```bash",
        fix_block,
        "```",
        "",
        "**Step 7 — Verify recovery**",
        "```bash",
        "sleep 60  # allow two Prometheus scrapes after fix",
        *verify_metrics,
        "# Loki: confirm no new ERROR entries",
        f"curl -s 'http://localhost:8080/api/v1/observability/logs/{service}?minutes=3&limit=5' \\",
        "  | python3 -c \"import json,sys; d=json.load(sys.stdin); print('Recent errors:', d.get('total',0))\"",
        "```",
        "",
        "---",
        "",
        "### Lane Promotion Gates",
        "",
        "| Gate | DEV → SIT | SIT → UAT | UAT → PREPROD | PREPROD → PROD |",
        "|------|-----------|-----------|---------------|----------------|",
        *gate_rows,
        "",
        "---",
        "",
        "### Config Differences Per Lane",
        "",
        "| Config Key | DEV | SIT | UAT | PROD |",
        "|------------|-----|-----|-----|------|",
        "| Replica count | 1 | 2 | 2 | 3+ (HPA) |",
        "| DB pool size | 5 | 10 | 15 | 20–50 |",
        "| Log level | DEBUG | INFO | INFO | WARN |",
        "| Circuit breaker threshold | 80% | 70% | 60% | 50% |",
        "| Prometheus scrape interval | 30s | 15s | 15s | 10s |",
        "| Alert routing | Dev channel | SIT channel | UAT + QA channel | PagerDuty + NOC |",
        "",
        "---",
        "",
        "### Citi-Style Change Management Checklist",
        "",
        f"- [ ] **INC ticket created** in ServiceNow: `INC-<number>` — severity {severity}, service `{service}`",
        "- [ ] **Root cause documented** in ticket (link to this report)",
        "- [ ] **Fix validated** in DEV lane with matching reproduce steps",
        "- [ ] **SIT regression suite** executed — attach results to ticket",
        "- [ ] **UAT sign-off** obtained from application owner",
        "- [ ] **Change record created** (Emergency for P1/P2, Standard for P3): `CHG-<number>`",
        "- [ ] **CAB approval** obtained (Emergency CAB for P1/P2 out-of-hours)",
        "- [ ] **On-call SRE** notified of deployment window",
        "- [ ] **Rollback procedure** confirmed and tested in PREPROD",
        "- [ ] **Post-deployment validation** executed using Step 7 commands above",
        "- [ ] **Incident closed** in ServiceNow with MTTR and RCA attached",
        "",
    ]
    return "\n".join(lines)


# ── /trigger-issue ────────────────────────────────────────────────────────────

@router.post("/trigger-issue")
async def trigger_issue(body: dict):
    """Trigger a failure mode on a synthetic service via its simulate endpoint."""
    service = body.get("service", "auth-service")
    issue   = body.get("issue", "high_error_rate")
    ip      = body.get("minikube_ip", _MINIKUBE_IP_DEFAULT)

    ports = _SERVICE_PORTS
    port  = ports.get(service, 30500)
    url   = f"http://{ip}:{port}/simulate/{issue}"

    try:
        with urllib.request.urlopen(url, timeout=8) as r:
            result = json.load(r)
        return {"status": "triggered", "service": service, "issue": issue, "response": result}
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=502)


# ── /reports ─────────────────────────────────────────────────────────────────

@router.get("/reports")
def list_reports():
    """
    List saved incident reports.

    Filename format: ``<service>_<issue-slug>_<YYYYMMDD>_<HHMMSS>.md``

    The split logic must tolerate underscores in service names (e.g. ``my_api``)
    AND in issue slugs (e.g. ``high_error_rate``) — so we anchor on the date
    token and split from there. We also surface the parsed ``service`` and
    ``issue`` in the response so the frontend doesn't have to re-parse.
    """
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(REPORTS_DIR.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    out: list[dict] = []
    known = set(_KNOWN)
    for f in files[:20]:
        stem = f.stem
        parts = stem.split("_")
        # Anchor: locate first 8-digit date token. Everything before it is
        # service + issue. Everything after is the timestamp.
        date_idx = next((i for i, p in enumerate(parts) if re.fullmatch(r"\d{8}", p)), -1)
        if date_idx <= 0:
            service, issue = parts[0] if parts else stem, ""
        else:
            head = parts[:date_idx]
            # Prefer known service names from registry (handles underscores).
            service, issue = head[0], "_".join(head[1:])
            for cand_len in range(min(4, len(head)), 0, -1):
                cand = "_".join(head[:cand_len])
                if cand in known:
                    service = cand
                    issue = "_".join(head[cand_len:])
                    break
        out.append({
            "filename": f.name,
            "service":  service,
            "issue":    issue or "baseline",
            "size":     f.stat().st_size,
            "modified": datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc).isoformat(),
        })
    return {"reports": out}


@router.get("/reports/{filename}")
def get_report(filename: str):
    """Read a saved report by filename."""
    path = REPORTS_DIR / filename
    if not path.exists() or not path.suffix == ".md":
        return JSONResponse({"error": "not found"}, status_code=404)
    return {"filename": filename, "content": path.read_text()}


# ── /analyze-live ─────────────────────────────────────────────────────────────

@router.post("/analyze-live")
async def analyze_live(body: dict):
    """Collect signals in parallel, correlate, stream AI analysis, auto-save report."""
    service          = body.get("service", "auth-service")
    environment      = body.get("environment", "production")
    minutes          = int(body.get("minutes", 10))
    issue_to_trigger = body.get("issue")
    minikube_ip      = body.get("minikube_ip", _MINIKUBE_IP_DEFAULT)

    agent = AnalysisAgent(prom_url=_prom_url(), loki_url=_loki_url(), namespace=NAMESPACE)

    gen = agent.stream(
        service          = service,
        environment      = environment,
        minutes          = minutes,
        issue_triggered  = issue_to_trigger,
        minikube_ip      = minikube_ip,
        reports_dir      = REPORTS_DIR,
        build_header_fn  = _build_report_header,
        build_risk_fn    = _build_risk_section,
        build_validation_fn = _build_validation_section,
        build_replicate_fn  = _build_replicate_section,
        service_ports    = _SERVICE_PORTS,
        live_prompt      = _LIVE_PROMPT,
        ollama_url       = settings.ollama_base_url,
        ollama_model     = settings.ollama_model,
    )

    return StreamingResponse(gen, media_type="text/event-stream", headers={
        "Cache-Control":    "no-cache",
        "X-Accel-Buffering": "no",
        "Connection":       "keep-alive",
    })
