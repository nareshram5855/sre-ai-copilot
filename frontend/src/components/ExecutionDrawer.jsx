import { useState, useEffect, useRef } from "react";
import {
  X, CheckCircle, XCircle, Loader2, Terminal, ShieldAlert,
  Check, Zap, Database, FileText, Activity, Brain, ChevronRight,
  Radio, GitBranch, Cpu, Code2, AlertTriangle, Copy,
} from "lucide-react";
import axios from "axios";

// ── Agent activity label map ──────────────────────────────────────────────────
const GATHER_ICONS = { pods: Database, logs: FileText, metrics: Activity };
const GATHER_LABELS = { pods: "get_pods", logs: "get_logs", metrics: "top_pods" };

const STATUS_CONFIG = {
  running:          { color: "text-blue-400",   label: "Running",           icon: Loader2,     spin: true  },
  waiting_approval: { color: "text-yellow-400", label: "Awaiting Approval", icon: ShieldAlert, spin: false },
  resolved:         { color: "text-green-400",  label: "Resolved",          icon: CheckCircle, spin: false },
  escalated:        { color: "text-orange-400", label: "Escalated",         icon: XCircle,     spin: false },
  failed:           { color: "text-red-400",    label: "Failed",            icon: XCircle,     spin: false },
};

// ── Animation helper ──────────────────────────────────────────────────────────
function FadeIn({ children, delay = 0 }) {
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => setVisible(true), delay);
    return () => clearTimeout(t);
  }, [delay]);
  return (
    <div style={{
      opacity: visible ? 1 : 0,
      transform: visible ? "translateY(0)" : "translateY(8px)",
      transition: "opacity 0.3s ease, transform 0.3s ease",
    }}>
      {children}
    </div>
  );
}

// ── Typing dots ───────────────────────────────────────────────────────────────
function ThinkingDots() {
  return (
    <span className="inline-flex gap-0.5 ml-1">
      {[0, 1, 2].map(i => (
        <span
          key={i}
          className="w-1 h-1 rounded-full bg-blue-400"
          style={{ animation: `pulse 1.2s ease-in-out ${i * 0.2}s infinite` }}
        />
      ))}
    </span>
  );
}

// ── Gather pill ───────────────────────────────────────────────────────────────
function GatherPill({ label, status, output }) {
  const [open, setOpen] = useState(false);
  const Icon = GATHER_ICONS[label] || Database;
  return (
    <div className="border border-sre-border rounded-lg overflow-hidden text-xs">
      <button
        onClick={() => status === "done" && setOpen(v => !v)}
        className="w-full flex items-center gap-2 px-3 py-2 bg-sre-surface hover:bg-white/5 transition-colors"
      >
        {status === "running"
          ? <Loader2 size={12} className="text-blue-400 animate-spin flex-shrink-0" />
          : <CheckCircle size={12} className="text-green-400 flex-shrink-0" />
        }
        <Icon size={11} className="text-gray-400 flex-shrink-0" />
        <span className={status === "running" ? "text-blue-300" : "text-gray-300"}>
          {GATHER_LABELS[label]}
        </span>
        <span className="text-gray-600 ml-auto">{label}</span>
        {status === "done" && output && (
          <ChevronRight size={11} className={`text-gray-600 transition-transform ${open ? "rotate-90" : ""}`} />
        )}
      </button>
      {open && output && (
        <pre className="px-3 py-2 bg-black/30 font-mono text-green-300 text-[10px] leading-relaxed whitespace-pre-wrap border-t border-sre-border overflow-x-auto">
          {output.slice(0, 600)}{output.length > 600 ? "\n..." : ""}
        </pre>
      )}
    </div>
  );
}

