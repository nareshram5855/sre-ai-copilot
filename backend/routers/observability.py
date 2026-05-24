"""
Live Observability API — queries Prometheus and Loki directly,
returns structured telemetry for the SRE dashboard.

Endpoints:
  GET  /api/v1/observability/services           — discover active services
  GET  /api/v1/observability/metrics/{service}  — live SLI metrics
  GET  /api/v1/observability/logs/{service}     — recent ERROR/WARN logs
  POST /api/v1/observability/analyze-live       — collect + stream AI analysis
"""
import json
import os
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse, StreamingResponse

from backend.config import settings
from backend.routers.incident_analysis import SYSTEM_PROMPT

router = APIRouter(prefix="/api/v1/observability", tags=["observability"])

PROM_URL  = os.getenv("PROMETHEUS_URL", "http://localhost:19090")
LOKI_URL  = os.getenv("LOKI_URL",       "http://localhost:13100")
NAMESPACE = "synthetic"
_KNOWN    = ["auth-service", "order-service"]

# External-access URLs for the browser links (NodePort via minikube)
_PROM_UI   = os.getenv("PROMETHEUS_UI_URL",  "http://localhost:19090")
_LOKI_UI   = os.getenv("LOKI_UI_URL",        "http://localhost:13100")


# ── Shared HTTP helpers ────────────────────────────────────────────────────────

def _get(url: str, timeout=10) -> dict:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.load(r)
    except Exception as e:
        return {"error": str(e)}


def _prom(expr: str, timeout=10) -> list:
    url = f"{PROM_URL}/api/v1/query?" + urllib.parse.urlencode({"query": expr})
    d = _get(url, timeout)
    return d.get("data", {}).get("result", []) if "error" not in d else []


def _loki(logql: str, start_ns: int, end_ns: int, limit=50, timeout=15) -> dict:
    url = f"{LOKI_URL}/loki/api/v1/query_range?" + urllib.parse.urlencode({
        "query": logql, "start": start_ns, "end": end_ns,
        "limit": limit, "direction": "backward",
    })
    return _get(url, timeout)


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

@router.get("/services")
def list_services():
    """Discover active services scrapped by Prometheus in the synthetic namespace."""
    raw = _prom(f'up{{kubernetes_namespace="{NAMESPACE}"}}')
    seen: dict[str, dict] = {}
    for r in raw:
        labels = r.get("metric", {})
        svc = labels.get("service") or labels.get("app", "")
        if not svc:
            continue
        is_up = r.get("value", [0, "0"])[1] == "1"
        if svc not in seen:
            seen[svc] = {"name": svc, "namespace": NAMESPACE,
                         "status": "up" if is_up else "down", "instances": 0}
        seen[svc]["instances"] += 1

    # Fallback if Prometheus not yet scraping
    for svc in _KNOWN:
        if svc not in seen:
            seen[svc] = {"name": svc, "namespace": NAMESPACE,
                         "status": "unknown", "instances": 0}

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


