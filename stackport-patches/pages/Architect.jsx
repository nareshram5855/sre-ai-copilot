import { useState, useEffect, useRef } from "react";
import {
  Sparkles, Layers, Shield, CheckCircle, XCircle, AlertTriangle,
  Loader2, ChevronDown, ChevronRight, Server, Database, Globe, Lock,
  Zap, Rocket, ExternalLink, BarChart2, DollarSign, RefreshCw,
} from "lucide-react";
import PageHeader from "../components/ui/PageHeader.jsx";
import { Card, CardHeader } from "../components/ui/Card.jsx";
import Badge from "../components/ui/Badge.jsx";
import Button from "../components/ui/Button.jsx";
import { fetchJSON } from "../utils/api.js";
import ArchitectureDiagram from "../components/ai/ArchitectureDiagram.jsx";
import ArchitectureChat from "../components/ai/ArchitectureChat.jsx";

const CATEGORY_ICONS = {
  networking: Globe, compute: Server, data: Database,
  security: Lock, cicd: Zap, storage: Layers, monitoring: BarChart2,
  integration: RefreshCw,
};

// ── SSE streaming helper ──────────────────────────────────────────────────────

async function streamPost(path, body, { onEvent, onDone, onError }) {
  try {
    const token = sessionStorage.getItem("infra_platform_token");
    const res = await fetch("/api/ai" + path, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(body),
    });
    if (!res.ok) { onError(`${res.status}: ${await res.text()}`); return; }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      const lines = buf.split("\n");
      buf = lines.pop() ?? "";
      for (const line of lines) {
        const raw = line.startsWith("data: ") ? line.slice(6) : line;
        if (!raw.trim()) continue;
        try { onEvent(JSON.parse(raw)); } catch { /**/ }
      }
    }
    onDone();
  } catch (e) { onError(e.message); }
}

// ── Well-Architected Assessment card ─────────────────────────────────────────

const WA_PILLARS = [
  { key: "operational_excellence", label: "Operational Excellence", short: "Ops" },
  { key: "security",               label: "Security",               short: "Sec" },
  { key: "reliability",            label: "Reliability",            short: "Rel" },
  { key: "performance",            label: "Performance Efficiency", short: "Perf" },
  { key: "cost_optimization",      label: "Cost Optimization",      short: "Cost" },
  { key: "sustainability",         label: "Sustainability",         short: "Sus" },
];

function scoreColor(s) {
  if (s >= 80) return { bar: "bg-emerald-500", text: "text-emerald-400" };
  if (s >= 60) return { bar: "bg-amber-500",   text: "text-amber-400"   };
  return            { bar: "bg-red-500",        text: "text-red-400"     };
}

function WellArchitectedCard({ wa }) {
  const [expanded, setExpanded] = useState(true);
  if (!wa || !Object.keys(wa).length) return null;

  const scores = WA_PILLARS.map(p => wa[p.key]?.score ?? 0);
  const overall = Math.round(scores.reduce((a, b) => a + b, 0) / scores.length);
  const { text: overallColor } = scoreColor(overall);

  return (
    <Card>
      <button
        onClick={() => setExpanded(v => !v)}
        className="w-full flex items-center justify-between mb-1"
      >
        <div className="flex items-center gap-2">
          <BarChart2 size={14} className="text-accent" />
          <span className="text-sm font-semibold text-[var(--text-primary)]">Well-Architected Assessment</span>
          <span className="text-[10px] text-[var(--text-faint)] bg-[var(--bg-muted)] px-1.5 py-0.5 rounded">
            AWS 6-Pillar Framework
          </span>
        </div>
        <div className="flex items-center gap-3">
          <div className="text-right">
            <span className={`text-xl font-bold ${overallColor}`}>{overall}</span>
            <span className="text-[10px] text-[var(--text-faint)]">/100</span>
          </div>
          {expanded ? <ChevronDown size={13} className="text-[var(--text-faint)]" /> : <ChevronRight size={13} className="text-[var(--text-faint)]" />}
        </div>
      </button>

      {/* Mini score bar (always visible) */}
      <div className="flex gap-1 mb-3">
        {WA_PILLARS.map((p, i) => {
          const s = wa[p.key]?.score ?? 0;
          const { bar } = scoreColor(s);
          return (
            <div key={p.key} className="flex-1" title={`${p.label}: ${s}/100`}>
              <div className="text-[9px] text-[var(--text-faint)] text-center mb-0.5">{p.short}</div>
              <div className="h-1.5 bg-[var(--bg-muted)] rounded-full overflow-hidden">
                <div className={`h-full ${bar} rounded-full`} style={{ width: `${s}%` }} />
              </div>
            </div>
          );
        })}
      </div>

      {expanded && (
        <div className="space-y-3 border-t border-[var(--border-subtle)] pt-3">
          {WA_PILLARS.map(p => {
            const { score = 0, notes = "" } = wa[p.key] ?? {};
            const { bar, text } = scoreColor(score);
            return (
              <div key={p.key}>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs text-[var(--text-secondary)]">{p.label}</span>
                  <span className={`text-xs font-mono font-semibold ${text}`}>{score}/100</span>
                </div>
                <div className="h-1.5 bg-[var(--bg-muted)] rounded-full overflow-hidden mb-1">
                  <div className={`h-full ${bar} rounded-full transition-all duration-700`} style={{ width: `${score}%` }} />
                </div>
                {notes && (
                  <p className="text-[10px] text-[var(--text-faint)] leading-relaxed">{notes}</p>
                )}
              </div>
            );
          })}
        </div>
      )}
    </Card>
  );
}

