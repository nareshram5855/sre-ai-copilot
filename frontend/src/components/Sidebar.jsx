import { useState, useEffect } from "react";
import { AlertTriangle, Activity, BookOpen, FileSearch, Shield, Radio, Stethoscope } from "lucide-react";
import axios from "axios";

const navItems = [
  { id: "triage",    label: "Alert Triage",     icon: AlertTriangle },
  { id: "incidents", label: "Live Incidents",   icon: Radio },
  { id: "runbooks",  label: "Runbook Executor", icon: BookOpen },
  { id: "rca",       label: "Auto RCA",         icon: FileSearch },
  { id: "analyze",   label: "Incident Analysis",icon: Stethoscope },
  { id: "metrics",   label: "Anomaly Watch",    icon: Activity, disabled: true, badge: "Soon" },
];

export function Sidebar({ activeView, onViewChange }) {
  const [incidentCount, setIncidentCount] = useState(0);
  const [prevCount, setPrevCount] = useState(0);

  useEffect(() => {
    async function poll() {
      try {
        const { data } = await axios.get("/api/v1/webhook/alertmanager/recent?limit=20");
        const count = data.length;
        if (count > prevCount && activeView !== "incidents") {
          setIncidentCount(count);
        }
        setPrevCount(count);
      } catch (_) {}
    }
    poll();
    const id = setInterval(poll, 15_000);
    return () => clearInterval(id);
  }, [activeView, prevCount]);

  function handleNav(id) {
    if (id === "incidents") setIncidentCount(0);
    onViewChange(id);
  }

  return (
    <aside className="w-52 flex-shrink-0 bg-sre-surface border-r border-sre-border flex flex-col">
      {/* Brand */}
      <div className="px-4 py-4 border-b border-sre-border">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 bg-sre-accent rounded-lg flex items-center justify-center flex-shrink-0">
            <Shield size={16} className="text-white" />
          </div>
          <div>
            <p className="text-sm font-bold text-white tracking-tight">SRE Copilot</p>
            <p className="text-xs text-gray-500">Mistral 7B · On-Prem</p>
          </div>
        </div>
      </div>

      {/* Section label */}
      <div className="px-4 pt-4 pb-1">
        <p className="text-xs font-semibold text-gray-600 uppercase tracking-widest">Incident Tools</p>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-2 pb-4 space-y-0.5">
        {navItems.map(({ id, label, icon: Icon, disabled, badge }) => (
          <button
            key={id}
            onClick={() => !disabled && handleNav(id)}
            disabled={disabled}
            className={`
              w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-left text-sm transition-colors
              ${activeView === id
                ? "bg-indigo-600/20 text-indigo-300 border border-indigo-600/30"
                : disabled
                  ? "text-gray-700 cursor-not-allowed"
                  : "text-gray-400 hover:bg-white/5 hover:text-gray-200"
              }
            `}
          >
            <Icon size={15} className={activeView === id ? "text-indigo-400" : ""} />
            <span className="flex-1 text-sm">{label}</span>
            {/* Live incident badge */}
            {id === "incidents" && incidentCount > 0 && activeView !== "incidents" && (
              <span className="bg-red-500 text-white text-xs rounded-full px-1.5 py-0.5 font-bold min-w-[20px] text-center">
                {incidentCount}
              </span>
            )}
            {/* Disabled badge */}
            {badge && (
              <span className="text-xs bg-gray-800 text-gray-500 px-1.5 py-0.5 rounded font-mono">
                {badge}
              </span>
            )}
          </button>
        ))}
      </nav>

      <StatusFooter />
    </aside>
  );
}

function StatusFooter() {
  const [health, setHealth] = useState(null);

  useEffect(() => {
    function check() {
      fetch("/health")
        .then((r) => r.json())
        .then((d) => setHealth(d))
        .catch(() => setHealth(null));
    }
    check();
    const id = setInterval(check, 30_000);
    return () => clearInterval(id);
  }, []);

  const online = health?.status === "healthy";

  return (
    <div className="px-4 py-3 border-t border-sre-border space-y-1.5">
      <div className="flex items-center gap-1.5">
        <span className={`w-1.5 h-1.5 rounded-full ${online ? "bg-green-400" : health === null ? "bg-yellow-400 animate-pulse" : "bg-red-400"}`} />
        <span className="text-xs text-gray-500">{online ? "Systems operational" : health === null ? "Connecting..." : "Backend offline"}</span>
      </div>
      {online && (
        <p className="text-xs text-gray-700 font-mono">{health.ollama_model}</p>
      )}
    </div>
  );
}
