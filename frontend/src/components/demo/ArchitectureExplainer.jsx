import { useState, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import {
  Play, Github, ExternalLink, ChevronRight, ArrowDown, Clock,
  Layout, Server, Brain, Database, Activity, Cloud,
  Ticket, Filter, Shield, FileText, BarChart3,
} from "lucide-react";
import { DEMO_LANDING, DEMO_TOUR_STEPS } from "../../data/demoTourContent.js";
import { DEMO_METRICS, FEATURED_PROJECT, TECH_STACK_COMPARISON } from "../../data/resumeContent.js";
import {
  ARCHITECTURE_SECTIONS,
  INCIDENT_FLOW_STEPS,
  COMPONENT_LAYERS,
  TOOL_STACK_CATEGORIES,
  ENTERPRISE_BENEFITS,
  SIXTY_SECOND_SUMMARY,
} from "../../data/architectureExplainerContent.js";
import { ArchitectureDiagram } from "./ArchitectureDiagram.jsx";
import { getTourStepFromSearchParams, isDemoTourActive } from "../../utils/demoTour.js";

const LAYER_ICONS = {
  layout: Layout,
  server: Server,
  brain: Brain,
  database: Database,
  activity: Activity,
  cloud: Cloud,
};

const BENEFIT_ICONS = {
  ticket: Ticket,
  filter: Filter,
  shield: Shield,
  file: FileText,
  clock: Clock,
  chart: BarChart3,
};

const ACCENT_STYLES = {
  teal: {
    border: "border-teal-500/30",
    bg: "bg-teal-950/25",
    text: "text-teal-300",
    dot: "bg-teal-400",
    ring: "ring-teal-500/40",
  },
  indigo: {
    border: "border-indigo-500/30",
    bg: "bg-indigo-950/25",
    text: "text-indigo-300",
    dot: "bg-indigo-400",
    ring: "ring-indigo-500/40",
  },
  amber: {
    border: "border-amber-500/30",
    bg: "bg-amber-950/25",
    text: "text-amber-300",
    dot: "bg-amber-400",
    ring: "ring-amber-500/40",
  },
  violet: {
    border: "border-violet-500/30",
    bg: "bg-violet-950/25",
    text: "text-violet-300",
    dot: "bg-violet-400",
    ring: "ring-violet-500/40",
  },
  emerald: {
    border: "border-emerald-500/30",
    bg: "bg-emerald-950/25",
    text: "text-emerald-300",
    dot: "bg-emerald-400",
    ring: "ring-emerald-500/40",
  },
  sky: {
    border: "border-sky-500/30",
    bg: "bg-sky-950/25",
    text: "text-sky-300",
    dot: "bg-sky-400",
    ring: "ring-sky-500/40",
  },
};

function scrollToSection(id) {
  document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
}

export function HeroTechStack({ compact = false, className = "" }) {
  const categories = FEATURED_PROJECT.techStackCategories ?? [];
  return (
    <div className={`arch-hero-stack ${className}`}>
      <p className="text-[9px] font-bold uppercase tracking-[0.14em] text-stone-500 mb-2">
        Tech stack
      </p>
      <div className={`grid gap-2 ${compact ? "sm:grid-cols-2" : "sm:grid-cols-2 lg:grid-cols-3"}`}>
        {categories.map((cat) => (
          <div
            key={cat.category}
            className="rounded-lg border border-sre-border/45 bg-sre-bg/30 px-2.5 py-2"
          >
            <p className="text-[9px] font-bold uppercase tracking-wide text-indigo-300/80 mb-1.5">
              {cat.category}
            </p>
            <div className="flex flex-wrap gap-1">
              {cat.tools.map((tool) => (
                <span
                  key={tool}
                  className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-sre-bg border border-sre-border/50 text-gray-400"
                >
                  {tool}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function SectionHeading({ id, title, subtitle }) {
  return (
    <div id={id} className="scroll-mt-24 mb-4">
      <h4 className="text-sm font-bold text-white">{title}</h4>
      {subtitle && <p className="text-xs text-gray-500 mt-1 leading-relaxed max-w-2xl">{subtitle}</p>}
    </div>
  );
}

function FlowPipeline() {
  const [activeId, setActiveId] = useState(INCIDENT_FLOW_STEPS[0].id);
  const active = INCIDENT_FLOW_STEPS.find((s) => s.id === activeId) ?? INCIDENT_FLOW_STEPS[0];
  const activeStyle = ACCENT_STYLES[active.accent] ?? ACCENT_STYLES.indigo;

  return (
    <div className="arch-flow">
      <div className="arch-flow-track overflow-x-auto pb-2 -mx-1 px-1">
        <div className="arch-flow-steps flex items-stretch gap-0 min-w-max sm:min-w-0 sm:flex-wrap sm:justify-center">
          {INCIDENT_FLOW_STEPS.map((step, idx) => {
            const style = ACCENT_STYLES[step.accent] ?? ACCENT_STYLES.indigo;
            const isActive = step.id === activeId;
            return (
              <div key={step.id} className="arch-flow-step-wrap flex items-center">
                <button
                  type="button"
                  onClick={() => setActiveId(step.id)}
                  className={`arch-flow-step group relative flex flex-col items-center gap-1.5 px-2 py-2 rounded-xl transition-all ${
                    isActive ? `ring-2 ${style.ring} ${style.bg}` : "hover:bg-white/[0.03]"
                  }`}
                  aria-pressed={isActive}
                  aria-label={`Step ${step.step}: ${step.title}`}
                >
                  <span
                    className={`arch-flow-num w-7 h-7 rounded-full flex items-center justify-center text-[11px] font-bold font-mono border ${
                      isActive
                        ? `${style.border} ${style.bg} ${style.text}`
                        : "border-sre-border/60 bg-sre-bg/50 text-gray-500 group-hover:text-gray-300"
                    }`}
                  >
                    {step.step}
                  </span>
                  <span
                    className={`text-[10px] font-medium text-center leading-tight max-w-[4.5rem] sm:max-w-none ${
                      isActive ? "text-white" : "text-gray-500 group-hover:text-gray-300"
                    }`}
                  >
                    {step.short}
                  </span>
                </button>
                {idx < INCIDENT_FLOW_STEPS.length - 1 && (
                  <ChevronRight
                    size={14}
                    className="arch-flow-arrow shrink-0 text-indigo-500/40 mx-0.5 hidden sm:block"
                    aria-hidden="true"
                  />
                )}
              </div>
            );
          })}
        </div>
      </div>

      <div className={`arch-flow-detail mt-3 rounded-xl border p-4 ${activeStyle.border} ${activeStyle.bg}`}>
        <div className="flex flex-wrap items-center gap-2 mb-2">
          <span className={`text-[10px] font-bold uppercase tracking-wide ${activeStyle.text}`}>
            Step {active.step} of {INCIDENT_FLOW_STEPS.length}
          </span>
          <span className="text-[10px] font-mono text-gray-600">→</span>
          <span className="text-xs font-semibold text-white">{active.title}</span>
        </div>
        <p className="text-sm text-gray-300 leading-relaxed">{active.detail}</p>
        <p className="text-[10px] font-mono text-gray-500 mt-2">{active.tech}</p>
      </div>

      <div className="arch-flow-mobile-arrows flex justify-center gap-1 mt-2 sm:hidden resume-no-print">
        {INCIDENT_FLOW_STEPS.map((step) => (
          <button
            key={step.id}
            type="button"
            onClick={() => setActiveId(step.id)}
            className={`w-1.5 h-1.5 rounded-full transition-all ${
              step.id === activeId ? "bg-teal-400 w-4" : "bg-gray-600"
            }`}
            aria-label={step.title}
          />
        ))}
      </div>
    </div>
  );
}

function ComponentMap() {
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {COMPONENT_LAYERS.map((layer) => {
        const Icon = LAYER_ICONS[layer.icon] ?? Server;
        const style = ACCENT_STYLES[layer.accent] ?? ACCENT_STYLES.indigo;
        return (
          <div
            key={layer.id}
            className={`arch-layer-card rounded-xl border p-4 h-full flex flex-col ${style.border} bg-sre-bg/30`}
          >
            <div className="flex items-start gap-3 mb-3">
              <div className={`p-2 rounded-lg border ${style.border} ${style.bg}`}>
                <Icon size={16} className={style.text} />
              </div>
              <div>
                <h5 className="text-sm font-semibold text-white">{layer.title}</h5>
                <p className="text-[11px] text-gray-500 mt-0.5 leading-snug">{layer.summary}</p>
              </div>
            </div>
            <ul className="space-y-1.5 flex-1">
              {layer.items.map((item) => (
                <li key={item} className="text-[11px] text-gray-400 flex gap-1.5 leading-relaxed">
                  <span className={`${style.text} shrink-0 mt-0.5`}>•</span>
                  {item}
                </li>
              ))}
            </ul>
          </div>
        );
      })}
    </div>
  );
}

function ToolStackGrid() {
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {TOOL_STACK_CATEGORIES.map((cat) => (
        <div key={cat.category} className="rounded-xl border border-sre-border/50 bg-sre-bg/30 p-4">
          <h5 className="text-[11px] font-bold uppercase tracking-wide text-indigo-300/90 mb-2.5">
            {cat.category}
          </h5>
          <div className="flex flex-wrap gap-1.5">
            {cat.tools.map((tool) => (
              <span
                key={tool}
                className="text-[10px] font-mono px-2 py-0.5 rounded-md bg-sre-bg border border-sre-border/60 text-gray-400"
              >
                {tool}
              </span>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function EnterpriseBenefits() {
  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2">
        {ENTERPRISE_BENEFITS.map((benefit) => {
          const Icon = BENEFIT_ICONS[benefit.icon] ?? Shield;
          return (
            <div key={benefit.title} className="arch-benefit-card rounded-xl border border-sre-border/50 bg-sre-bg/25 p-4">
              <div className="flex items-start gap-3">
                <div className="p-2 rounded-lg bg-indigo-950/40 border border-indigo-800/30 shrink-0">
                  <Icon size={15} className="text-indigo-400" />
                </div>
                <div className="min-w-0">
                  <h5 className="text-sm font-semibold text-white">{benefit.title}</h5>
                  <div className="mt-2 space-y-2">
                    <div>
                      <p className="text-[9px] font-bold uppercase tracking-wide text-teal-400/80">Enterprise</p>
                      <p className="text-[11px] text-gray-400 leading-relaxed mt-0.5">{benefit.enterprise}</p>
                    </div>
                    <div>
                      <p className="text-[9px] font-bold uppercase tracking-wide text-indigo-300/80">This demo</p>
                      <p className="text-[11px] text-gray-400 leading-relaxed mt-0.5">{benefit.demo}</p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      <div className="arch-stack-compare rounded-xl border border-sre-border/50 overflow-hidden">
        <div className="grid md:grid-cols-2 gap-px bg-sre-border/40">
          <div className="bg-sre-surface/80 p-4">
            <p className="text-[10px] font-bold uppercase tracking-wide text-teal-400/90 mb-3">
              Client work (Citi · BofA · Verizon · Toyota)
            </p>
            <ul className="space-y-2.5">
              {TECH_STACK_COMPARISON.enterprise.map((row) => (
                <li key={row.category}>
                  <p className="text-[11px] font-semibold text-stone-200">{row.category}</p>
                  <p className="text-[10px] text-stone-500 mt-0.5 leading-relaxed">{row.tools}</p>
                </li>
              ))}
            </ul>
          </div>
          <div className="bg-indigo-950/20 p-4">
            <p className="text-[10px] font-bold uppercase tracking-wide text-indigo-300/90 mb-3">
              This portfolio demo
            </p>
            <ul className="space-y-2.5">
              {TECH_STACK_COMPARISON.demo.map((row) => (
                <li key={row.category}>
                  <p className="text-[11px] font-semibold text-stone-200">{row.category}</p>
                  <p className="text-[10px] text-stone-500 mt-0.5 leading-relaxed">{row.tools}</p>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}

function SixtySecondSummary() {
  return (
    <div
      id="architecture-sixty"
      className="arch-sixty scroll-mt-24 rounded-2xl border border-teal-500/20 bg-gradient-to-br from-teal-950/20 via-sre-bg/40 to-indigo-950/15 p-5 sm:p-6"
    >
      <div className="flex items-start gap-3 mb-4">
        <div className="p-2 rounded-lg bg-teal-950/50 border border-teal-500/25 shrink-0">
          <Clock size={18} className="text-teal-300" />
        </div>
        <div>
          <h4 className="text-base font-bold text-white">{SIXTY_SECOND_SUMMARY.headline}</h4>
          <p className="text-sm text-gray-300 leading-relaxed mt-1.5 max-w-2xl">{SIXTY_SECOND_SUMMARY.intro}</p>
        </div>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        {SIXTY_SECOND_SUMMARY.bullets.map((item) => (
          <div
            key={item.label}
            className="rounded-xl border border-sre-border/40 bg-sre-bg/30 px-3.5 py-3"
          >
            <p className="text-[10px] font-bold uppercase tracking-wide text-teal-400/90 mb-1">{item.label}</p>
            <p className="text-xs text-gray-400 leading-relaxed">{item.text}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

export function ArchitectureExplainer({ onStartTour }) {
  const [searchParams] = useSearchParams();
  const tourStep = getTourStepFromSearchParams(searchParams);
  const tourActive = isDemoTourActive() && tourStep > 0;
  const tourDef = DEMO_TOUR_STEPS.find((s) => s.step === tourStep);
  const [diagramId, setDiagramId] = useState("systemContext");

  useEffect(() => {
    if (tourActive && tourDef?.diagramId) {
      setDiagramId(tourDef.diagramId);
    }
  }, [tourActive, tourDef?.diagramId, tourStep]);
  return (
    <div className="arch-explainer space-y-8">
      {/* Hero */}
      <div id="architecture-hero" className="scroll-mt-24">
        <div className="flex flex-wrap items-start justify-between gap-3 mb-2">
          <div>
            <div className="flex flex-wrap items-center gap-2 mb-1">
              <h3 className="text-xl font-bold text-white">{FEATURED_PROJECT.name}</h3>
              {FEATURED_PROJECT.badge && (
                <span className="text-[10px] font-semibold uppercase tracking-wide px-2 py-0.5 rounded-full border border-teal-500/30 text-teal-300/95 bg-teal-950/30">
                  {FEATURED_PROJECT.badge}
                </span>
              )}
            </div>
            <p className="text-sm text-indigo-300/95">{FEATURED_PROJECT.role}</p>
          </div>
          <span className="text-xs text-gray-500 font-mono">{FEATURED_PROJECT.period}</span>
        </div>

        <p className="text-sm text-gray-300 leading-relaxed max-w-2xl">{FEATURED_PROJECT.summary}</p>
        <p className="text-xs text-teal-300/90 leading-relaxed max-w-2xl mt-2">
          Unified observability: Prometheus metrics, Loki logs, and OTEL traces and events in one Command Center
          pane — so on-call engineers build context without console hopping.
        </p>

        <div className="grid grid-cols-3 gap-2 mt-5">
          {DEMO_METRICS.map((m) => (
            <div
              key={m.label}
              className="rounded-xl border border-sre-border/50 bg-sre-bg/40 px-3 py-2 text-center"
            >
              <p className="text-base font-bold text-white font-mono">{m.value}</p>
              <p className="text-[9px] text-stone-500 mt-0.5 leading-snug">{m.label}</p>
            </div>
          ))}
        </div>

        <HeroTechStack className="mt-4" />

        <nav
          className="flex flex-wrap gap-1.5 mt-5 resume-no-print"
          aria-label="Architecture section navigation"
        >
          {ARCHITECTURE_SECTIONS.map((sec) => (
            <button
              key={sec.id}
              type="button"
              onClick={() => scrollToSection(sec.id)}
              className="text-[10px] font-medium px-2.5 py-1 rounded-full border border-sre-border/50 text-gray-400 hover:text-white hover:border-indigo-500/35 hover:bg-indigo-950/20 transition-all"
            >
              {sec.label}
            </button>
          ))}
        </nav>
      </div>

      {/* 60-second recruiter summary */}
      <SixtySecondSummary />

      {/* Canonical architecture diagrams (same source as /docs) */}
      <div>
        <SectionHeading
          id="architecture-diagram-heading"
          title="Architecture diagram"
          subtitle="Same mermaid diagrams as the enterprise docs — system context, layers, unified observability pipeline, and incident lifecycle. Tap a tab to explore."
        />
        <ArchitectureDiagram
          activeDiagramId={diagramId}
          onDiagramChange={setDiagramId}
          defaultDiagramId="systemContext"
        />
      </div>

      {/* End-to-end flow */}
      <div>
        <SectionHeading
          id="architecture-flow"
          title="End-to-end incident flow"
          subtitle="Click any step to walk the pipeline — alert ingestion through unified Observe, AI analysis, gated remediation, and audit."
        />
        <FlowPipeline />
      </div>

      {/* Component map */}
      <div>
        <SectionHeading
          id="architecture-components"
          title="Component map"
          subtitle="Six layers that mirror how enterprise SRE platforms are structured — UI, API, agents, data, observability, and infra."
        />
        <ComponentMap />
      </div>

      {/* Tool stack */}
      <div>
        <SectionHeading
          id="architecture-stack"
          title="Tool stack"
          subtitle="Production-grade choices grouped by concern — same patterns scaled at Citi, BofA, and Verizon."
        />
        <ToolStackGrid />
      </div>

      {/* Enterprise benefits */}
      <div>
        <SectionHeading
          id="architecture-enterprise"
          title="Enterprise benefits"
          subtitle="Every demo capability maps to a pattern from Fortune-scale client work — not a toy chatbot."
        />
        <EnterpriseBenefits />
      </div>

      {/* CTAs */}
      <div
        id="architecture-cta"
        className="arch-cta-footer pt-4 border-t border-sre-border/40 resume-no-print"
      >
        <div className="flex flex-col sm:flex-row sm:items-center gap-4">
          <div className="flex-1">
            <p className="text-sm font-semibold text-white">See it in action</p>
            <p className="text-xs text-gray-500 mt-1 leading-relaxed">
              5-step guided tour on this page — problem, architecture diagram, data flow, unified observability, and enterprise safety.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={onStartTour}
              className="demo-cta-primary inline-flex items-center gap-1.5 px-4 py-2.5 rounded-lg text-xs font-semibold text-white"
            >
              <Play size={13} className="fill-current" />
              {DEMO_LANDING.tourCta}
            </button>
            <a
              href={FEATURED_PROJECT.repoUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 px-3 py-2.5 rounded-lg text-xs font-medium text-gray-300 border border-sre-border hover:border-indigo-500/40 hover:text-white transition-all"
            >
              <Github size={13} />
              Source
              <ExternalLink size={10} className="text-gray-600" />
            </a>
          </div>
        </div>
        <button
          type="button"
          onClick={() => scrollToSection("architecture-diagram")}
          className="mt-4 inline-flex items-center gap-1 text-[10px] text-gray-600 hover:text-indigo-400 transition-colors"
        >
          <ArrowDown size={11} />
          Back to architecture diagram
        </button>
      </div>
    </div>
  );
}
