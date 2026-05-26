import { useState, useEffect } from "react";
import {
  Activity, ChevronDown, ChevronUp, RefreshCw, Copy, Check,
  TriangleAlert, Zap, CheckCircle, Loader2, BookOpen,
} from "lucide-react";
import axios from "axios";
import { ExecutionDrawer } from "./ExecutionDrawer.jsx";
import { authHeaders } from "../config/api.js";

const SEV_STYLES = {
  P1: {
    card: "border-red-700 bg-red-950/40",
    badge: "bg-red-600 text-white",
    dot: "bg-red-400 animate-pulse",
    ring: "ring-1 ring-red-700",
  },
  P2: {
    card: "border-orange-700 bg-orange-950/30",
    badge: "bg-orange-600 text-white",
    dot: "bg-orange-400",
    ring: "",
  },
  P3: {
    card: "border-yellow-700/50 bg-yellow-950/20",
    badge: "bg-yellow-700 text-yellow-100",
    dot: "bg-yellow-500",
    ring: "",
  },
  P4: {
    card: "border-gray-700 bg-gray-900/40",
    badge: "bg-gray-700 text-gray-300",
    dot: "bg-gray-500",
    ring: "",
  },
};

function getSev(sev) {
  return SEV_STYLES[sev] ?? SEV_STYLES.P4;
}

function CopyBtn({ text }) {
  const [ok, setOk] = useState(false);
  function copy() {
    navigator.clipboard.writeText(text);
    setOk(true);
    setTimeout(() => setOk(false), 2000);
  }
  return (
    <button onClick={copy} className="ml-1 text-gray-500 hover:text-gray-300 flex-shrink-0" title="Copy fix">
      {ok ? <Check size={11} /> : <Copy size={11} />}
    </button>
  );
}

function incidentKey(t) {
  return `${t.alert_name}:${t.namespace}`;
}

