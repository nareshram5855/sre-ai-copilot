import { useState, useEffect } from "react";
import {
  Shield, AlertTriangle, CheckCircle, Zap, Radio, Server,
  ChevronRight, Stethoscope, Activity, ExternalLink,
  Database, GitBranch, Clock, Gauge, Copy, Check,
} from "lucide-react";
import axios from "axios";
import { fleetHealthDisplay } from "../utils/fleetHealth.js";

/* ─── helpers ────────────────────────────────────────────────────────────── */

const HEALTH = {
  healthy:  { border: "border-emerald-800/50", bg: "bg-emerald-950/20", badge: "text-emerald-400 bg-emerald-900/30", dot: "bg-emerald-400" },
  warning:  { border: "border-yellow-800/50",  bg: "bg-yellow-950/20",  badge: "text-yellow-300 bg-yellow-900/30",  dot: "bg-yellow-400 animate-pulse" },
  critical: { border: "border-red-800/50",     bg: "bg-red-950/30",     badge: "text-red-400 bg-red-900/30",        dot: "bg-red-500 animate-pulse" },
  unknown:  { border: "border-gray-700",       bg: "bg-gray-900/40",    badge: "text-gray-400 bg-gray-800/40",      dot: "bg-gray-500" },
};

const TOOL_ICONS = { Prometheus: Activity, Loki: Database, "OTel Collector": Radio, Promtail: GitBranch };

/* ─── sub-components ─────────────────────────────────────────────────────── */

function KpiCard({ label, value, sub, color, icon: Icon, onClick }) {
  const colors = {
    emerald: { val: "text-emerald-400", border: "border-emerald-800/40 bg-emerald-950/10" },
    red:     { val: "text-red-400",     border: "border-red-800/50 bg-red-950/15" },
    yellow:  { val: "text-yellow-300",  border: "border-yellow-800/40 bg-yellow-950/10" },
    orange:  { val: "text-orange-400",  border: "border-orange-800/40 bg-orange-950/10" },
    blue:    { val: "text-blue-400",    border: "border-blue-800/40 bg-blue-950/10" },
  };
  const c = colors[color] || colors.blue;
  return (
    <button
      onClick={onClick}
      disabled={!onClick}
      className={`w-full text-left rounded-xl border px-5 py-4 transition-all ${c.border} ${onClick ? "hover:ring-1 hover:ring-indigo-500/30 cursor-pointer" : "cursor-default"}`}
    >
      <div className="flex items-center gap-2 mb-2">
        <Icon size={14} className={c.val} />
        <span className="text-[10px] text-gray-500 uppercase tracking-widest font-semibold">{label}</span>
      </div>
      <p className={`text-3xl font-bold font-mono tabular-nums leading-none ${c.val}`}>{value}</p>
      <p className="text-[11px] text-gray-500 mt-1.5 truncate">{sub}</p>
    </button>
  );
}

function ServiceHealthCard({ svc, onAnalyze, onViewChange }) {
  const s = HEALTH[svc.health] || HEALTH.unknown;
  return (
    <div className={`rounded-xl border ${s.border} ${s.bg} px-4 py-3`}>
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-white truncate">{svc.name}</p>
          <p className="text-[10px] text-gray-500 mt-0.5">
            {svc.instances} instance{svc.instances !== 1 ? "s" : ""} · {svc.status}
          </p>
        </div>
        <span className={`shrink-0 flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full font-medium ${s.badge}`}>
          <span className={`w-1.5 h-1.5 rounded-full ${s.dot}`} />
          {svc.health}
        </span>
      </div>
      {svc.anomaly_count > 0 ? (
        <div className="flex items-center justify-between">
          <p className="text-xs text-red-300/90 flex items-center gap-1">
            <AlertTriangle size={11} />
            {svc.anomaly_count} anomal{svc.anomaly_count === 1 ? "y" : "ies"}
          </p>
          <button
            onClick={() => onAnalyze(svc.name)}
            className="text-[10px] text-indigo-400 hover:text-indigo-300 flex items-center gap-0.5"
          >
            <Stethoscope size={10} /> Analyze <ChevronRight size={10} />
          </button>
        </div>
      ) : (
        <p className="text-xs text-gray-500 flex items-center gap-1">
          <CheckCircle size={11} className="text-emerald-500/70" />
          All SLIs nominal
        </p>
      )}
    </div>
  );
}

