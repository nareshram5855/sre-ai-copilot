import { useState, useEffect, useCallback, useRef } from "react";
import {
  AlertTriangle, CheckCircle, RefreshCw, Stethoscope,
  Clock, Play, Pause, ChevronRight, Activity,
} from "lucide-react";
import axios from "axios";
import { ChartPanel, StackCard } from "./observability/widgets.jsx";

const POLL_MS = 30_000;
const LOOKBACKS = [5, 10, 15, 30];

const HEALTH_STYLE = {
  healthy:  { border: "border-emerald-500/40", bg: "bg-emerald-950/20", badge: "text-emerald-400 bg-emerald-900/30", dot: "bg-emerald-400" },
  warning:  { border: "border-yellow-500/40",  bg: "bg-yellow-950/20",  badge: "text-yellow-300 bg-yellow-900/30",  dot: "bg-yellow-400 animate-pulse" },
  critical: { border: "border-red-500/50",     bg: "bg-red-950/30",     badge: "text-red-400 bg-red-900/30",        dot: "bg-red-500 animate-pulse" },
  unknown:  { border: "border-gray-700",       bg: "bg-gray-900/40",    badge: "text-gray-400 bg-gray-800/40",      dot: "bg-gray-500" },
};

const CHART_METRICS = [
  "error_rate", "request_rate",
  "latency_p99_ms", "latency_p50_ms",
  "db_errors", "pool_exhaustion",
  "jvm_heap_used", "jvm_cpu",
];

