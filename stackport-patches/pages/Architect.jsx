import { useState, useEffect, useRef } from "react";
import { Sparkles, Layers, Shield,
         CheckCircle, XCircle, AlertTriangle, Loader2, ChevronDown, ChevronRight,
         Server, Database, Globe, Lock, Zap, Rocket, ExternalLink } from "lucide-react";
import PageHeader from "../components/ui/PageHeader.jsx";
import { Card, CardHeader } from "../components/ui/Card.jsx";
import Badge from "../components/ui/Badge.jsx";
import Button from "../components/ui/Button.jsx";
import { fetchJSON } from "../utils/api.js";
import ArchitectureDiagram from "../components/ai/ArchitectureDiagram.jsx";
import ArchitectureChat from "../components/ai/ArchitectureChat.jsx";

const CATEGORY_ICONS = {
  networking: Globe, compute: Server, data: Database,
  security: Lock, cicd: Zap, storage: Layers,
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

// ── Architecture card ─────────────────────────────────────────────────────────

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

function ArchitectureCard({ arch, onProvision, provisioning }) {
  // Support both old long-form and new compact schema
  const security = arch.security ?? arch.security_analysis ?? {};
  const cost = arch.cost ?? arch.estimated_monthly_cost ?? {};
  const repo = arch.repo ?? arch.repo_structure ?? null;
  // Normalise security fields
  const sox = security.sox ?? security.sox_compliant ?? false;
  const pci = security.pci ?? security.pci_compliant ?? false;
  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <Card className="border-accent/30 bg-gradient-to-br from-accent/5 to-transparent">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <Sparkles size={15} className="text-accent" />
              <p className="text-[10px] font-bold uppercase tracking-widest text-accent">Stackport AI Architecture</p>
            </div>
            <h2 className="text-lg font-semibold text-[var(--text-primary)] mb-1">{arch.architecture_name}</h2>
            <p className="text-sm text-[var(--text-muted)] leading-relaxed max-w-2xl">{arch.summary}</p>
          </div>
          <div className="flex flex-col gap-2 shrink-0">
            <Badge variant={sox ? "success" : "warning"}>SOX {sox ? "✓" : "⚠"}</Badge>
            <Badge variant={pci ? "success" : "warning"}>PCI {pci ? "✓" : "⚠"}</Badge>
          </div>
        </div>
      </Card>

      {/* Modules */}
      <div>
        <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-3 flex items-center gap-2">
          <Layers size={14} className="text-accent" />
          {arch.modules?.length} AWS modules to provision
          <span className="text-[11px] text-[var(--text-muted)] font-normal">— deployed in order</span>
        </h3>
        <div className="space-y-2">
          {(arch.modules ?? []).sort((a,b) => a.deploy_order - b.deploy_order).map((m, i) => (
            <ModuleCard key={i} mod={m} />
          ))}
        </div>
      </div>

      {/* Security flags */}
      {security.flags?.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-3 flex items-center gap-2">
            <Shield size={14} className="text-amber-400" /> Security flags
          </h3>
          <div className="space-y-2">
            {security.flags.map((f, i) =>
              typeof f === "string"
                ? <div key={i} className="flex items-start gap-2 p-2 rounded-lg border border-amber-500/20 bg-amber-500/10 text-xs text-amber-300"><Shield size={11} className="shrink-0 mt-0.5" />{f}</div>
                : <SecurityFlag key={i} flag={f} />
            )}
          </div>
        </div>
      )}

      {/* Cost + Repo */}
      <div className="grid sm:grid-cols-2 gap-4">
        {cost.min_usd && (
          <Card>
            <CardHeader title="Estimated cost" description="Monthly estimate" />
            <p className="text-2xl font-bold text-[var(--text-primary)] mb-2">
              ${cost.min_usd}–${cost.max_usd}<span className="text-sm font-normal text-[var(--text-muted)]">/mo</span>
            </p>
            {cost.note && <p className="text-[11px] text-[var(--text-muted)]">• {cost.note}</p>}
            {(cost.breakdown ?? []).map((b, i) => <p key={i} className="text-[11px] text-[var(--text-muted)]">• {b}</p>)}
          </Card>
        )}
        {repo && (
          <Card>
            <CardHeader title="App scaffold" description="Generated repo structure" />
            <div className="space-y-1.5">
              {[["Language", repo.language], ["Framework", repo.framework], ["Deploy target", repo.deploy_target]].map(([k, v]) => v ? (
                <div key={k} className="flex items-center justify-between text-xs">
                  <span className="text-[var(--text-muted)]">{k}</span>
                  <Badge variant="default">{v}</Badge>
                </div>
              ) : null)}
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
          Writes Terragrunt configs · runs plan · creates GitHub repo & app scaffold
        </p>
      </div>
    </div>
  );
}

// ── Provision stream ──────────────────────────────────────────────────────────

function ProvisionStream({ events, repoUrl }) {
  const bottomRef = useRef(null);
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [events]);

  // Extract key links from events
  const prEvent = events.find(e => e.type === "branch_pushed" && e.url?.includes("/pull/"));
  const branchEvent = events.find(e => e.type === "branch_pushed");
  const workflowEvent = events.find(e => e.type === "workflow_started");
  const repoEvent = events.find(e => e.type === "repo_created");

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-semibold text-[var(--text-primary)] flex items-center gap-2">
        <Rocket size={14} className="text-accent" />
        Provisioning in progress
      </h3>

      {/* Key action links — shown prominently as they appear */}
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

      {/* Log stream */}
      <div className="bg-[#0a0a0c] border border-[var(--border-subtle)] rounded-xl p-4 font-mono text-[11px] space-y-1 max-h-72 overflow-y-auto">
        {events.map((evt, i) => {
          if (evt.type === "status")
            return <p key={i} className="text-[var(--text-muted)]">→ {evt.message}</p>;
          if (evt.type === "file_written")
            return <p key={i} className="text-emerald-400/80">  ✓ {evt.path}</p>;
          if (evt.type === "log" && evt.line?.trim())
            return <p key={i} className="text-[var(--text-faint)] pl-2 whitespace-pre-wrap">{evt.line.trim()}</p>;
          if (evt.type === "error")
            return <p key={i} className="text-red-400">✗ {evt.message}</p>;
          if (evt.type === "repo_created")
            return <p key={i} className="text-violet-400">✓ {evt.url}</p>;
          if (evt.type === "branch_pushed")
            return <p key={i} className="text-sky-400">✓ branch: {evt.branch}</p>;
          return null;
        })}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

const EXAMPLES = [
  "Node.js REST API for a payments microservice with PostgreSQL, Redis cache, and JWT auth",
  "Python ML inference service with GPU-backed ECS, S3 model storage, and CloudFront CDN",
  "React static site on S3 + CloudFront with a Lambda API and DynamoDB backend",
  "Java Spring Boot app on EKS with Aurora PostgreSQL, multi-AZ, SOX compliance required",
];

export default function Architect() {
  const [geminiAvailable, setGeminiAvailable] = useState(null);
  const [requirements, setRequirements] = useState("");
  const [appName, setAppName] = useState("");
  const [teamName, setTeamName] = useState("");
  const [env, setEnv] = useState("dev");
  const [creating, setCreating] = useState(false);
  const [statuses, setStatuses] = useState([]);
  const [architecture, setArchitecture] = useState(null);
  const [error, setError] = useState("");

  const [provisioning, setProvisioning] = useState(false);
  const [provisionEvents, setProvisionEvents] = useState([]);
  const [repoUrl, setRepoUrl] = useState("");
  const [done, setDone] = useState(false);
  const [doneStatus, setDoneStatus] = useState(""); // plan_passed | plan_failed | pr_opened
  const [runUrl, setRunUrl] = useState("");

  useEffect(() => {
    fetchJSON("/ai/architect/status")
      .then(d => setGeminiAvailable(d.available))
      .catch(() => setGeminiAvailable(false));
  }, []);

  function slugify(v) {
    return v.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 40);
  }

  async function handleGenerate(e) {
    e.preventDefault();
    setCreating(true); setError(""); setStatuses([]); setArchitecture(null);
    await streamPost("/architect",
      { requirements, app_name: slugify(appName) || appName, team_name: slugify(teamName) || teamName, env },
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

  return (
    <div className="p-6 lg:p-8 space-y-8 max-w-4xl animate-fade-in">
      <PageHeader
        title="Architecture Wizard"
        description="Describe what you need — Stackport AI designs the AWS architecture, writes Terragrunt configs, and provisions everything end-to-end."
        breadcrumbs={["Platform", "Architect"]}
        actions={
          <Badge variant={geminiAvailable ? "success" : geminiAvailable === false ? "danger" : "default"} dot>
            {geminiAvailable ? "Stackport AI ready" : geminiAvailable === false ? "AI not configured" : "Checking…"}
          </Badge>
        }
      />

      {geminiAvailable === false && (
        <Card className="border-amber-500/25 bg-amber-500/5">
          <p className="text-sm text-amber-200 font-medium mb-1">Stackport AI not configured</p>
          <p className="text-xs text-[var(--text-muted)]">
            Set <code className="text-accent">GOOGLE_API_KEY</code> in the backend environment and restart.
            Free tier: 15 RPM, 1M tokens/day — <a href="https://aistudio.google.com/app/apikey" target="_blank" rel="noopener noreferrer" className="text-accent underline">get a key</a>.
          </p>
        </Card>
      )}

      {/* Input form */}
      {!architecture && (
        <form onSubmit={handleGenerate} className="space-y-5">
          <Card>
            <CardHeader title="Describe your requirements" description="Plain English — include language, team, scale, and compliance needs" />
            <div className="grid sm:grid-cols-3 gap-3 mb-4">
              <div>
                <label className="text-[11px] text-[var(--text-muted)] mb-1 block">App name</label>
                <input value={appName} onChange={e => setAppName(e.target.value)} required
                  placeholder="payments-api"
                  className="w-full bg-[var(--bg-muted)] border border-[var(--border-default)] rounded-lg px-3 py-2 text-sm text-[var(--text-primary)] font-mono focus:outline-none focus:border-accent/50" />
              </div>
              <div>
                <label className="text-[11px] text-[var(--text-muted)] mb-1 block">Team name</label>
                <input value={teamName} onChange={e => setTeamName(e.target.value)} required
                  placeholder="fintech"
                  className="w-full bg-[var(--bg-muted)] border border-[var(--border-default)] rounded-lg px-3 py-2 text-sm text-[var(--text-primary)] font-mono focus:outline-none focus:border-accent/50" />
              </div>
              <div>
                <label className="text-[11px] text-[var(--text-muted)] mb-1 block">Environment</label>
                <select value={env} onChange={e => setEnv(e.target.value)}
                  className="w-full bg-[var(--bg-muted)] border border-[var(--border-default)] rounded-lg px-3 py-2 text-sm text-[var(--text-primary)] focus:outline-none">
                  <option value="dev">dev</option>
                  <option value="staging">staging</option>
                  <option value="prod">prod</option>
                </select>
              </div>
            </div>
            <textarea value={requirements} onChange={e => setRequirements(e.target.value)} required
              placeholder="Describe your application — language, expected load, data storage, auth, compliance requirements, team size…"
              rows={5}
              className="w-full bg-[var(--bg-muted)] border border-[var(--border-default)] rounded-xl px-4 py-3 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-faint)] resize-none focus:outline-none focus:border-accent/50 mb-3" />
            <div className="flex flex-wrap gap-1.5 mb-4">
              <span className="text-[10px] text-[var(--text-faint)] self-center">Examples:</span>
              {EXAMPLES.map(ex => (
                <button key={ex} type="button" onClick={() => setRequirements(ex)}
                  className="text-[10px] text-[var(--text-muted)] px-2 py-1 rounded-lg border border-[var(--border-subtle)] hover:border-accent/30 hover:text-accent hover:bg-accent-muted transition-colors text-left">
                  {ex.slice(0, 55)}…
                </button>
              ))}
            </div>
            <Button type="submit" icon={Sparkles} disabled={creating || !geminiAvailable || !appName || !teamName || !requirements}>
              {creating ? "Stackport AI is designing…" : "Design with Stackport AI"}
            </Button>
          </Card>

          {statuses.length > 0 && (
            <div className="flex items-center gap-2 text-sm text-[var(--text-muted)]">
              <Loader2 size={14} className="animate-spin text-accent" />
              {statuses[statuses.length - 1]}
            </div>
          )}
          {error && <p className="text-xs text-red-400">{error}</p>}
        </form>
      )}

      {/* Architecture result */}
      {architecture && !provisioning && !done && (
        <>
          <button onClick={() => { setArchitecture(null); setStatuses([]); }}
            className="text-xs text-[var(--text-muted)] hover:text-[var(--text-secondary)] transition-colors">
            ← Start over
          </button>

          {/* Architecture diagram — shown prominently before module list */}
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

          <ArchitectureCard arch={architecture} onProvision={handleProvision} provisioning={provisioning} />

          {/* Chat panel for iterative changes */}
          <ArchitectureChat
            architecture={architecture}
            appName={appName}
            teamName={teamName}
            env={env}
            onArchitectureUpdate={(updated) => setArchitecture(updated)}
          />
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
          <Card className={
            isFailed ? "border-red-500/25 bg-red-500/5"
            : isPassed ? "border-emerald-500/25 bg-emerald-500/5"
            : "border-amber-500/25 bg-amber-500/5"
          }>
            <div className="flex items-center gap-2 mb-2">
              {isFailed
                ? <XCircle size={16} className="text-red-400" />
                : isPassed
                ? <CheckCircle size={16} className="text-emerald-400" />
                : <AlertTriangle size={16} className="text-amber-400" />}
              <p className={`text-sm font-semibold ${isFailed ? "text-red-300" : isPassed ? "text-emerald-300" : "text-amber-300"}`}>
                {isFailed ? "Plan failed — action required"
                  : isPassed ? "Plan passed — ready to apply"
                  : "Configs pushed — plan still running"}
              </p>
            </div>
            <p className="text-xs text-[var(--text-muted)] mb-3">
              {isFailed
                ? "The tf-plan GitHub Actions job failed. Likely cause: AWS_ROLE_ARN secret missing or OIDC trust policy not configured for this repo."
                : isPassed
                ? "All Terragrunt plans passed. Review the PR and merge to trigger apply."
                : "Terragrunt configs written and PR opened. Check GitHub Actions for plan results."}
            </p>
            <div className="flex flex-wrap gap-3">
              {isPassed && <a href="/deploy" className="text-xs text-accent hover:text-accent-hover transition-colors">Go to Deploy →</a>}
              {repoUrl && (
                <a href={repoUrl} target="_blank" rel="noopener noreferrer"
                  className="text-xs text-violet-400 hover:text-violet-300 transition-colors flex items-center gap-1">
                  <ExternalLink size={10} />View PR
                </a>
              )}
              {runUrl && (
                <a href={runUrl} target="_blank" rel="noopener noreferrer"
                  className="text-xs text-red-400 hover:text-red-300 transition-colors flex items-center gap-1">
                  <ExternalLink size={10} />{isFailed ? "See failure logs" : "View Actions run"}
                </a>
              )}
            </div>
          </Card>
        );
      })()}
    </div>
  );
}