@router.get("/metrics/{service}")
def get_metrics(service: str, minutes: int = Query(10, ge=1, le=60)):
    """Live SLI metrics from Prometheus, with anomaly detection."""
    metrics: dict[str, float] = {}
    anomalies: list[dict]     = []

    for name, (tmpl, unit, warn, crit) in _METRIC_DEFS.items():
        expr = tmpl.format(s=service, m=minutes)
        val  = _scalar(_prom(expr))
        if val is None:
            continue
        metrics[name] = round(val, 6)

        # Anomaly check against warn threshold (crit = anomaly)
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
        return JSONResponse({"error": raw["error"], "entries": []}, status_code=502)

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
    try:
        td = _get(f"{PROM_URL}/api/v1/targets", timeout=5)
        active = td.get("data", {}).get("activeTargets", [])
        prom_ok = True
        prom_targets = len(active)
        up_count = sum(1 for t in active if t.get("health") == "up")
        # rough series count
        sd = _get(f"{PROM_URL}/api/v1/query?" + urllib.parse.urlencode({"query": "count({__name__=~\".+\"})"}), timeout=5)
        r = sd.get("data", {}).get("result", [])
        prom_series = int(float(r[0]["value"][1])) if r else 0
    except Exception:
        up_count = 0

    # ── Loki ────────────────────────────────────────────────────────────────
    loki_ok, loki_streams, loki_labels = False, 0, []
    try:
        with urllib.request.urlopen(f"{LOKI_URL}/ready", timeout=5) as r:
            loki_ok = r.status == 200
        ld = _get(f"{LOKI_URL}/loki/api/v1/labels", timeout=5)
        loki_labels = ld.get("data", [])
        # count active streams
        sq = _get(f"{LOKI_URL}/loki/api/v1/query?" + urllib.parse.urlencode(
            {"query": f'{{namespace="{NAMESPACE}"}}', "limit": "1"}), timeout=5)
        loki_streams = len(sq.get("data", {}).get("result", []))
    except Exception:
        pass

    # ── OTel Collector (in-cluster only — check via Prometheus target) ──────
    otel_ok = False
    try:
        td2 = _get(f"{PROM_URL}/api/v1/targets", timeout=5)
        for t in td2.get("data", {}).get("activeTargets", []):
            if "otel" in t.get("labels", {}).get("job", "").lower():
                otel_ok = t.get("health") == "up"
                break
    except Exception:
        pass

    # ── Promtail (check Loki has logs from synthetic namespace) ─────────────
    promtail_ok = False
    try:
        vd = _get(f"{LOKI_URL}/loki/api/v1/label/service/values", timeout=5)
        promtail_ok = len(vd.get("data", [])) > 0
    except Exception:
        pass

    return {
        "tools": [
            {
                "name":     "Prometheus",
                "role":     "Metrics scraper & TSDB",
                "endpoint": _PROM_UI,
                "status":   "up" if prom_ok else "down",
                "stats":    {"targets_up": up_count, "total_targets": prom_targets, "series": prom_series},
                "ui_path":  "/graph",
            },
            {
                "name":     "Loki",
                "role":     "Log aggregation",
                "endpoint": _LOKI_UI,
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
                "endpoint": f"promtail.observability:9080",
                "status":   "up" if promtail_ok else "unknown",
                "stats":    {"services_shipping": len(vd.get("data", [])) if promtail_ok else 0},
                "ui_path":  None,
            },
        ],
        "namespace": NAMESPACE,
        "fetched_at": datetime.now(tz=timezone.utc).isoformat(),
    }


# ── /timeseries ───────────────────────────────────────────────────────────────

_TS_QUERIES = {
    "error_rate":     'sum(rate(http_errors_total{{service="{s}"}}[2m]))',
    "request_rate":   'sum(rate(http_requests_total{{service="{s}"}}[2m]))',
    "latency_p99_ms": 'histogram_quantile(0.99,sum by(le)(rate(http_request_duration_ms_bucket{{service="{s}"}}[2m])))',
    "latency_p50_ms": 'histogram_quantile(0.50,sum by(le)(rate(http_request_duration_ms_bucket{{service="{s}"}}[2m])))',
    "db_errors":      'sum(rate(db_errors_total{{service="{s}"}}[2m]))',
    "jvm_heap_used":  'sum(jvm_memory_used_bytes{{service="{s}",jvm_memory_type="heap"}})',
    "jvm_cpu":        'avg(jvm_cpu_recent_utilization_ratio{{service="{s}"}})',
    "jvm_gc_count":   'sum(rate(jvm_gc_duration_seconds_count{{service="{s}"}}[2m]))',
}


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
    for name, tmpl in _TS_QUERIES.items():
        expr = tmpl.format(s=service)
        url  = f"{PROM_URL}/api/v1/query_range?" + urllib.parse.urlencode({
            "query": expr, "start": start, "end": now, "step": step,
        })
        d = _get(url, timeout=10)
        results = d.get("data", {}).get("result", [])
        if results:
            pts = [
                [float(ts), float(v)]
                for ts, v in results[0].get("values", [])
                if v not in ("NaN", "+Inf", "-Inf")
            ]
            if pts:
                series[name] = pts

    return {"service": service, "minutes": minutes, "step": step, "series": series}


# ── /analyze-live ─────────────────────────────────────────────────────────────

