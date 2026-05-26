import { useState, useEffect, useRef, useCallback } from "react";
import {
  LayoutDashboard, Activity, Zap, BookOpen, Stethoscope,
  Shield, X, Circle, BookMarked, ShieldCheck, User, Gauge, Lock, LogOut, Play,
} from "lucide-react";
import axios from "axios";
import { useSystemHealth } from "../hooks/useSystemHealth.js";
import { useAuth } from "../context/AuthContext.jsx";
import { canViewPage, ROLE_META } from "../config/roles.js";
import { LoginModal } from "./LoginModal.jsx";

const NAV_ITEMS = [
  { id: "dashboard", label: "Command Center", icon: LayoutDashboard, section: "OVERVIEW" },
  { id: "observe",   label: "Observe",        icon: Activity,        section: "OVERVIEW" },
  { id: "incidents", label: "Incidents",       icon: Zap,             section: "OPERATIONS" },
  { id: "runbooks",  label: "Playbooks",       icon: BookOpen,        section: "OPERATIONS" },
  { id: "audit",     label: "Audit Log",       icon: ShieldCheck,     section: "OPERATIONS" },
  { id: "profiler",  label: "App Profiler",    icon: Gauge,           section: "OPERATIONS" },
  { id: "analyze",   label: "AI Analysis",     icon: Stethoscope,     section: "INTELLIGENCE" },
  { id: "docs",      label: "Architecture",    icon: BookMarked,      section: "INTELLIGENCE" },
  { id: "resume",    label: "Resume",          icon: User,            section: "CAREER" },
  { id: "demo",      label: "Demo Hub",        icon: Play,            section: "CAREER" },
];

const SECTIONS = ["OVERVIEW", "OPERATIONS", "INTELLIGENCE", "CAREER"];