function AnomalyStrip({ item, onAnalyze }) {
  const isCrit = item.severity === "critical";
  return (
    <div className={`flex items-start gap-3 px-3 py-2 rounded-lg border text-xs ${
      isCrit ? "border-red-800/50 bg-red-950/20" : "border-yellow-800/40 bg-yellow-950/15"
    }`}>
      <AlertTriangle size={13} className={`${isCrit ? "text-red-400" : "text-yellow-400"} shrink-0 mt-0.5`} />
      <div className="flex-1 min-w-0">
        <span className="font-semibold text-gray-200">{item.service}</span>
        <span className={`ml-2 text-[10px] px-1.5 py-0.5 rounded font-bold uppercase ${
          isCrit ? "bg-red-900/50 text-red-300" : "bg-yellow-900/40 text-yellow-300"
        }`}>
          {item.type?.replace(/_/g, " ")}
        </span>
        <p className="text-gray-400 mt-0.5 font-mono truncate">{item.label}</p>
      </div>
      <button
        onClick={() => onAnalyze(item.service)}
        className="shrink-0 text-[10px] text-indigo-400 hover:text-indigo-300 flex items-center gap-0.5"
      >
        Analyze <ChevronRight size={10} />
      </button>
    </div>
  );
}

function PortForwardBanner({ stack }) {
  const [copied, setCopied] = useState(false);
  const promDown = stack?.tools?.find((t) => t.name === "Prometheus")?.status === "down";
  const lokiDown = stack?.tools?.find((t) => t.name === "Loki")?.status === "down";
  if (!promDown && !lokiDown) return null;

  const cmd = stack?.remediation?.command || "make observability-port-forward";

  async function copyCmd() {
    try {
      await navigator.clipboard.writeText(cmd);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (_) {}
  }

  return (
    <div className="rounded-xl border border-amber-700/60 bg-amber-950/30 px-4 py-3 flex flex-col sm:flex-row sm:items-center gap-3">
      <div className="flex items-start gap-2 flex-1 min-w-0">
        <AlertTriangle size={16} className="text-amber-400 shrink-0 mt-0.5" />
        <div>
          <p className="text-sm font-semibold text-amber-200">
            Observability port-forwards stale or missing
          </p>
          <p className="text-xs text-amber-200/70 mt-0.5">
            Prometheus/Loki are DOWN from the host backend — common after Mac sleep or minikube restart.
            The port-forward daemon restarts automatically when you run:
          </p>
          <code className="mt-2 block text-xs font-mono text-amber-100 bg-black/30 rounded px-2 py-1 truncate">
            {cmd}
          </code>
        </div>
      </div>
      <button
        type="button"
        onClick={copyCmd}
        className="shrink-0 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-amber-700/50 bg-amber-900/40 text-xs font-medium text-amber-100 hover:bg-amber-900/60 transition-colors"
      >
        {copied ? <Check size={13} /> : <Copy size={13} />}
        {copied ? "Copied" : "Copy command"}
      </button>
    </div>
  );
}

function StackRow({ tool }) {
  const Icon = TOOL_ICONS[tool.name] || Server;
  const statusCls =
    tool.status === "up"   ? "text-emerald-400 bg-emerald-900/30 border-emerald-800/40" :
    tool.status === "down" ? "text-red-400 bg-red-900/30 border-red-800/40" :
    "text-gray-500 bg-gray-800/30 border-gray-700/40";
  const dotCls =
    tool.status === "up"   ? "bg-emerald-400" :
    tool.status === "down" ? "bg-red-400 animate-pulse" : "bg-gray-500";

  return (
    <div className="flex items-center gap-3 px-3 py-2.5 rounded-lg border border-gray-800/60 bg-gray-900/30">
      <div className="w-7 h-7 rounded-md bg-gray-800 flex items-center justify-center shrink-0">
        <Icon size={13} className="text-gray-400" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold text-gray-200">{tool.name}</span>
          <span className={`flex items-center gap-1 text-[10px] px-1.5 rounded border font-medium ${statusCls}`}>
            <span className={`w-1 h-1 rounded-full ${dotCls}`} />
            {tool.status}
          </span>
        </div>
        <p className="text-[10px] text-gray-600 truncate">{tool.role}</p>
      </div>
      {tool.ui_path && (
        <a href={`${tool.endpoint}${tool.ui_path}`} target="_blank" rel="noreferrer"
          className="shrink-0 text-[10px] text-indigo-400 hover:text-indigo-300">
          <ExternalLink size={11} />
        </a>
      )}
    </div>
  );
}

function SectionHeader({ title, action }) {
  return (
    <div className="flex items-center justify-between mb-3">
      <h2 className="text-[10px] font-semibold text-gray-600 uppercase tracking-widest">{title}</h2>
      {action && (
        <button
          onClick={action.onClick}
          className="text-[11px] text-indigo-400 hover:text-indigo-300 flex items-center gap-0.5 transition-colors"
        >
          {action.label} <ChevronRight size={11} />
        </button>
      )}
    </div>
  );
}

function IncidentRow({ inc, onOpen }) {
  const sev = inc.severity || inc.labels?.severity || "unknown";
  const sevCls = sev === "critical" ? "text-red-400 bg-red-900/30 border-red-800/40" :
                 sev === "warning"  ? "text-yellow-300 bg-yellow-900/30 border-yellow-800/40" :
                 "text-gray-400 bg-gray-800/30 border-gray-700/40";
  const key = inc.alert_name ? `${inc.alert_name}:${inc.namespace}` : null;
  return (
    <button
      onClick={() => onOpen && key ? onOpen(key) : onOpen?.()}
      disabled={!onOpen}
      className="w-full flex items-start gap-2 px-3 py-2 rounded-lg border border-gray-800/60 bg-gray-900/30 text-xs text-left hover:border-indigo-500/30 hover:bg-gray-900/60 transition-all group disabled:cursor-default"
    >
      <Radio size={12} className="text-gray-500 mt-0.5 shrink-0 group-hover:text-indigo-400 transition-colors" />
      <div className="flex-1 min-w-0">
        <p className="text-gray-200 font-medium truncate">{inc.name || inc.alert_name || inc.labels?.alertname || "Alert"}</p>
        <p className="text-gray-600 truncate text-[10px]">{inc.namespace || inc.labels?.namespace || inc.labels?.app || "—"}</p>
      </div>
      <span className={`shrink-0 text-[10px] px-1.5 py-0.5 rounded border font-medium uppercase ${sevCls}`}>
        {sev}
      </span>
    </button>
  );
}

// ── SLO widget ────────────────────────────────────────────────────────────────
function SloWidget({ slo }) {
  if (!slo?.services?.length) return null;
  const hasIssue = slo.services.some(s => s.status !== "ok" && s.status !== "no_data");
  return (
    <div>
      <SectionHeader title="SLO / Error Budget" />
      <div className="space-y-2">
        {slo.services.map((s) => {
          const budgetPct = s.error_budget_remaining_pct;
          const statusCls =
            s.status === "critical" ? "text-red-400" :
            s.status === "warning"  ? "text-yellow-300" :
            s.status === "no_data"  ? "text-gray-600" :
            "text-emerald-400";
          const barCls =
            s.status === "critical" ? "bg-red-500" :
            s.status === "warning"  ? "bg-yellow-400" :
            s.status === "no_data"  ? "bg-gray-700" :
            "bg-emerald-500";
          return (
            <div key={s.service} className="rounded-lg border border-gray-800/60 bg-gray-900/30 px-3 py-2">
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-medium text-gray-200">{s.service}</span>
                <span className={`text-[10px] font-mono font-semibold ${statusCls}`}>
                  {s.status === "no_data" ? "no data" : `${budgetPct?.toFixed(1) ?? "—"}% budget`}
                </span>
              </div>
              {budgetPct != null && (
                <div className="h-1 rounded-full bg-gray-800 overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all ${barCls}`}
                    style={{ width: `${Math.min(100, budgetPct)}%` }}
                  />
                </div>
              )}
              {s.burn_rate != null && (
                <p className="text-[10px] text-gray-600 mt-0.5">
                  burn rate {s.burn_rate}× · target {(s.target * 100).toFixed(1)}% SLO
                </p>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ─── main panel ─────────────────────────────────────────────────────────── */

export function CommandCenterPanel({ onAnalyzeService, onViewChange, onOpenIncident }) {
  const [watch, setWatch] = useState(null);
  const [incidents, setIncidents] = useState([]);
  const [stack, setStack] = useState(null);
  const [slo, setSlo] = useState(null);
  const [loading, setLoading] = useState(true);
  const [lastRefresh, setLastRefresh] = useState(null);
  const [streamLive, setStreamLive] = useState(false);

  useEffect(() => {
    async function fetchAll() {
      try {
        const [watchRes, incRes, stackRes, sloRes] = await Promise.allSettled([
          axios.get("/api/v1/observability/watch?minutes=10"),
          axios.get("/api/v1/webhook/alertmanager/recent?limit=8&scope=fleet"),
          axios.get("/api/v1/observability/stack"),
          axios.get("/api/v1/observability/slo?window_hours=24"),
        ]);
        if (watchRes.status === "fulfilled") setWatch(watchRes.value.data);
        if (incRes.status === "fulfilled") setIncidents(incRes.value.data || []);
        if (stackRes.status === "fulfilled") setStack(stackRes.value.data);
        if (sloRes.status === "fulfilled") setSlo(sloRes.value.data);
        setLastRefresh(new Date().toISOString().slice(11, 19));
      } finally {
        setLoading(false);
      }
    }
    fetchAll();

    // SSE: incident stream — same source as LiveIncidents (lower-frequency polling needed when live)
    let es;
    try {
      es = new EventSource("/api/v1/events/incidents/stream");
      es.onmessage = (ev) => {
        try {
          const data = JSON.parse(ev.data);
          if (data.type === "connected") {
            setStreamLive(true);
            return;
          }
          if (data.type === "heartbeat") return;
          if (data.type === "incident" && data.incident) {
            const inc = data.incident;
            setIncidents((prev) => {
              const k = `${inc.alert_name}:${inc.namespace}`;
              const filtered = prev.filter((p) => `${p.alert_name}:${p.namespace}` !== k);
              return [inc, ...filtered].slice(0, 8);
            });
            setLastRefresh(new Date().toISOString().slice(11, 19));
          }
        } catch (_) {}
      };
      es.onerror = () => setStreamLive(false);
    } catch (_) {
      setStreamLive(false);
    }

    // Background refresh — every 60s when live (SSE handles the rest), every 30s when not.
    const id = setInterval(fetchAll, streamLive ? 60_000 : 30_000);
    return () => {
      es?.close();
      clearInterval(id);
    };
  }, [streamLive]);

  const criticalSvcs = watch?.services?.filter((s) => s.health === "critical") || [];
  const fleetKpi = fleetHealthDisplay(watch, loading);
  const connectivityDown = stack?.remediation || watch?.prometheus_reachable === false;

  return (
    <div className="px-6 py-5 space-y-6 min-h-full">
      {/* page title */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-indigo-600/15 border border-indigo-500/25 flex items-center justify-center">
            <Shield size={18} className="text-indigo-400" />
          </div>
          <div>
            <h1 className="text-lg font-semibold text-white leading-none">Command Center</h1>
            <p className="text-[11px] text-gray-500 mt-0.5">Real-time fleet health · 10-minute window</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className={`text-[10px] px-2 py-0.5 rounded-full border ${
            streamLive
              ? "text-emerald-400 border-emerald-800/50 bg-emerald-950/30"
              : "text-gray-500 border-gray-700 bg-gray-900/40"
          }`}>
            {streamLive ? "Live stream" : "Polling 30s"}
          </span>
          {lastRefresh && (
            <span className="text-[10px] text-gray-600 flex items-center gap-1 tabular-nums">
              <Clock size={10} /> {lastRefresh} UTC
            </span>
          )}
        </div>
      </div>

      <PortForwardBanner stack={stack} />

      {/* KPI row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard
          label="Fleet Health"
          value={fleetKpi.value}
          sub={fleetKpi.sub}
          color={fleetKpi.color}
          icon={Shield}
        />
        <KpiCard
          label="Active Anomalies"
          value={loading ? "—" : watch?.anomaly_count ?? 0}
          sub={watch?.anomaly_count > 0 ? "Requires attention" : "All signals clear"}
          color={watch?.anomaly_count > 0 ? "red" : "emerald"}
          icon={AlertTriangle}
          onClick={() => onViewChange("observe")}
        />
        <KpiCard
          label="Critical Services"
          value={loading ? "—" : criticalSvcs.length}
          sub={criticalSvcs.length > 0 ? criticalSvcs.map((s) => s.name).join(", ") : "None degraded"}
          color={criticalSvcs.length > 0 ? "red" : "emerald"}
          icon={Zap}
          onClick={criticalSvcs.length > 0 ? () => onViewChange("observe") : null}
        />
        <KpiCard
          label="Recent Incidents"
          value={incidents.length}
          sub={incidents.length > 0 ? "View in Incidents tab" : "No recent incidents"}
          color={incidents.length > 0 ? "orange" : "emerald"}
          icon={Radio}
          onClick={incidents.length > 0 ? () => onViewChange("incidents") : null}
        />
      </div>

      {/* main content grid */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* Service health map */}
        <div className="xl:col-span-2 space-y-5">
          <div>
            <SectionHeader
              title="Service Health Map"
              action={{ label: "Open Observe", onClick: () => onViewChange("observe") }}
            />
            {loading ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {[1, 2].map((i) => (
                  <div key={i} className="h-20 rounded-xl border border-gray-800 bg-gray-900/30 animate-pulse" />
                ))}
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {(watch?.services || []).map((svc) => (
                  <ServiceHealthCard
                    key={svc.name}
                    svc={svc}
                    onAnalyze={onAnalyzeService}
                    onViewChange={onViewChange}
                  />
                ))}
                {(!watch?.services || watch.services.length === 0) && (
                  <div className="col-span-2 py-10 text-center text-xs text-gray-600">
                    {connectivityDown
                      ? "No live metrics — observability connectivity issue. Run make dev-up to restore port-forwards."
                      : "No services found — ensure Prometheus is running and services are instrumented"}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Active anomalies */}
          {(watch?.anomalies?.length > 0) && (
            <div>
              <SectionHeader
                title={`Active Anomalies (${watch.anomaly_count})`}
                action={{ label: "View charts", onClick: () => onViewChange("observe") }}
              />
              <div className="space-y-2">
                {watch.anomalies.slice(0, 5).map((a, i) => (
                  <AnomalyStrip key={i} item={a} onAnalyze={onAnalyzeService} />
                ))}
              </div>
            </div>
          )}

          {watch && !watch.anomalies?.length && !connectivityDown && (
            <div className="rounded-xl border border-emerald-800/30 bg-emerald-950/10 px-4 py-6 text-center">
              <CheckCircle size={24} className="mx-auto text-emerald-500/60 mb-2" />
              <p className="text-sm text-emerald-300/90 font-medium">No active anomalies</p>
              <p className="text-xs text-gray-600 mt-1">All SLIs within normal thresholds</p>
            </div>
          )}
        </div>

        {/* Right sidebar */}
        <div className="space-y-6">
          {/* Observability stack */}
          <div>
            <SectionHeader title="Observability Stack" />
            {stack?.tools ? (
              <div className="space-y-2">
                {stack.tools.map((tool) => <StackRow key={tool.name} tool={tool} />)}
              </div>
            ) : (
              <div className="rounded-lg border border-gray-800 bg-gray-900/30 px-3 py-4 text-center text-xs text-gray-600">
                Stack status unavailable
              </div>
            )}
          </div>

          {/* Recent incidents */}
          <div>
            <SectionHeader
              title="Recent Incidents"
              action={incidents.length > 0 ? { label: "View all", onClick: () => onViewChange("incidents") } : null}
            />
            {incidents.length > 0 ? (
              <div className="space-y-2">
                {incidents.slice(0, 5).map((inc, i) => (
                  <IncidentRow key={i} inc={inc} onOpen={onOpenIncident} />
                ))}
              </div>
            ) : (
              <div className="rounded-lg border border-gray-800 bg-gray-900/30 px-3 py-4 text-center text-xs text-gray-600">
                No incidents in last 24h
              </div>
            )}
          </div>

          {/* SLO / Error Budget */}
          <SloWidget slo={slo} />

          {/* Quick actions */}
          <div>
            <SectionHeader title="Quick Actions" />
            <div className="space-y-2">
              {[
                { label: "Run AI Analysis", desc: "Live telemetry deep-dive", icon: Stethoscope, view: "analyze" },
                { label: "View Metrics",    desc: "Grafana-style chart panels",  icon: Activity,   view: "observe" },
                { label: "Playbooks",       desc: "Runbook library",             icon: Radio,      view: "runbooks" },
              ].map(({ label, desc, icon: Icon, view }) => (
                <button
                  key={view}
                  onClick={() => onViewChange(view)}
                  className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg border border-gray-800/60 bg-gray-900/30 hover:bg-gray-900/60 hover:border-indigo-500/30 text-left transition-all group"
                >
                  <div className="w-7 h-7 rounded-md bg-indigo-600/15 border border-indigo-500/20 flex items-center justify-center shrink-0">
                    <Icon size={13} className="text-indigo-400" />
                  </div>
                  <div className="min-w-0">
                    <p className="text-xs font-medium text-gray-200 group-hover:text-white">{label}</p>
                    <p className="text-[10px] text-gray-600">{desc}</p>
                  </div>
                  <ChevronRight size={13} className="text-gray-600 group-hover:text-indigo-400 ml-auto shrink-0" />
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
