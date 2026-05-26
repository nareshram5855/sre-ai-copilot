import { useEffect, useMemo, useState } from "react";
import {
  Shield, RefreshCw, FileText, CheckCircle, XCircle,
  AlertTriangle, Search, Filter, X,
} from "lucide-react";
import axios from "axios";
import { PageHeader } from "./layout/PageHeader.jsx";
import { PageShell } from "./layout/PageShell.jsx";
import { StatusPill } from "./layout/StatusPill.jsx";
import { EmptyState } from "./layout/EmptyState.jsx";

const STATUS_STYLES = {
  success:  { color: "text-emerald-400", bg: "bg-emerald-950/30 border-emerald-800/40", icon: CheckCircle },
  error:    { color: "text-red-400",     bg: "bg-red-950/30 border-red-800/40",         icon: XCircle },
  denied:   { color: "text-red-400",     bg: "bg-red-950/30 border-red-800/40",         icon: XCircle },
  started:  { color: "text-blue-400",    bg: "bg-blue-950/30 border-blue-800/40",       icon: RefreshCw },
  approved: { color: "text-emerald-400", bg: "bg-emerald-950/30 border-emerald-800/40", icon: CheckCircle },
  pending:  { color: "text-yellow-300",  bg: "bg-yellow-950/30 border-yellow-800/40",   icon: AlertTriangle },
};

function fmtTime(iso) {
  if (!iso) return "—";
  try { return new Date(iso).toLocaleString(); } catch { return iso; }
}

function tryParseJSON(text) {
  if (!text) return null;
  try { return JSON.parse(text); } catch { return null; }
}

function CommandPreview({ raw }) {
  const parsed = tryParseJSON(raw);
  if (!parsed) {
    return raw ? <code className="text-[10px] font-mono text-gray-400 break-all">{raw}</code> : <span className="text-gray-700 italic text-[10px]">empty</span>;
  }
  return (
    <pre className="text-[10px] font-mono text-gray-400 whitespace-pre-wrap break-all leading-relaxed">
      {JSON.stringify(parsed, null, 2)}
    </pre>
  );
}

function AuditRow({ entry, expanded, onToggle }) {
  const style = STATUS_STYLES[entry.status] || STATUS_STYLES.started;
  const Icon = style.icon;
  return (
    <div className={`border rounded-lg ${style.bg} transition-colors`}>
      <button
        onClick={onToggle}
        className="w-full flex items-start gap-3 px-3 py-2.5 text-left hover:bg-white/[0.03]"
      >
        <Icon size={13} className={`${style.color} flex-shrink-0 mt-0.5`} />
        <div className="flex-1 min-w-0">
          <div className="flex items-baseline gap-2 flex-wrap">
            <code className="text-xs font-mono text-gray-200 font-semibold">{entry.action_type}</code>
            {entry.tool_name && (
              <span className="text-[11px] text-gray-500 font-mono">{entry.tool_name}</span>
            )}
            <span className={`text-[10px] uppercase tracking-wider font-semibold ${style.color}`}>
              {entry.status}
            </span>
            {entry.approval_required && (
              <span className="text-[10px] bg-yellow-900/40 text-yellow-300 border border-yellow-700/30 rounded px-1.5 font-semibold">
                APPROVAL
              </span>
            )}
          </div>
          <div className="flex gap-3 text-[10px] text-gray-600 mt-1 font-mono truncate">
            <span>{fmtTime(entry.timestamp)}</span>
            {entry.execution_id && <span>exec: {entry.execution_id.slice(0, 12)}…</span>}
            {entry.incident_id && <span>inc: {entry.incident_id.slice(0, 16)}</span>}
            {entry.approved_by && <span>by: {entry.approved_by}</span>}
          </div>
        </div>
      </button>
      {expanded && (
        <div className="px-3 pb-3 border-t border-white/5 pt-2 space-y-2">
          {entry.error && (
            <div className="text-[11px] text-red-300 bg-red-950/40 border border-red-900/40 rounded px-2 py-1.5">
              <span className="text-red-500 font-semibold">error:</span> {entry.error}
            </div>
          )}
          {entry.command_details && (
            <div>
              <p className="text-[10px] text-gray-500 uppercase tracking-wider font-semibold mb-1">Command Details</p>
              <div className="bg-black/40 border border-white/5 rounded p-2 overflow-x-auto">
                <CommandPreview raw={entry.command_details} />
              </div>
            </div>
          )}
          <div className="grid grid-cols-2 gap-2 text-[10px] text-gray-500">
            <div><span className="text-gray-600">execution_id:</span> <span className="font-mono break-all text-gray-400">{entry.execution_id || "—"}</span></div>
            <div><span className="text-gray-600">incident_id:</span> <span className="font-mono break-all text-gray-400">{entry.incident_id || "—"}</span></div>
            <div><span className="text-gray-600">actor:</span> {entry.actor || "system"}</div>
            <div><span className="text-gray-600">id:</span> {entry.id}</div>
          </div>
        </div>
      )}
    </div>
  );
}