export function LiveIncidents({ initialIncidentKey = null, onOpenAudit = null }) {
  const [all, setAll] = useState([]);
  const [expanded, setExpanded] = useState(null);
  const [loading, setLoading] = useState(false);
  const [lastFetch, setLastFetch] = useState(null);
  const [streamLive, setStreamLive] = useState(false);
  const [nsFilter, setNsFilter] = useState("all");
  const [sevFilter, setSevFilter] = useState("all");
  const [execIncident, setExecIncident] = useState(null);
  const [resolving, setResolving] = useState({});      // key → bool
  const [resolved, setResolved] = useState({});        // key → { prior_resolutions, learning }

  const upsertIncident = (incident) => {
    setAll((prev) => {
      const key = incidentKey(incident);
      const idx = prev.findIndex((t) => incidentKey(t) === key);
      if (idx >= 0) {
        const next = [...prev];
        next[idx] = incident;
        return next;
      }
      return [incident, ...prev].slice(0, 20);
    });
    setLastFetch(new Date());
  };

  async function fetchTriages() {
    setLoading(true);
    try {
      const { data } = await axios.get("/api/v1/webhook/alertmanager/recent?limit=20");
      setAll(data);
      setLastFetch(new Date());
    } catch (_) {}
    finally { setLoading(false); }
  }

  useEffect(() => {
    fetchTriages();

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
            upsertIncident(data.incident);
          }
        } catch (_) {}
      };
      es.onerror = () => setStreamLive(false);
    } catch (_) {
      setStreamLive(false);
    }

    const id = setInterval(fetchTriages, 60_000);
    return () => {
      es?.close();
      clearInterval(id);
    };
  }, []);

  // Deep-link: auto-expand and (optionally) auto-open drawer for ?incident=key
  useEffect(() => {
    if (!initialIncidentKey || all.length === 0) return;
    const idx = all.findIndex((t) => incidentKey(t) === initialIncidentKey);
    if (idx >= 0) {
      setExpanded(idx);
    }
  }, [initialIncidentKey, all]);

  async function markResolved(t) {
    const key = incidentKey(t);
    setResolving((p) => ({ ...p, [key]: true }));
    try {
      const { data } = await axios.post(
        `/api/v1/incidents/${encodeURIComponent(key)}/resolve`,
        {
          outcome: "resolved",
          alert_name: t.alert_name,
          namespace: t.namespace,
          final_summary: `Manually marked resolved by engineer. Suggested fix: ${t.suggested_fix || "n/a"}`,
          triage_summary: t.summary || "",
          servicenow_number: t.servicenow_number || "",
        },
        { headers: authHeaders() },
      );
      setResolved((p) => ({ ...p, [key]: data }));
    } catch (e) {
      setResolved((p) => ({ ...p, [key]: { error: e.response?.data?.detail || e.message } }));
    } finally {
      setResolving((p) => ({ ...p, [key]: false }));
    }
  }

  // Unique namespaces for filter tabs
  const namespaces = ["all", ...Array.from(new Set(all.map((t) => t.namespace))).sort()];

  const filtered = all.filter((t) => {
    if (nsFilter !== "all" && t.namespace !== nsFilter) return false;
    if (sevFilter === "critical" && !["P1", "P2"].includes(t.severity)) return false;
    if (sevFilter === "low" && !["P3", "P4"].includes(t.severity)) return false;
    return true;
  });

  function age(iso) {
    const diff = Math.floor((Date.now() - new Date(iso)) / 1000);
    if (diff < 60) return `${diff}s ago`;
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    return `${Math.floor(diff / 3600)}h ago`;
  }

  return (
    <div className="bg-sre-surface border border-sre-border rounded-xl overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-sre-border">
        <div className="flex items-center gap-2">
          <Activity size={14} className="text-sre-accent" />
          <span className="text-sm font-semibold text-white">Live Auto-Triaged Alerts</span>
          {all.length > 0 && (
            <span className="text-xs bg-sre-accent text-white rounded-full px-2 py-0.5 font-mono">
              {all.length}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <span className={`text-[10px] px-2 py-0.5 rounded-full border ${
            streamLive
              ? "text-emerald-400 border-emerald-800/50 bg-emerald-950/30"
              : "text-gray-500 border-sre-border bg-sre-bg"
          }`}>
            {streamLive ? "Live stream" : "Polling 60s"}
          </span>
          {lastFetch && (
            <span className="text-xs text-gray-600">updated {age(lastFetch.toISOString())}</span>
          )}
          <button onClick={fetchTriages} className="text-gray-500 hover:text-gray-300" title="Refresh">
            <RefreshCw size={13} className={loading ? "animate-spin" : ""} />
          </button>
        </div>
      </div>

      {/* Filters */}
      {all.length > 0 && (
        <div className="flex items-center gap-3 px-4 py-2 border-b border-sre-border bg-sre-bg/50 flex-wrap">
          {/* Namespace tabs */}
          <div className="flex gap-1 flex-wrap">
            {namespaces.map((ns) => (
              <button
                key={ns}
                onClick={() => { setNsFilter(ns); setExpanded(null); }}
                className={`text-xs px-2.5 py-1 rounded-md transition-colors ${
                  nsFilter === ns
                    ? "bg-sre-accent text-white"
                    : "bg-sre-surface text-gray-400 hover:text-gray-200"
                }`}
              >
                {ns === "all" ? "All namespaces" : ns}
              </button>
            ))}
          </div>
          <div className="w-px h-4 bg-sre-border" />
          {/* Severity filter */}
          <div className="flex gap-1">
            {[["all", "All"], ["critical", "P1–P2"], ["low", "P3–P4"]].map(([v, label]) => (
              <button
                key={v}
                onClick={() => { setSevFilter(v); setExpanded(null); }}
                className={`text-xs px-2.5 py-1 rounded-md transition-colors ${
                  sevFilter === v
                    ? "bg-sre-accent text-white"
                    : "bg-sre-surface text-gray-400 hover:text-gray-200"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Execution drawer — slides in from right when Fix is clicked */}
      {execIncident && (
        <ExecutionDrawer
          incident={execIncident}
          onClose={() => setExecIncident(null)}
          onOpenAudit={onOpenAudit}
        />
      )}

      {/* List */}
      <div className="divide-y divide-sre-border/50">
        {filtered.length === 0 ? (
          <div className="text-center py-8 text-gray-600 text-xs">
            <Activity size={20} className="mx-auto mb-2 opacity-20" />
            {all.length === 0
              ? "No auto-triaged alerts yet — the OOM demo app will trigger alerts here automatically."
              : "No alerts match the current filters."}
          </div>
        ) : (
          filtered.map((t, i) => {
            const s = getSev(t.severity);
            const isOpen = expanded === i;
            const key = incidentKey(t);
            const resolveResult = resolved[key];
            return (
              <div key={i} className={`border-l-4 ${s.card} ${s.ring}`} style={{ borderLeftColor: undefined }}>
                {/* Row */}
                <button
                  className="w-full flex items-center gap-2.5 px-4 py-3 text-left hover:bg-white/5 transition-colors"
                  onClick={() => setExpanded(isOpen ? null : i)}
                >
                  {/* Severity badge */}
                  <span className={`text-xs font-bold px-1.5 py-0.5 rounded flex-shrink-0 ${s.badge}`}>
                    {t.severity}
                  </span>

                  {/* Alert name */}
                  <span className="text-sm text-white font-medium flex-1 truncate">{t.alert_name}</span>

                  {/* Fire count */}
                  {t.fire_count > 1 && (
                    <span className="text-xs text-gray-500 flex-shrink-0 bg-sre-bg rounded px-1.5 py-0.5" title={`Fired ${t.fire_count} times`}>
                      ×{t.fire_count}
                    </span>
                  )}

                  {/* Integration badges */}
                  {t.servicenow_number && (
                    <span className="text-[10px] text-blue-300 bg-blue-900/30 border border-blue-800/40 rounded px-1.5 flex-shrink-0 font-mono" title="ServiceNow incident">
                      {t.servicenow_number}
                    </span>
                  )}
                  {t.pagerduty_triggered && (
                    <span className="text-[10px] text-orange-300 bg-orange-900/30 border border-orange-800/40 rounded px-1.5 flex-shrink-0" title="PagerDuty triggered">
                      PD
                    </span>
                  )}

                  {/* Escalate */}
                  {t.escalate && (
                    <span className="flex items-center gap-1 text-xs text-red-400 flex-shrink-0" title="Escalation required">
                      <TriangleAlert size={11} /> Escalate
                    </span>
                  )}

                  {/* Mark Resolved button */}
                  {!resolveResult?.outcome && (
                    <button
                      onClick={(e) => { e.stopPropagation(); markResolved(t); }}
                      disabled={resolving[key]}
                      className="flex items-center gap-1 text-xs bg-emerald-600/15 hover:bg-emerald-600/30 border border-emerald-600/30 text-emerald-300 px-2 py-0.5 rounded-md transition-colors flex-shrink-0 disabled:opacity-50"
                      title="Mark resolved + teach the system (writes to learning RAG)"
                    >
                      {resolving[key] ? <Loader2 size={10} className="animate-spin" /> : <CheckCircle size={10} />}
                      Resolve
                    </button>
                  )}

                  {/* Execute Fix button */}
                  <button
                    onClick={(e) => { e.stopPropagation(); setExecIncident(t); }}
                    className="flex items-center gap-1 text-xs bg-indigo-600/20 hover:bg-indigo-600/40 border border-indigo-600/30 text-indigo-300 px-2 py-0.5 rounded-md transition-colors flex-shrink-0"
                    title="Launch ExecutorAgent to autonomously fix this incident"
                  >
                    <Zap size={10} /> Fix
                  </button>

                  {/* Namespace */}
                  <span className="text-xs text-gray-500 flex-shrink-0 font-mono">{t.namespace}</span>

                  {/* Age */}
                  <span className="text-xs text-gray-600 flex-shrink-0 w-16 text-right">{age(t.triaged_at)}</span>

                  {isOpen ? <ChevronUp size={13} className="text-gray-500" /> : <ChevronDown size={13} className="text-gray-500" />}
                </button>

                {/* Inline resolve feedback */}
                {resolveResult && !resolveResult.error && (
                  <div className="mx-4 mb-2 mt-1 text-xs text-emerald-300 bg-emerald-950/40 border border-emerald-800/40 rounded-md px-3 py-2 flex items-center gap-2">
                    <BookOpen size={11} />
                    <span>
                      Marked resolved.
                      {resolveResult.learning?.ingested ? " Learning ingested." : ` ${resolveResult.learning?.reason || "Learning skipped."}`}
                      {resolveResult.prior_resolutions > 0 && (
                        <> Learned from <strong>{resolveResult.prior_resolutions}</strong> prior resolution{resolveResult.prior_resolutions === 1 ? "" : "s"}.</>
                      )}
                      {resolveResult.side_effects?.servicenow_attached && " RCA attached to ServiceNow."}
                      {resolveResult.side_effects?.pagerduty_resolved && " PagerDuty resolved."}
                    </span>
                  </div>
                )}
                {resolveResult?.error && (
                  <div className="mx-4 mb-2 mt-1 text-xs text-red-300 bg-red-950/40 border border-red-800/40 rounded-md px-3 py-2">
                    Resolve failed: {resolveResult.error}
                  </div>
                )}

                {/* Expanded detail */}
                {isOpen && (
                  <div className="px-4 pb-4 space-y-3 border-t border-white/5 pt-3">
                    {/* Pod */}
                    <div className="flex items-start gap-2">
                      <span className="text-xs text-gray-500 w-14 flex-shrink-0 pt-0.5">Pod</span>
                      <span className="text-xs font-mono text-gray-300">{t.pod}</span>
                    </div>

                    {/* AI summary */}
                    <div className="flex items-start gap-2">
                      <span className="text-xs text-gray-500 w-14 flex-shrink-0 pt-0.5">Summary</span>
                      <span className="text-xs text-gray-300 leading-relaxed">{t.summary}</span>
                    </div>

                    {/* Suggested fix */}
                    <div className="flex items-start gap-2">
                      <span className="text-xs text-gray-500 w-14 flex-shrink-0 pt-0.5">Fix</span>
                      <div className="flex-1 flex items-start gap-1">
                        <span className="text-xs font-mono bg-black/40 border border-white/10 rounded px-2 py-1.5 text-green-300 leading-relaxed flex-1 whitespace-pre-wrap">
                          {t.suggested_fix}
                        </span>
                        <CopyBtn text={t.suggested_fix} />
                      </div>
                    </div>

                    {/* Meta */}
                    <div className="flex gap-3 text-xs text-gray-600 pt-1 flex-wrap">
                      <span>LLM: {t.llm_tier}</span>
                      <span>·</span>
                      <span>Triaged {age(t.triaged_at)}</span>
                      {t.fire_count > 1 && <><span>·</span><span>Fired {t.fire_count}×</span></>}
                      {t.servicenow_number && <><span>·</span><span>ServiceNow {t.servicenow_number}</span></>}
                      {t.pagerduty_triggered && <><span>·</span><span>PagerDuty paged</span></>}
                    </div>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
