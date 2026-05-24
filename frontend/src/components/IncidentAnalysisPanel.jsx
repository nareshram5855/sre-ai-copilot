import { useState, useRef, useEffect, useCallback } from "react";
import {
  AlertTriangle, Activity, RefreshCw, Zap, Terminal,
  CheckCircle, XCircle, Clock, Copy, CheckCheck, RotateCcw,
  Square, ExternalLink, Database, Radio, Server, GitBranch
} from "lucide-react";
import ReactMarkdown from "react-markdown";

// ── Sparkline SVG ─────────────────────────────────────────────────────────────

function Sparkline({ points, color = "#22c55e", height = 28, width = 80 }) {
  if (!points || points.length < 2) return <div style={{ width, height }} />;
  const vals = points.map(p => p[1]);
  const min = Math.min(...vals);
  const max = Math.max(...vals);
  const range = max - min || 0.001;
  const pad = 2;
  const xs  = points.map((_, i) => pad + (i / (points.length - 1)) * (width - pad * 2));
  const ys  = vals.map(v => pad + (1 - (v - min) / range) * (height - pad * 2));
  const d   = xs.map((x, i) => `${i === 0 ? "M" : "L"}${x.toFixed(1)},${ys[i].toFixed(1)}`).join(" ");
  const area = `${d} L${xs[xs.length-1].toFixed(1)},${height} L${xs[0].toFixed(1)},${height} Z`;
  return (
    <svg width={width} height={height} className="overflow-visible">
      <defs>
        <linearGradient id={`sg-${color.replace("#","")}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.3" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={area} fill={`url(#sg-${color.replace("#","")})`} />
      <path d={d} fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

// ── Metric config ──────────────────────────────────────────────────────────────

const METRIC_META = {
  error_rate:      { label: "Error Rate",   unit: "/s",    fmt: v => `${v.toFixed(4)}/s`,       warn: 0.05,  crit: 0.5,   spark_color: "#f87171" },
  request_rate:    { label: "Request Rate", unit: "/s",    fmt: v => `${v.toFixed(2)}/s`,        warn: null,  crit: null,  spark_color: "#60a5fa" },
  latency_p99_ms:  { label: "P99 Latency",  unit: "ms",   fmt: v => `${v.toFixed(0)}ms`,        warn: 500,   crit: 2000,  spark_color: "#fb923c" },
  latency_p50_ms:  { label: "P50 Latency",  unit: "ms",   fmt: v => `${v.toFixed(0)}ms`,        warn: 200,   crit: 1000,  spark_color: "#a78bfa" },
  db_errors:       { label: "DB Errors",    unit: "",      fmt: v => v.toFixed(0),               warn: 1,     crit: 10,    spark_color: "#f87171" },
  pool_exhaustion: { label: "Pool Exhaust", unit: "",      fmt: v => v.toFixed(0),               warn: 1,     crit: 5,     spark_color: "#f87171" },
  memory_bytes:    { label: "Heap",         unit: "MB",    fmt: v => `${(v/1e6).toFixed(1)}MB`,  warn: 80e6,  crit: 100e6, spark_color: "#34d399" },
  jvm_heap_used:   { label: "JVM Heap",     unit: "MB",    fmt: v => `${(v/1e6).toFixed(1)}MB`,  warn: 60e6,  crit: 80e6,  spark_color: "#34d399" },
  jvm_heap_limit:  { label: "JVM Max",      unit: "MB",    fmt: v => `${(v/1e6).toFixed(1)}MB`,  warn: null,  crit: null,  spark_color: "#6b7280" },
  jvm_cpu:         { label: "JVM CPU",      unit: "%",     fmt: v => `${(v*100).toFixed(1)}%`,   warn: 0.6,   crit: 0.8,   spark_color: "#fb923c" },
  jvm_threads:     { label: "Threads",      unit: "",      fmt: v => v.toFixed(0),               warn: null,  crit: null,  spark_color: "#60a5fa" },
  jvm_gc_count:    { label: "GC Count",     unit: "",      fmt: v => v.toFixed(0),               warn: 10,    crit: 20,    spark_color: "#a78bfa" },
};

function metricHealth(name, v) {
  const m = METRIC_META[name];
  if (!m || v === undefined) return "normal";
  if (m.crit !== null && v >= m.crit) return "critical";
  if (m.warn !== null && v >= m.warn) return "warning";
  return "normal";
}

const H = {
  normal:   { card: "border-gray-800 bg-gray-900/40",          val: "text-emerald-400", dot: "bg-emerald-500" },
  warning:  { card: "border-yellow-800/50 bg-yellow-950/20",   val: "text-yellow-300",  dot: "bg-yellow-400" },
  critical: { card: "border-red-800/50 bg-red-950/20",         val: "text-red-400",     dot: "bg-red-500 animate-pulse" },
};

// ── MetricCard with sparkline ──────────────────────────────────────────────────

function MetricCard({ name, value, sparkPoints }) {
  const meta   = METRIC_META[name] || { label: name, fmt: v => v.toFixed(4), spark_color: "#6b7280" };
  const health = metricHealth(name, value);
  const c      = H[health];
  return (
    <div className={`rounded-lg border px-3 pt-2 pb-1.5 flex flex-col gap-0.5 ${c.card} relative overflow-hidden`}>
      <div className="flex items-center justify-between">
        <span className="text-[11px] text-gray-500 truncate">{meta.label}</span>
        <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${c.dot}`} />
      </div>
      <span className={`text-sm font-mono font-bold ${c.val}`}>
        {meta.fmt(value)}
      </span>
      <div className="mt-0.5">
        <Sparkline
          points={sparkPoints || []}
          color={health === "normal" ? meta.spark_color : health === "warning" ? "#fbbf24" : "#f87171"}
          height={22}
          width={90}
        />
      </div>
    </div>
  );
}

// ── Stack tool card ───────────────────────────────────────────────────────────

const TOOL_ICONS = {
  Prometheus:       Activity,
  Loki:             Database,
  "OTel Collector": Radio,
  Promtail:         GitBranch,
};

function StackCard({ tool }) {
  const Icon = TOOL_ICONS[tool.name] || Server;
  const statusColor =
    tool.status === "up"      ? "text-emerald-400 bg-emerald-900/30 border-emerald-800/40" :
    tool.status === "down"    ? "text-red-400 bg-red-900/30 border-red-800/40" :
                                "text-gray-500 bg-gray-800/30 border-gray-700/40";
  const dotColor =
    tool.status === "up"   ? "bg-emerald-400" :
    tool.status === "down" ? "bg-red-400 animate-pulse" : "bg-gray-500";

  const statsEntries = Object.entries(tool.stats || {});

  return (
    <div className="flex items-start gap-3 px-3 py-2.5 rounded-lg border border-gray-800 bg-gray-900/40 hover:bg-gray-900/60 transition-colors group">
      <div className="w-7 h-7 rounded-md bg-gray-800 flex items-center justify-center shrink-0 mt-0.5">
        <Icon size={13} className="text-gray-400" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-0.5">
          <span className="text-xs font-semibold text-gray-200">{tool.name}</span>
          <span className={`flex items-center gap-1 text-[10px] px-1.5 rounded border font-medium ${statusColor}`}>
            <span className={`w-1 h-1 rounded-full ${dotColor}`} />
            {tool.status}
          </span>
        </div>
        <p className="text-[10px] text-gray-600 truncate mb-1">{tool.role}</p>
        <div className="flex items-center gap-3">
          <code className="text-[10px] text-gray-500 font-mono truncate flex-1">{tool.endpoint}</code>
          {tool.ui_path && (
            <a
              href={`${tool.endpoint}${tool.ui_path}`}
              target="_blank"
              rel="noreferrer"
              className="opacity-0 group-hover:opacity-100 transition-opacity"
            >
              <ExternalLink size={10} className="text-indigo-400 hover:text-indigo-300" />
            </a>
          )}
        </div>
        {statsEntries.length > 0 && (
          <div className="flex gap-2 mt-1.5 flex-wrap">
            {statsEntries.map(([k, v]) => (
              <span key={k} className="text-[10px] text-gray-600">
                <span className="text-gray-400 font-mono">{v}</span>{" "}
                {k.replace(/_/g, " ")}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Log row ───────────────────────────────────────────────────────────────────

const LEVEL_CLS = {
  ERROR: "bg-red-900/50 text-red-300",
  WARN:  "bg-yellow-900/40 text-yellow-300",
  "?":   "bg-gray-800 text-gray-400",
};

function LogRow({ entry }) {
  const ts  = entry.ts ? entry.ts.slice(11, 19) : "—";
  const lvl = entry.level || "?";
  return (
    <div className="flex items-start gap-2 py-1.5 px-2 rounded hover:bg-gray-800/40 text-xs font-mono">
      <span className="text-gray-600 shrink-0 w-16">{ts}</span>
      <span className={`shrink-0 px-1.5 rounded text-[10px] font-bold leading-5 ${LEVEL_CLS[lvl] || LEVEL_CLS["?"]}`}>{lvl}</span>
      <span className="text-gray-500 shrink-0 max-w-[80px] truncate">[{entry.component}]</span>
      <span className="text-gray-300 flex-1 break-all leading-relaxed">{entry.msg}</span>
    </div>
  );
}

// ── Tabs ──────────────────────────────────────────────────────────────────────

const TABS = [
  { id: "metrics", label: "Metrics & Logs" },
  { id: "stack",   label: "Stack Health"   },
];

// ── Main panel ────────────────────────────────────────────────────────────────

const LOOKBACKS = [5, 10, 15, 30];

export function IncidentAnalysisPanel() {
  const [tab,            setTab]            = useState("metrics");
  const [services,       setServices]       = useState([]);
  const [selected,       setSelected]       = useState(null);
  const [lookback,       setLookback]       = useState(10);
  const [metrics,        setMetrics]        = useState({});
  const [anomalies,      setAnomalies]      = useState([]);
  const [logs,           setLogs]           = useState([]);
  const [timeseries,     setTimeseries]     = useState({});
  const [stackHealth,    setStackHealth]    = useState(null);
  const [fetchedAt,      setFetchedAt]      = useState(null);
  const [dataPhase,      setDataPhase]      = useState("idle");
  const [analysisPhase,  setAnalysisPhase]  = useState("idle");
  const [output,         setOutput]         = useState("");
  const [statusMsg,      setStatusMsg]      = useState("");
  const [errorMsg,       setErrorMsg]       = useState("");
  const [copied,         setCopied]         = useState(false);

  const abortRef  = useRef(null);
  const outputRef = useRef(null);
  const pollRef   = useRef(null);

  useEffect(() => {
    if (outputRef.current) outputRef.current.scrollTop = outputRef.current.scrollHeight;
  }, [output]);

  // Load services on mount
  useEffect(() => {
    fetch("/api/v1/observability/services")
      .then(r => r.json())
      .then(d => {
        const svcs = d.services || [];
        setServices(svcs);
        if (svcs.length > 0) setSelected(svcs[0].name);
      })
      .catch(() => {
        const fallback = [
          { name: "auth-service",  status: "unknown" },
          { name: "order-service", status: "unknown" },
        ];
        setServices(fallback);
        setSelected("auth-service");
      });
    // Load stack health once
    fetch("/api/v1/observability/stack")
      .then(r => r.json())
      .then(setStackHealth)
      .catch(() => {});
  }, []);

  const fetchTelemetry = useCallback(async (svc, mins) => {
    if (!svc) return;
    setDataPhase("loading");
    try {
      const [mRes, lRes, tsRes] = await Promise.all([
        fetch(`/api/v1/observability/metrics/${svc}?minutes=${mins}`).then(r => r.json()),
        fetch(`/api/v1/observability/logs/${svc}?minutes=${mins}&limit=60`).then(r => r.json()),
        fetch(`/api/v1/observability/timeseries/${svc}?minutes=${mins}&step=60s`).then(r => r.json()),
      ]);
      setMetrics(mRes.metrics   || {});
      setAnomalies(mRes.anomalies || []);
      setLogs(lRes.entries      || []);
      setTimeseries(tsRes.series  || {});
      setFetchedAt(new Date().toLocaleTimeString());
      setDataPhase("ready");
    } catch {
      setDataPhase("error");
    }
  }, []);

  useEffect(() => {
    if (selected) {
      fetchTelemetry(selected, lookback);
      clearInterval(pollRef.current);
      pollRef.current = setInterval(() => fetchTelemetry(selected, lookback), 15000);
    }
    return () => clearInterval(pollRef.current);
  }, [selected, lookback, fetchTelemetry]);

  async function runAnalysis() {
    if (!selected || analysisPhase === "running") return;
    setAnalysisPhase("running");
    setOutput("");
    setErrorMsg("");
    setStatusMsg("Initializing…");
    const controller = new AbortController();
    abortRef.current = controller;
    try {
      const resp = await fetch("/api/v1/observability/analyze-live", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ service: selected, environment: "production", minutes: lookback, session_id: `live-${Date.now()}` }),
        signal: controller.signal,
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const reader = resp.body.getReader();
      const dec    = new TextDecoder();
      let buf = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        const lines = buf.split("\n"); buf = lines.pop();
        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          try {
            const ev = JSON.parse(line.slice(6));
            if (ev.type === "status")    setStatusMsg(ev.text);
            if (ev.type === "telemetry") { if (ev.metrics) setMetrics(ev.metrics); if (ev.anomalies) setAnomalies(ev.anomalies); }
            if (ev.type === "token")     setOutput(p => p + ev.text);
            if (ev.type === "done")      { setAnalysisPhase("done"); setStatusMsg(""); }
            if (ev.type === "error")     { setAnalysisPhase("error"); setErrorMsg(ev.message); }
          } catch {}
        }
      }
      setAnalysisPhase(p => p === "running" ? "done" : p);
    } catch (err) {
      if (err.name !== "AbortError") { setAnalysisPhase("error"); setErrorMsg(err.message); }
      else setAnalysisPhase("idle");
    }
  }

  function stop()  { abortRef.current?.abort(); setAnalysisPhase("idle"); setStatusMsg(""); }
  function reset() { abortRef.current?.abort(); setAnalysisPhase("idle"); setOutput(""); setErrorMsg(""); setStatusMsg(""); }
  async function copy() { await navigator.clipboard.writeText(output); setCopied(true); setTimeout(() => setCopied(false), 2000); }

  const metricEntries  = Object.entries(metrics);
  const criticalCount  = anomalies.filter(a => a.severity === "critical").length;
  const warningCount   = anomalies.filter(a => a.severity === "warning").length;

  return (
    <div className="flex h-full bg-gray-950 text-gray-100 overflow-hidden">

      {/* ── Left: Telemetry panel ─────────────────────────────────────────── */}
      <div className="w-[48%] flex flex-col border-r border-gray-800 min-h-0">

        {/* Header + tabs */}
        <div className="shrink-0 border-b border-gray-800 bg-gray-900">
          <div className="flex items-center gap-2 px-4 pt-3 pb-0">
            <Activity size={14} className="text-emerald-400" />
            <span className="text-sm font-semibold">Live Observability</span>
            {fetchedAt && <span className="text-xs text-gray-600">· {fetchedAt}</span>}
            <button
              onClick={() => { fetchTelemetry(selected, lookback); fetch("/api/v1/observability/stack").then(r=>r.json()).then(setStackHealth).catch(()=>{}); }}
              className="ml-auto flex items-center gap-1 px-2 py-0.5 rounded bg-gray-800 hover:bg-gray-700 text-gray-500 text-xs"
            >
              <RefreshCw size={10} className={dataPhase === "loading" ? "animate-spin" : ""} /> Refresh
            </button>
          </div>
          <div className="flex gap-0 px-4 mt-2">
            {TABS.map(t => (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                className={`px-3 py-1.5 text-xs border-b-2 transition-colors ${
                  tab === t.id
                    ? "border-indigo-500 text-indigo-300 font-medium"
                    : "border-transparent text-gray-600 hover:text-gray-400"
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>
        </div>

        {/* Service selector */}
        <div className="px-4 py-2.5 border-b border-gray-800 bg-gray-900/40 shrink-0">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-[11px] text-gray-500 w-14 shrink-0">Service</span>
            <div className="flex gap-1.5">
              {services.map(s => (
                <button
                  key={s.name}
                  onClick={() => setSelected(s.name)}
                  className={`flex items-center gap-1.5 px-3 py-1 rounded-full text-xs border transition-all ${
                    selected === s.name
                      ? "bg-indigo-900/60 border-indigo-600 text-indigo-200"
                      : "bg-gray-800/50 border-gray-700 text-gray-400 hover:border-gray-600"
                  }`}
                >
                  <span className={`w-1.5 h-1.5 rounded-full ${s.status === "up" ? "bg-emerald-400" : s.status === "down" ? "bg-red-400" : "bg-gray-500"}`} />
                  {s.name}
                </button>
              ))}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[11px] text-gray-500 w-14 shrink-0">Lookback</span>
            <div className="flex gap-1">
              {LOOKBACKS.map(m => (
                <button
                  key={m}
                  onClick={() => setLookback(m)}
                  className={`px-2 py-0.5 rounded text-[11px] border transition-all ${
                    lookback === m ? "bg-gray-700 border-gray-500 text-gray-200" : "border-gray-800 text-gray-600 hover:border-gray-700"
                  }`}
                >
                  {m}m
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* ── Tab: Metrics & Logs ─────────────────────────────────────────── */}
        {tab === "metrics" && (
          <div className="flex flex-col flex-1 min-h-0 overflow-y-auto">

            {/* Anomaly banner */}
            {anomalies.length > 0 && (
              <div className="px-4 py-2 border-b border-red-900/30 bg-red-950/15 shrink-0">
                <div className="flex items-center gap-1.5 mb-1.5">
                  <AlertTriangle size={11} className="text-red-400" />
                  <span className="text-[11px] font-semibold text-red-400">
                    {criticalCount > 0 && `${criticalCount} Critical`}{criticalCount > 0 && warningCount > 0 && " · "}
                    {warningCount > 0  && `${warningCount} Warning`}
                  </span>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {anomalies.map((a, i) => (
                    <span key={i} className={`px-2 py-0.5 rounded text-[10px] font-medium border ${
                      a.severity === "critical"
                        ? "bg-red-900/40 text-red-300 border-red-800/50"
                        : "bg-yellow-900/30 text-yellow-300 border-yellow-800/40"
                    }`}>
                      {a.label}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Metrics grid */}
            <div className="px-4 py-3 border-b border-gray-800 shrink-0">
              <span className="text-[10px] font-semibold text-gray-500 uppercase tracking-wider">Metrics · {lookback}m window · 1m sparklines</span>
              <div className="grid grid-cols-3 gap-2 mt-2">
                {dataPhase === "loading" && metricEntries.length === 0
                  ? [1,2,3,4,5,6].map(i => <div key={i} className="rounded-lg border border-gray-800 h-20 animate-pulse bg-gray-900/40" />)
                  : metricEntries.map(([name, val]) => (
                      <MetricCard key={name} name={name} value={val} sparkPoints={timeseries[name]} />
                    ))
                }
                {dataPhase === "ready" && metricEntries.length === 0 && (
                  <p className="col-span-3 text-xs text-gray-600 py-2">No metrics found for {selected}</p>
                )}
              </div>
            </div>

            {/* Error logs */}
            <div className="flex flex-col flex-1 min-h-0 px-4 py-3">
              <div className="flex items-center gap-1.5 mb-2 shrink-0">
                <Terminal size={11} className="text-gray-500" />
                <span className="text-[10px] font-semibold text-gray-500 uppercase tracking-wider">Error Logs · Loki</span>
                {logs.length > 0 && <span className="ml-auto text-[10px] text-gray-600">{logs.length} entries</span>}
              </div>
              <div className="flex-1 overflow-y-auto rounded-lg bg-gray-900/30 border border-gray-800 divide-y divide-gray-800/40">
                {dataPhase === "loading" && logs.length === 0
                  ? <div className="flex items-center justify-center h-20 text-xs text-gray-600"><RefreshCw size={11} className="animate-spin mr-1.5" />Fetching…</div>
                  : logs.length === 0
                    ? <div className="flex flex-col items-center justify-center h-20 gap-1"><CheckCircle size={14} className="text-emerald-800" /><span className="text-xs text-gray-600">No ERROR/WARN logs in last {lookback}m</span></div>
                    : logs.map((e, i) => <LogRow key={i} entry={e} />)
                }
              </div>
            </div>
          </div>
        )}

        {/* ── Tab: Stack Health ───────────────────────────────────────────── */}
        {tab === "stack" && (
          <div className="flex-1 overflow-y-auto px-4 py-4 min-h-0">
            <div className="flex items-center justify-between mb-3">
              <span className="text-[10px] font-semibold text-gray-500 uppercase tracking-wider">
                Observability Stack · {NAMESPACE} namespace
              </span>
              {stackHealth?.fetched_at && (
                <span className="text-[10px] text-gray-700">
                  {new Date(stackHealth.fetched_at).toLocaleTimeString()}
                </span>
              )}
            </div>
            <div className="flex flex-col gap-2">
              {(stackHealth?.tools || []).map(tool => (
                <StackCard key={tool.name} tool={tool} />
              ))}
              {!stackHealth && (
                <div className="flex items-center justify-center h-32 text-xs text-gray-600">
                  <RefreshCw size={12} className="animate-spin mr-2" /> Loading stack health…
                </div>
              )}
            </div>

            {/* Prometheus target breakdown */}
            {stackHealth && (
              <div className="mt-4">
                <span className="text-[10px] font-semibold text-gray-500 uppercase tracking-wider">Prometheus Scrape Targets</span>
                <div className="mt-2 rounded-lg border border-gray-800 overflow-hidden">
                  <a
                    href={`${_PROM_UI}/targets`}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center justify-between px-3 py-2 bg-gray-900/40 hover:bg-gray-900/60 transition-colors text-xs text-indigo-400 border-b border-gray-800"
                  >
                    <span>Open Prometheus Targets UI</span>
                    <ExternalLink size={11} />
                  </a>
                  <a
                    href={`${_PROM_UI}/graph`}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center justify-between px-3 py-2 bg-gray-900/40 hover:bg-gray-900/60 transition-colors text-xs text-indigo-400 border-b border-gray-800"
                  >
                    <span>Open Prometheus Graph Explorer</span>
                    <ExternalLink size={11} />
                  </a>
                  <a
                    href={`${_LOKI_UI}/loki/api/v1/label/service/values`}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center justify-between px-3 py-2 bg-gray-900/40 hover:bg-gray-900/60 transition-colors text-xs text-indigo-400"
                  >
                    <span>Loki API — service label values</span>
                    <ExternalLink size={11} />
                  </a>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Analyze button */}
        <div className="px-4 py-3 border-t border-gray-800 bg-gray-900/60 shrink-0">
          {analysisPhase === "running" ? (
            <div className="flex items-center gap-3">
              <span className="flex items-center gap-1.5 text-xs text-indigo-400 flex-1">
                <span className="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-pulse" />
                {statusMsg || "Analyzing…"}
              </span>
              <button onClick={stop} className="flex items-center gap-1.5 px-3 py-1.5 bg-gray-700 hover:bg-gray-600 rounded text-xs text-gray-300">
                <Square size={10} /> Stop
              </button>
            </div>
          ) : (
            <button
              onClick={runAnalysis}
              disabled={!selected || dataPhase === "loading"}
              className={`w-full flex items-center justify-center gap-2 py-2.5 rounded text-sm font-semibold transition-all ${
                selected && dataPhase !== "loading"
                  ? "bg-indigo-700 hover:bg-indigo-600 text-white shadow-lg shadow-indigo-900/30"
                  : "bg-gray-800 text-gray-600 cursor-not-allowed"
              }`}
            >
              <Zap size={14} /> Analyze Live — {selected || "select a service"}
            </button>
          )}
        </div>
      </div>

      {/* ── Right: AI Diagnostic Report ───────────────────────────────────── */}
      <div className="flex-1 flex flex-col min-h-0 min-w-0">
        <div className="flex items-center gap-2 px-4 py-3 border-b border-gray-800 bg-gray-900 shrink-0">
          <span className="text-sm font-semibold">Diagnostic Report</span>
          {analysisPhase === "running" && (
            <span className="flex items-center gap-1.5 text-xs text-indigo-400 ml-2">
              <span className="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-pulse" />
              {statusMsg || "Generating…"}
            </span>
          )}
          {analysisPhase === "done"  && <span className="flex items-center gap-1 text-xs text-emerald-500 ml-2"><CheckCircle size={11} /> Complete</span>}
          {analysisPhase === "error" && <span className="flex items-center gap-1 text-xs text-red-500 ml-2"><XCircle size={11} /> Error</span>}
          <div className="ml-auto flex gap-2">
            {output && (
              <button onClick={copy} className="flex items-center gap-1 px-2.5 py-1 bg-gray-800 hover:bg-gray-700 rounded text-xs text-gray-400">
                {copied ? <CheckCheck size={11} className="text-emerald-400" /> : <Copy size={11} />}
                {copied ? "Copied" : "Copy"}
              </button>
            )}
            {(output || analysisPhase === "error") && (
              <button onClick={reset} className="flex items-center gap-1 px-2.5 py-1 bg-gray-800 hover:bg-gray-700 rounded text-xs text-gray-400">
                <RotateCcw size={11} /> Reset
              </button>
            )}
          </div>
        </div>

        <div ref={outputRef} className="flex-1 overflow-y-auto px-6 py-4">
          {!output && analysisPhase === "idle" && (
            <div className="flex flex-col items-center justify-center h-full gap-4 text-center">
              <div className="w-16 h-16 rounded-2xl bg-gray-900 border border-gray-800 flex items-center justify-center">
                <Zap size={28} className="text-indigo-800" />
              </div>
              <div>
                <p className="text-sm text-gray-500 font-medium">Click Analyze Live to generate a report</p>
                <p className="text-xs text-gray-700 mt-1">Pulls live data from Prometheus + Loki → structured AI SRE report</p>
              </div>
              <div className="flex gap-4 text-xs text-gray-700">
                <span className="flex items-center gap-1"><Activity size={10}/> Prometheus metrics</span>
                <span className="flex items-center gap-1"><Terminal size={10}/> Loki error logs</span>
                <span className="flex items-center gap-1"><Clock size={10}/> AI root cause</span>
              </div>
            </div>
          )}
          {analysisPhase === "error" && errorMsg && (
            <div className="rounded-lg border border-red-900 bg-red-950/40 px-4 py-3 text-sm text-red-400 font-mono mb-4">{errorMsg}</div>
          )}
          {output && (
            <div className="prose prose-invert prose-sm max-w-none
              prose-headings:text-gray-100
              prose-h2:text-base prose-h2:font-bold prose-h2:mt-6 prose-h2:mb-2 prose-h2:border-b prose-h2:border-gray-800 prose-h2:pb-1
              prose-h3:text-sm prose-h3:font-semibold prose-h3:mt-4 prose-h3:mb-1 prose-h3:text-gray-300
              prose-p:text-gray-300 prose-p:leading-relaxed prose-p:my-1.5
              prose-li:text-gray-300 prose-li:my-0.5
              prose-strong:text-gray-100
              prose-code:text-emerald-300 prose-code:bg-gray-900 prose-code:rounded prose-code:px-1 prose-code:text-xs
              prose-pre:bg-gray-900 prose-pre:border prose-pre:border-gray-800 prose-pre:rounded-lg prose-pre:text-xs
              prose-a:text-indigo-400"
            >
              <ReactMarkdown>{output}</ReactMarkdown>
            </div>
          )}
          {analysisPhase === "running" && <span className="inline-block w-1.5 h-4 bg-indigo-400 ml-0.5 animate-pulse rounded-sm" />}
        </div>
      </div>
    </div>
  );
}

// Expose prometheus UI URL for stack links
const _PROM_UI = "http://localhost:19090";
const _LOKI_UI = "http://localhost:13100";
