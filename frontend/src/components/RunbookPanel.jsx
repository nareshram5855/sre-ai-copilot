import { useState } from "react";
import axios from "axios";
import {
  BookOpen, Send, Loader2, CheckCircle, AlertTriangle,
  XCircle, Terminal, Clock, ChevronDown, ChevronUp,
} from "lucide-react";

const RISK_CONFIG = {
  SAFE: {
    icon: CheckCircle,
    color: "text-green-400",
    bg: "bg-green-950 border-green-800",
    badge: "bg-green-900 text-green-300 border-green-700",
    label: "Safe",
  },
  REQUIRES_APPROVAL: {
    icon: AlertTriangle,
    color: "text-yellow-400",
    bg: "bg-yellow-950 border-yellow-800",
    badge: "bg-yellow-900 text-yellow-300 border-yellow-700",
    label: "Needs Approval",
  },
  DANGEROUS: {
    icon: XCircle,
    color: "text-red-400",
    bg: "bg-red-950 border-red-800",
    badge: "bg-red-900 text-red-300 border-red-700",
    label: "Dangerous",
  },
};

const EXAMPLE_ALERTS = [
  {
    alert_name: "KubePodCrashLooping",
    description: "ping-identity-auth pod OOMKilled, restarting every 30s in iam namespace",
  },
  {
    alert_name: "HighCPUUsage",
    description: "SiteMinder policy server at 95% CPU, SSO logins timing out",
  },
];

const inputClass =
  "w-full bg-sre-bg border border-sre-border rounded-lg px-3 py-2 text-sm text-gray-100 placeholder-gray-600 focus:outline-none focus:border-sre-accent transition-colors";