function ServiceListItem({ svc, selected, onSelect }) {
  const s = HEALTH_STYLE[svc.health] || HEALTH_STYLE.unknown;
  return (
    <button
      onClick={() => onSelect(svc.name)}
      className={`w-full text-left px-3 py-2.5 rounded-lg border transition-all ${
        selected === svc.name
          ? `${s.border} ${s.bg} ring-1 ring-indigo-500/40`
          : "border-transparent hover:bg-white/5"
      }`}
    >
      <div className="flex items-center gap-2 mb-1">
        <span className={`w-2 h-2 rounded-full shrink-0 ${s.dot}`} />
        <span className="text-xs font-semibold text-gray-200 truncate flex-1">{svc.name}</span>
        <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${s.badge}`}>
          {svc.health}
        </span>
      </div>
      {svc.anomaly_count > 0 ? (
        <p className="text-[10px] text-red-300/80 flex items-center gap-1 pl-4">
          <AlertTriangle size={9} />
          {svc.anomaly_count} anomal{svc.anomaly_count === 1 ? "y" : "ies"}
        </p>
      ) : (
        <p className="text-[10px] text-gray-600 flex items-center gap-1 pl-4">
          <CheckCircle size={9} className="text-emerald-600/70" />
          SLIs nominal
        </p>
      )}
    </button>
  );
}

function AnomalyRow({ item }) {
  const isCrit = item.severity === "critical";
  return (
    <div className={`flex items-start gap-3 px-3 py-2 rounded-lg border text-xs ${
      isCrit ? "border-red-800/50 bg-red-950/20" : "border-yellow-800/40 bg-yellow-950/15"
    }`}>
      <AlertTriangle size={13} className={`${isCrit ? "text-red-400" : "text-yellow-400"} shrink-0 mt-0.5`} />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="font-semibold text-gray-200">{item.service}</span>
          <span className={`text-[10px] px-1.5 py-0.5 rounded font-bold uppercase ${
            isCrit ? "bg-red-900/50 text-red-300" : "bg-yellow-900/40 text-yellow-300"
          }`}>
            {item.type?.replace(/_/g, " ")}
          </span>
        </div>
        <p className="text-gray-400 mt-0.5 font-mono truncate">{item.label}</p>
      </div>
    </div>
  );
}

export function AnomalyWatchPanel({ onAnalyzeService }) {
  const [lookback, setLookback] = useState(10);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [phase, setPhase] = useState("idle");
  const [watch, setWatch] = useState(null);
  const [stack, setStack] = useState(null);
  const [selected, setSelected] = useState(null);
  const [timeseries, setTimeseries] = useState({});
  const [lastRefresh, setLastRefresh] = useState(null);
  const [error, setError] = useState(null);
  const [streamLive, setStreamLive] = useState(false);
  const pollRef = useRef(null);
  const esRef = useRef(null);
  const refreshDebounceRef = useRef(null);

  const selectedSvc = watch?.services?.find((s) => s.name === selected) || watch?.services?.[0];

  const fetchWatch = useCallback(async () => {
    setPhase((p) => (p === "idle" ? "loading" : "refreshing"));
    setError(null);
    try {
      const { data } = await axios.get(`/api/v1/observability/watch?minutes=${lookback}`);
      setWatch(data);
      setLastRefresh(new Date().toISOString().slice(11, 19));
      setSelected((prev) => {
        if (prev && data.services?.some((s) => s.name === prev)) return prev;
        return data.services?.[0]?.name || null;
      });
      setPhase("ready");
    } catch (err) {
      setError(err.message || "Failed to load");
      setPhase("error");
    }
  }, [lookback]);

  const fetchTimeseries = useCallback(async (svc) => {
    if (!svc) return;
    try {
      const { data } = await axios.get(
        `/api/v1/observability/timeseries/${svc}?minutes=${lookback}&step=60s`
      );
      setTimeseries(data.series || {});
    } catch {
      setTimeseries({});
    }
  }, [lookback]);

  useEffect(() => {
    fetchWatch();
    axios.get("/api/v1/observability/stack").then((r) => setStack(r.data)).catch(() => {});
  }, [fetchWatch]);

  useEffect(() => {
    let es;
    const scheduleRefresh = () => {
      if (refreshDebounceRef.current) clearTimeout(refreshDebounceRef.current);
      refreshDebounceRef.current = setTimeout(() => fetchWatch(), 500);
    };

    try {
      es = new EventSource("/api/v1/events/anomalies/stream");
      esRef.current = es;
      es.onmessage = (ev) => {
        try {
          const data = JSON.parse(ev.data);
          if (data.type === "connected") {
            setStreamLive(true);
            return;
          }
          if (data.type === "heartbeat") return;
          if (data.type === "anomaly") {
            scheduleRefresh();
          }
        } catch (_) {}
      };
      es.onerror = () => setStreamLive(false);
    } catch (_) {
      setStreamLive(false);
    }

    return () => {
      es?.close();
      esRef.current = null;
      if (refreshDebounceRef.current) clearTimeout(refreshDebounceRef.current);
    };
  }, [fetchWatch]);

  useEffect(() => {
    if (selectedSvc?.name) fetchTimeseries(selectedSvc.name);
  }, [selectedSvc?.name, fetchTimeseries]);

  useEffect(() => {
    if (!autoRefresh) { clearInterval(pollRef.current); return; }
    const intervalMs = streamLive ? 60_000 : POLL_MS;
    pollRef.current = setInterval(fetchWatch, intervalMs);
    return () => clearInterval(pollRef.current);
  }, [autoRefresh, fetchWatch, streamLive]);

  const overall = watch?.overall_health || "unknown";
  const overallStyle = HEALTH_STYLE[overall] || HEALTH_STYLE.unknown;
  const chartsToShow = CHART_METRICS.filter(
    (k) => selectedSvc?.metrics?.[k] !== undefined || timeseries[k]?.length > 0
  );

  return (
    <div className="flex flex-col h-full">
      {/* ── Top bar ─────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between gap-3 px-5 py-3 border-b border-sre-border bg-sre-surface/60 shrink-0 flex-wrap gap-y-2">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-indigo-600/15 border border-indigo-500/25 flex items-center justify-center">
            <Activity size={16} className="text-indigo-400" />
          </div>
          <div>
            <h1 className="text-sm font-semibold text-white leading-none">Observe</h1>
            <p className="text-[10px] text-gray-500 mt-0.5">SLI · Metrics · Anomalies</p>
          </div>
          <span className={`flex items-center gap-1.5 text-[11px] px-2 py-0.5 rounded-md border font-medium ${overallStyle.badge} ${overallStyle.border}`}>
            <span className={`w-1.5 h-1.5 rounded-full ${overallStyle.dot}`} />
            Fleet {overall}
          </span>
          <span className={`text-[10px] px-2 py-0.5 rounded-full border ${
            streamLive
              ? "text-emerald-400 border-emerald-800/50 bg-emerald-950/30"
              : "text-gray-500 border-gray-700 bg-gray-900/40"
          }`}>
            {streamLive ? "Connected" : "Polling"}
          </span>
        </div>

        <div className="flex items-center gap-2">
          {lastRefresh && (
            <span className="text-[10px] text-gray-600 flex items-center gap-1 tabular-nums">
              <Clock size={10} /> {lastRefresh} UTC
            </span>
          )}
          <div className="flex rounded-lg border border-gray-700 overflow-hidden">
            {LOOKBACKS.map((m) => (
              <button
                key={m}
                onClick={() => setLookback(m)}
                className={`px-2.5 py-1 text-[11px] font-medium transition-colors ${
                  lookback === m ? "bg-indigo-600 text-white" : "text-gray-500 hover:bg-gray-800"
                }`}
              >
                {m}m
              </button>
            ))}
          </div>
          <button
            onClick={() => setAutoRefresh((v) => !v)}
            className={`flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs border transition-colors ${
              autoRefresh
                ? streamLive
                  ? "border-emerald-800/50 text-emerald-400 bg-emerald-950/20"
                  : "border-yellow-800/50 text-yellow-400 bg-yellow-950/20"
                : "border-gray-700 text-gray-500"
            }`}
          >
            {autoRefresh ? <Play size={10} /> : <Pause size={10} />}
            {autoRefresh ? (streamLive ? "Live" : "Poll fallback") : "Paused"}
          </button>
          <button
            onClick={fetchWatch}
            disabled={phase === "loading"}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-sre-accent hover:bg-indigo-500 text-white text-xs disabled:opacity-50 transition-colors"
          >
            <RefreshCw size={11} className={phase === "refreshing" ? "animate-spin" : ""} />
            Refresh
          </button>
        </div>
      </div>

      {error && (
        <div className="mx-5 mt-3 rounded-lg border border-red-800/50 bg-red-950/20 px-4 py-2 text-xs text-red-300">
          {error} — ensure Prometheus is running on :19090
          {!streamLive && autoRefresh && (
            <span className="block text-red-400/80 mt-1">
              SSE unavailable — poll fallback every {POLL_MS / 1000}s
            </span>
          )}
        </div>
      )}

      {/* ── Summary strip ───────────────────────────────────────────── */}
      {watch && (
        <div className="flex gap-4 px-5 py-3 border-b border-sre-border/50 shrink-0">
          {[
            { label: "Services",  value: watch.service_count,  cls: "text-blue-400" },
            { label: "Anomalies", value: watch.anomaly_count,  cls: watch.anomaly_count ? "text-red-400" : "text-emerald-400" },
            { label: "Critical",  value: watch.services?.filter((s) => s.health === "critical").length, cls: "text-orange-400" },
            { label: "Window",    value: `${watch.minutes}m`,  cls: "text-gray-400" },
          ].map(({ label, value, cls }) => (
            <div key={label} className="flex items-center gap-2">
              <span className={`text-lg font-bold font-mono tabular-nums ${cls}`}>{value}</span>
              <span className="text-[10px] text-gray-600 uppercase tracking-wide">{label}</span>
            </div>
          ))}
        </div>
      )}

      {/* ── Main layout ─────────────────────────────────────────────── */}
      <div className="flex flex-1 min-h-0 overflow-hidden">
        {/* Left: service list + stack */}
        <aside className="w-52 flex-shrink-0 border-r border-sre-border flex flex-col overflow-y-auto bg-sre-surface/30">
          <div className="px-3 pt-4 pb-2">
            <p className="text-[10px] font-semibold text-gray-600 uppercase tracking-widest mb-2">Services</p>
            {phase === "loading" && !watch ? (
              <p className="text-xs text-gray-600 animate-pulse py-4 text-center">Loading…</p>
            ) : (
              <div className="space-y-1">
                {(watch?.services || []).map((svc) => (
                  <ServiceListItem
                    key={svc.name}
                    svc={svc}
                    selected={selectedSvc?.name}
                    onSelect={setSelected}
                  />
                ))}
              </div>
            )}
          </div>

          {stack?.tools && (
            <div className="px-3 pt-2 pb-4 mt-auto">
              <p className="text-[10px] font-semibold text-gray-600 uppercase tracking-widest mb-2">Stack</p>
              <div className="space-y-1.5">
                {stack.tools.map((tool) => (
                  <StackCard key={tool.name} tool={tool} />
                ))}
              </div>
            </div>
          )}
        </aside>

        {/* Right: charts + anomaly feed */}
        <div className="flex-1 overflow-y-auto">
          {selectedSvc && (
            <div className="px-5 pt-4 pb-2">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <h2 className="text-sm font-semibold text-gray-300">{selectedSvc.name}</h2>
                  <span className="text-[10px] text-gray-600">· SLI metrics · last {lookback}m</span>
                </div>
                {onAnalyzeService && (
                  <button
                    onClick={() => onAnalyzeService(selectedSvc.name)}
                    className="flex items-center gap-1 text-xs text-indigo-400 hover:text-indigo-300 transition-colors"
                  >
                    <Stethoscope size={12} />
                    Deep analysis
                    <ChevronRight size={12} />
                  </button>
                )}
              </div>

              {chartsToShow.length > 0 ? (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                  {chartsToShow.map((name) => (
                    <ChartPanel
                      key={name}
                      name={name}
                      value={selectedSvc.metrics[name]}
                      sparkPoints={timeseries[name]}
                    />
                  ))}
                </div>
              ) : (
                <div className="text-xs text-gray-600 text-center py-12">
                  No metric data available — trigger a failure to see charts
                </div>
              )}
            </div>
          )}

          {/* Anomaly feed */}
          <div className="px-5 pt-4 pb-6">
            <h2 className="text-[10px] font-semibold text-gray-600 uppercase tracking-widest mb-3">
              Anomaly Feed
              {watch?.anomaly_count > 0 && (
                <span className="ml-2 text-red-400 normal-case font-normal">
                  ({watch.anomaly_count} active)
                </span>
              )}
            </h2>
            {watch?.anomalies?.length > 0 ? (
              <div className="space-y-2">
                {watch.anomalies.map((a, i) => (
                  <AnomalyRow key={`${a.service}-${a.type}-${i}`} item={a} />
                ))}
              </div>
            ) : (
              <div className="rounded-xl border border-emerald-800/30 bg-emerald-950/10 px-4 py-8 text-center">
                <CheckCircle size={28} className="mx-auto text-emerald-500/60 mb-2" />
                <p className="text-sm text-emerald-300/90 font-medium">No anomalies detected</p>
                <p className="text-xs text-gray-500 mt-1">
                  All SLIs within thresholds for the last {lookback} minutes
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
