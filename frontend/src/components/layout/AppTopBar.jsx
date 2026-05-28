import { useState, useEffect } from "react";
import { Menu, X, ChevronRight, Radio, Loader2 } from "lucide-react";
import { VIEW_LABELS } from "../../config/nav.js";
import { useSystemHealth } from "../../hooks/useSystemHealth.js";
import { StatusPill } from "./StatusPill.jsx";
import { useAuth } from "../../context/AuthContext.jsx";
import { ROLE_META } from "../../config/roles.js";

export function AppTopBar({
  activeView,
  onBurger,
  navOpen,
  environment = "production",
  observeDemoActive = false,
  observeDemoService = "auth-service",
}) {
  const { health, loading, online, observabilityDegraded } = useSystemHealth();
  const { role } = useAuth();
  const roleMeta = ROLE_META[role];
  const viewLabel = VIEW_LABELS[activeView] || "Dashboard";
  const backendStatus = loading ? "loading" : online ? (observabilityDegraded ? "degraded" : "up") : "down";

  const [utcTime, setUtcTime] = useState(() => new Date().toISOString().slice(11, 19));
  const [demoLive, setDemoLive] = useState(null);

  useEffect(() => {
    const id = setInterval(() => setUtcTime(new Date().toISOString().slice(11, 19)), 1000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    if (!observeDemoActive) return;
    let cancelled = false;
    fetch("/api/v1/demo/status")
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (!cancelled) setDemoLive(d?.live ?? false);
      })
      .catch(() => {
        if (!cancelled) setDemoLive(false);
      });
    return () => {
      cancelled = true;
    };
  }, [observeDemoActive]);

  return (
    <header
      className="flex-shrink-0 z-30 relative flex flex-col"
      style={{
        background: "rgba(11,13,22,0.92)",
        borderBottom: "1px solid rgba(255,255,255,0.06)",
        backdropFilter: "blur(16px)",
      }}
    >
      {observeDemoActive && (
        <div className="observe-demo-banner">
          <div className="observe-demo-banner-inner">
            <span className="observe-demo-banner-text">
              Observability demo · {observeDemoService} · metrics · logs · traces
            </span>
            {demoLive === null ? (
              <Loader2 size={11} className="animate-spin text-indigo-300/70" />
            ) : (
              <span
                className={`observe-demo-live-badge ${demoLive ? "observe-demo-live-badge--live" : "observe-demo-live-badge--mock"}`}
              >
                <Radio size={9} className={demoLive ? "animate-pulse" : ""} />
                {demoLive ? "Live stack" : "Mock telemetry"}
              </span>
            )}
          </div>
        </div>
      )}
    <div
      className="h-12 px-4 flex items-center gap-3"
    >
      {/* Burger */}
      <button
        onClick={onBurger}
        className={`w-8 h-8 flex items-center justify-center rounded-lg transition-all ${
          navOpen
            ? "bg-indigo-500/20 text-indigo-300"
            : "text-gray-500 hover:text-gray-200 hover:bg-white/8"
        }`}
        aria-label="Toggle navigation"
      >
        {navOpen ? <X size={17} /> : <Menu size={17} />}
      </button>

      {/* vertical rule */}
      <div className="h-4 w-px bg-white/10" />

      {/* Breadcrumb */}
      <nav className="flex items-center gap-1.5 flex-1 min-w-0">
        <span className="text-[11px] text-gray-600 font-medium hidden sm:inline">SRE</span>
        <ChevronRight size={12} className="text-gray-700 hidden sm:inline shrink-0" />
        <span className="text-[13px] text-gray-200 font-semibold truncate">{viewLabel}</span>
      </nav>

      {/* Right pills */}
      <div className="flex items-center gap-1.5 shrink-0">
        <span className="hidden lg:inline text-[10px] font-mono text-gray-600 tabular-nums px-2 py-1 rounded-md"
          style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.06)" }}>
          {utcTime} UTC
        </span>

        <span className="hidden md:inline-flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-amber-400"
          style={{ background: "rgba(251,191,36,0.08)", border: "1px solid rgba(251,191,36,0.2)", borderRadius: "6px", padding: "2px 8px" }}>
          <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse" />
          {environment}
        </span>

        {/* Role badge */}
        {roleMeta && (
          <span className={`hidden sm:inline-flex items-center text-[10px] font-semibold px-2 py-1 rounded-md border ${roleMeta.badge}`}>
            {roleMeta.label}
          </span>
        )}

        {role !== "recruiter" && <StatusPill label="API" status={backendStatus} compact />}

        {online && health?.ollama_model && role !== "recruiter" && (
          <span className="hidden lg:inline text-[10px] text-gray-600 font-mono px-2 py-1 rounded-md"
            style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.06)" }}>
            {health.ollama_model}
          </span>
        )}
      </div>
    </div>
    </header>
  );
}