// ── Security flag ─────────────────────────────────────────────────────────────

function SecurityFlag({ flag }) {
  const colors = {
    CRITICAL: "text-red-400 bg-red-500/10 border-red-500/20",
    HIGH:     "text-orange-400 bg-orange-500/10 border-orange-500/20",
    MEDIUM:   "text-amber-400 bg-amber-500/10 border-amber-500/20",
    LOW:      "text-sky-400 bg-sky-500/10 border-sky-500/20",
  };
  return (
    <div className={`flex items-start gap-2 p-2 rounded-lg border text-xs ${colors[flag.severity] ?? colors.LOW}`}>
      <Shield size={11} className="shrink-0 mt-0.5" />
      <div>
        <span className="font-semibold">[{flag.severity}] {flag.rule}</span>
        <p className="opacity-80 mt-0.5">{flag.detail}</p>
      </div>
    </div>
  );
}

// ── Module card ───────────────────────────────────────────────────────────────

function ModuleCard({ mod }) {
  const [open, setOpen] = useState(false);
  const cat = mod.module?.split("/")[0] ?? "compute";
  const Icon = CATEGORY_ICONS[cat] ?? Layers;
  return (
    <div className="border border-[var(--border-subtle)] rounded-lg overflow-hidden">
      <button onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-4 py-3 bg-[var(--bg-elevated)] hover:bg-[var(--bg-hover)] transition-colors text-left">
        <div className="flex items-center gap-3">
          <div className="p-1.5 rounded-lg bg-accent-muted border border-accent/20">
            <Icon size={13} className="text-accent" />
          </div>
          <div>
            <p className="text-sm font-medium text-[var(--text-primary)]">{mod.label}</p>
            <p className="text-[11px] text-[var(--text-muted)] font-mono">{mod.module}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="default">order {mod.deploy_order}</Badge>
          {open ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
        </div>
      </button>
      {open && (
        <div className="px-4 py-3 bg-[var(--bg-surface)] border-t border-[var(--border-subtle)] space-y-2">
          <p className="text-[11px] text-[var(--text-muted)] italic">{mod.reason}</p>
          <pre className="font-mono text-[10px] text-emerald-300 bg-[#0a0a0c] rounded-lg p-3 overflow-x-auto">
            {JSON.stringify(mod.inputs, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}

// ── Architecture result card ──────────────────────────────────────────────────

function ArchitectureCard({ arch, onProvision, provisioning }) {
  const security = arch.security ?? {};
  const cost     = arch.cost ?? arch.estimated_monthly_cost ?? {};
  const wa       = arch.well_architected ?? {};
  const repo     = arch.repo ?? arch.repo_structure ?? null;
  const sox   = security.sox   ?? false;
  const pci   = security.pci   ?? false;
  const hipaa = security.hipaa ?? false;
  const gdpr  = security.gdpr  ?? false;

  const complianceBadges = [
    sox   && { label: "SOX",   ok: true  },
    pci   && { label: "PCI",   ok: true  },
    hipaa && { label: "HIPAA", ok: true  },
    gdpr  && { label: "GDPR",  ok: true  },
    !sox && !pci && !hipaa && !gdpr && { label: "Standard", ok: null },
  ].filter(Boolean);

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <Card className="border-accent/30 bg-gradient-to-br from-accent/5 to-transparent">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-2">
              <Sparkles size={15} className="text-accent" />
              <p className="text-[10px] font-bold uppercase tracking-widest text-accent">Stackport AI Architecture</p>
            </div>
            <h2 className="text-lg font-semibold text-[var(--text-primary)] mb-1">{arch.architecture_name}</h2>
            <p className="text-sm text-[var(--text-muted)] leading-relaxed">{arch.summary}</p>
          </div>
          <div className="flex flex-wrap gap-1.5 shrink-0">
            {complianceBadges.map(b => (
              <Badge key={b.label} variant={b.ok ? "success" : "default"}>
                {b.label} {b.ok ? "✓" : ""}
              </Badge>
            ))}
          </div>
        </div>
      </Card>

      {/* Well-Architected Assessment */}
      <WellArchitectedCard wa={wa} />

      {/* Modules */}
      <div>
        <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-3 flex items-center gap-2">
          <Layers size={14} className="text-accent" />
          {arch.modules?.length ?? 0} AWS modules to provision
          <span className="text-[11px] text-[var(--text-muted)] font-normal">— deployed in order</span>
        </h3>
        <div className="space-y-2">
          {(arch.modules ?? []).sort((a, b) => a.deploy_order - b.deploy_order).map((m, i) => (
            <ModuleCard key={i} mod={m} />
          ))}
        </div>
      </div>

      {/* Security flags */}
      {(security.flags?.length > 0) && (
        <div>
          <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-3 flex items-center gap-2">
            <Shield size={14} className="text-amber-400" /> Security flags
          </h3>
          <div className="space-y-2">
            {security.flags.map((f, i) =>
              typeof f === "string"
                ? <div key={i} className="flex items-start gap-2 p-2 rounded-lg border border-amber-500/20 bg-amber-500/10 text-xs text-amber-300">
                    <Shield size={11} className="shrink-0 mt-0.5" />{f}
                  </div>
                : <SecurityFlag key={i} flag={f} />
            )}
          </div>
        </div>
      )}

      {/* Cost + Repo */}
      <div className="grid sm:grid-cols-2 gap-4">
        {cost.min_usd && (
          <Card>
            <div className="flex items-center gap-2 mb-3">
              <DollarSign size={14} className="text-emerald-400" />
              <CardHeader title="Estimated cost" description="Monthly AWS spend" />
            </div>
            <p className="text-2xl font-bold text-[var(--text-primary)] mb-2">
              ${cost.min_usd}–${cost.max_usd}
              <span className="text-sm font-normal text-[var(--text-muted)]">/mo</span>
            </p>
            {cost.note && <p className="text-[11px] text-[var(--text-muted)] mb-2">↳ {cost.note}</p>}
            <div className="space-y-1">
              {(cost.breakdown ?? []).map((b, i) => (
                <p key={i} className="text-[11px] text-[var(--text-faint)]">• {b}</p>
              ))}
            </div>
          </Card>
        )}
        {repo && (
          <Card>
            <CardHeader title="App scaffold" description="Generated repo structure" />
            <div className="space-y-1.5 mt-2">
              {[["Language", repo.language], ["Framework", repo.framework], ["Deploy target", repo.deploy_target]]
                .filter(([, v]) => v)
                .map(([k, v]) => (
                  <div key={k} className="flex items-center justify-between text-xs">
                    <span className="text-[var(--text-muted)]">{k}</span>
                    <Badge variant="default">{v}</Badge>
                  </div>
                ))}
            </div>
          </Card>
        )}
      </div>

      {/* Provision CTA */}
      <div className="flex items-center gap-3 pt-2 border-t border-[var(--border-subtle)]">
        <Button icon={Rocket} onClick={onProvision} disabled={provisioning}>
          {provisioning ? "Provisioning…" : "Provision this architecture"}
        </Button>
        <p className="text-[11px] text-[var(--text-muted)]">
          Writes Terragrunt configs · opens GitHub PR · triggers Terraform plan
        </p>
      </div>
    </div>
  );
}

// ── Provision stream ──────────────────────────────────────────────────────────

function ProvisionStream({ events, repoUrl }) {
  const bottomRef = useRef(null);
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [events]);

  const prEvent       = events.find(e => e.type === "branch_pushed" && e.url?.includes("/pull/"));
  const branchEvent   = events.find(e => e.type === "branch_pushed");
  const workflowEvent = events.find(e => e.type === "workflow_started");
  const repoEvent     = events.find(e => e.type === "repo_created");

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-semibold text-[var(--text-primary)] flex items-center gap-2">
        <Rocket size={14} className="text-accent" /> Provisioning in progress
      </h3>
      {(repoEvent || branchEvent || prEvent || workflowEvent) && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
          {repoEvent && (
            <a href={repoEvent.url} target="_blank" rel="noopener noreferrer"
              className="flex items-center gap-2 px-3 py-2.5 rounded-lg border border-violet-500/30 bg-violet-500/10 text-xs text-violet-300 hover:bg-violet-500/20 transition-colors">
              <ExternalLink size={12} className="shrink-0" />
              <span className="min-w-0"><p className="font-semibold truncate">Team Repo</p><p className="text-[10px] opacity-70 truncate">{repoEvent.url.split("github.com/")[1]}</p></span>
            </a>
          )}
          {(prEvent || branchEvent) && (
            <a href={(prEvent || branchEvent).url} target="_blank" rel="noopener noreferrer"
              className="flex items-center gap-2 px-3 py-2.5 rounded-lg border border-sky-500/30 bg-sky-500/10 text-xs text-sky-300 hover:bg-sky-500/20 transition-colors">
              <ExternalLink size={12} className="shrink-0" />
              <span className="min-w-0"><p className="font-semibold">{prEvent ? "Review PR" : "View Branch"}</p><p className="text-[10px] opacity-70 truncate">{(prEvent || branchEvent).branch}</p></span>
            </a>
          )}
          {workflowEvent && (
            <a href={workflowEvent.url} target="_blank" rel="noopener noreferrer"
              className="flex items-center gap-2 px-3 py-2.5 rounded-lg border border-amber-500/30 bg-amber-500/10 text-xs text-amber-300 hover:bg-amber-500/20 transition-colors">
              <ExternalLink size={12} className="shrink-0" />
              <span className="min-w-0"><p className="font-semibold">GitHub Actions</p><p className="text-[10px] opacity-70">View plan run</p></span>
            </a>
          )}
        </div>
      )}
      <div className="bg-[#0a0a0c] border border-[var(--border-subtle)] rounded-xl p-4 font-mono text-[11px] space-y-1 max-h-72 overflow-y-auto">
        {events.map((evt, i) => {
          if (evt.type === "status")       return <p key={i} className="text-[var(--text-muted)]">→ {evt.message}</p>;
          if (evt.type === "file_written") return <p key={i} className="text-emerald-400/80">  ✓ {evt.path}</p>;
          if (evt.type === "log" && evt.line?.trim()) return <p key={i} className="text-[var(--text-faint)] pl-2 whitespace-pre-wrap">{evt.line.trim()}</p>;
          if (evt.type === "error")        return <p key={i} className="text-red-400">✗ {evt.message}</p>;
          if (evt.type === "repo_created") return <p key={i} className="text-violet-400">✓ {evt.url}</p>;
          if (evt.type === "branch_pushed") return <p key={i} className="text-sky-400">✓ branch: {evt.branch}</p>;
          return null;
        })}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}

// ── Intake form ───────────────────────────────────────────────────────────────

const SCALE_OPTIONS = [
  { value: "small",  label: "Small",  sub: "< 10k req/day · serverless-first" },
  { value: "medium", label: "Medium", sub: "10k–500k/day · containers" },
  { value: "large",  label: "Large",  sub: "500k+/day · EKS + Aurora" },
];

const COMPLIANCE_OPTIONS = ["PCI-DSS", "HIPAA", "SOX", "GDPR"];

const PATTERN_OPTIONS = [
  { value: "api",        label: "REST API" },
  { value: "event",      label: "Event-driven" },
  { value: "ml",         label: "ML / AI workload" },
  { value: "static",     label: "Static site" },
  { value: "streaming",  label: "Real-time streaming" },
  { value: "batch",      label: "Batch processing" },
];

const EXAMPLES = [
  "Node.js payment API with PostgreSQL, Redis cache, JWT auth — PCI-DSS required, handles 100k transactions/day",
  "Python ML inference service with GPU-backed containers, S3 model storage, and auto-scaling queue worker",
  "React SPA on CloudFront + S3 with a Lambda GraphQL API and DynamoDB — serverless, no servers to manage",
  "Java Spring Boot EKS microservices with Aurora PostgreSQL Multi-AZ, ElastiCache, SOX audit trail required",
  "Real-time fraud detection pipeline using Kinesis, Lambda, SageMaker, DynamoDB — sub-100ms latency required",
];

// ── Phase C: Clarifying questions ─────────────────────────────────────────────

async function getClarifyingQuestions(requirements, { onQuestions, onError }) {
  try {
    const token = sessionStorage.getItem("infra_platform_token");
    const res = await fetch("/api/ai/architect/clarify", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ requirements }),
    });
    if (!res.ok) { onError("Could not get clarifications"); return; }
    const data = await res.json();
    onQuestions(data.questions ?? []);
  } catch (e) { onError(e.message); }
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function Architect() {
  const [geminiAvailable, setGeminiAvailable]   = useState(null);
  const [step, setStep]                         = useState("form"); // form | clarify | result
  const [requirements, setRequirements]         = useState("");
  const [appName, setAppName]                   = useState("");
  const [teamName, setTeamName]                 = useState("");
  const [env, setEnv]                           = useState("dev");
  const [scale, setScale]                       = useState("medium");
  const [compliance, setCompliance]             = useState([]);
  const [patterns, setPatterns]                 = useState([]);
  const [clarifyQuestions, setClarifyQuestions] = useState([]);
  const [clarifyAnswers, setClarifyAnswers]     = useState({});
  const [clarifying, setClarifying]             = useState(false);
  const [creating, setCreating]                 = useState(false);
  const [statuses, setStatuses]                 = useState([]);
  const [architecture, setArchitecture]         = useState(null);
  const [error, setError]                       = useState("");
  const [provisioning, setProvisioning]         = useState(false);
  const [provisionEvents, setProvisionEvents]   = useState([]);
  const [repoUrl, setRepoUrl]                   = useState("");
  const [done, setDone]                         = useState(false);
  const [doneStatus, setDoneStatus]             = useState("");
  const [runUrl, setRunUrl]                     = useState("");
  const [variant, setVariant]                   = useState(null); // ha | cost | serverless

  useEffect(() => {
    fetchJSON("/ai/architect/status")
      .then(d => setGeminiAvailable(d.available))
      .catch(() => setGeminiAvailable(false));
  }, []);

  function slugify(v) {
    return v.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 40);
  }

  function toggleCompliance(c) {
    setCompliance(p => p.includes(c) ? p.filter(x => x !== c) : [...p, c]);
  }
  function togglePattern(p) {
    setPatterns(prev => prev.includes(p) ? prev.filter(x => x !== p) : [...prev, p]);
  }

  async function handleClarify(e) {
    e.preventDefault();
    setClarifying(true); setError("");
    await getClarifyingQuestions(requirements, {
      onQuestions: (qs) => {
        if (qs.length) { setClarifyQuestions(qs); setStep("clarify"); }
        else handleGenerate();
      },
      onError: () => handleGenerate(), // graceful fallback
    });
    setClarifying(false);
  }

  function buildFinalRequirements() {
    if (!clarifyQuestions.length || !Object.keys(clarifyAnswers).length) return requirements;
    const qa = clarifyQuestions
      .filter(q => clarifyAnswers[q])
      .map(q => `${q}: ${clarifyAnswers[q]}`)
      .join("\n");
    return `${requirements}\n\nAdditional context:\n${qa}`;
  }

  async function handleGenerate(e) {
    if (e?.preventDefault) e.preventDefault();
    setCreating(true); setError(""); setStatuses([]); setArchitecture(null);
    setStep("result");
    const finalReqs = buildFinalRequirements();
    await streamPost("/architect",
      {
        requirements: finalReqs,
        app_name:  slugify(appName) || appName,
        team_name: slugify(teamName) || teamName,
        env,
        scale,
        compliance,
        patterns,
      },
      {
        onEvent: (evt) => {
          if (evt.type === "status")       setStatuses(p => [...p, evt.message]);
          if (evt.type === "architecture") setArchitecture(evt.data);
          if (evt.type === "error")        setError(evt.message);
        },
        onDone:  () => setCreating(false),
        onError: (err) => { setError(err); setCreating(false); },
      }
    );
  }

  async function handleVariant(type) {
    if (!architecture) return;
    setVariant(type); setCreating(true); setError(""); setStatuses([]);
    const variantMap = {
      ha:         "Make this architecture highly available: Multi-AZ for all data stores, auto-scaling for compute, health checks, failover routing",
      cost:       "Optimize this architecture for cost: use Fargate Spot, DynamoDB on-demand, Lambda where possible, reserved pricing noted",
      serverless: "Convert this architecture to be fully serverless: Lambda functions, DynamoDB, S3, API Gateway — eliminate all servers",
    };
    await streamPost("/architect/update",
      {
        architecture,
        message: variantMap[type],
        app_name:  slugify(appName) || appName,
        team_name: slugify(teamName) || teamName,
        env,
      },
      {
        onEvent: (evt) => {
          if (evt.type === "status") setStatuses(p => [...p, evt.message]);
        },
        onDone: () => { setCreating(false); setVariant(null); },
        onError: (err) => { setError(err); setCreating(false); setVariant(null); },
      }
    );
    // Update architecture via non-streaming update endpoint
    try {
      const token = sessionStorage.getItem("infra_platform_token");
      const res = await fetch("/api/ai/architect/update", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
        body: JSON.stringify({
          architecture,
          message: variantMap[type],
          app_name:  slugify(appName) || appName,
          team_name: slugify(teamName) || teamName,
          env,
        }),
      });
      if (res.ok) { const updated = await res.json(); if (!updated.error) setArchitecture(updated); }
    } catch {/**/ }
    setCreating(false); setVariant(null);
  }

  async function handleProvision() {
    if (!architecture) return;
    setProvisioning(true); setProvisionEvents([]); setRepoUrl(""); setDone(false); setDoneStatus(""); setRunUrl("");
    await streamPost("/provision",
      { architecture, app_name: slugify(appName) || appName, team_name: slugify(teamName) || teamName, env, create_repo: true },
      {
        onEvent: (evt) => {
          setProvisionEvents(p => [...p, evt]);
          if (evt.type === "repo_created") setRepoUrl(evt.url);
          if (evt.type === "branch_pushed" && evt.url?.includes("/pull/")) setRepoUrl(evt.url);
          if (evt.type === "workflow_result") setRunUrl(evt.url);
          if (evt.type === "done") { setDone(true); setDoneStatus(evt.status || "pr_opened"); }
        },
        onDone:  () => setProvisioning(false),
        onError: (err) => { setProvisionEvents(p => [...p, { type: "error", message: err }]); setProvisioning(false); },
      }
    );
  }

  function reset() {
    setArchitecture(null); setStatuses([]); setClarifyQuestions([]);
    setClarifyAnswers({}); setDone(false); setStep("form");
  }

  return (
    <div className="p-6 lg:p-8 space-y-8 max-w-4xl animate-fade-in">
      <PageHeader
        title="Architecture Wizard"
        description="Describe your application in plain English — Stackport AI designs the AWS architecture following Well-Architected best practices, generates Terragrunt configs, and provisions everything end-to-end."
        breadcrumbs={["Platform", "Architect"]}
        actions={
          <Badge variant={geminiAvailable ? "success" : geminiAvailable === false ? "danger" : "default"} dot>
            {geminiAvailable ? "Gemini 2.5 Flash · Ready" : geminiAvailable === false ? "AI not configured" : "Checking…"}
          </Badge>
        }
      />

      {geminiAvailable === false && (
        <Card className="border-amber-500/25 bg-amber-500/5">
          <p className="text-sm text-amber-200 font-medium mb-1">Stackport AI not configured</p>
          <p className="text-xs text-[var(--text-muted)]">
            Set <code className="text-accent">GOOGLE_API_KEY</code> in the backend environment and restart.
            Free tier: 15 RPM, 1M tokens/day —{" "}
            <a href="https://aistudio.google.com/app/apikey" target="_blank" rel="noopener noreferrer" className="text-accent underline">get a key</a>.
          </p>
        </Card>
      )}

      {/* ── Step 1: Intake form ── */}
      {step === "form" && (
        <form onSubmit={handleClarify} className="space-y-5">
          <Card>
            <CardHeader title="Application details" description="Name, team, and target environment" />
            <div className="grid sm:grid-cols-3 gap-3 mt-3 mb-5">
              {[["App name", appName, setAppName, "payments-api"], ["Team name", teamName, setTeamName, "fintech"], null].map((field, i) =>
                field ? (
                  <div key={i}>
                    <label className="text-[11px] text-[var(--text-muted)] mb-1 block">{field[0]}</label>
                    <input value={field[1]} onChange={e => field[2](e.target.value)} required placeholder={field[3]}
                      className="w-full bg-[var(--bg-muted)] border border-[var(--border-default)] rounded-lg px-3 py-2 text-sm text-[var(--text-primary)] font-mono focus:outline-none focus:border-accent/50" />
                  </div>
                ) : (
                  <div key={i}>
                    <label className="text-[11px] text-[var(--text-muted)] mb-1 block">Environment</label>
                    <select value={env} onChange={e => setEnv(e.target.value)}
                      className="w-full bg-[var(--bg-muted)] border border-[var(--border-default)] rounded-lg px-3 py-2 text-sm text-[var(--text-primary)] focus:outline-none">
                      <option value="dev">dev</option>
                      <option value="staging">staging</option>
                      <option value="prod">prod</option>
                    </select>
                  </div>
                )
              )}
            </div>

            {/* Scale */}
            <div className="mb-5">
              <label className="text-[11px] text-[var(--text-muted)] mb-2 block font-semibold uppercase tracking-wide">Scale</label>
              <div className="grid grid-cols-3 gap-2">
                {SCALE_OPTIONS.map(o => (
                  <button key={o.value} type="button" onClick={() => setScale(o.value)}
                    className={`px-3 py-2.5 rounded-lg border text-left transition-all ${
                      scale === o.value
                        ? "border-accent/50 bg-accent-muted text-accent"
                        : "border-[var(--border-subtle)] text-[var(--text-muted)] hover:border-accent/30 hover:text-[var(--text-primary)]"
                    }`}>
                    <p className="text-xs font-medium">{o.label}</p>
                    <p className="text-[10px] opacity-70 mt-0.5">{o.sub}</p>
                  </button>
                ))}
              </div>
            </div>

            {/* Compliance */}
            <div className="mb-5">
              <label className="text-[11px] text-[var(--text-muted)] mb-2 block font-semibold uppercase tracking-wide">
                Compliance requirements
              </label>
              <div className="flex flex-wrap gap-2">
                {COMPLIANCE_OPTIONS.map(c => (
                  <button key={c} type="button" onClick={() => toggleCompliance(c)}
                    className={`px-3 py-1.5 rounded-lg border text-xs transition-all ${
                      compliance.includes(c)
                        ? "border-red-500/50 bg-red-500/10 text-red-300"
                        : "border-[var(--border-subtle)] text-[var(--text-muted)] hover:border-red-500/30"
                    }`}>
                    {compliance.includes(c) ? "✓ " : ""}{c}
                  </button>
                ))}
                <span className="text-[10px] text-[var(--text-faint)] self-center ml-1">
                  {compliance.length === 0 ? "None selected — standard security applied" : `${compliance.join(", ")} enforced`}
                </span>
              </div>
            </div>

            {/* Patterns */}
            <div className="mb-5">
              <label className="text-[11px] text-[var(--text-muted)] mb-2 block font-semibold uppercase tracking-wide">
                Architecture patterns
              </label>
              <div className="flex flex-wrap gap-2">
                {PATTERN_OPTIONS.map(p => (
                  <button key={p.value} type="button" onClick={() => togglePattern(p.value)}
                    className={`px-3 py-1.5 rounded-lg border text-xs transition-all ${
                      patterns.includes(p.value)
                        ? "border-accent/50 bg-accent-muted text-accent"
                        : "border-[var(--border-subtle)] text-[var(--text-muted)] hover:border-accent/30"
                    }`}>
                    {patterns.includes(p.value) ? "✓ " : ""}{p.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Requirements text */}
            <div>
              <label className="text-[11px] text-[var(--text-muted)] mb-2 block font-semibold uppercase tracking-wide">
                Describe your application
              </label>
              <textarea value={requirements} onChange={e => setRequirements(e.target.value)} required
                placeholder="Describe what your application does — tech stack, data patterns, user count, latency requirements, integrations…"
                rows={4}
                className="w-full bg-[var(--bg-muted)] border border-[var(--border-default)] rounded-xl px-4 py-3 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-faint)] resize-none focus:outline-none focus:border-accent/50 mb-3" />
              <div className="flex flex-wrap gap-1.5 mb-4">
                <span className="text-[10px] text-[var(--text-faint)] self-center">Try:</span>
                {EXAMPLES.map(ex => (
                  <button key={ex} type="button" onClick={() => setRequirements(ex)}
                    className="text-[10px] text-[var(--text-muted)] px-2 py-1 rounded-lg border border-[var(--border-subtle)] hover:border-accent/30 hover:text-accent hover:bg-accent-muted transition-colors text-left">
                    {ex.slice(0, 60)}…
                  </button>
                ))}
              </div>
              <Button type="submit" icon={Sparkles}
                disabled={clarifying || creating || !geminiAvailable || !appName || !teamName || !requirements}>
                {clarifying ? "Analysing requirements…" : "Design Architecture"}
              </Button>
            </div>
          </Card>
          {error && <p className="text-xs text-red-400">{error}</p>}
        </form>
      )}

      {/* ── Step 2: Clarifying questions (Phase C) ── */}
      {step === "clarify" && clarifyQuestions.length > 0 && (
        <Card>
          <div className="flex items-center gap-2 mb-4">
            <Sparkles size={14} className="text-accent" />
            <h3 className="text-sm font-semibold text-[var(--text-primary)]">A few quick questions</h3>
            <span className="text-[10px] text-[var(--text-faint)]">Helps Stackport AI design a more precise architecture</span>
          </div>
          <div className="space-y-4">
            {clarifyQuestions.map((q, i) => (
              <div key={i}>
                <label className="text-xs text-[var(--text-secondary)] mb-1.5 block">{q}</label>
                <input
                  value={clarifyAnswers[q] ?? ""}
                  onChange={e => setClarifyAnswers(p => ({ ...p, [q]: e.target.value }))}
                  placeholder="Your answer…"
                  className="w-full bg-[var(--bg-muted)] border border-[var(--border-default)] rounded-lg px-3 py-2 text-sm text-[var(--text-primary)] focus:outline-none focus:border-accent/50"
                />
              </div>
            ))}
          </div>
          <div className="flex gap-3 mt-5">
            <Button icon={Sparkles} onClick={handleGenerate} disabled={creating}>
              {creating ? "Designing…" : "Generate architecture"}
            </Button>
            <button type="button" onClick={() => { setClarifyQuestions([]); setStep("form"); }}
              className="text-xs text-[var(--text-muted)] hover:text-[var(--text-secondary)] transition-colors">
              ← Back
            </button>
          </div>
        </Card>
      )}

      {/* ── Step 3: Generating / Result ── */}
      {step === "result" && (
        <>
          {creating && (
            <div className="space-y-2">
              {statuses.map((s, i) => (
                <div key={i} className="flex items-center gap-2 text-sm text-[var(--text-muted)]">
                  {i === statuses.length - 1
                    ? <Loader2 size={14} className="animate-spin text-accent" />
                    : <CheckCircle size={14} className="text-emerald-500" />}
                  {s}
                </div>
              ))}
            </div>
          )}
          {error && <p className="text-xs text-red-400">{error}</p>}

          {architecture && !provisioning && !done && (
            <>
              <button onClick={reset}
                className="text-xs text-[var(--text-muted)] hover:text-[var(--text-secondary)] transition-colors">
                ← Start over
              </button>

              {/* Diagram */}
              {(architecture.svg_diagram || architecture.mermaid) && (
                <div className="space-y-2">
                  <p className="text-xs font-semibold text-[var(--text-muted)] uppercase tracking-widest flex items-center gap-2">
                    <span className="text-accent">◆</span> Architecture Diagram
                  </p>
                  <ArchitectureDiagram
                    svgDef={architecture.svg_diagram}
                    mermaidDef={architecture.mermaid}
                    architectureName={architecture.architecture_name}
                  />
                </div>
              )}

              {/* Architecture variants (Phase C) */}
              <div className="flex flex-wrap gap-2">
                <span className="text-[11px] text-[var(--text-faint)] self-center">Generate variant:</span>
                {[
                  { type: "ha",         label: "High Availability" },
                  { type: "cost",       label: "Cost-Optimized"    },
                  { type: "serverless", label: "Serverless"        },
                ].map(v => (
                  <button key={v.type} type="button"
                    onClick={() => handleVariant(v.type)}
                    disabled={creating}
                    className="text-[11px] px-3 py-1.5 rounded-lg border border-[var(--border-subtle)] text-[var(--text-muted)] hover:border-accent/40 hover:text-accent hover:bg-accent-muted transition-all disabled:opacity-40">
                    {variant === v.type && creating ? <Loader2 size={10} className="animate-spin inline mr-1" /> : null}
                    {v.label}
                  </button>
                ))}
              </div>

              <ArchitectureCard arch={architecture} onProvision={handleProvision} provisioning={provisioning} />

              <ArchitectureChat
                architecture={architecture}
                appName={appName}
                teamName={teamName}
                env={env}
                onArchitectureUpdate={(updated) => setArchitecture(updated)}
              />
            </>
          )}
        </>
      )}

      {/* Provision stream */}
      {(provisioning || provisionEvents.length > 0) && (
        <ProvisionStream events={provisionEvents} repoUrl={repoUrl} />
      )}

      {done && (() => {
        const isPassed = doneStatus === "plan_passed";
        const isFailed = doneStatus === "plan_failed";
        return (
          <Card className={isFailed ? "border-red-500/25 bg-red-500/5" : isPassed ? "border-emerald-500/25 bg-emerald-500/5" : "border-amber-500/25 bg-amber-500/5"}>
            <div className="flex items-center gap-2 mb-2">
              {isFailed ? <XCircle size={16} className="text-red-400" /> : isPassed ? <CheckCircle size={16} className="text-emerald-400" /> : <AlertTriangle size={16} className="text-amber-400" />}
              <p className={`text-sm font-semibold ${isFailed ? "text-red-300" : isPassed ? "text-emerald-300" : "text-amber-300"}`}>
                {isFailed ? "Plan failed — action required" : isPassed ? "Plan passed — ready to apply" : "Configs pushed — PR opened"}
              </p>
            </div>
            <p className="text-xs text-[var(--text-muted)] mb-3">
              {isFailed
                ? "The tf-plan GitHub Actions job failed. Check AWS_ROLE_ARN secret and OIDC trust policy."
                : isPassed
                ? "All Terragrunt plans passed. Review the PR and merge to trigger apply."
                : "Terragrunt configs written and PR opened. Check GitHub Actions for plan results."}
            </p>
            <div className="flex flex-wrap gap-3">
              {isPassed && <a href="/deploy" className="text-xs text-accent hover:underline">Go to Deploy →</a>}
              {repoUrl && <a href={repoUrl} target="_blank" rel="noopener noreferrer" className="text-xs text-violet-400 hover:underline flex items-center gap-1"><ExternalLink size={10} />View PR</a>}
              {runUrl  && <a href={runUrl}  target="_blank" rel="noopener noreferrer" className={`text-xs flex items-center gap-1 hover:underline ${isFailed ? "text-red-400" : "text-sky-400"}`}><ExternalLink size={10} />{isFailed ? "See failure logs" : "View Actions run"}</a>}
            </div>
          </Card>
        );
      })()}
    </div>
  );
}
