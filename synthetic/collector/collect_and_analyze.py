#!/usr/bin/env python3
"""
Observability-grade incident collector.

Telemetry sources:
  Prometheus  → error_rate, latency P99, DB errors, memory pressure
  Loki        → structured JSON log entries (ERROR + WARN lines)
  kubectl     → pod events, restart counts, OOMKilled status

Feeds combined telemetry to /api/v1/incident/analyze → saves markdown report.

Usage:
  python3 collect_and_analyze.py                          # all services, current state
  python3 collect_and_analyze.py --issue db_timeout       # trigger issue first
  python3 collect_and_analyze.py --service auth-service
  python3 collect_and_analyze.py --lookback 10m           # Loki/Prometheus window
"""
import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# ── Config ─────────────────────────────────────────────────────────────────────
SRE_API      = "http://localhost:8080/api/v1/incident/analyze"
NAMESPACE    = "synthetic"
SERVICES     = {
    "auth-service":  {"app": "auth-service",  "sim_port": 30500, "language": "Python"},
    "order-service": {"app": "order-service", "sim_port": 30800, "language": "Java"},
}

# Port-forwarded or NodePort addresses filled in at runtime
_prom_url = ""
_loki_url = ""


# ── Helpers ────────────────────────────────────────────────────────────────────

def run(cmd, check=False):
    r = subprocess.run(cmd, shell=True, text=True, capture_output=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def get_minikube_ip():
    ip = run("minikube ip")
    return ip or "127.0.0.1"


def http_get(url, timeout=10):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"error": str(e)}


# ── Prometheus queries ─────────────────────────────────────────────────────────

def prom_query(expr, step="15s"):
    """Instant query against Prometheus."""
    url = f"{_prom_url}/api/v1/query?" + urllib.parse.urlencode({"query": expr})
    data = http_get(url)
    if data.get("status") != "success":
        return []
    return data.get("data", {}).get("result", [])


def prom_range(expr, minutes=10, step="30s"):
    """Range query — returns list of (timestamp, value) tuples."""
    now   = int(time.time())
    start = now - minutes * 60
    url   = f"{_prom_url}/api/v1/query_range?" + urllib.parse.urlencode({
        "query": expr, "start": start, "end": now, "step": step,
    })
    data = http_get(url)
    if data.get("status") != "success":
        return []
    results = data.get("data", {}).get("result", [])
    return results