@router.post("/analyze-live")
async def analyze_live(body: dict):
    """Collect live telemetry from Prometheus+Loki and stream AI incident analysis."""
    service     = body.get("service", "auth-service")
    environment = body.get("environment", "production")
    minutes     = int(body.get("minutes", 10))
    session_id  = body.get("session_id", f"live-{int(time.time())}")

    async def _stream():
        # ── Step 1: Prometheus ─────────────────────────────────────────────
        yield f'data: {json.dumps({"type": "status", "text": "Querying Prometheus metrics..."})}\n\n'
        m_resp    = get_metrics(service, minutes)
        metrics   = m_resp.get("metrics", {})
        anomalies = m_resp.get("anomalies", [])

        # ── Step 2: Loki ───────────────────────────────────────────────────
        yield f'data: {json.dumps({"type": "status", "text": "Fetching Loki error logs..."})}\n\n'
        l_resp  = get_logs(service, minutes, 30)
        entries = l_resp.get("entries", [])

        # ── Step 3: Build raw incident string ─────────────────────────────
        prom_lines = [f"=== Prometheus Metrics [{service}] (last {minutes}m) ==="]
        if anomalies:
            prom_lines.append("ANOMALIES DETECTED:")
            for a in anomalies:
                prom_lines.append(f"  ⚠ [{a['severity'].upper()}] {a['type']}: {a['label']}")
        for k, v in metrics.items():
            prom_lines.append(f"  {k}: {v}")

        log_lines = [f"=== Loki Logs [{service}] (last {minutes}m, ERROR+WARN only) ===",
                     f"Retrieved {len(entries)} log entries"]
        for e in entries[:25]:
            ts_short  = e["ts"][11:19] if len(e.get("ts", "")) > 19 else e.get("ts", "")
            extra_str = " | ".join(f"{k}={v}" for k, v in (e.get("extra") or {}).items() if v)
            log_lines.append(
                f"  [{ts_short}] {e['level']:5s} [{e['component']}] {e['msg']}"
                + (f" | trace={e['trace_id']}" if e.get("trace_id") else "")
                + (f" | {extra_str}" if extra_str else "")
            )

        raw_incident = "\n\n".join([
            f"Service: {service}",
            f"Environment: {environment} | Namespace: {NAMESPACE}",
            f"Lookback: last {minutes} minutes",
            "\n".join(prom_lines),
            "\n".join(log_lines),
        ])

        # Emit collected telemetry back to UI for display
        yield f'data: {json.dumps({"type": "telemetry", "metrics": metrics, "anomalies": anomalies, "log_count": len(entries)})}\n\n'
        yield f'data: {json.dumps({"type": "status", "text": "Streaming AI analysis..."})}\n\n'

        # ── Step 4: Stream AI ──────────────────────────────────────────────
        user_msg = (
            f"Environment: {environment}\nService: {service}\n"
            f"\n--- RAW INCIDENT DATA ---\n{raw_incident.strip()}\n--- END INCIDENT DATA ---\n\n"
            "Analyze this incident and respond using the required SRE response schema exactly."
        )
        llm_body = {
            "model":    settings.ollama_model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": user_msg},
            ],
            "stream":  True,
            "options": {"num_ctx": 8192, "num_predict": 2048, "temperature": 0.05},
        }

        try:
            async with httpx.AsyncClient(timeout=120) as http:
                async with http.stream("POST", f"{settings.ollama_base_url}/api/chat",
                                       json=llm_body) as resp:
                    async for raw_line in resp.aiter_lines():
                        if not raw_line.strip():
                            continue
                        try:
                            chunk = json.loads(raw_line)
                        except json.JSONDecodeError:
                            continue
                        token = chunk.get("message", {}).get("content", "")
                        if token:
                            yield f'data: {json.dumps({"type": "token", "text": token})}\n\n'
                        if chunk.get("done"):
                            yield f'data: {json.dumps({"type": "done"})}\n\n'
                            return
        except httpx.TimeoutException:
            yield f'data: {json.dumps({"type": "error", "message": "LLM timed out"})}\n\n'
        except Exception as exc:
            yield f'data: {json.dumps({"type": "error", "message": str(exc)})}\n\n'

    return StreamingResponse(_stream(), media_type="text/event-stream", headers={
        "Cache-Control":    "no-cache",
        "X-Accel-Buffering": "no",
        "Connection":       "keep-alive",
    })