export function NavDrawer({ activeView, onViewChange, open, onClose }) {
  const { health } = useSystemHealth();
  const { role, logout } = useAuth();
  const [showLogin, setShowLogin] = useState(false);
  const modelLabel = health?.ollama_model || "model loading…";
  const environmentLabel = health?.environment || "production";
  const [incidentCount, setIncidentCount] = useState(0);
  const [anomalyCount, setAnomalyCount]   = useState(0);
  const [fleetHealth, setFleetHealth]     = useState(null);
  const [streamLive, setStreamLive]       = useState(false);
  const [prevCount, setPrevCount]         = useState(0);
  const debounceRef = useRef(null);

  const fetchWatch = useCallback(async () => {
    try {
      const { data } = await axios.get("/api/v1/observability/watch?minutes=10");
      setAnomalyCount(data.anomaly_count || 0);
      setFleetHealth(data.overall_health || null);
    } catch (_) {}
  }, []);

  useEffect(() => {
    async function pollAlerts() {
      try {
        const { data } = await axios.get("/api/v1/webhook/alertmanager/recent?limit=20");
        const count = data.length;
        if (count > prevCount && activeView !== "incidents") setIncidentCount(count);
        setPrevCount(count);
      } catch (_) {}
    }
    pollAlerts();
    const id = setInterval(pollAlerts, 15_000);
    return () => clearInterval(id);
  }, [activeView, prevCount]);

  useEffect(() => {
    fetchWatch();
    let es;
    try {
      es = new EventSource("/api/v1/events/anomalies/stream");
      es.onmessage = (ev) => {
        try {
          const d = JSON.parse(ev.data);
          if (d.type === "connected") { setStreamLive(true); return; }
          if (d.type === "heartbeat") return;
          if (d.type === "anomaly") {
            if (d.anomaly?.anomaly_count != null) setAnomalyCount(d.anomaly.anomaly_count);
            if (d.anomaly?.overall_health)        setFleetHealth(d.anomaly.overall_health);
            clearTimeout(debounceRef.current);
            debounceRef.current = setTimeout(fetchWatch, 500);
          }
        } catch (_) {}
      };
      es.onerror = () => setStreamLive(false);
    } catch (_) { setStreamLive(false); }
    const id = setInterval(fetchWatch, 60_000);
    return () => { es?.close(); clearInterval(id); clearTimeout(debounceRef.current); };
  }, [fetchWatch]);

  useEffect(() => {
    if (!open) return;
    const handler = (e) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, onClose]);

  function handleNav(id) {
    if (!canViewPage(role, id)) {
      setShowLogin(true);
      return;
    }
    if (id === "incidents") setIncidentCount(0);
    if (id === "observe")   setAnomalyCount(0);
    onViewChange(id);
    onClose();
  }

  function getBadge(id) {
    if (id === "incidents" && incidentCount > 0 && activeView !== "incidents")
      return { n: incidentCount, cls: "bg-red-500/90 text-white" };
    if (id === "observe" && anomalyCount > 0 && activeView !== "observe")
      return { n: anomalyCount, cls: "bg-orange-500/90 text-white" };
    return null;
  }

  const healthColor =
    fleetHealth === "healthy"  ? { ring: "border-emerald-500/25", bg: "bg-emerald-500/10", dot: "bg-emerald-400",       text: "text-emerald-300" } :
    fleetHealth === "critical" ? { ring: "border-red-500/30",     bg: "bg-red-500/10",     dot: "bg-red-400 animate-pulse", text: "text-red-300"     } :
    fleetHealth === "warning"  ? { ring: "border-yellow-500/25",  bg: "bg-yellow-500/10",  dot: "bg-yellow-400 animate-pulse", text: "text-yellow-300" } :
                                 { ring: "border-gray-700/40",    bg: "bg-gray-800/20",    dot: "bg-gray-600",           text: "text-gray-400"   };

  return (
    <>
      {/* ── Backdrop ─────────────────────────────────────── */}
      <div
        onClick={onClose}
        className={`fixed inset-0 z-40 transition-all duration-300 ${
          open
            ? "bg-black/60 backdrop-blur-[2px] pointer-events-auto"
            : "bg-transparent pointer-events-none"
        }`}
      />

      {/* ── Drawer ───────────────────────────────────────── */}
      <div
        style={{ boxShadow: "32px 0 80px rgba(0,0,0,0.9), 0 0 0 1px rgba(255,255,255,0.05)" }}
        className={`fixed left-0 top-12 bottom-0 z-50 w-72 flex flex-col
          bg-[#0b0d16] border-r border-white/[0.06]
          transition-transform duration-300 ease-[cubic-bezier(0.32,0.72,0,1)]
          ${open ? "translate-x-0" : "-translate-x-full"}`}
      >
        {/* ── Brand header ─────────────────────────────── */}
        <div className="flex items-center justify-between px-5 py-5">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl flex items-center justify-center shrink-0"
              style={{ background: "linear-gradient(135deg,#6366f1,#4f46e5)", boxShadow: "0 4px 20px rgba(99,102,241,0.4)" }}>
              <Shield size={17} className="text-white" />
            </div>
            <div>
              <p className="text-[13px] font-bold text-white tracking-tight leading-none">SRE Copilot</p>
              <p className="text-[10px] text-gray-600 mt-0.5 font-medium capitalize">On-prem · {environmentLabel}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-7 h-7 flex items-center justify-center rounded-lg text-gray-600 hover:text-gray-300 hover:bg-white/8 transition-all"
          >
            <X size={14} />
          </button>
        </div>

        {/* ── Fleet status card ────────────────────────── */}
        {fleetHealth && (
          <div className={`mx-4 mb-2 px-4 py-3 rounded-xl border ${healthColor.ring} ${healthColor.bg} flex items-center gap-3`}>
            <div className={`w-2.5 h-2.5 rounded-full shrink-0 ${healthColor.dot}`} />
            <div className="flex-1 min-w-0">
              <p className={`text-xs font-semibold capitalize ${healthColor.text}`}>Fleet {fleetHealth}</p>
              {anomalyCount > 0
                ? <p className="text-[10px] text-gray-500">{anomalyCount} anomal{anomalyCount === 1 ? "y" : "ies"} active</p>
                : <p className="text-[10px] text-gray-600">All signals normal</p>
              }
            </div>
            <span className={`text-[9px] px-1.5 py-1 rounded-md border font-semibold uppercase tracking-wide ${
              streamLive
                ? "text-emerald-400 border-emerald-700/50 bg-emerald-950/40"
                : "text-gray-600 border-gray-700/50"
            }`}>
              {streamLive ? "Live" : "Poll"}
            </span>
          </div>
        )}

        {/* ── Nav sections ─────────────────────────────── */}
        <nav className="flex-1 px-3 py-3 overflow-y-auto">
          {SECTIONS.map((section, si) => {
            const items = NAV_ITEMS.filter((i) => i.section === section);
            return (
              <div key={section} className={si > 0 ? "mt-5" : ""}>
                <p className="px-3 mb-2 text-[10px] font-bold text-gray-700 uppercase tracking-[0.15em]">
                  {section}
                </p>
                <div className="space-y-0.5">
                  {items.map(({ id, label, icon: Icon }) => {
                    const active  = activeView === id;
                    const badge   = getBadge(id);
                    const allowed = canViewPage(role, id);
                    return (
                      <button
                        key={id}
                        onClick={() => handleNav(id)}
                        className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-left transition-all group relative ${
                          !allowed
                            ? "opacity-50 cursor-pointer"
                            : active
                              ? "bg-indigo-500/[0.15]"
                              : "hover:bg-white/[0.04]"
                        }`}
                      >
                        {/* icon box */}
                        <div className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 transition-all ${
                          active && allowed
                            ? "bg-indigo-600 shadow-lg shadow-indigo-900/60"
                            : "bg-white/[0.06] group-hover:bg-white/[0.09]"
                        }`}>
                          <Icon size={15} className={active && allowed ? "text-white" : "text-gray-500 group-hover:text-gray-300"} />
                        </div>

                        {/* label */}
                        <span className={`flex-1 text-sm font-medium transition-colors ${
                          active && allowed ? "text-white" : "text-gray-400 group-hover:text-gray-200"
                        }`}>
                          {label}
                        </span>

                        {/* locked indicator */}
                        {!allowed && (
                          <Lock size={11} className="text-gray-600 shrink-0" />
                        )}

                        {/* badge */}
                        {badge && allowed && (
                          <span className={`${badge.cls} text-[10px] rounded-full px-2 py-0.5 font-bold min-w-[20px] text-center tabular-nums`}>
                            {badge.n}
                          </span>
                        )}

                        {/* active dot */}
                        {active && allowed && (
                          <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 shrink-0" />
                        )}
                      </button>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </nav>

        {/* ── Footer ───────────────────────────────────── */}
        <div className="px-4 py-4 border-t border-white/[0.05] space-y-3">
          {/* Role badge + switch */}
          <div className="flex items-center gap-2">
            <span className={`flex-1 text-[11px] font-semibold px-2.5 py-1.5 rounded-lg border ${ROLE_META[role]?.badge} truncate`}>
              {ROLE_META[role]?.label ?? role}
            </span>
            <button
              onClick={() => setShowLogin(true)}
              className="text-[10px] px-2.5 py-1.5 rounded-lg border border-white/10 text-gray-400 hover:text-white hover:border-white/25 transition-all font-medium whitespace-nowrap"
            >
              Switch role
            </button>
            {role !== "recruiter" && (
              <button
                onClick={logout}
                title="Back to Recruiter / Guest"
                className="w-7 h-7 flex items-center justify-center rounded-lg border border-white/10 text-gray-600 hover:text-red-400 hover:border-red-500/30 transition-all"
              >
                <LogOut size={13} />
              </button>
            )}
          </div>

          {/* Model / stack info */}
          <div className="flex items-center gap-2 mb-1.5">
            <div className="w-4 h-4 rounded bg-indigo-600/30 flex items-center justify-center">
              <Circle size={6} className="text-indigo-400 fill-indigo-400" />
            </div>
            <span className="text-[11px] text-gray-500 font-mono">{modelLabel} · On-prem</span>
          </div>
          <div className="flex items-center gap-2 text-[10px] text-gray-700">
            {["Prometheus", "Loki", "LangGraph"].map((t) => (
              <span key={t} className="flex items-center gap-1">
                <span className="w-1 h-1 rounded-full bg-emerald-500" />{t}
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* Role picker modal */}
      {showLogin && <LoginModal onClose={() => setShowLogin(false)} />}
    </>
  );
}
