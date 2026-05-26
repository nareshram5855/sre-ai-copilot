import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  BookOpen, ChevronDown, ChevronRight, Shield, CheckCircle2,
  Clock, Server, Layers, Network, Lock, Rocket, Code2, User,
} from "lucide-react";
import { PageShell } from "../components/layout/PageShell.jsx";
import { PageHeader } from "../components/layout/PageHeader.jsx";
import { MermaidDiagram } from "../components/docs/MermaidDiagram.jsx";
import {
  DOC_SECTIONS,
  TECH_STACK,
  COMPONENT_MAP,
  INTEGRATIONS,
  SECURITY_ITEMS,
  API_GROUPS,
  MERMAID,
} from "../components/docs/docsContent.js";

function StatusBadge({ status }) {
  const cls =
    status === "Shipped" || status === "Connected" || status === "Required (local)" || status === "Required"
      ? "text-emerald-400 bg-emerald-950/40 border-emerald-800/40"
      : status === "Optional" || status === "Plugin"
        ? "text-blue-400 bg-blue-950/40 border-blue-800/40"
        : status === "Placeholder"
          ? "text-amber-400 bg-amber-950/40 border-amber-800/40"
          : "text-gray-400 bg-gray-800/40 border-gray-700/40";
  return (
    <span className={`text-[10px] px-2 py-0.5 rounded-full border font-medium whitespace-nowrap ${cls}`}>
      {status}
    </span>
  );
}

function Collapsible({ title, summary, children, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="panel-card overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-start gap-3 px-4 py-3.5 text-left hover:bg-white/[0.02] transition-colors"
      >
        {open ? (
          <ChevronDown size={16} className="text-indigo-400 mt-0.5 shrink-0" />
        ) : (
          <ChevronRight size={16} className="text-gray-500 mt-0.5 shrink-0" />
        )}
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium text-white">{title}</p>
          {!open && summary && (
            <p className="text-xs text-gray-500 mt-1 line-clamp-2">{summary}</p>
          )}
        </div>
      </button>
      {open && (
        <div className="px-4 pb-4 pt-0 border-t border-sre-border/60 text-sm text-gray-300 leading-relaxed">
          {children}
        </div>
      )}
    </div>
  );
}

function SectionHeading({ id, icon: Icon, title, subtitle }) {
  return (
    <div id={id} className="scroll-mt-24 mb-5">
      <div className="flex items-center gap-2.5 mb-1">
        {Icon && <Icon size={18} className="text-indigo-400" />}
        <h2 className="text-lg font-semibold text-white tracking-tight">{title}</h2>
      </div>
      {subtitle && <p className="text-sm text-gray-400 max-w-3xl">{subtitle}</p>}
    </div>
  );
}

