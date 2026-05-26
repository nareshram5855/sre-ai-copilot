"""
Multi-signal SRE Analysis Agent

Collects Prometheus SLI metrics, OTel collector metrics, Loki error/trace logs,
and OTel-specific Prometheus counters in parallel, then runs deterministic Python
correlation before calling the LLM with a compressed ~2000-token context.

Five SSE progress steps:
  1/5 — Parallel signal collection (Prometheus + Loki + OTel)
  2/5 — Cross-signal correlation & cascade detection
  3/5 — Streaming AI narrative
  4/5 — Python-generated structured sections
  5/5 — Saving report
"""
from __future__ import annotations

import asyncio
import json
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncGenerator, Callable


# ── HTTP helpers (sync, run in thread) ────────────────────────────────────────

def _get(url: str, timeout: int = 10) -> dict:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.load(r)
    except Exception as exc:
        return {"error": str(exc)}


def _prom_instant(prom_url: str, expr: str, timeout: int = 10) -> list:
    url = f"{prom_url}/api/v1/query?" + urllib.parse.urlencode({"query": expr})
    d = _get(url, timeout)
    return d.get("data", {}).get("result", []) if "error" not in d else []


def _scalar(results: list) -> float | None:
    for r in results:
        v = r.get("value", [])
        if v and v[1] not in ("NaN", "+Inf", "-Inf"):
            try:
                return float(v[1])
            except (ValueError, TypeError):
                pass
    return None


def _loki_query(loki_url: str, logql: str, start_ns: int, end_ns: int,
                limit: int = 50, timeout: int = 15) -> dict:
    url = f"{loki_url}/loki/api/v1/query_range?" + urllib.parse.urlencode({
        "query": logql, "start": start_ns, "end": end_ns,
        "limit": limit, "direction": "backward",
    })
    return _get(url, timeout)


# ── Cascade pattern library ────────────────────────────────────────────────────
# Each pattern is (trigger_anomaly, downstream_anomalies, cascade_name)

_CASCADE_PATTERNS = [
    (
        "POOL_EXHAUSTION",
        {"POOL_EXHAUSTION", "DB_ERRORS", "HIGH_LATENCY", "HIGH_ERROR_RATE"},
        "DB Pool → Query Timeout → High Latency → Error Cascade",
    ),
    (
        "DB_ERRORS",
        {"DB_ERRORS", "HIGH_ERROR_RATE"},
        "DB Errors → Service Error Rate",
    ),
    (
        "JVM_HIGH_CPU",
        {"JVM_HIGH_CPU", "HIGH_LATENCY", "HIGH_ERROR_RATE"},
        "JVM CPU Saturation → Thread Contention → Latency → Errors",
    ),
    (
        "JVM_HIGH_HEAP",
        {"JVM_HIGH_HEAP", "EXCESSIVE_GC", "HIGH_LATENCY"},
        "Heap Pressure → GC Thrash → Latency Spike",
    ),
    (
        "HIGH_LATENCY",
        {"HIGH_LATENCY", "HIGH_ERROR_RATE"},
        "Timeout Threshold → Upstream Error Rate",
    ),
]

_CONFIDENCE_ORDER = ["HIGH", "MEDIUM", "LOW"]


