import { useState } from "react";
import axios from "axios";
import {
  FileSearch, Send, Loader2, Plus, X, Clock,
  AlertTriangle, ChevronDown, ChevronUp, Copy, CheckCircle,
} from "lucide-react";

const SEVERITY_CONFIG = {
  P1: { color: "text-red-400", bg: "bg-red-950 border-red-800", label: "Critical" },
  P2: { color: "text-yellow-400", bg: "bg-yellow-950 border-yellow-800", label: "High" },
  P3: { color: "text-blue-400", bg: "bg-blue-950 border-blue-800", label: "Medium" },
};

const inputClass =
  "w-full bg-sre-bg border border-sre-border rounded-lg px-3 py-2 text-sm text-gray-100 placeholder-gray-600 focus:outline-none focus:border-sre-accent transition-colors";

const EXAMPLE = {
  title: "SiteMinder CPU Spike — SSO Outage",
  severity: "P1",
  environment: "production",
  affected_services: ["siteminder-policy-server", "auth-gateway"],
  duration_minutes: 22,
  timeline: [
    { time: "10:02", event: "Stale ConfigMap deployed via ArgoCD", actor: "system" },
    { time: "10:04", event: "CPU spike detected on policy-server pods", actor: "system" },
    { time: "10:07", event: "SSO login failures begin — PagerDuty P1 created", actor: "system" },
    { time: "10:18", event: "On-call engineer identifies bad ConfigMap", actor: "engineer" },
    { time: "10:24", event: "ConfigMap rolled back, pods restarted", actor: "engineer" },
  ],
  resolution: "Rolled back ConfigMap to previous version, restarted affected pods. All SSO logins recovered.",
};