export function EnterpriseDocsPage() {
  const navigate = useNavigate();
  const [activeSection, setActiveSection] = useState("summary");

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio);
        if (visible[0]?.target?.id) {
          setActiveSection(visible[0].target.id);
        }
      },
      { rootMargin: "-20% 0px -60% 0px", threshold: [0, 0.25, 0.5] },
    );

    DOC_SECTIONS.forEach(({ id }) => {
      const el = document.getElementById(id);
      if (el) observer.observe(el);
    });
    return () => observer.disconnect();
  }, []);

  function scrollTo(id) {
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
    setActiveSection(id);
  }

  return (
    <PageShell constrained className="pb-16">
      <PageHeader
        title="Enterprise Architecture"
        description="Stakeholder-friendly overview of SRE AI Copilot — what it does, how it is built, and how data flows from alert to resolution."
        icon={BookOpen}
        badges={
          <>
            <span className="text-[10px] px-2.5 py-1 rounded-md border border-indigo-500/30 bg-indigo-950/30 text-indigo-300 font-medium">
              v0.1.0
            </span>
            <span className="text-[10px] px-2.5 py-1 rounded-md border border-emerald-800/40 bg-emerald-950/20 text-emerald-400 font-medium">
              On-prem first
            </span>
          </>
        }
        actions={
          <button
            type="button"
            onClick={() => navigate("/resume")}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-gray-300 border border-sre-border hover:border-indigo-500/40 hover:text-white hover:bg-indigo-950/20 transition-all"
          >
            <User size={14} />
            Resume & Portfolio
          </button>
        }
      />

      <div className="flex gap-8 items-start">
        {/* In-page TOC */}
        <nav
          className="hidden lg:block w-52 shrink-0 sticky top-6 self-start"
          aria-label="Documentation sections"
        >
          <p className="text-[10px] font-bold text-gray-600 uppercase tracking-widest mb-3 px-2">
            On this page
          </p>
          <ul className="space-y-0.5">
            {DOC_SECTIONS.map(({ id, label }) => (
              <li key={id}>
                <button
                  type="button"
                  onClick={() => scrollTo(id)}
                  className={`w-full text-left px-3 py-2 rounded-lg text-xs transition-all ${
                    activeSection === id
                      ? "bg-indigo-600/15 text-indigo-200 border border-indigo-500/25 font-medium"
                      : "text-gray-500 hover:text-gray-300 hover:bg-white/[0.03] border border-transparent"
                  }`}
                >
                  {label}
                </button>
              </li>
            ))}
          </ul>
        </nav>

        {/* Main content */}
        <div className="flex-1 min-w-0 space-y-12">
          {/* Executive Summary */}
          <section>
            <SectionHeading
              id="summary"
              icon={Shield}
              title="Executive Summary"
              subtitle="Plain-language overview for engineering leaders and platform stakeholders."
            />
            <div className="grid gap-4 md:grid-cols-3 mb-6">
              {[
                {
                  label: "Problem",
                  text: "On-call teams drown in alerts, lose tribal knowledge, and repeat the same fixes weekly.",
                  color: "border-red-800/40 bg-red-950/10",
                },
                {
                  label: "Solution",
                  text: "An on-prem AI copilot that triages alerts, retrieves runbooks, executes fixes with guardrails, and learns from every resolution.",
                  color: "border-indigo-800/40 bg-indigo-950/10",
                },
                {
                  label: "Outcome",
                  text: "Faster MTTR, fewer escalations, auditable automation — without sending sensitive infra data to the cloud by default.",
                  color: "border-emerald-800/40 bg-emerald-950/10",
                },
              ].map((card) => (
                <div key={card.label} className={`panel-card p-4 border ${card.color}`}>
                  <p className="text-[10px] uppercase tracking-widest text-gray-500 font-semibold mb-2">
                    {card.label}
                  </p>
                  <p className="text-sm text-gray-300 leading-relaxed">{card.text}</p>
                </div>
              ))}
            </div>

            <div className="panel-card p-5 space-y-3">
              <p className="text-sm text-gray-300 leading-relaxed">
                <strong className="text-white font-medium">SRE AI Copilot</strong> sits between your
                alerting stack (Prometheus / AlertManager) and your on-call engineers. It uses a local
                large language model plus a searchable knowledge base of your runbooks and past incidents
                to classify severity, suggest exact remediation commands, and — when confidence is high
                enough — execute fixes with human approval gates.
              </p>
              <p className="text-sm text-gray-400 leading-relaxed">
                Real-time updates reach the UI through Server-Sent Events, optionally backed by Kafka for
                durable fan-out. Redis persistence, SQLite audit trails, and LangGraph checkpointing
                support production-grade state — all with in-memory fallbacks for local development.
              </p>
            </div>

            <div className="mt-4">
            <Collapsible
              title="Technical capabilities (expand for detail)"
              summary="Multi-agent LangGraph orchestration, RAG over ChromaDB, tiered LLM routing, proactive anomaly watch."
            >
              <ul className="space-y-2 text-sm text-gray-400 list-disc pl-5">
                <li>Seven specialist agents: Triage, Chat, Runbook, RCA, Executor, Supervisor, Learning</li>
                <li>RAG collections: runbooks, incidents, architecture, resolved_incidents</li>
                <li>ExecutorAgent: parallel K8s gather → ReAct loop → write approval interrupt</li>
                <li>Observe page: Prometheus + Loki live telemetry with SSE anomaly stream</li>
                <li>Voice input plugin (optional Whisper STT) for hands-free chat</li>
              </ul>
            </Collapsible>
            </div>
          </section>

          {/* Tech Stack */}
          <section>
            <SectionHeading
              id="tech-stack"
              icon={Layers}
              title="Tech Stack"
              subtitle="Technologies in production use today, grouped by platform layer."
            />
            <div className="panel-card overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-sre-border text-left">
                    <th className="px-4 py-3 text-[10px] uppercase tracking-widest text-gray-500 font-semibold">
                      Layer
                    </th>
                    <th className="px-4 py-3 text-[10px] uppercase tracking-widest text-gray-500 font-semibold">
                      Technology
                    </th>
                    <th className="px-4 py-3 text-[10px] uppercase tracking-widest text-gray-500 font-semibold hidden md:table-cell">
                      Role
                    </th>
                    <th className="px-4 py-3 text-[10px] uppercase tracking-widest text-gray-500 font-semibold">
                      Status
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {TECH_STACK.map((row) => (
                    <tr key={row.layer} className="border-b border-sre-border/60 last:border-0 hover:bg-white/[0.02]">
                      <td className="px-4 py-3 font-medium text-white whitespace-nowrap">{row.layer}</td>
                      <td className="px-4 py-3 text-gray-300 font-mono text-xs">{row.technology}</td>
                      <td className="px-4 py-3 text-gray-400 hidden md:table-cell max-w-md">{row.role}</td>
                      <td className="px-4 py-3">
                        <StatusBadge status={row.status} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          {/* Architecture Overview */}
          <section>
            <SectionHeading
              id="architecture"
              icon={Network}
              title="Architecture Overview"
              subtitle="System context and internal component relationships."
            />
            <div className="space-y-6">
              <MermaidDiagram
                title="System Context"
                chart={MERMAID.systemContext}
                caption="Users interact with the React UI. External observability systems feed alerts and telemetry. AI workloads stay local unless external LLM tiers are explicitly enabled."
              />
              <MermaidDiagram
                title="Container / Component View"
                chart={MERMAID.containers}
                caption="Frontend panels call FastAPI routers. Agents share RAG and persistence layers. Observability feeds proactive anomaly detection."
              />
            </div>
          </section>

          {/* Data Flows */}
          <section>
            <SectionHeading
              id="data-flows"
              icon={Server}
              title="Data Flows"
              subtitle="How alerts, observability signals, and agent actions move through the platform."
            />
            <div className="space-y-6">
              <MermaidDiagram
                title="Alert → Triage → Kafka/SSE → UI"
                chart={MERMAID.alertTriageFlow}
                caption="AlertManager webhooks trigger background triage. Events fan out via Kafka (when enabled) and always via in-process SSE to the React UI."
              />
              <MermaidDiagram
                title="Observability Pipeline"
                chart={MERMAID.observabilityPipeline}
                caption="Synthetic demo apps emit metrics and logs. anomaly_watcher scans Prometheus; Observe page queries /observability APIs."
              />
              <MermaidDiagram
                title="Agent Execution Loop"
                chart={MERMAID.agentLoop}
                caption="Supervisor routes to specialists. ExecutorAgent runs a LangGraph ReAct loop with parallel gather and human-in-the-loop write gates."
              />
              <MermaidDiagram
                title="Incident Lifecycle (Sequence)"
                chart={MERMAID.incidentLifecycle}
                caption="End-to-end path from pod failure through triage, optional auto-execution, and learning ingestion."
              />
            </div>
          </section>

          {/* Component Map */}
          <section>
            <SectionHeading
              id="components"
              icon={Code2}
              title="Component Map"
              subtitle="Major folders and modules — mapped from the actual repository layout."
            />
            <div className="space-y-3">
              {COMPONENT_MAP.map((item) => (
                <Collapsible
                  key={item.path}
                  title={item.path}
                  summary={item.purpose}
                  defaultOpen={item.path.startsWith("backend/agents") || item.path.startsWith("frontend")}
                >
                  <p className="mb-3 text-gray-400">{item.purpose}</p>
                  <div className="flex flex-wrap gap-1.5">
                    {item.modules.map((m) => (
                      <span
                        key={m}
                        className="text-[11px] font-mono px-2 py-1 rounded-md bg-sre-bg border border-sre-border text-gray-400"
                      >
                        {m}
                      </span>
                    ))}
                  </div>
                </Collapsible>
              ))}
            </div>
          </section>

          {/* Integrations */}
          <section>
            <SectionHeading
              id="integrations"
              icon={Network}
              title="Integration Points"
              subtitle="External systems — connected, optional, or planned placeholder."
            />
            <div className="grid gap-3 sm:grid-cols-2">
              {INTEGRATIONS.map((integ) => (
                <div key={integ.name} className="panel-card p-4">
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <h3 className="text-sm font-semibold text-white">{integ.name}</h3>
                    <StatusBadge status={integ.status} />
                  </div>
                  <p className="text-xs text-gray-400 mb-2 leading-relaxed">{integ.description}</p>
                  <p className="text-[10px] font-mono text-gray-600">{integ.config}</p>
                </div>
              ))}
            </div>
          </section>

          {/* Security */}
          <section>
            <SectionHeading
              id="security"
              icon={Lock}
              title="Security & Compliance Posture"
              subtitle="Honest assessment — what ships today vs. enterprise hardening on the roadmap."
            />
            <div className="grid gap-4 md:grid-cols-2">
              <div className="panel-card p-4 border-emerald-900/30">
                <div className="flex items-center gap-2 mb-3">
                  <CheckCircle2 size={16} className="text-emerald-400" />
                  <h3 className="text-sm font-semibold text-emerald-300">Implemented</h3>
                </div>
                <ul className="space-y-2">
                  {SECURITY_ITEMS.implemented.map((item) => (
                    <li key={item} className="text-xs text-gray-400 flex gap-2 leading-relaxed">
                      <span className="text-emerald-600 shrink-0">•</span>
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
              <div className="panel-card p-4 border-amber-900/30">
                <div className="flex items-center gap-2 mb-3">
                  <Clock size={16} className="text-amber-400" />
                  <h3 className="text-sm font-semibold text-amber-300">Planned / Roadmap</h3>
                </div>
                <ul className="space-y-2">
                  {SECURITY_ITEMS.planned.map((item) => (
                    <li key={item} className="text-xs text-gray-400 flex gap-2 leading-relaxed">
                      <span className="text-amber-600 shrink-0">•</span>
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </section>

          {/* Deployment */}
          <section>
            <SectionHeading
              id="deployment"
              icon={Rocket}
              title="Deployment Topology"
              subtitle="Local Minikube development vs. production target architecture."
            />
            <div className="grid gap-4 lg:grid-cols-2">
              <div className="panel-card p-5">
                <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-emerald-400" />
                  Development (Minikube + host-native)
                </h3>
                <ul className="space-y-2 text-xs text-gray-400">
                  <li><span className="text-gray-500">Frontend</span> — Vite dev server on localhost:5173</li>
                  <li><span className="text-gray-500">Backend</span> — FastAPI on localhost:8080 (native venv, hot reload)</li>
                  <li><span className="text-gray-500">Ollama</span> — native macOS :11434 (Metal GPU)</li>
                  <li><span className="text-gray-500">ChromaDB</span> — Minikube pod, port-forward :8000</li>
                  <li><span className="text-gray-500">Observability</span> — Prometheus :19090, Loki :13100 (port-forward)</li>
                  <li><span className="text-gray-500">Kafka / Redis</span> — optional K8s manifests, port-forward when enabled</li>
                  <li><span className="text-gray-500">AlertManager</span> — webhook to host.minikube.internal:8080</li>
                </ul>
              </div>
              <div className="panel-card p-5 border-dashed border-indigo-800/40">
                <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-indigo-400" />
                  Production Target (Phase 4)
                </h3>
                <ul className="space-y-2 text-xs text-gray-400">
                  <li><span className="text-gray-500">Compute</span> — EKS with Karpenter node autoscaling</li>
                  <li><span className="text-gray-500">GitOps</span> — ArgoCD + Helm charts from infrastructure/</li>
                  <li><span className="text-gray-500">IaC</span> — Terraform modules for VPC, EKS, RDS/ElastiCache</li>
                  <li><span className="text-gray-500">CI/CD</span> — GitHub Actions build → scan → deploy pipeline</li>
                  <li><span className="text-gray-500">Secrets</span> — External Secrets Operator / AWS Secrets Manager</li>
                  <li><span className="text-gray-500">Observability</span> — Managed Prometheus/Grafana or in-cluster stack</li>
                  <li><span className="text-gray-500">HA</span> — Redis cluster, Kafka MSK, multi-replica backend</li>
                </ul>
              </div>
            </div>
          </section>

          {/* API Overview */}
          <section>
            <SectionHeading
              id="api"
              icon={Code2}
              title="API Overview"
              subtitle="Key REST and SSE endpoints grouped by domain. Full OpenAPI at /docs on the backend."
            />
            <div className="space-y-4">
              {API_GROUPS.map((group) => (
                <Collapsible
                  key={group.domain}
                  title={group.domain}
                  summary={`${group.endpoints.length} endpoints`}
                  defaultOpen={group.domain === "Incidents & Triage"}
                >
                  <div className="overflow-x-auto -mx-1">
                    <table className="w-full text-xs mt-2">
                      <thead>
                        <tr className="text-left text-gray-600">
                          <th className="pb-2 pr-3 font-semibold">Method</th>
                          <th className="pb-2 pr-3 font-semibold">Path</th>
                          <th className="pb-2 font-semibold">Description</th>
                        </tr>
                      </thead>
                      <tbody>
                        {group.endpoints.map((ep) => (
                          <tr key={ep.path + ep.method} className="border-t border-sre-border/40">
                            <td className="py-2 pr-3">
                              <span className="font-mono text-indigo-400">{ep.method}</span>
                            </td>
                            <td className="py-2 pr-3 font-mono text-gray-300 whitespace-nowrap">{ep.path}</td>
                            <td className="py-2 text-gray-500">{ep.desc}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </Collapsible>
              ))}
            </div>
          </section>
        </div>
      </div>
    </PageShell>
  );
}