def collect_prometheus_telemetry(service, minutes=10):
    """Pull key SLI metrics from Prometheus for a given service label."""
    lines = [f"=== Prometheus Metrics [{service}] (last {minutes}m) ==="]

    # Python app (auth-service) metrics
    python_queries = {
        "error_rate":        f'rate(http_errors_total{{service="{service}"}}[{minutes}m])',
        "request_rate":      f'rate(http_requests_total{{service="{service}"}}[{minutes}m])',
        "latency_p99_ms":    f'histogram_quantile(0.99, rate(http_request_duration_ms_bucket{{service="{service}"}}[{minutes}m]))',
        "latency_p50_ms":    f'histogram_quantile(0.50, rate(http_request_duration_ms_bucket{{service="{service}"}}[{minutes}m]))',
        "db_errors":         f'increase(db_errors_total{{service="{service}"}}[{minutes}m])',
        "auth_failures":     f'increase(auth_failures_total{{service="{service}"}}[{minutes}m])',
        "pool_exhaustion":   f'increase(db_pool_exhaustion_total{{service="{service}"}}[{minutes}m])',
        "memory_heap_bytes": f'memory_heap_bytes{{service="{service}"}}',
        "memory_leak_objs":  f'memory_leak_objects_total{{service="{service}"}}',
    }
    # JVM metrics from OTel Java agent (order-service) — real metric names
    jvm_queries = {
        "jvm_heap_used_bytes":  f'sum(jvm_memory_used_bytes{{service="{service}",jvm_memory_type="heap"}})',
        "jvm_heap_limit_bytes": f'sum(jvm_memory_limit_bytes{{service="{service}",jvm_memory_type="heap"}})',
        "jvm_cpu_utilization":  f'jvm_cpu_recent_utilization_ratio{{service="{service}"}}',
        "jvm_gc_count":         f'increase(jvm_gc_duration_seconds_count{{service="{service}"}}[{minutes}m])',
        "jvm_thread_count":     f'jvm_thread_count{{service="{service}"}}',
    }
    queries = {**python_queries, **jvm_queries}

    anomalies = []
    for name, expr in queries.items():
        results = prom_query(expr)
        if not results:
            continue
        for r in results:
            val = float(r["value"][1]) if r.get("value") else None
            if val is None or val != val:   # NaN check
                continue
            labels_str = " ".join(f'{k}="{v}"' for k, v in r.get("metric", {}).items()
                                   if k not in ("__name__",))
            lines.append(f"  {name}{{{labels_str}}}: {val:.4f}")

            # Flag anomalies
            if name == "error_rate"           and val > 0.05:
                anomalies.append(f"HIGH ERROR RATE: {val:.4f} errors/s")
            if name == "latency_p99_ms"       and val > 1000:
                anomalies.append(f"HIGH P99 LATENCY: {val:.0f}ms")
            if name == "db_errors"            and val > 2:
                anomalies.append(f"DB ERRORS: {val:.0f} in last {minutes}m")
            if name == "pool_exhaustion"      and val > 0:
                anomalies.append(f"CONNECTION POOL EXHAUSTION: {val:.0f} events")
            if name == "memory_heap_bytes"    and val > 100_000_000:
                anomalies.append(f"HIGH HEAP: {val/1_048_576:.1f}MB")
            if name == "memory_leak_objs"     and val > 10_000:
                anomalies.append(f"MEMORY LEAK: {val:.0f} leaked objects")
            if name == "jvm_heap_used_bytes"  and val > 80_000_000:
                anomalies.append(f"JVM HIGH HEAP: {val/1_048_576:.1f}MB")
            if name == "jvm_cpu_utilization"  and val > 0.80:
                anomalies.append(f"JVM HIGH CPU: {val*100:.0f}%")
            if name == "jvm_gc_count"         and val > 20:
                anomalies.append(f"EXCESSIVE GC: {val:.0f} collections in last {minutes}m")

    if anomalies:
        lines.insert(1, "ANOMALIES DETECTED:")
        for a in anomalies:
            lines.insert(2, f"  ⚠ {a}")

    return "\n".join(lines), anomalies


# ── Loki queries ───────────────────────────────────────────────────────────────

def collect_loki_logs(service, minutes=10, limit=100):
    """Query Loki for recent ERROR/WARN log entries for a service."""
    now_ns  = int(time.time() * 1e9)
    start_ns = int((time.time() - minutes * 60) * 1e9)

    # LogQL: filter by stream labels promoted by Promtail (service, level, namespace).
    # Using label selectors is faster and avoids re-parsing the JSON body.
    logql = f'{{service="{service}",namespace="{NAMESPACE}",level=~"ERROR|WARN"}}'
    url   = f"{_loki_url}/loki/api/v1/query_range?" + urllib.parse.urlencode({
        "query":     logql,
        "start":     start_ns,
        "end":       now_ns,
        "limit":     limit,
        "direction": "backward",
    })

    data = http_get(url, timeout=15)
    lines = [f"=== Loki Logs [{service}] (last {minutes}m, ERROR+WARN, limit={limit}) ==="]

    if "error" in data:
        lines.append(f"[Loki unavailable: {data['error']}]")
        return "\n".join(lines)

    results = data.get("data", {}).get("result", [])
    if not results:
        lines.append("[No error/warn logs found in Loki for this window]")
        return "\n".join(lines)

    count = 0
    for stream in results:
        for ts_ns, log_line in reversed(stream.get("values", [])):
            try:
                record = json.loads(log_line)
                level  = record.get("level", "?")
                comp   = record.get("component", "?")
                msg    = record.get("msg", log_line)
                trace  = record.get("trace_id", "")
                extra  = {k: v for k, v in record.items()
                          if k not in ("ts","level","service","env","version",
                                       "component","msg","trace_id","span_id")}
                extra_str = " ".join(f"{k}={v}" for k, v in extra.items())
                dt = datetime.fromtimestamp(int(ts_ns) / 1e9, tz=timezone.utc)
                lines.append(
                    f"  [{dt.strftime('%H:%M:%S')}] {level:5s} [{comp}] {msg}"
                    + (f" | trace={trace}" if trace else "")
                    + (f" | {extra_str}" if extra_str else "")
                )
                count += 1
            except json.JSONDecodeError:
                lines.append(f"  {log_line[:200]}")
                count += 1

    lines.insert(1, f"Retrieved {count} log entries")
    return "\n".join(lines)


