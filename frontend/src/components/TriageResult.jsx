import { Shield, Zap, CheckCircle, AlertTriangle, Clock, ChevronDown, ChevronUp, Terminal } from "lucide-react";
import { useState } from "react";
import { ExecutionDrawer } from "./ExecutionDrawer.jsx";

const SEVERITY_CONFIG = {
  P1: { color: "text-red-400", bg: "bg-red-950 border-red-800", badge: "bg-red-500", label: "Critical" },
  P2: { color: "text-yellow-400", bg: "bg-yellow-950 border-yellow-800", badge: "bg-yellow-500", label: "High" },
  P3: { color: "text-blue-400", bg: "bg-blue-950 border-blue-800", badge: "bg-blue-500", label: "Medium" },
};

export function TriageResult({ result, alertName = "UnknownAlert", namespace = "default" }) {
  const [showIncidents, setShowIncidents] = useState(false);
  const [showDrawer,    setShowDrawer]    = useState(false);
  const cfg = SEVERITY_CONFIG[result.severity] || SEVERITY_CONFIG.P2;
  const confidencePct = Math.round((result.confidence || 0) * 100);

  // Shape expected by ExecutionDrawer
  const incident = {
    alert_name: alertName,
    namespace,
    summary:    result.reasoning || result.suggested_fix || "",
  };

  return (
    <>
    {showDrawer && <ExecutionDrawer incident={incident} onClose={() => setShowDrawer(false)} />}
    <div className={`bg-sre-surface border rounded-xl p-5 space-y-4 ${cfg.bg}`}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className={`text-3xl font-black ${cfg.color}`}>{result.severity}</span>
          <div>
            <p className={`text-sm font-semibold ${cfg.color}`}>{cfg.label}</p>
            {result.escalate && (
              <p className="text-xs text-red-400 flex items-center gap-1">
                <AlertTriangle size={10} /> Escalate now
              </p>
            )}
          </div>
        </div>
        <ConfidenceMeter pct={confidencePct} />
      </div>

      {/* Estimated impact */}
      {result.estimated_impact && (
        <div className="flex items-center gap-2 text-xs text-gray-400">
          <Clock size={12} />
          <span>Impact: {result.estimated_impact}</span>
        </div>
      )}

      {/* Reasoning */}
      <Section icon={<Shield size={14} />} title="Reasoning">
        <p className="text-sm text-gray-300">{result.reasoning}</p>
      </Section>

      {/* Suggested fix */}
      <Section icon={<Zap size={14} className="text-yellow-400" />} title="Suggested Fix">
        <pre className="text-xs text-green-300 bg-sre-bg border border-sre-border rounded-lg p-3 overflow-x-auto whitespace-pre-wrap">
          {result.suggested_fix}
        </pre>
      </Section>

      {/* Similar incidents */}
      {result.similar_incidents?.length > 0 && (
        <div>
          <button
            onClick={() => setShowIncidents((v) => !v)}
            className="flex items-center gap-2 text-xs text-gray-400 hover:text-gray-200 transition-colors w-full text-left"
          >
            <CheckCircle size={14} className="text-sre-accent" />
            <span>{result.similar_incidents.length} similar past incident(s) found</span>
            {showIncidents ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
          </button>
          {showIncidents && (
            <ul className="mt-2 space-y-1.5">
              {result.similar_incidents.map((inc, i) => (
                <li key={i} className="text-xs text-gray-400 bg-sre-bg border border-sre-border rounded-lg px-3 py-2">
                  {inc}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {/* Execute Fix — launches ExecutorAgent */}
      <button
        onClick={() => setShowDrawer(true)}
        className="w-full flex items-center justify-center gap-2 border border-indigo-600/40 bg-indigo-600/10 hover:bg-indigo-600/20 text-indigo-300 text-sm font-semibold py-2.5 rounded-xl transition-colors"
      >
        <Terminal size={14} />
        Auto-Fix with ExecutorAgent
      </button>
    </div>
    </>
  );
}

function ConfidenceMeter({ pct }) {
  const color = pct >= 80 ? "bg-green-400" : pct >= 60 ? "bg-yellow-400" : "bg-red-400";
  return (
    <div className="text-right">
      <p className="text-xs text-gray-500 mb-1">Confidence</p>
      <p className="text-lg font-bold text-white">{pct}%</p>
      <div className="w-20 h-1.5 bg-sre-border rounded-full mt-1">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function Section({ icon, title, children }) {
  return (
    <div>
      <div className="flex items-center gap-1.5 mb-2 text-gray-400">
        {icon}
        <span className="text-xs font-semibold uppercase tracking-wider">{title}</span>
      </div>
      {children}
    </div>
  );
}