export function AuditPanel({ initialExecutionId = "" }) {
  const [entries, setEntries] = useState([]);
  const [facets, setFacets] = useState({ action_types: [], statuses: [] });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [expanded, setExpanded] = useState({});
  const [filters, setFilters] = useState({
    execution_id: initialExecutionId,
    action_type: "",
    status: "",
    search: "",
  });
  const [limit, setLimit] = useState(100);

  async function fetchEntries() {
    setLoading(true);
    setError(null);
    try {
      const params = { limit };
      if (filters.execution_id) params.execution_id = filters.execution_id;
      if (filters.action_type)  params.action_type  = filters.action_type;
      if (filters.status)       params.status       = filters.status;
      const { data } = await axios.get("/api/v1/audit/executions", { params });
      setEntries(data.entries || []);
    } catch (e) {
      setError(e.response?.data?.detail || e.message);
    } finally {
      setLoading(false);
    }
  }

  async function fetchFacets() {
    try {
      const { data } = await axios.get("/api/v1/audit/facets");
      setFacets(data);
    } catch {}
  }

  useEffect(() => { fetchFacets(); }, []);
  useEffect(() => { fetchEntries(); /* eslint-disable-line */ }, [filters.execution_id, filters.action_type, filters.status, limit]);

  const visible = useMemo(() => {
    if (!filters.search) return entries;
    const q = filters.search.toLowerCase();
    return entries.filter((e) =>
      (e.action_type || "").toLowerCase().includes(q) ||
      (e.tool_name || "").toLowerCase().includes(q) ||
      (e.execution_id || "").toLowerCase().includes(q) ||
      (e.incident_id || "").toLowerCase().includes(q) ||
      (e.command_details || "").toLowerCase().includes(q) ||
      (e.error || "").toLowerCase().includes(q)
    );
  }, [entries, filters.search]);

  const counts = useMemo(() => {
    const grouped = { success: 0, error: 0, pending: 0, other: 0 };
    for (const e of entries) {
      if (e.status in grouped) grouped[e.status] += 1;
      else grouped.other += 1;
    }
    return grouped;
  }, [entries]);

  return (
    <PageShell>
      <PageHeader
        icon={Shield}
        title="Audit Log"
        description="Append-only execution audit trail — every tool invocation, approval gate, and shell command is recorded."
        badges={
          <div className="flex gap-2 items-center">
            <StatusPill label={`${entries.length} entries`} status="up" compact />
            {counts.error > 0 && <StatusPill label={`${counts.error} errors`} status="down" compact />}
            {counts.pending > 0 && <StatusPill label={`${counts.pending} pending`} status="loading" compact />}
          </div>
        }
        actions={
          <button
            onClick={fetchEntries}
            disabled={loading}
            className="flex items-center gap-1.5 text-xs bg-sre-surface border border-sre-border rounded-md px-3 py-1.5 hover:border-indigo-500/40 text-gray-300"
          >
            <RefreshCw size={11} className={loading ? "animate-spin" : ""} /> Refresh
          </button>
        }
      />

      {/* Filters */}
      <div className="bg-sre-surface border border-sre-border rounded-xl p-4 mb-4 grid grid-cols-1 md:grid-cols-4 gap-3">
        <div className="md:col-span-2">
          <label className="text-[10px] text-gray-500 uppercase tracking-wider font-semibold flex items-center gap-1.5 mb-1">
            <Search size={10} /> Search
          </label>
          <input
            type="text"
            value={filters.search}
            onChange={(e) => setFilters({ ...filters, search: e.target.value })}
            placeholder="Search across action, tool, IDs, commands, errors…"
            className="input-field"
          />
        </div>
        <div>
          <label className="text-[10px] text-gray-500 uppercase tracking-wider font-semibold flex items-center gap-1.5 mb-1">
            <Filter size={10} /> Action type
          </label>
          <select
            value={filters.action_type}
            onChange={(e) => setFilters({ ...filters, action_type: e.target.value })}
            className="input-field"
          >
            <option value="">All actions</option>
            {facets.action_types.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        </div>
        <div>
          <label className="text-[10px] text-gray-500 uppercase tracking-wider font-semibold flex items-center gap-1.5 mb-1">
            <Filter size={10} /> Status
          </label>
          <select
            value={filters.status}
            onChange={(e) => setFilters({ ...filters, status: e.target.value })}
            className="input-field"
          >
            <option value="">All statuses</option>
            {facets.statuses.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
        <div className="md:col-span-3">
          <label className="text-[10px] text-gray-500 uppercase tracking-wider font-semibold mb-1 block">
            Execution ID
          </label>
          <input
            type="text"
            value={filters.execution_id}
            onChange={(e) => setFilters({ ...filters, execution_id: e.target.value })}
            placeholder="Filter by exact execution_id…"
            className="input-field"
          />
        </div>
        <div>
          <label className="text-[10px] text-gray-500 uppercase tracking-wider font-semibold mb-1 block">
            Limit
          </label>
          <select
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
            className="input-field"
          >
            {[50, 100, 200, 500].map((n) => <option key={n} value={n}>{n}</option>)}
          </select>
        </div>
        {(filters.execution_id || filters.action_type || filters.status || filters.search) && (
          <div className="md:col-span-4 flex justify-end">
            <button
              onClick={() => setFilters({ execution_id: "", action_type: "", status: "", search: "" })}
              className="text-[11px] text-gray-500 hover:text-gray-300 flex items-center gap-1"
            >
              <X size={11} /> Clear filters
            </button>
          </div>
        )}
      </div>

      {error && (
        <div className="border border-red-800 bg-red-950/30 rounded-xl p-3 text-sm text-red-300 mb-4">
          {error}
        </div>
      )}

      <div className="space-y-2">
        {visible.length === 0 ? (
          <EmptyState
            icon={FileText}
            title="No audit entries match the filters"
            description="Try clearing filters or trigger an ExecutorAgent run to populate the log."
          />
        ) : (
          visible.map((e) => (
            <AuditRow
              key={`${e.id}-${e.timestamp}`}
              entry={e}
              expanded={!!expanded[e.id]}
              onToggle={() => setExpanded((p) => ({ ...p, [e.id]: !p[e.id] }))}
            />
          ))
        )}
      </div>
    </PageShell>
  );
}
