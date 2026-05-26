import { useCallback, useEffect, useState } from "react";
import {
  Activity, RefreshCw, Cpu, Database, Radio, Server, Zap,
} from "lucide-react";
import axios from "axios";
import { PageHeader } from "./layout/PageHeader.jsx";
import { PageShell } from "./layout/PageShell.jsx";
import { StatusPill } from "./layout/StatusPill.jsx";

function fmtUptime(seconds) {
  if (seconds == null) return "—";
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  if (h > 0) return `${h}h ${m}m ${s}s`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

function fmtNum(n, digits = 1) {
  if (n == null || Number.isNaN(n)) return "—";
  return Number(n).toFixed(digits);
}

function integrationStatus(enabled, connected) {
  if (!enabled) return "unknown";
  return connected ? "up" : "down";
}

function MetricCard({ label, value, sub, icon: Icon, accent = "indigo" }) {
  const accents = {
    indigo: "border-indigo-500/20 bg-indigo-950/20",
    emerald: "border-emerald-500/20 bg-emerald-950/20",
    amber: "border-amber-500/20 bg-amber-950/20",
    slate: "border-white/10 bg-white/[0.03]",
  };
  return (
    <div className={`rounded-xl border p-4 ${accents[accent] || accents.slate}`}>
      <div className="flex items-center justify-between gap-2 mb-2">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-gray-500">{label}</span>
        {Icon && <Icon size={14} className="text-gray-600 shrink-0" />}
      </div>
      <p className="text-2xl font-semibold text-white tabular-nums tracking-tight">{value}</p>
      {sub && <p className="text-[11px] text-gray-500 mt-1">{sub}</p>}
    </div>
  );
}

export function ProfilerPanel() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastRefresh, setLastRefresh] = useState(null);

  const fetchProfiler = useCallback(async () => {
    try {
      const { data: body } = await axios.get("/api/v1/profiler");
      setData(body);
      setError(null);
      setLastRefresh(new Date());
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || "Failed to load profiler");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchProfiler();
    const id = setInterval(fetchProfiler, 5000);
    return () => clearInterval(id);
  }, [fetchProfiler]);

  const req = data?.requests;
  const lat = req?.latency_ms;
  const rt = data?.runtime;
  const integ = data?.integrations;

  const kafkaStatus = integrationStatus(integ?.kafka_enabled, integ?.kafka_connected);
  const redisStatus = integrationStatus(integ?.redis_enabled, integ?.redis_connected);

  return (
    <PageShell constrained>
      <PageHeader
        title="App Profiler"
        description="Live runtime stats — request throughput, latency percentiles, integration health, and memory. Auto-refreshes every 5 seconds."
        icon={Activity}
        badges={
          <>
            <StatusPill label={loading && !data ? "Loading" : "Live"} status={error ? "down" : loading ? "loading" : "up"} compact />
            {lastRefresh && (
              <span className="text-[10px] text-gray-600 font-mono">
                {lastRefresh.toLocaleTimeString()}
              </span>
            )}
          </>
        }
        actions={
          <button
            onClick={fetchProfiler}
            className="inline-flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border border-white/10 text-gray-400 hover:text-white hover:bg-white/5 transition-colors"
          >
            <RefreshCw size={12} className={loading ? "animate-spin" : ""} />
            Refresh
          </button>
        }
      />

      {error && (
        <div className="mb-4 text-sm text-red-300 bg-red-950/30 border border-red-800/40 rounded-lg px-4 py-3">
          {error}
        </div>
      )}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <MetricCard label="Uptime" value={fmtUptime(data?.uptime_seconds)} sub={data?.started_at ? `Since ${data.started_at}` : null} icon={Server} accent="indigo" />
        <MetricCard label="Requests / sec" value={fmtNum(req?.per_second, 2)} sub={`${req?.total ?? 0} total · ${req?.in_flight ?? 0} in flight`} icon={Zap} accent="emerald" />
        <MetricCard label="Avg latency" value={lat?.avg != null ? `${fmtNum(lat.avg, 1)} ms` : "—"} sub={`p50 ${fmtNum(lat?.p50, 1)} · p99 ${fmtNum(lat?.p99, 1)} ms`} icon={Activity} accent="amber" />
        <MetricCard label="Memory" value={rt?.memory_mb != null ? `${fmtNum(rt.memory_mb, 1)} MB` : "—"} sub={rt?.python_version ? `Python ${rt.python_version}` : null} icon={Cpu} accent="slate" />
      </div>

      <div className="grid md:grid-cols-2 gap-4 mb-6">
        <section className="rounded-xl border border-white/10 bg-white/[0.02] p-4">
          <div className="flex items-center gap-2 mb-4">
            <Radio size={15} className="text-indigo-400" />
            <h2 className="text-sm font-semibold text-white">Integrations</h2>
          </div>
          <div className="space-y-3">
            <div className="flex items-center justify-between gap-3 py-2 border-b border-white/5">
              <div>
                <p className="text-sm text-gray-200">Kafka</p>
                <p className="text-[11px] text-gray-600">
                  {integ?.kafka_enabled ? "Enabled — event bus for multi-replica SSE" : "Disabled — in-process SSE only"}
                </p>
              </div>
              <StatusPill
                label={integ?.kafka_enabled ? (integ?.kafka_connected ? "Connected" : "Unavailable") : "Off"}
                status={kafkaStatus}
                compact
              />
            </div>
            <div className="flex items-center justify-between gap-3 py-2 border-b border-white/5">
              <div>
                <p className="text-sm text-gray-200">Redis</p>
                <p className="text-[11px] text-gray-600">
                  Session: {integ?.session_backend ?? "—"} · Dedup: {integ?.dedup_backend ?? "—"} · CP: {integ?.checkpointer_backend ?? "—"}
                </p>
              </div>
              <StatusPill
                label={integ?.redis_enabled ? (integ?.redis_connected ? "Connected" : "Unavailable") : "Off"}
                status={redisStatus}
                compact
              />
            </div>
            <div className="flex items-center justify-between gap-3 py-2">
              <div>
                <p className="text-sm text-gray-200">SSE subscribers</p>
                <p className="text-[11px] text-gray-600">Live incident & anomaly streams</p>
              </div>
              <span className="text-lg font-semibold text-white tabular-nums">{integ?.sse_subscriber_total ?? 0}</span>
            </div>
          </div>
        </section>

        <section className="rounded-xl border border-white/10 bg-white/[0.02] p-4">
          <div className="flex items-center gap-2 mb-4">
            <Database size={15} className="text-indigo-400" />
            <h2 className="text-sm font-semibold text-white">Runtime</h2>
          </div>
          <dl className="space-y-2 text-sm">
            {[
              ["Environment", rt?.environment],
              ["Ollama model", rt?.ollama_model],
              ["Fast model", rt?.ollama_fast_model],
              ["Active chat sessions", integ?.active_sessions >= 0 ? integ.active_sessions : "—"],
              ["Latency samples", lat?.samples ?? 0],
              ["Platform", rt?.platform],
            ].map(([k, v]) => (
              <div key={k} className="flex justify-between gap-4 py-1.5 border-b border-white/5 last:border-0">
                <dt className="text-gray-500 text-xs">{k}</dt>
                <dd className="text-gray-200 text-xs font-mono text-right truncate max-w-[60%]">{v ?? "—"}</dd>
              </div>
            ))}
          </dl>
        </section>
      </div>

      {integ?.sse_subscribers && (
        <section className="rounded-xl border border-white/10 bg-white/[0.02] p-4">
          <h2 className="text-sm font-semibold text-white mb-3">SSE streams</h2>
          <div className="flex flex-wrap gap-2">
            {Object.entries(integ.sse_subscribers).map(([stream, count]) => (
              <span
                key={stream}
                className="text-xs font-mono px-2.5 py-1 rounded-md border border-white/10 bg-black/20 text-gray-300"
              >
                {stream}: <span className="text-white font-semibold">{count}</span>
              </span>
            ))}
          </div>
        </section>
      )}

      <p className="mt-6 text-[11px] text-gray-600">
        Prometheus self-scrape: <code className="text-gray-500">GET /api/v1/metrics</code>
        {" · "}
        FastAPI instrumentator: <code className="text-gray-500">GET /metrics</code>
      </p>
    </PageShell>
  );
}