export function RCAPanel() {
  const [form, setForm] = useState({
    title: "",
    severity: "P2",
    environment: "production",
    duration_minutes: "",
    resolution: "",
  });
  const [services, setServices] = useState([""]);
  const [timeline, setTimeline] = useState([{ time: "", event: "", actor: "system" }]);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  function loadExample() {
    setForm({
      title: EXAMPLE.title,
      severity: EXAMPLE.severity,
      environment: EXAMPLE.environment,
      duration_minutes: String(EXAMPLE.duration_minutes),
      resolution: EXAMPLE.resolution,
    });
    setServices([...EXAMPLE.affected_services]);
    setTimeline(EXAMPLE.timeline.map((e) => ({ ...e })));
    setResult(null);
    setError(null);
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const { data } = await axios.post("/api/v1/rca", {
        title: form.title,
        severity: form.severity,
        environment: form.environment,
        duration_minutes: parseInt(form.duration_minutes || "0", 10),
        affected_services: services.filter((s) => s.trim()),
        timeline: timeline.filter((e) => e.time.trim() && e.event.trim()),
        resolution: form.resolution,
      });
      setResult(data);
    } catch (err) {
      setError(err.response?.data?.detail || err.message || "RCA request failed");
    } finally {
      setLoading(false);
    }
  }

  function updateService(i, val) {
    setServices((prev) => prev.map((s, idx) => (idx === i ? val : s)));
  }
  function addService() { setServices((prev) => [...prev, ""]); }
  function removeService(i) { setServices((prev) => prev.filter((_, idx) => idx !== i)); }

  function updateTimeline(i, field, val) {
    setTimeline((prev) => prev.map((e, idx) => (idx === i ? { ...e, [field]: val } : e)));
  }
  function addTimelineEvent() { setTimeline((prev) => [...prev, { time: "", event: "", actor: "system" }]); }
  function removeTimelineEvent(i) { setTimeline((prev) => prev.filter((_, idx) => idx !== i)); }

  return (
    <div className="p-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-xl font-bold text-white flex items-center gap-2">
          <FileSearch size={20} className="text-sre-accent" />
          Auto RCA Generator
        </h1>
        <p className="text-sm text-gray-500 mt-1">
          Generates a structured Root Cause Analysis with timeline, action items, and Confluence-ready markdown.
        </p>
      </div>

      {/* Quick load */}
      <div className="mb-5">
        <button
          onClick={loadExample}
          className="text-xs px-3 py-1.5 bg-sre-surface border border-sre-border rounded-lg text-gray-400 hover:text-white hover:border-sre-accent transition-colors"
        >
          Load SiteMinder example
        </button>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="bg-sre-surface border border-sre-border rounded-xl p-5 space-y-4">
            <Field label="Incident Title" required>
              <input
                type="text"
                value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
                placeholder="e.g. SiteMinder CPU Spike — SSO Outage"
                required
                className={inputClass}
              />
            </Field>

            <div className="grid grid-cols-3 gap-3">
              <Field label="Severity">
                <select
                  value={form.severity}
                  onChange={(e) => setForm({ ...form, severity: e.target.value })}
                  className={inputClass}
                >
                  <option value="P1">P1 — Critical</option>
                  <option value="P2">P2 — High</option>
                  <option value="P3">P3 — Medium</option>
                </select>
              </Field>
              <Field label="Environment">
                <select
                  value={form.environment}
                  onChange={(e) => setForm({ ...form, environment: e.target.value })}
                  className={inputClass}
                >
                  <option value="production">production</option>
                  <option value="staging">staging</option>
                </select>
              </Field>
              <Field label="Duration (min)">
                <input
                  type="number"
                  value={form.duration_minutes}
                  onChange={(e) => setForm({ ...form, duration_minutes: e.target.value })}
                  placeholder="22"
                  min={0}
                  className={inputClass}
                />
              </Field>
            </div>

            {/* Affected services */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="text-xs text-gray-400">Affected Services</label>
                <button type="button" onClick={addService} className="text-xs text-sre-accent hover:underline flex items-center gap-1">
                  <Plus size={12} /> Add
                </button>
              </div>
              <div className="space-y-2">
                {services.map((svc, i) => (
                  <div key={i} className="flex gap-2">
                    <input
                      type="text"
                      value={svc}
                      onChange={(e) => updateService(i, e.target.value)}
                      placeholder="e.g. siteminder-policy-server"
                      className={`${inputClass} flex-1`}
                    />
                    <button type="button" onClick={() => removeService(i)} className="text-gray-600 hover:text-red-400">
                      <X size={14} />
                    </button>
                  </div>
                ))}
              </div>
            </div>

            {/* Timeline */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="text-xs text-gray-400">Timeline Events</label>
                <button type="button" onClick={addTimelineEvent} className="text-xs text-sre-accent hover:underline flex items-center gap-1">
                  <Plus size={12} /> Add
                </button>
              </div>
              <div className="space-y-2">
                {timeline.map((evt, i) => (
                  <div key={i} className="flex gap-2 items-center">
                    <input
                      type="text"
                      value={evt.time}
                      onChange={(e) => updateTimeline(i, "time", e.target.value)}
                      placeholder="HH:MM"
                      className={`${inputClass} w-20 flex-shrink-0`}
                    />
                    <input
                      type="text"
                      value={evt.event}
                      onChange={(e) => updateTimeline(i, "event", e.target.value)}
                      placeholder="What happened"
                      className={`${inputClass} flex-1`}
                    />
                    <select
                      value={evt.actor}
                      onChange={(e) => updateTimeline(i, "actor", e.target.value)}
                      className={`${inputClass} w-24 flex-shrink-0`}
                    >
                      <option value="system">system</option>
                      <option value="engineer">engineer</option>
                    </select>
                    <button type="button" onClick={() => removeTimelineEvent(i)} className="text-gray-600 hover:text-red-400 flex-shrink-0">
                      <X size={14} />
                    </button>
                  </div>
                ))}
              </div>
            </div>

            <Field label="Resolution Summary" required>
              <textarea
                value={form.resolution}
                onChange={(e) => setForm({ ...form, resolution: e.target.value })}
                placeholder="What was done to resolve the incident?"
                rows={3}
                required
                className={`${inputClass} resize-none`}
              />
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
              <><Loader2 size={16} className="animate-spin" /> Generating RCA...</>
            ) : (
              <><Send size={16} /> Generate RCA</>
            )}
          </button>
        </form>

        {/* Result */}
        <div>
          {result ? (
            <RCAResult result={result} />
          ) : (
            <div className="h-full flex items-center justify-center border border-dashed border-sre-border rounded-xl text-gray-600 text-sm p-8 text-center">
              Fill in the incident details and click Generate RCA
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function RCAResult({ result }) {
  const [tab, setTab] = useState("structured");
  const [copied, setCopied] = useState(false);
  const cfg = SEVERITY_CONFIG[result.severity] || SEVERITY_CONFIG.P2;
  const impact = result.impact || {};

  async function copyMarkdown() {
    await navigator.clipboard.writeText(result.rca_markdown || "");
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div className="bg-sre-surface border border-sre-border rounded-xl p-5 space-y-4 max-h-[80vh] overflow-y-auto">
      {/* Title & severity */}
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-bold text-white">{result.title}</h3>
          <div className="flex items-center gap-3 mt-1 text-xs text-gray-500">
            <span className={`font-semibold ${cfg.color}`}>{result.severity} — {cfg.label}</span>
            {impact.duration_minutes > 0 && (
              <span className="flex items-center gap-1">
                <Clock size={10} /> {impact.duration_minutes} min
              </span>
            )}
            <span className="text-gray-600">{result.llm_tier}</span>
          </div>
        </div>
        <div className={`text-xs px-2 py-1 rounded border ${cfg.bg} ${cfg.color}`}>
          {result.severity}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-sre-border gap-4">
        {["structured", "markdown"].map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`pb-2 text-xs font-medium capitalize transition-colors ${
              tab === t ? "text-sre-accent border-b-2 border-sre-accent" : "text-gray-500 hover:text-gray-300"
            }`}
          >
            {t === "markdown" ? "Confluence Markdown" : "Structured View"}
          </button>
        ))}
      </div>

      {tab === "structured" ? (
        <div className="space-y-4">
          <RCASection title="Summary">
            <p className="text-sm text-gray-300">{result.summary}</p>
          </RCASection>

          <RCASection title="Root Cause">
            <p className="text-sm text-gray-200 font-medium">{result.root_cause}</p>
          </RCASection>

          {result.contributing_factors?.length > 0 && (
            <RCASection title="Contributing Factors">
              <ul className="space-y-1">
                {result.contributing_factors.map((f, i) => (
                  <li key={i} className="text-sm text-gray-300 flex items-start gap-2">
                    <span className="text-sre-accent mt-1">•</span> {f}
                  </li>
                ))}
              </ul>
            </RCASection>
          )}

          <RCASection title="Impact">
            <div className="grid grid-cols-2 gap-2 text-xs text-gray-400">
              <span>Users: <span className="text-gray-200">{impact.users_affected || "unknown"}</span></span>
              <span>Detection gap: <span className="text-gray-200">{result.detection_gap}</span></span>
              {impact.services_affected?.length > 0 && (
                <span className="col-span-2">Services: <span className="text-gray-200">{impact.services_affected.join(", ")}</span></span>
              )}
            </div>
          </RCASection>

          {result.timeline?.length > 0 && (
            <RCASection title="Timeline">
              <div className="space-y-2">
                {result.timeline.map((evt, i) => (
                  <div key={i} className="flex gap-3 text-xs">
                    <span className="text-sre-accent font-mono flex-shrink-0">{evt.time}</span>
                    <span className="text-gray-300">{evt.event}</span>
                    <span className="text-gray-600 flex-shrink-0">{evt.actor}</span>
                  </div>
                ))}
              </div>
            </RCASection>
          )}

          {result.prevention?.length > 0 && (
            <RCASection title="Prevention">
              <ul className="space-y-1">
                {result.prevention.map((p, i) => (
                  <li key={i} className="text-sm text-gray-300 flex items-start gap-2">
                    <CheckCircle size={12} className="text-green-400 mt-0.5 flex-shrink-0" /> {p}
                  </li>
                ))}
              </ul>
            </RCASection>
          )}

          {result.action_items?.length > 0 && (
            <RCASection title="Action Items">
              <div className="space-y-2">
                {result.action_items.map((item, i) => (
                  <div key={i} className="bg-sre-bg border border-sre-border rounded-lg px-3 py-2 text-xs">
                    <div className="flex items-center justify-between mb-0.5">
                      <span className="text-white font-medium">{item.action}</span>
                      <span className={`${item.priority === "P1" ? "text-red-400" : "text-yellow-400"}`}>{item.priority}</span>
                    </div>
                    <span className="text-gray-500">{item.owner} · Due: {item.due}</span>
                  </div>
                ))}
              </div>
            </RCASection>
          )}
        </div>
      ) : (
        <div className="space-y-2">
          <div className="flex justify-end">
            <button
              onClick={copyMarkdown}
              className="flex items-center gap-1.5 text-xs text-gray-400 hover:text-white border border-sre-border rounded-lg px-3 py-1.5 transition-colors"
            >
              {copied ? <CheckCircle size={12} className="text-green-400" /> : <Copy size={12} />}
              {copied ? "Copied!" : "Copy markdown"}
            </button>
          </div>
          <pre className="text-xs text-gray-300 bg-sre-bg border border-sre-border rounded-lg p-4 overflow-x-auto whitespace-pre-wrap leading-relaxed">
            {result.rca_markdown}
          </pre>
        </div>
      )}
    </div>
  );
}

function RCASection({ title, children }) {
  const [open, setOpen] = useState(true);
  return (
    <div>
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-gray-500 hover:text-gray-300 mb-2 w-full text-left"
      >
        {open ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
        {title}
      </button>
      {open && children}
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