class AnalysisAgent:
    """Parallel signal collector + Python correlator + LLM narrative streamer."""

    def __init__(self, prom_url: str, loki_url: str, namespace: str = "synthetic"):
        self.prom_url  = prom_url
        self.loki_url  = loki_url
        self.namespace = namespace

    # ── 1. Collection methods (sync, called via asyncio.to_thread) ─────────────

    def collect_prometheus(self, service: str, minutes: int) -> dict:
        """SLI metrics + OTel collector counters — batched into one multi-query URL."""
        m = minutes

        queries = {
            "error_rate":            f'sum(rate(http_errors_total{{service="{service}"}}[{m}m]))',
            "request_rate":          f'sum(rate(http_requests_total{{service="{service}"}}[{m}m]))',
            "latency_p99_ms":        f'histogram_quantile(0.99,sum by(le)(rate(http_request_duration_ms_bucket{{service="{service}"}}[{m}m])))',
            "latency_p50_ms":        f'histogram_quantile(0.50,sum by(le)(rate(http_request_duration_ms_bucket{{service="{service}"}}[{m}m])))',
            "db_errors":             f'sum(increase(db_errors_total{{service="{service}"}}[{m}m]))',
            "pool_exhaustion":       f'sum(increase(db_pool_exhaustion_total{{service="{service}"}}[{m}m]))',
            "jvm_heap_used":         f'sum(jvm_memory_used_bytes{{service="{service}",jvm_memory_type="heap"}})',
            "jvm_cpu":               f'avg(jvm_cpu_recent_utilization_ratio{{service="{service}"}})',
            "jvm_gc_count":          f'sum(increase(jvm_gc_duration_seconds_count{{service="{service}"}}[{m}m]))',
            "otel_spans_accepted":   f"sum(increase(otelcol_receiver_accepted_spans_total[{m}m]))",
            "otel_spans_refused":    f"sum(increase(otelcol_receiver_refused_spans_total[{m}m]))",
            "otel_exporter_queue":   "sum(otelcol_exporter_queue_size)",
            "otel_exporter_dropped": f"sum(increase(otelcol_exporter_send_failed_spans_total[{m}m]))",
        }

        metrics: dict[str, float] = {}
        for name, expr in queries.items():
            val = _scalar(_prom_instant(self.prom_url, expr, timeout=6))
            if val is not None:
                metrics[name] = round(val, 6)

        return metrics

    def collect_loki(self, service: str, minutes: int) -> dict:
        """Error/warn logs only — single fast query, trace_ids extracted from JSON."""
        now_ns   = int(time.time() * 1e9)
        start_ns = int((time.time() - minutes * 60) * 1e9)
        ns = self.namespace

        def _parse_stream(raw: dict, limit: int = 20) -> list[dict]:
            entries: list[dict] = []
            for stream in raw.get("data", {}).get("result", []):
                for _, line in stream.get("values", []):
                    try:
                        rec = json.loads(line)
                        entries.append({
                            "ts":        rec.get("ts", ""),
                            "level":     rec.get("level", "?"),
                            "component": rec.get("component", "app"),
                            "msg":       rec.get("msg", line[:200]),
                            "trace_id":  rec.get("trace_id", ""),
                            "span_id":   rec.get("span_id", ""),
                            "extra":     {k: v for k, v in rec.items()
                                          if k not in ("ts", "level", "service", "env",
                                                       "version", "component", "msg",
                                                       "trace_id", "span_id")},
                        })
                    except json.JSONDecodeError:
                        entries.append({"ts": "", "level": "?", "component": "?",
                                        "msg": line[:200], "trace_id": "", "span_id": "", "extra": {}})
            entries.sort(key=lambda x: x.get("ts", ""), reverse=True)
            return entries[:limit]

        # Single Loki query — fast, no complex pipeline filters
        error_raw = _loki_query(self.loki_url,
            f'{{service="{service}",namespace="{ns}",level=~"ERROR|WARN"}}',
            start_ns, now_ns, limit=50, timeout=8)

        all_entries = _parse_stream(error_raw, 50)
        error_count = len(all_entries)

        # Extract trace IDs directly from parsed JSON (no extra Loki query needed)
        trace_logs = [e for e in all_entries if e.get("trace_id")][:10]

        return {
            "error_logs":  all_entries[:20],
            "trace_logs":  trace_logs,
            "otel_logs":   [],
            "error_count": error_count,
        }

    def collect_otel_signals(self, service: str, minutes: int) -> dict:
        """OTel-semantic span error ratio + exporter pressure via Prometheus."""
        m = minutes
        queries = {
            "span_error_ratio": (
                f'sum(rate(http_errors_total{{service="{service}"}}[{m}m])) / '
                f'sum(rate(http_requests_total{{service="{service}"}}[{m}m]))'
            ),
            "otel_http_p99_ms": (
                f'histogram_quantile(0.99,sum by(le)(rate('
                f'http_server_duration_milliseconds_bucket{{service="{service}"}}[{m}m])))'
            ),
            "otel_db_p99_ms": (
                f'histogram_quantile(0.99,sum by(le)(rate('
                f'db_client_duration_milliseconds_bucket{{service="{service}"}}[{m}m])))'
            ),
        }
        signals: dict[str, float] = {}
        for name, expr in queries.items():
            val = _scalar(_prom_instant(self.prom_url, expr))
            if val is not None:
                signals[name] = round(val, 6)
        return signals

    # ── 2. Correlation (pure Python, deterministic) ───────────────────────────

    def correlate(self, metrics: dict, logs: dict, otel: dict, minutes: int) -> dict:
        """Detect anomalies, rank root-cause candidates, find cascade chain."""

        # Anomaly detection thresholds
        _rules = {
            "error_rate":      ("HIGH_ERROR_RATE",   "critical", 0.5,   0.05),
            "latency_p99_ms":  ("HIGH_LATENCY",      "critical", 2000,  500),
            "db_errors":       ("DB_ERRORS",         "warning",  10,    1),
            "pool_exhaustion": ("POOL_EXHAUSTION",   "critical", 5,     1),
            "jvm_heap_used":   ("JVM_HIGH_HEAP",     "warning",  80e6,  60e6),
            "jvm_cpu":         ("JVM_HIGH_CPU",      "critical", 0.8,   0.6),
            "jvm_gc_count":    ("EXCESSIVE_GC",      "warning",  20,    10),
        }

        anomalies: list[dict] = []
        for metric_name, (atype, base_sev, crit_thresh, warn_thresh) in _rules.items():
            val = metrics.get(metric_name)
            if val is None:
                continue
            if val >= crit_thresh:
                anomalies.append({"type": atype, "severity": "critical",
                                   "metric": metric_name, "value": val,
                                   "threshold": crit_thresh})
            elif val >= warn_thresh:
                anomalies.append({"type": atype, "severity": "warning",
                                   "metric": metric_name, "value": val,
                                   "threshold": warn_thresh})

        anom_types = {a["type"] for a in anomalies}

        # OTel pipeline pressure anomalies
        otel_queue = metrics.get("otel_exporter_queue")
        otel_dropped = metrics.get("otel_exporter_dropped", 0)
        if otel_queue is not None and otel_queue > 500:
            anomalies.append({"type": "OTEL_QUEUE_PRESSURE", "severity": "warning",
                               "metric": "otel_exporter_queue", "value": otel_queue,
                               "threshold": 500})
            anom_types.add("OTEL_QUEUE_PRESSURE")
        if otel_dropped > 0:
            anomalies.append({"type": "OTEL_SPANS_DROPPED", "severity": "critical",
                               "metric": "otel_exporter_dropped", "value": otel_dropped,
                               "threshold": 0})
            anom_types.add("OTEL_SPANS_DROPPED")

        # Cascade detection
        cascade_chain: list[str] = []
        for trigger, downstream, chain_name in _CASCADE_PATTERNS:
            if trigger in anom_types and len(anom_types & downstream) >= 2:
                cascade_chain.append(chain_name)

        # Root-cause candidate ranking
        candidates: list[dict] = []
        error_logs  = logs.get("error_logs", [])
        error_count = logs.get("error_count", 0)

        # Extract dominant error components
        component_counts: dict[str, int] = {}
        error_keywords: dict[str, int]   = {}
        for e in error_logs:
            comp = e.get("component", "unknown")
            component_counts[comp] = component_counts.get(comp, 0) + 1
            msg = e.get("msg", "").lower()
            for kw in ("timeout", "connection", "pool", "heap", "oom", "null",
                       "deadlock", "refused", "overflow", "error", "exception"):
                if kw in msg:
                    error_keywords[kw] = error_keywords.get(kw, 0) + 1

        top_components = sorted(component_counts.items(), key=lambda x: -x[1])[:3]
        top_keywords   = sorted(error_keywords.items(), key=lambda x: -x[1])[:5]

        # Rank candidates by evidence weight
        if "POOL_EXHAUSTION" in anom_types:
            evidence = [f"pool_exhaustion={metrics.get('pool_exhaustion', '?')} events"]
            if "DB_ERRORS" in anom_types:
                evidence.append(f"db_errors={metrics.get('db_errors', '?')}")
            if any(kw in error_keywords for kw in ("pool", "connection", "timeout")):
                evidence.append("Loki: pool/connection/timeout keywords in error logs")
            candidates.append({
                "rank": 1, "hypothesis": "DB connection pool exhaustion",
                "confidence": "HIGH" if len(evidence) >= 2 else "MEDIUM",
                "evidence": evidence,
                "cascade": "pool_exhaustion → db_errors → high_latency → error_rate",
            })

        if "JVM_HIGH_CPU" in anom_types or "JVM_HIGH_HEAP" in anom_types:
            evidence = []
            if "JVM_HIGH_CPU" in anom_types:
                evidence.append(f"jvm_cpu={metrics.get('jvm_cpu', 0)*100:.0f}%")
            if "JVM_HIGH_HEAP" in anom_types:
                heap_mb = metrics.get("jvm_heap_used", 0) / 1e6
                evidence.append(f"jvm_heap={heap_mb:.0f}MB")
            if "EXCESSIVE_GC" in anom_types:
                evidence.append(f"gc_count={metrics.get('jvm_gc_count', '?')}")
            if any(kw in error_keywords for kw in ("heap", "oom", "gc")):
                evidence.append("Loki: heap/OOM keywords in logs")
            candidates.append({
                "rank": len(candidates) + 1,
                "hypothesis": "JVM resource saturation (CPU/heap pressure)",
                "confidence": "HIGH" if "EXCESSIVE_GC" in anom_types else "MEDIUM",
                "evidence": evidence,
                "cascade": "jvm_cpu_spike → thread_contention → latency → errors",
            })

        if "DB_ERRORS" in anom_types and "POOL_EXHAUSTION" not in anom_types:
            evidence = [f"db_errors={metrics.get('db_errors', '?')} events"]
            if any(kw in error_keywords for kw in ("timeout", "refused", "connection")):
                evidence.append("Loki: DB timeout/refused errors")
            candidates.append({
                "rank": len(candidates) + 1,
                "hypothesis": "Upstream database failure / slow queries",
                "confidence": "MEDIUM",
                "evidence": evidence,
                "cascade": "db_failure → query_errors → service_error_rate",
            })

        if "HIGH_ERROR_RATE" in anom_types and not candidates:
            evidence = [f"error_rate={metrics.get('error_rate', 0):.4f}/s"]
            if top_components:
                evidence.append(f"Top error components: {', '.join(c for c,_ in top_components)}")
            if "OTEL_SPANS_DROPPED" in anom_types:
                evidence.append("OTel spans being dropped — trace coverage degraded")
            candidates.append({
                "rank": 1,
                "hypothesis": "Application error cascade (unknown root cause)",
                "confidence": "LOW",
                "evidence": evidence,
                "cascade": "unknown_trigger → error_rate_spike",
            })

        # OTel pipeline degradation
        if "OTEL_QUEUE_PRESSURE" in anom_types or "OTEL_SPANS_DROPPED" in anom_types:
            evidence = []
            if otel_queue:
                evidence.append(f"exporter_queue={otel_queue:.0f} items")
            if otel_dropped:
                evidence.append(f"dropped_spans={otel_dropped:.0f}")
            candidates.append({
                "rank": len(candidates) + 1,
                "hypothesis": "OTel collector exporter backpressure",
                "confidence": "HIGH" if otel_dropped > 0 else "MEDIUM",
                "evidence": evidence,
                "cascade": "collector_queue_full → spans_dropped → blind_spots_in_traces",
            })

        # Sort by confidence then rank
        conf_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        candidates.sort(key=lambda c: (conf_order.get(c["confidence"], 3), c["rank"]))

        # Trace IDs from logs for cross-signal linkage
        trace_ids = list({
            e["trace_id"] for e in (logs.get("trace_logs", []) + error_logs)
            if e.get("trace_id")
        })[:5]

        return {
            "anomalies":           anomalies,
            "anom_types":          list(anom_types),
            "root_cause_candidates": candidates,
            "cascade_chain":       cascade_chain,
            "error_components":    top_components,
            "error_keywords":      top_keywords,
            "trace_ids":           trace_ids,
            "otel_spans_accepted": metrics.get("otel_spans_accepted"),
            "otel_spans_refused":  metrics.get("otel_spans_refused"),
        }

    # ── 3. LLM context builder ─────────────────────────────────────────────────

    def build_llm_context(self, service: str, environment: str, minutes: int,
                          metrics: dict, logs: dict, otel: dict,
                          correlation: dict, issue_triggered: str | None) -> str:
        """Compress all signals into ~2000-token structured context for LLM."""
        lines: list[str] = [
            f"Service: {service} | Env: {environment} | Window: {minutes}m",
        ]

        if issue_triggered:
            lines.append(f"ISSUE MODE TRIGGERED: {issue_triggered}")

        # Prometheus SLI block
        lines += ["", "=== PROMETHEUS SLI METRICS ==="]
        fmt = {
            "error_rate":      lambda v: f"{v:.4f}/s {'⚠ CRITICAL' if v>=0.5 else '⚠ elevated' if v>0.05 else '✓'}",
            "request_rate":    lambda v: f"{v:.2f}/s",
            "latency_p99_ms":  lambda v: f"{v:.0f}ms {'⚠ CRITICAL' if v>=2000 else '⚠' if v>=500 else '✓'}",
            "latency_p50_ms":  lambda v: f"{v:.0f}ms",
            "db_errors":       lambda v: f"{v:.0f} events {'⚠' if v>0 else '✓'}",
            "pool_exhaustion": lambda v: f"{v:.0f} events {'⚠' if v>0 else '✓'}",
            "jvm_heap_used":   lambda v: f"{v/1e6:.0f}MB {'⚠' if v>60e6 else '✓'}",
            "jvm_cpu":         lambda v: f"{v*100:.0f}% {'⚠' if v>0.6 else '✓'}",
            "jvm_gc_count":    lambda v: f"{v:.0f} GC events",
            "jvm_threads":     lambda v: f"{v:.0f} threads",
        }
        sli_keys = ["error_rate", "request_rate", "latency_p99_ms", "latency_p50_ms",
                    "db_errors", "pool_exhaustion", "jvm_heap_used", "jvm_cpu",
                    "jvm_gc_count", "jvm_threads"]
        for k in sli_keys:
            v = metrics.get(k)
            if v is not None:
                fn = fmt.get(k, lambda x: str(round(x, 4)))
                lines.append(f"  {k:<22} {fn(v)}")

        # Anomalies
        anomalies = correlation["anomalies"]
        if anomalies:
            lines += ["", "ACTIVE ANOMALIES (cite ALL in analysis):"]
            for a in anomalies:
                lines.append(f"  ❌ [{a['severity'].upper()}] {a['type']} — {a['metric']}={a['value']:.4g} (threshold={a['threshold']:.4g})")
        else:
            lines.append("  NO ANOMALIES — service healthy")

        # OTel signals
        lines += ["", "=== OPENTELEMETRY SIGNALS ==="]
        otel_keys = [
            ("otel_spans_accepted",   "spans_accepted_Δ"),
            ("otel_spans_refused",    "spans_refused_Δ"),
            ("otel_logs_accepted",    "log_records_Δ"),
            ("otel_exporter_queue",   "exporter_queue_depth"),
            ("otel_exporter_dropped", "spans_dropped_Δ"),
        ]
        has_otel = False
        for prom_key, label in otel_keys:
            v = metrics.get(prom_key)
            if v is not None:
                lines.append(f"  {label:<28} {v:.0f}")
                has_otel = True
        if otel.get("span_error_ratio") is not None:
            lines.append(f"  {'span_error_ratio':<28} {otel['span_error_ratio']*100:.1f}%")
            has_otel = True
        if not has_otel:
            lines.append("  (OTel collector metrics unavailable — check port-forward)")

        # Cascade
        cascade = correlation.get("cascade_chain", [])
        if cascade:
            lines += ["", "=== DETECTED CASCADE ==="]
            for c in cascade:
                lines.append(f"  → {c}")

        # Root-cause candidates
        candidates = correlation.get("root_cause_candidates", [])
        if candidates:
            lines += ["", "=== ROOT CAUSE CANDIDATES (ranked) ==="]
            for c in candidates:
                conf = c["confidence"]
                lines.append(f"  [{conf}] #{c['rank']} {c['hypothesis']}")
                lines.append(f"    cascade: {c['cascade']}")
                for ev in c["evidence"]:
                    lines.append(f"    evidence: {ev}")

        # Log samples
        error_logs = logs.get("error_logs", [])
        lines += ["", f"=== LOKI LOGS ({logs.get('error_count',0)} total ERROR/WARN) — top 15 ==="]
        for e in error_logs[:15]:
            ts = e["ts"][11:19] if len(e.get("ts", "")) > 19 else e.get("ts", "?")
            extra_parts = [f"{k}={v}" for k, v in (e.get("extra") or {}).items() if v]
            line = f"  [{ts}] {e['level']:5} [{e['component']}] {e['msg']}"
            if e.get("trace_id"):
                line += f" trace={e['trace_id'][:16]}"
            if extra_parts:
                line += f" | {' '.join(extra_parts[:2])}"
            lines.append(line)
        if not error_logs:
            lines.append("  (no ERROR/WARN logs in window)")

        # Trace linkage
        trace_ids = correlation.get("trace_ids", [])
        if trace_ids:
            lines += ["", "=== TRACE IDs (cross-signal linkage) ==="]
            for tid in trace_ids:
                lines.append(f"  {tid}")

        # OTel collector logs
        otel_logs = logs.get("otel_logs", [])
        if otel_logs:
            lines += ["", "=== OTEL COLLECTOR LOGS ==="]
            for e in otel_logs[:5]:
                ts = e["ts"][11:19] if len(e.get("ts", "")) > 19 else e.get("ts", "?")
                lines.append(f"  [{ts}] {e['level']:5} {e['msg'][:120]}")

        lines += [
            "",
            "="*60,
            "TASK: Begin immediately with ## 🔍 Root Cause Analysis",
            "Then ## 🛠️ Remediation Actions. Reference cascade chain and ranked candidates.",
            "Quote exact metric values and exact log lines from the data above.",
        ]

        return "\n".join(lines)

    # ── 4. Main streaming entry point ─────────────────────────────────────────

    async def stream(
        self,
        service: str,
        environment: str,
        minutes: int,
        issue_triggered: str | None,
        minikube_ip: str,
        reports_dir: Path,
        build_header_fn: Callable,
        build_risk_fn: Callable,
        build_validation_fn: Callable,
        build_replicate_fn: Callable,
        service_ports: dict,
        live_prompt: str,
        ollama_url: str,
        ollama_model: str,
    ) -> AsyncGenerator[str, None]:
        import httpx

        def _sse(payload: dict) -> str:
            return f"data: {json.dumps(payload)}\n\n"

        # ── Step 0: optional issue trigger ────────────────────────────────────
        if issue_triggered:
            yield _sse({"type": "status",
                         "text": f"Triggering {issue_triggered} on {service}…"})
            try:
                import urllib.request as _ur
                port = service_ports.get(service, 30500)
                url  = f"http://{minikube_ip}:{port}/simulate/{issue_triggered}"
                with _ur.urlopen(url, timeout=8) as r:
                    json.load(r)
                yield _sse({"type": "status",
                             "text": "Issue triggered — waiting 20s for telemetry…"})
                await asyncio.sleep(20)
            except Exception as exc:
                yield _sse({"type": "status",
                             "text": f"Trigger failed ({exc}), analyzing current state…"})

        # ── Step 1/5: parallel signal collection (bounded to 20s total) ─────────
        yield _sse({"type": "status",
                     "text": "Step 1/5 — Collecting signals: Prometheus + Loki…"})

        _empty_metrics: dict = {}
        _empty_logs = {"error_logs": [], "trace_logs": [], "otel_logs": [], "error_count": 0}
        _empty_otel: dict = {}

        try:
            metrics, logs, otel = await asyncio.wait_for(
                asyncio.gather(
                    asyncio.to_thread(self.collect_prometheus, service, minutes),
                    asyncio.to_thread(self.collect_loki, service, minutes),
                    asyncio.to_thread(self.collect_otel_signals, service, minutes),
                ),
                timeout=20,
            )
        except asyncio.TimeoutError:
            yield _sse({"type": "status", "text": "Collection timed out — using partial data…"})
            metrics, logs, otel = _empty_metrics, _empty_logs, _empty_otel

        yield _sse({"type": "telemetry",
                     "metrics": {k: v for k, v in metrics.items()
                                  if not k.startswith("otel_")},
                     "anomalies": [],
                     "log_count": logs.get("error_count", 0)})

        # ── Step 2/5: Python correlation (pure Python, no thread needed) ──────
        yield _sse({"type": "status",
                     "text": "Step 2/5 — Correlating signals…"})

        correlation = self.correlate(metrics, logs, otel, minutes)

        anomalies = correlation["anomalies"]
        candidates = correlation["root_cause_candidates"]
        cascade = correlation["cascade_chain"]

        # Update telemetry with real anomalies
        yield _sse({"type": "telemetry",
                     "metrics": {k: v for k, v in metrics.items()
                                  if not k.startswith("otel_")},
                     "anomalies": anomalies,
                     "log_count": logs.get("error_count", 0),
                     "cascade":   cascade,
                     "candidates": len(candidates)})

        # ── Step 3a: emit pre-computed header ─────────────────────────────────
        header_md = build_header_fn(service, environment, minutes, metrics, anomalies)
        yield _sse({"type": "token", "text": header_md})

        # ── Step 3/5: LLM narrative ────────────────────────────────────────────
        yield _sse({"type": "status",
                     "text": "Step 3/5 — Streaming AI narrative…"})

        user_msg = self.build_llm_context(
            service, environment, minutes, metrics, logs, otel,
            correlation, issue_triggered,
        )

        llm_body = {
            "model":   ollama_model,
            "messages": [
                {"role": "system", "content": live_prompt},
                {"role": "user",   "content": user_msg},
            ],
            "stream":  True,
            "options": {"num_ctx": 8192, "num_predict": 3500, "temperature": 0.05},
        }

        full_text = [header_md]
        text_buf  = ""

        def _fix_headers(txt: str) -> str:
            # Ensure ### headings don't get promoted to #
            return re.sub(r"^(#{1,2})([^#])", lambda m: "##" + m.group(2)
                          if m.group(1) == "#" else m.group(0), txt, flags=re.MULTILINE)

        try:
            async with httpx.AsyncClient(timeout=240) as http:
                async with http.stream("POST", f"{ollama_url}/api/chat",
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
                            text_buf  += token
                            full_text.append(token)
                            if "\n" in text_buf:
                                parts    = text_buf.split("\n")
                                text_buf = parts.pop()
                                fixed    = _fix_headers("\n".join(parts))
                                yield _sse({"type": "token",
                                             "text": fixed + "\n"})

                        if chunk.get("done"):
                            if text_buf:
                                fixed = _fix_headers(text_buf)
                                full_text.append(fixed)
                                yield _sse({"type": "token", "text": fixed})
                            break

        except Exception as exc:
            is_timeout = "timeout" in str(exc).lower() or "Timeout" in type(exc).__name__
            msg = ("LLM timed out — appending structured sections"
                   if is_timeout else f"LLM error: {exc}")
            yield _sse({"type": "status", "text": msg})

        # ── Step 4/5: Python-generated structured sections ────────────────────
        yield _sse({"type": "status",
                     "text": "Step 4/5 — Generating risk assessment & validation checklist…"})

        risk_md       = build_risk_fn(service, anomalies, metrics, issue_triggered)
        validation_md = build_validation_fn(service, anomalies, metrics)
        replicate_md  = build_replicate_fn(service, anomalies, metrics,
                                           issue_triggered, minikube_ip)

        # Append cascade + OTel summary before risk section
        otel_summary = self._build_otel_summary(metrics, correlation)
        cascade_md   = self._build_cascade_md(correlation, candidates)

        yield _sse({"type": "token", "text": otel_summary})
        yield _sse({"type": "token", "text": cascade_md})
        yield _sse({"type": "token", "text": risk_md})
        yield _sse({"type": "token", "text": validation_md})
        yield _sse({"type": "status", "text": "Building replication guide…"})
        yield _sse({"type": "token", "text": replicate_md})

        # ── Step 5/5: save report ─────────────────────────────────────────────
        yield _sse({"type": "status", "text": "Step 5/5 — Saving report…"})

        report_body = (
            _fix_headers("".join(full_text))
            + otel_summary + cascade_md
            + risk_md + validation_md + replicate_md
        )
        reports_dir.mkdir(parents=True, exist_ok=True)
        ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
        slug = (issue_triggered or ("anomaly" if anomalies else "baseline")).replace(" ", "_")
        fname = reports_dir / f"{service}_{slug}_{ts}.md"
        fname.write_text(report_body)

        yield _sse({"type": "saved", "filename": fname.name})
        yield _sse({"type": "done"})

    # ── Supplemental section builders ─────────────────────────────────────────

    def _build_otel_summary(self, metrics: dict, correlation: dict) -> str:
        lines = ["", "## 📡 OpenTelemetry Pipeline Status", ""]
        otel_keys = [
            ("otel_spans_accepted",   "Spans Accepted (Δ window)"),
            ("otel_spans_refused",    "Spans Refused (Δ window)"),
            ("otel_logs_accepted",    "Log Records Accepted (Δ)"),
            ("otel_exporter_queue",   "Exporter Queue Depth"),
            ("otel_exporter_dropped", "Spans Dropped (Δ window)"),
        ]
        has_data = False
        lines += ["| Signal | Value | Status |", "|--------|-------|--------|"]
        for key, label in otel_keys:
            val = metrics.get(key)
            if val is None:
                continue
            has_data = True
            if key == "otel_exporter_dropped" and val > 0:
                status = "🔴 DROPS DETECTED"
            elif key == "otel_exporter_queue" and val > 500:
                status = "🟡 QUEUE PRESSURE"
            elif key == "otel_spans_refused" and val > 0:
                status = "🟡 REFUSED"
            else:
                status = "🟢 normal"
            lines.append(f"| {label} | `{val:.0f}` | {status} |")

        if not has_data:
            lines.append("| OTel metrics | N/A | ⬜ unavailable — check port-forward |")

        anom_types = set(correlation.get("anom_types", []))
        if "OTEL_SPANS_DROPPED" in anom_types:
            lines += [
                "",
                "> ⚠️ **Span drops detected** — distributed traces will have gaps.",
                "> Check OTel collector exporter configuration and downstream backend capacity.",
            ]
        elif "OTEL_QUEUE_PRESSURE" in anom_types:
            lines += [
                "",
                "> 🟡 **Exporter queue growing** — collector under backpressure.",
                "> Increase `sending_queue.queue_size` or reduce export batch interval.",
            ]
        lines.append("")
        return "\n".join(lines)

    def _build_cascade_md(self, correlation: dict, candidates: list) -> str:
        lines = ["", "## 🔗 Cascade Analysis", ""]

        cascade = correlation.get("cascade_chain", [])
        if cascade:
            lines.append("**Detected failure cascade(s):**")
            for c in cascade:
                lines.append(f"- `{c}`")
            lines.append("")

        if candidates:
            lines += ["**Root-cause candidates (ranked by evidence):**", ""]
            lines += ["| Rank | Hypothesis | Confidence | Key Evidence |",
                      "|------|-----------|------------|--------------|"]
            for c in candidates[:4]:
                evidence_str = "; ".join(c["evidence"][:2]) or "—"
                lines.append(
                    f"| #{c['rank']} | {c['hypothesis']} | **{c['confidence']}** | {evidence_str} |"
                )
            lines.append("")

        trace_ids = correlation.get("trace_ids", [])
        if trace_ids:
            lines += ["**Correlated trace IDs** (use in Loki/Jaeger for end-to-end view):"]
            for tid in trace_ids:
                lines.append(f"- `{tid}`")
            lines.append("")

        if not cascade and not candidates:
            lines.append("No cascade detected — service appears healthy across all signals.")
            lines.append("")

        return "\n".join(lines)