// ── Step card ─────────────────────────────────────────────────────────────────
function StepCard({ step, index }) {
  const [open, setOpen] = useState(true);
  return (
    <FadeIn delay={index * 80}>
      <div className={`border rounded-xl overflow-hidden text-xs ${
        step.write
          ? "border-orange-700/50 bg-orange-950/20"
          : "border-sre-border bg-sre-surface"
      }`}>
        {/* Header */}
        <button
          onClick={() => setOpen(v => !v)}
          className="w-full flex items-center gap-2 px-3 py-2.5 text-left hover:bg-white/5 transition-colors"
        >
          <span className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold flex-shrink-0 ${
            step.write ? "bg-orange-900/60 text-orange-300" : "bg-indigo-900/60 text-indigo-300"
          }`}>{index + 1}</span>
          <code className={`font-mono font-semibold ${step.write ? "text-orange-300" : "text-blue-300"}`}>
            {step.action}
          </code>
          {step.write && (
            <span className="text-[10px] bg-orange-900/40 text-orange-400 border border-orange-700/30 rounded px-1 py-0.5 font-mono flex-shrink-0">
              WRITE
            </span>
          )}
          <span className="text-gray-600 font-mono truncate flex-1 text-left">
            ({Object.entries(step.args || {}).map(([k,v]) => `${k}="${v}"`).join(", ")})
          </span>
          <ChevronRight size={11} className={`text-gray-600 flex-shrink-0 transition-transform ${open ? "rotate-90" : ""}`} />
        </button>

        {open && (
          <div className="px-3 pb-3 space-y-2 border-t border-white/5">
            {/* Thought */}
            <div className="flex gap-2 pt-2">
              <Brain size={11} className="text-purple-400 flex-shrink-0 mt-0.5" />
              <p className="text-gray-400 italic leading-relaxed">{step.thought}</p>
            </div>
            {/* Observation */}
            {step.observation && (
              <pre className="font-mono text-green-300 bg-black/30 rounded p-2 overflow-x-auto leading-relaxed whitespace-pre-wrap text-[10px]">
                {step.observation.slice(0, 500)}{step.observation.length > 500 ? "\n..." : ""}
              </pre>
            )}
          </div>
        )}
      </div>
    </FadeIn>
  );
}

// ── Code Fix Panel ────────────────────────────────────────────────────────────
const ISSUE_COLORS = {
  memory_leak:    { border: "border-red-700/50",    bg: "bg-red-950/20",    badge: "bg-red-900/40 text-red-300 border-red-700/30" },
  stack_overflow: { border: "border-purple-700/50", bg: "bg-purple-950/20", badge: "bg-purple-900/40 text-purple-300 border-purple-700/30" },
  null_reference: { border: "border-yellow-700/50", bg: "bg-yellow-950/20", badge: "bg-yellow-900/40 text-yellow-300 border-yellow-700/30" },
  connection_leak:{ border: "border-orange-700/50", bg: "bg-orange-950/20", badge: "bg-orange-900/40 text-orange-300 border-orange-700/30" },
  infinite_retry: { border: "border-pink-700/50",   bg: "bg-pink-950/20",   badge: "bg-pink-900/40 text-pink-300 border-pink-700/30" },
  config_error:   { border: "border-blue-700/50",   bg: "bg-blue-950/20",   badge: "bg-blue-900/40 text-blue-300 border-blue-700/30" },
};

function CodeFixCard({ suggestion, index }) {
  const [open, setOpen] = useState(index === 0);
  const [copied, setCopied] = useState(false);
  const colors = ISSUE_COLORS[suggestion.issue_type] || ISSUE_COLORS.config_error;

  function copyCode() {
    navigator.clipboard.writeText(suggestion.code_example || "");
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <FadeIn delay={index * 100}>
      <div className={`border rounded-xl overflow-hidden text-xs ${colors.border} ${colors.bg}`}>
        <button
          onClick={() => setOpen(v => !v)}
          className="w-full flex items-center gap-2 px-3 py-2.5 text-left hover:bg-white/5 transition-colors"
        >
          <AlertTriangle size={12} className="text-yellow-400 flex-shrink-0" />
          <span className="font-semibold text-gray-200 flex-1">{suggestion.title}</span>
          <span className={`text-[10px] border rounded px-1.5 py-0.5 font-mono flex-shrink-0 ${colors.badge}`}>
            {suggestion.issue_type.replace(/_/g, "-")}
          </span>
          <ChevronRight size={11} className={`text-gray-500 flex-shrink-0 transition-transform ${open ? "rotate-90" : ""}`} />
        </button>

        {open && (
          <div className="px-3 pb-3 space-y-2.5 border-t border-white/5">
            {/* Root cause */}
            <div className="pt-2 space-y-1">
              <p className="text-[10px] text-gray-500 uppercase tracking-wider font-semibold">Root Cause</p>
              <p className="text-gray-300 leading-relaxed">{suggestion.root_cause}</p>
            </div>
            {/* Code pattern */}
            <div className="space-y-1">
              <p className="text-[10px] text-gray-500 uppercase tracking-wider font-semibold">What to Look For</p>
              <p className="text-gray-400 leading-relaxed italic">{suggestion.code_pattern}</p>
            </div>
            {/* Fix suggestion */}
            <div className="space-y-1">
              <p className="text-[10px] text-gray-500 uppercase tracking-wider font-semibold">Fix</p>
              <p className="text-gray-300 leading-relaxed">{suggestion.fix_suggestion}</p>
            </div>
            {/* Code example */}
            {suggestion.code_example && (
              <div className="space-y-1">
                <div className="flex items-center justify-between">
                  <p className="text-[10px] text-gray-500 uppercase tracking-wider font-semibold">Code Example</p>
                  <button
                    onClick={copyCode}
                    className="flex items-center gap-1 text-[10px] text-gray-500 hover:text-gray-300 transition-colors"
                  >
                    <Copy size={10} />
                    {copied ? "Copied!" : "Copy"}
                  </button>
                </div>
                <pre className="font-mono text-green-300 bg-black/40 rounded-lg p-2.5 overflow-x-auto leading-relaxed whitespace-pre text-[10px] border border-white/5">
                  {suggestion.code_example}
                </pre>
              </div>
            )}
          </div>
        )}
      </div>
    </FadeIn>
  );
}

// ── Main drawer ───────────────────────────────────────────────────────────────
export function ExecutionDrawer({ incident, onClose }) {
  const [execId,        setExecId]        = useState(null);
  const [status,        setStatus]        = useState("idle");   // idle|running|waiting_approval|resolved|escalated|failed
  const [gatherState,   setGatherState]   = useState({});       // {pods|logs|metrics: {status, output}}
  const [steps,         setSteps]         = useState([]);
  const [thinking,      setThinking]      = useState(false);
  const [currentThought,setCurrentThought]= useState("");
  const [pendingAction, setPendingAction] = useState(null);
  const [finalSummary,  setFinalSummary]  = useState("");
  const [codeSuggestions,setCodeSuggestions] = useState([]);
  const [alertCategory,  setAlertCategory]   = useState("");
  const [starting,      setStarting]      = useState(false);
  const [approving,     setApproving]     = useState(false);
  const [error,         setError]         = useState(null);
  const esRef   = useRef(null);           // EventSource ref
  const bottomRef = useRef(null);
  const incidentId = `${incident.alert_name}-${incident.namespace}`;

  // Auto-scroll as steps arrive
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [steps.length, thinking]);

  // Cleanup EventSource on unmount
  useEffect(() => () => esRef.current?.close(), []);

  function connectSSE(execId) {
    esRef.current?.close();
    const es = new EventSource(
      `/api/v1/incidents/${incidentId}/execution/${execId}/stream`
    );
    esRef.current = es;

    es.onmessage = (e) => {
      const event = JSON.parse(e.data);
      handleEvent(event, execId);
    };
    es.onerror = () => {
      es.close();
      // Fallback: poll once to get final state
      axios.get(`/api/v1/incidents/${incidentId}/execution/${execId}`)
        .then(r => {
          setStatus(r.data.status);
          setSteps(r.data.scratchpad || []);
          setPendingAction(r.data.pending_action);
          setFinalSummary(r.data.final_summary || "");
          setCodeSuggestions(r.data.code_suggestions || []);
          setThinking(false);
        }).catch(() => {});
    };
  }

  function handleEvent(event, execId) {
    switch (event.type) {
      case "start":
        setStatus("running");
        setThinking(false);
        if (event.data.category) setAlertCategory(event.data.category);
        break;

      case "gather":
        setGatherState(prev => ({
          ...prev,
          [event.data.label]: { status: event.data.status, output: event.data.output || "" },
        }));
        break;

      case "thinking":
        setThinking(true);
        setCurrentThought(event.data.message);
        break;

      case "decision":
        setThinking(false);
        if (event.data.done) {
          setStatus(event.data.escalate ? "escalated" : "resolved");
          setFinalSummary(event.data.thought);
        } else if (event.data.action in {"rollout_restart":1,"patch_resources":1,"scale":1,"delete_pod":1}) {
          setStatus("waiting_approval");
          setPendingAction({ action: event.data.action, args: event.data.args, thought: event.data.thought });
        }
        break;

      case "step":
        setThinking(false);
        setSteps(prev => {
          const exists = prev.some(s => s.action === event.data.action &&
            JSON.stringify(s.args) === JSON.stringify(event.data.args));
          return exists ? prev : [...prev, event.data];
        });
        if (event.data.write) {
          setPendingAction(null);
        }
        break;

      case "approved":
        setStatus("running");
        setThinking(true);
        setCurrentThought(`Executing ${event.data.action}...`);
        break;

      case "done":
        setThinking(false);
        esRef.current?.close();
        // Refresh final state from REST
        axios.get(`/api/v1/incidents/${incidentId}/execution/${execId}`)
          .then(r => {
            setStatus(r.data.status);
            setSteps(r.data.scratchpad || []);
            setFinalSummary(r.data.final_summary || "");
            setPendingAction(r.data.pending_action);
            setCodeSuggestions(r.data.code_suggestions || []);
          }).catch(() => {});
        break;

      case "code_fix":
        setCodeSuggestions(event.data.suggestions || []);
        break;

      case "heartbeat":
      default:
        break;
    }
  }

  async function start() {
    setStarting(true);
    setError(null);
    setSteps([]);
    setGatherState({});
    setThinking(false);
    setFinalSummary("");
    setPendingAction(null);
    setCodeSuggestions([]);
    setAlertCategory("");
    try {
      const { data } = await axios.post(`/api/v1/incidents/${incidentId}/execute`, {
        alert_name:     incident.alert_name,
        namespace:      incident.namespace,
        triage_summary: incident.summary,
      });
      setExecId(data.execution_id);
      setStatus("running");
      connectSSE(data.execution_id);
      // Also handle case where graph finished before SSE connects
      if (data.pending_action) setPendingAction(data.pending_action);
      if (data.scratchpad?.length) setSteps(data.scratchpad);
    } catch (e) {
      setError(e.response?.data?.detail || e.message);
      setStatus("failed");
    } finally {
      setStarting(false);
    }
  }

  async function approve() {
    setApproving(true);
    setError(null);
    try {
      connectSSE(execId);   // re-connect SSE before resuming
      await axios.post(`/api/v1/incidents/${incidentId}/approve/${execId}`);
      setPendingAction(null);
    } catch (e) {
      setError(e.response?.data?.detail || e.message);
    } finally {
      setApproving(false);
    }
  }

  const cfg        = STATUS_CONFIG[status];
  const StatusIcon = cfg?.icon;
  const gatherDone = Object.values(gatherState).filter(g => g.status === "done").length;
  const gatherTotal = 3;

  return (
    <div className="fixed inset-0 z-50 flex justify-end" onClick={onClose}>
      <div
        className="relative w-full max-w-2xl h-full bg-sre-bg border-l border-sre-border flex flex-col shadow-2xl"
        onClick={e => e.stopPropagation()}
      >
        {/* ── Header ── */}
        <div className="flex items-center gap-3 px-5 py-4 border-b border-sre-border flex-shrink-0 bg-sre-surface">
          <div className="w-7 h-7 rounded-lg bg-indigo-600/20 border border-indigo-600/30 flex items-center justify-center flex-shrink-0">
            <Terminal size={13} className="text-indigo-400" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <p className="text-sm font-semibold text-white truncate">ExecutorAgent</p>
              {alertCategory && (
                <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded border flex-shrink-0 ${
                  alertCategory === "CONTROL_PLANE" ? "bg-purple-900/40 text-purple-300 border-purple-700/30" :
                  alertCategory === "ETCD"          ? "bg-red-900/40 text-red-300 border-red-700/30" :
                  alertCategory === "OOM_MEMORY"    ? "bg-orange-900/40 text-orange-300 border-orange-700/30" :
                  alertCategory === "REPLICA"       ? "bg-blue-900/40 text-blue-300 border-blue-700/30" :
                  "bg-gray-900/40 text-gray-400 border-gray-700/30"
                }`}>
                  {alertCategory}
                </span>
              )}
            </div>
            <p className="text-xs text-gray-500">
              <span className="text-indigo-400">{incident.alert_name}</span>
              <span className="mx-1 text-gray-700">·</span>
              <span className="font-mono">{incident.namespace}</span>
            </p>
          </div>
          {cfg && (
            <div className={`flex items-center gap-1.5 text-xs font-medium ${cfg.color}`}>
              <StatusIcon size={13} className={cfg.spin ? "animate-spin" : ""} />
              {cfg.label}
            </div>
          )}
          <button onClick={onClose} className="text-gray-500 hover:text-gray-300 p-1 rounded hover:bg-sre-border transition-colors ml-1">
            <X size={15} />
          </button>
        </div>

        {/* ── Body ── */}
        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">

          {/* Not started — preflight */}
          {status === "idle" && !starting && (
            <FadeIn>
              <div className="space-y-4">
                <div className="bg-sre-surface border border-sre-border rounded-xl p-4">
                  <div className="flex items-center gap-2 mb-3">
                    <GitBranch size={13} className="text-sre-accent" />
                    <p className="text-xs font-semibold text-gray-300 uppercase tracking-wider">LangGraph Execution Plan</p>
                  </div>
                  <div className="space-y-2">
                    {[
                      { icon: Radio,    color: "text-blue-400",   label: "Parallel Gather",  desc: "get_pods · get_logs · top_pods — all simultaneously" },
                      { icon: Brain,    color: "text-purple-400", label: "Reason",            desc: "LLM analyses merged cluster state" },
                      { icon: Cpu,      color: "text-green-400",  label: "Act (read)",        desc: "describe_pod, logs — auto, no gate" },
                      { icon: ShieldAlert, color: "text-orange-400", label: "Act (write)",    desc: "patch / restart — pauses for your approval" },
                      { icon: CheckCircle, color: "text-teal-400", label: "Verify",           desc: "checks if alert cleared after each write" },
                    ].map(({ icon: Icon, color, label, desc }, i) => (
                      <div key={i} className="flex items-start gap-3 py-1">
                        <Icon size={13} className={`${color} flex-shrink-0 mt-0.5`} />
                        <div>
                          <span className="text-xs text-white font-medium">{label}</span>
                          <span className="text-xs text-gray-500 ml-2">{desc}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
                <div className="bg-sre-surface border border-sre-border rounded-xl p-4">
                  <p className="text-xs text-gray-500 mb-1.5 font-semibold uppercase tracking-wider">AI Triage</p>
                  <p className="text-xs text-gray-300 leading-relaxed">{incident.summary}</p>
                </div>
              </div>
            </FadeIn>
          )}

          {/* ── Parallel gather section ── */}
          {(status !== "idle" || starting) && (
            <FadeIn>
              <div className="space-y-1.5">
                <div className="flex items-center gap-2 mb-2">
                  <Radio size={12} className="text-blue-400" />
                  <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
                    Parallel Gather
                    {gatherDone < gatherTotal && status === "running" && (
                      <span className="ml-2 text-blue-400 font-normal normal-case">
                        {gatherDone}/{gatherTotal} complete<ThinkingDots />
                      </span>
                    )}
                    {gatherDone === gatherTotal && (
                      <span className="ml-2 text-green-400 font-normal normal-case">all done</span>
                    )}
                  </p>
                </div>
                {["pods", "logs", "metrics"].map(label => (
                  <GatherPill
                    key={label}
                    label={label}
                    status={gatherState[label]?.status ?? "running"}
                    output={gatherState[label]?.output}
                  />
                ))}
              </div>
            </FadeIn>
          )}

          {/* ── ReAct trace ── */}
          {steps.length > 0 && (
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <Zap size={12} className="text-yellow-400" />
                <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
                  ReAct Trace — {steps.length} step{steps.length !== 1 ? "s" : ""}
                </p>
              </div>
              {steps.map((step, i) => <StepCard key={i} step={step} index={i} />)}
            </div>
          )}

          {/* ── Thinking indicator ── */}
          {thinking && (
            <FadeIn>
              <div className="flex items-center gap-3 px-4 py-3 bg-sre-surface border border-sre-border rounded-xl">
                <div className="w-6 h-6 rounded-full bg-purple-900/40 border border-purple-700/30 flex items-center justify-center flex-shrink-0">
                  <Brain size={12} className="text-purple-400" />
                </div>
                <div>
                  <p className="text-xs text-purple-300 font-medium">
                    {currentThought}
                    <ThinkingDots />
                  </p>
                  <p className="text-[10px] text-gray-600 mt-0.5">mistral:7b · M1 Pro GPU · ctx/2048</p>
                </div>
              </div>
            </FadeIn>
          )}

          {/* ── Final result ── */}
          {finalSummary && ["resolved", "escalated", "failed"].includes(status) && (
            <FadeIn>
              <div className={`border rounded-xl p-4 ${
                status === "resolved"
                  ? "border-green-700/50 bg-green-950/20"
                  : "border-orange-700/50 bg-orange-950/20"
              }`}>
                <p className={`text-xs font-semibold mb-1.5 ${status === "resolved" ? "text-green-400" : "text-orange-400"}`}>
                  {status === "resolved" ? "Incident Resolved" : "Requires Human Escalation"}
                </p>
                <p className="text-xs text-gray-300 leading-relaxed">{finalSummary}</p>
              </div>
            </FadeIn>
          )}

          {/* ── Code Fix Suggestions ── */}
          {codeSuggestions.length > 0 && (
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <Code2 size={12} className="text-red-400" />
                <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
                  Code-Level Fix Required
                  <span className="ml-2 text-red-400 font-normal normal-case">
                    kubectl cannot fully resolve this — application code changes needed
                  </span>
                </p>
              </div>
              {codeSuggestions.map((s, i) => (
                <CodeFixCard key={i} suggestion={s} index={i} />
              ))}
            </div>
          )}

          {error && (
            <FadeIn>
              <div className="border border-red-800 bg-red-950/30 rounded-xl p-3 text-xs text-red-300">{error}</div>
            </FadeIn>
          )}

          <div ref={bottomRef} />
        </div>

        {/* ── Footer ── */}
        <div className="px-5 py-4 border-t border-sre-border flex-shrink-0 space-y-3 bg-sre-surface/50">

          {/* Approval gate */}
          {status === "waiting_approval" && pendingAction && (
            <FadeIn>
              <div className="bg-yellow-950/40 border border-yellow-700/50 rounded-xl p-4 space-y-3">
                <div className="flex items-center gap-2">
                  <ShieldAlert size={14} className="text-yellow-400" />
                  <p className="text-xs font-semibold text-yellow-400">Write action requires approval</p>
                </div>
                <div className="flex items-start gap-2">
                  <Brain size={11} className="text-purple-400 flex-shrink-0 mt-0.5" />
                  <p className="text-xs text-gray-400 italic leading-relaxed">{pendingAction.thought}</p>
                </div>
                <div className="bg-black/40 border border-orange-700/30 rounded-lg px-3 py-2">
                  <code className="text-xs font-mono text-orange-300">
                    {pendingAction.action}(
                    {Object.entries(pendingAction.args || {}).map(([k,v]) => `${k}="${v}"`).join(", ")}
                    )
                  </code>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={approve}
                    disabled={approving}
                    className="flex-1 flex items-center justify-center gap-1.5 bg-green-700 hover:bg-green-600 disabled:opacity-50 text-white text-xs font-semibold py-2.5 rounded-lg transition-colors"
                  >
                    {approving
                      ? <><Loader2 size={12} className="animate-spin" /> Executing...</>
                      : <><Check size={12} /> Approve & Execute</>
                    }
                  </button>
                  <button
                    onClick={onClose}
                    className="flex-1 text-xs text-gray-400 hover:text-gray-200 border border-sre-border py-2.5 rounded-lg transition-colors hover:bg-sre-border"
                  >
                    Reject — Escalate
                  </button>
                </div>
              </div>
            </FadeIn>
          )}

          {/* Launch button */}
          {status === "idle" && (
            <button
              onClick={start}
              disabled={starting}
              className="w-full flex items-center justify-center gap-2 bg-sre-accent hover:bg-indigo-500 disabled:opacity-50 text-white text-sm font-semibold py-3 rounded-xl transition-colors"
            >
              {starting
                ? <><Loader2 size={14} className="animate-spin" /> Initialising graph...</>
                : <><Terminal size={14} /> Launch ExecutorAgent</>
              }
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