# ── kubectl fallback ───────────────────────────────────────────────────────────

def collect_kubectl_fallback(pod_name, lines=80):
    logs = run(f"kubectl logs -n {NAMESPACE} {pod_name} --tail={lines} 2>&1")
    describe = run(f"kubectl describe pod -n {NAMESPACE} {pod_name} 2>&1")
    restart_info = "\n".join(
        l.strip() for l in describe.splitlines()
        if any(k in l for k in ("Restart Count", "OOMKilled", "Reason:", "Exit Code", "Last State"))
    )
    return logs, restart_info


def get_pod_events(pod_name):
    out = run(f"kubectl get events -n {NAMESPACE} --field-selector "
              f"involvedObject.name={pod_name} --sort-by=.lastTimestamp 2>&1")
    return out


# ── Trigger issue ──────────────────────────────────────────────────────────────

def trigger_issue(service, issue, minikube_ip):
    port = SERVICES[service]["sim_port"]
    url  = f"http://{minikube_ip}:{port}/simulate/{issue}"
    result = run(f"curl -s --max-time 5 '{url}'")
    print(f"  ✓ Triggered '{issue}' on {service}: {result}")


# ── Analysis via SRE AI ────────────────────────────────────────────────────────

def stream_analysis(payload):
    data = json.dumps(payload).encode()
    req  = urllib.request.Request(
        SRE_API, data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    tokens = []
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            buf = ""
            while True:
                chunk = resp.read(64).decode(errors="replace")
                if not chunk:
                    break
                buf += chunk
                while "\n\n" in buf:
                    line, buf = buf.split("\n\n", 1)
                    if line.startswith("data: "):
                        try:
                            ev = json.loads(line[6:])
                            if ev.get("type") == "token":
                                tokens.append(ev["text"])
                                print(ev["text"], end="", flush=True)
                            elif ev.get("type") == "done":
                                print()
                                return "".join(tokens)
                            elif ev.get("type") == "error":
                                print(f"\n  [API error] {ev.get('message')}")
                                return None
                        except json.JSONDecodeError:
                            pass
    except Exception as e:
        print(f"\n  [ERROR] {e}")
        print("  Ensure backend is running: python3 -m uvicorn backend.main:app --port 8080")
        return None
    return "".join(tokens)


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    global _prom_url, _loki_url

    parser = argparse.ArgumentParser(description="Collect observability telemetry and analyze incidents")
    parser.add_argument("--service",  default=None, help="Target specific service")
    parser.add_argument("--issue",    default=None, help="Trigger issue before collecting")
    parser.add_argument("--lookback", default="10m", help="Lookback window (e.g. 5m, 15m)")
    parser.add_argument("--output",   default="./reports", help="Report output directory")
    parser.add_argument("--wait",     type=int, default=15, help="Wait seconds after issue trigger")
    parser.add_argument("--prom",     default=None, help="Override Prometheus URL")
    parser.add_argument("--loki",     default=None, help="Override Loki URL")
    args = parser.parse_args()

    minutes = int(args.lookback.rstrip("m").rstrip("s"))

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Resolve Minikube NodePort endpoints
    ip = get_minikube_ip()
    print(f"Minikube IP: {ip}")

    _prom_url = args.prom or f"http://{ip}:30090"
    _loki_url = args.loki or f"http://{ip}:30310"

    # Probe Prometheus
    prom_ok = http_get(f"{_prom_url}/api/v1/query?query=up").get("status") == "success"
    # Loki returns 200 text on /ready, not JSON
    try:
        with urllib.request.urlopen(f"{_loki_url}/ready", timeout=5) as r:
            loki_ok = r.status == 200
    except Exception:
        loki_ok = False

    print(f"Prometheus [{_prom_url}]: {'✓ reachable' if prom_ok else '✗ not reachable (will use kubectl fallback)'}")
    print(f"Loki       [{_loki_url}]: {'✓ reachable' if loki_ok else '✗ not reachable (will use kubectl fallback)'}")

    targets = [args.service] if args.service and args.service in SERVICES else list(SERVICES.keys())

    for service in targets:
        info = SERVICES[service]
        print(f"\n{'='*70}")
        print(f"  {service} ({info['language']})")
        print(f"{'='*70}")

        if args.issue:
            print(f"\n  [1/5] Triggering: {args.issue}")
            trigger_issue(service, args.issue, ip)
            print(f"  Waiting {args.wait}s for telemetry to accumulate...")
            time.sleep(args.wait)
        else:
            print(f"\n  [1/5] No issue triggered — collecting current state")

        # Pod info
        print(f"\n  [2/5] Locating pod...")
        pod_name = run(f"kubectl get pods -n {NAMESPACE} -l app={info['app']} "
                       f"-o jsonpath='{{.items[0].metadata.name}}'")
        if not pod_name:
            print(f"  ✗ No pod found — skipping")
            continue
        print(f"  Pod: {pod_name}")

        events = get_pod_events(pod_name)

        # Collect metrics
        print(f"\n  [3/5] Collecting Prometheus metrics...")
        if prom_ok:
            prom_section, anomalies = collect_prometheus_telemetry(service, minutes)
            print(f"  Anomalies detected: {anomalies or ['none']}")
        else:
            prom_section = f"[Prometheus unavailable — checking /metrics directly]\n"
            direct = run(f"curl -s --max-time 5 http://{ip}:{info['sim_port']}/metrics")
            prom_section += direct[:2000] if direct else "[/metrics also unreachable]"
            anomalies = []

        # Collect logs
        print(f"\n  [4/5] Collecting logs (Loki + kubectl fallback)...")
        if loki_ok:
            loki_section = collect_loki_logs(service, minutes)
        else:
            raw_logs, restart_info = collect_kubectl_fallback(pod_name, lines=100)
            loki_section = (
                f"=== kubectl logs [{service}] ===\n"
                f"{restart_info}\n{raw_logs}"
            )

        # Build incident payload
        raw_incident = "\n\n".join([
            f"Service: {service} ({info['language']})",
            f"Environment: production | Namespace: {NAMESPACE}",
            f"Pod: {pod_name}",
            f"Lookback: last {minutes} minutes",
            prom_section,
            loki_section,
            f"=== Kubernetes Events ===\n{events}" if events else "",
        ])

        payload = {
            "raw_incident": raw_incident[:8000],
            "service":      service,
            "environment":  "production",
            "session_id":   f"collector-{service}-{int(time.time())}",
        }

        print(f"\n  [5/5] Analyzing with SRE AI...")
        print(f"\n{'─'*70}")
        report = stream_analysis(payload)
        print(f"{'─'*70}")

        if report:
            ts     = datetime.now().strftime("%Y%m%d_%H%M%S")
            issue  = (args.issue or (anomalies[0].split(":")[0].lower().replace(" ","_") if anomalies else "baseline"))
            fname  = output_dir / f"{service}_{issue}_{ts}.md"
            fname.write_text(report)
            print(f"\n  Report → {fname}")

    print(f"\n{'='*70}")
    print(f"  Done. Reports in: {output_dir.resolve()}")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()
