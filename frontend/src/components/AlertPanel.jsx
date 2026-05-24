import { useState } from "react";
import axios from "axios";
import { Send, Loader2, Plus, X } from "lucide-react";
import { TriageResult } from "./TriageResult.jsx";

const EXAMPLE_ALERTS = [
  {
    name: "KubePodCrashLooping",
    description: "Pod ping-identity-auth-7d9f8b-xxx has been restarting 8 times in the last 10 minutes with OOMKilled exit code",
    labels: { namespace: "iam", severity: "warning", app: "ping-identity-auth" },
    value: 8,
    environment: "production",
  },
  {
    name: "HighCPUUsage",
    description: "SiteMinder policy server pods running at 95% CPU for 8 minutes, causing SSO login timeouts",
    labels: { namespace: "ciso", severity: "critical", app: "siteminder-policy-server" },
    value: 95,
    environment: "production",
  },
  {
    name: "DBConnectionPoolExhausted",
    description: "IAM token service reporting 0 available connections, p99 latency at 8000ms",
    labels: { namespace: "iam", severity: "critical", service: "iam-token-service" },
    value: 0,
    environment: "production",
  },
];

export function AlertPanel() {
  const [form, setForm] = useState({
    name: "",
    description: "",
    value: "",
    environment: "production",
  });
  const [labels, setLabels] = useState([{ key: "", value: "" }]);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  function loadExample(example) {
    setForm({
      name: example.name,
      description: example.description,
      value: String(example.value),
      environment: example.environment,
    });
    setLabels(Object.entries(example.labels).map(([k, v]) => ({ key: k, value: v })));
    setResult(null);
    setError(null);
  }

  function updateLabel(index, field, val) {
    setLabels((prev) => prev.map((l, i) => (i === index ? { ...l, [field]: val } : l)));
  }

  function addLabel() {
    setLabels((prev) => [...prev, { key: "", value: "" }]);
  }

  function removeLabel(index) {
    setLabels((prev) => prev.filter((_, i) => i !== index));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);

    const labelsObj = Object.fromEntries(
      labels.filter((l) => l.key.trim()).map((l) => [l.key.trim(), l.value.trim()])
    );

    try {
      const { data } = await axios.post("/api/v1/triage", {
        name: form.name,
        description: form.description,
        labels: labelsObj,
        value: form.value ? parseFloat(form.value) : null,
        environment: form.environment,
        firing_since: new Date().toISOString(),
      });
      setResult(data);
    } catch (err) {
      setError(err.response?.data?.detail || err.message || "Triage request failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="p-6 max-w-5xl mx-auto">
      {/* Page header */}
      <div className="mb-6 pb-5 border-b border-sre-border flex items-start justify-between">
        <div>
          <h1 className="text-lg font-semibold text-white tracking-tight">Alert Triage</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            RAG retrieves similar incidents · LLM classifies severity · Suggests exact remediation steps
          </p>
        </div>
        <span className="text-xs text-gray-600 bg-sre-surface border border-sre-border rounded-md px-2.5 py-1 font-mono">
          mistral:7b · M1 GPU
        </span>
      </div>

      {/* Example quick-loads */}
      <div className="mb-5">
        <p className="text-xs text-gray-500 mb-2">Load example alert:</p>
        <div className="flex gap-2 flex-wrap">
          {EXAMPLE_ALERTS.map((ex) => (
            <button
              key={ex.name}
              onClick={() => loadExample(ex)}
              className="text-xs px-3 py-1.5 bg-sre-surface border border-sre-border rounded-lg text-gray-400 hover:text-white hover:border-sre-accent transition-colors"
            >
              {ex.name}
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
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="e.g. KubePodCrashLooping"
                required
                className={inputClass}
              />
            </Field>

            <Field label="Description" required>
              <textarea
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                placeholder="What is the alert telling you?"
                rows={3}
                required
                className={`${inputClass} resize-none`}
              />
            </Field>

            <div className="grid grid-cols-2 gap-3">
              <Field label="Current Value">
                <input
                  type="number"
                  value={form.value}
                  onChange={(e) => setForm({ ...form, value: e.target.value })}
                  placeholder="95.3"
                  className={inputClass}
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

            {/* Labels */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="text-xs text-gray-400">Labels</label>
                <button
                  type="button"
                  onClick={addLabel}
                  className="text-xs text-sre-accent hover:underline flex items-center gap-1"
                >
                  <Plus size={12} /> Add
                </button>
              </div>
              <div className="space-y-2">
                {labels.map((label, i) => (
                  <div key={i} className="flex gap-2 items-center">
                    <input
                      type="text"
                      value={label.key}
                      onChange={(e) => updateLabel(i, "key", e.target.value)}
                      placeholder="key"
                      className={`${inputClass} flex-1`}
                    />
                    <span className="text-gray-600">=</span>
                    <input
                      type="text"
                      value={label.value}
                      onChange={(e) => updateLabel(i, "value", e.target.value)}
                      placeholder="value"
                      className={`${inputClass} flex-1`}
                    />
                    <button type="button" onClick={() => removeLabel(i)} className="text-gray-600 hover:text-red-400">
                      <X size={14} />
                    </button>
                  </div>
                ))}
              </div>
            </div>
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
              <>
                <Loader2 size={16} className="animate-spin" /> Analyzing with Mistral 7B...
              </>
            ) : (
              <>
                <Send size={16} /> Triage Alert
              </>
            )}
          </button>
        </form>

        {/* Result */}
        <div>
          {result ? (
            <TriageResult
              result={result}
              alertName={form.name}
              namespace={labels.find((l) => l.key === "namespace")?.value || "default"}
            />
          ) : (
            <div className="h-full flex items-center justify-center border border-dashed border-sre-border rounded-xl text-gray-600 text-sm p-8 text-center">
              Submit an alert to see the AI triage result here
            </div>
          )}
        </div>
      </div>

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

const inputClass =
  "w-full bg-sre-bg border border-sre-border rounded-lg px-3 py-2 text-sm text-gray-100 placeholder-gray-600 focus:outline-none focus:border-sre-accent transition-colors";