export function RunbookPanel() {
  const [form, setForm] = useState({ alert_name: "", description: "", environment: "production" });
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [approved, setApproved] = useState(new Set());

  async function handleSubmit(e) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);
    setApproved(new Set());

    try {
      const { data } = await axios.post("/api/v1/runbook/execute", form);
      setResult(data);
    } catch (err) {
      setError(err.response?.data?.detail || err.message || "Runbook request failed");
    } finally {
      setLoading(false);
    }
  }

  function toggleApproval(stepNum) {
    setApproved((prev) => {
      const next = new Set(prev);
      next.has(stepNum) ? next.delete(stepNum) : next.add(stepNum);
      return next;
    });
  }

  return (
    <div className="p-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-xl font-bold text-white flex items-center gap-2">
          <BookOpen size={20} className="text-sre-accent" />
          Runbook Executor
        </h1>
        <p className="text-sm text-gray-500 mt-1">
          Finds the best matching runbook and classifies each step by risk level. Dangerous steps require explicit approval.
        </p>
      </div>

      {/* Quick load */}
      <div className="mb-5">
        <p className="text-xs text-gray-500 mb-2">Quick load:</p>
        <div className="flex gap-2 flex-wrap">
          {EXAMPLE_ALERTS.map((ex) => (
            <button
              key={ex.alert_name}
              onClick={() => { setForm({ ...form, ...ex }); setResult(null); setError(null); }}
              className="text-xs px-3 py-1.5 bg-sre-surface border border-sre-border rounded-lg text-gray-400 hover:text-white hover:border-sre-accent transition-colors"
            >
              {ex.alert_name}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="bg-sre-surface border border-sre-border rounded-xl p-5 space-y-4">
            <Field label="Alert Name" required>
              <input
                type="text"
                value={form.alert_name}
                onChange={(e) => setForm({ ...form, alert_name: e.target.value })}
                placeholder="e.g. KubePodCrashLooping"
                required
                className={inputClass}
              />
            </Field>

            <Field label="Description" required>
              <textarea
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                placeholder="Describe what's happening..."
                rows={3}
                required
                className={`${inputClass} resize-none`}
              />
            </Field>

            <Field label="Environment">
              <select
                value={form.environment}
                onChange={(e) => setForm({ ...form, environment: e.target.value })}
                className={inputClass}
              >
                <option value="production">production</option>
                <option value="staging">staging</option>
                <option value="development">development</option>
              </select>
            </Field>
          </div>

          {error && (
            <div className="bg-red-950 border border-red-800 rounded-lg px-4 py-3 text-sm text-red-300">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full flex items-center justify-center gap-2 bg-sre-accent hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold py-3 rounded-xl transition-colors"
          >
            {loading ? (
              <><Loader2 size={16} className="animate-spin" /> Finding runbook...</>
            ) : (
              <><Send size={16} /> Get Runbook Steps</>
            )}
          </button>
        </form>

        {/* Result */}
        <div>
          {result ? (
            <RunbookResult result={result} approved={approved} onToggle={toggleApproval} />
          ) : (
            <div className="h-full flex items-center justify-center border border-dashed border-sre-border rounded-xl text-gray-600 text-sm p-8 text-center">
              Submit an alert to see the matching runbook steps with risk classification
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function RunbookResult({ result, approved, onToggle }) {
  const [expanded, setExpanded] = useState(true);

  if (!result.steps?.length) {
    return (
      <div className="bg-sre-surface border border-sre-border rounded-xl p-5 text-center text-gray-500 text-sm">
        No matching runbook found in the knowledge base.
      </div>
    );
  }

  const safeCount = result.safe_steps_count ?? 0;
  const pendingCount = result.pending_approval?.length ?? 0;

  return (
    <div className="bg-sre-surface border border-sre-border rounded-xl p-5 space-y-4">
      {/* Runbook header */}
      <div className="flex items-start justify-between">
        <div>
          <h3 className="text-sm font-semibold text-white">{result.runbook_title}</h3>
          <div className="flex items-center gap-3 mt-1 text-xs text-gray-500">
            {result.runbook_source && <span className="text-sre-accent">{result.runbook_source}</span>}
            {result.estimated_time && (
              <span className="flex items-center gap-1">
                <Clock size={10} /> {result.estimated_time}
              </span>
            )}
            {result.similarity_score > 0 && (
              <span>Match: {Math.round(result.similarity_score * 100)}%</span>
            )}
          </div>
        </div>
        <div className="flex gap-2 text-xs">
          <span className="text-green-400">{safeCount} safe</span>
          {pendingCount > 0 && <span className="text-yellow-400">{pendingCount} pending</span>}
        </div>
      </div>

      {/* Approval notice */}
      {pendingCount > 0 && (
        <div className="flex items-center gap-2 text-xs text-yellow-300 bg-yellow-950 border border-yellow-800 rounded-lg px-3 py-2">
          <AlertTriangle size={12} />
          {pendingCount} step{pendingCount !== 1 ? "s" : ""} require approval before execution.
        </div>
      )}

      {/* Steps */}
      <button
        onClick={() => setExpanded((v) => !v)}
        className="flex items-center gap-2 text-xs text-gray-400 hover:text-white w-full text-left"
      >
        {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        {result.steps.length} steps
      </button>

      {expanded && (
        <div className="space-y-2">
          {result.steps.map((step) => (
            <StepCard
              key={step.number}
              step={step}
              approved={approved.has(step.number)}
              onToggle={() => onToggle(step.number)}
            />
          ))}
        </div>
      )}

      <div className="text-xs text-gray-600 pt-1 border-t border-sre-border">
        LLM tier: {result.llm_tier} · Agent never executes commands directly — use Runbook Executor for guided remediation
      </div>
    </div>
  );
}

function StepCard({ step, approved, onToggle }) {
  const risk = RISK_CONFIG[step.risk_level] || RISK_CONFIG.REQUIRES_APPROVAL;
  const Icon = risk.icon;
  const needsApproval = step.risk_level !== "SAFE";

  return (
    <div className={`rounded-lg border p-3 space-y-2 ${risk.bg}`}>
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 flex-1 min-w-0">
          <span className="text-xs text-gray-500 flex-shrink-0">#{step.number}</span>
          <p className="text-xs text-gray-300 truncate">{step.description}</p>
        </div>
        <span className={`flex items-center gap-1 text-xs border rounded px-1.5 py-0.5 flex-shrink-0 ${risk.badge}`}>
          <Icon size={10} />
          {risk.label}
        </span>
      </div>

      {step.command && (
        <div className="flex items-start gap-2">
          <Terminal size={11} className="text-gray-600 mt-0.5 flex-shrink-0" />
          <pre className="text-xs text-green-300 bg-sre-bg rounded px-2 py-1 overflow-x-auto flex-1">
            {step.command}
          </pre>
        </div>
      )}

      {step.expected_output && (
        <p className="text-xs text-gray-600 pl-5">Expected: {step.expected_output}</p>
      )}

      {needsApproval && (
        <button
          onClick={onToggle}
          className={`w-full text-xs py-1 rounded transition-colors border ${
            approved
              ? "bg-green-900 border-green-700 text-green-300"
              : "bg-sre-bg border-sre-border text-gray-400 hover:border-yellow-700 hover:text-yellow-300"
          }`}
        >
          {approved ? "✓ Approved — ready to run" : "Approve this step"}
        </button>
      )}
    </div>
  );
}

function Field({ label, required, children }) {
  return (
    <div>
      <label className="block text-xs text-gray-400 mb-1.5">
        {label} {required && <span className="text-red-400">*</span>}
      </label>
      {children}
    </div>
  );
}
