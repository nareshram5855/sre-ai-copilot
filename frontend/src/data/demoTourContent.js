/**
 * Hiring-manager architecture tour — single-page narrative on /resume.
 * Personal R&D portfolio (not client production work).
 * Steps reference sections in ArchitectureExplainer + shared docs diagrams.
 */

export const DEMO_TOUR_STEPS = [
  {
    step: 1,
    sectionId: "architecture-hero",
    title: "The problem",
    headline: "Fragmented signals slow every incident",
    body:
      "Most teams lose precious minutes because metrics live in one console, logs in another, and traces elsewhere. " +
      "Jumping between tabs stretches mean time to repair — especially when the on-call is new to the service.",
    hmHook:
      "For hiring managers: I design for faster time-to-context — one pane where logs, metrics, traces, and OTEL events connect, not another dashboard with more noise.",
    badge: "MTTR · unified context",
    icon: "problem",
    diagramId: null,
  },
  {
    step: 2,
    sectionId: "architecture-diagram",
    title: "Architecture layers",
    headline: "Same diagram as enterprise docs — system + components",
    body:
      "Scroll the tabs above the diagram: System overview shows users, alerting, and the copilot core. " +
      "Layers view maps the React UI, FastAPI routers, LangGraph agents, data stores, and observability stack — the same structure scaled at Fortune-scale clients.",
    hmHook:
      "This is not a slide-deck mockup — it mirrors the shipped /docs architecture and the actual repo layout.",
    badge: "System context · component layers",
    icon: "layers",
    diagramId: "containers",
  },
  {
    step: 3,
    sectionId: "architecture-flow",
    title: "Data flow",
    headline: "Alert → agents → unified observe → gated fix → audit",
    body:
      "Prometheus fires an alert → TriageAgent classifies severity and dedupes the incident → the Command Center shows live metrics, logs, and traces in one Observe pane → " +
      "AI builds an RCA brief → runbooks are matched via RAG → remediation runs only after human approval → every step lands in an append-only audit log. " +
      "See the Incident path tab in the diagram section for the sequence view.",
    hmHook:
      "End-to-end incident response on one page — observability and remediation connected, not bolted on after the fact.",
    badge: "Webhook · triage · observe · audit",
    icon: "flow",
    diagramId: null,
  },
  {
    step: 4,
    sectionId: "architecture-observe",
    title: "Unified observability",
    headline: "Metrics, logs, traces, and OTEL — one pane",
    body:
      "Synthetic demo services emit signals through Prometheus, Loki, Promtail, and the OTEL collector. " +
      "The anomaly watcher scans for drift; the Observe APIs surface everything in a single Command Center view — the observability story enterprises pay for, without vendor lock-in.",
    hmHook:
      "Shows I can unify observability silos (Splunk, Datadog, Dynatrace patterns) into one operator experience.",
    badge: "Prometheus · Loki · OTEL · one pane",
    icon: "observe",
    diagramId: "observabilityPipeline",
  },
  {
    step: 5,
    sectionId: "architecture-enterprise",
    title: "Enterprise value",
    headline: "MTTR, human gates, and audit — by design",
    body:
      "Deduped incident records, change-board approval before destructive writes, and append-only audit trails — " +
      "patterns from Fortune-scale client work, mapped side by side with what this demo implements.",
    hmHook:
      "Shows I can translate bank and telco constraints into shippable platform design, not just a toy chatbot.",
    badge: "MTTR · audit · human gates",
    icon: "enterprise",
    diagramId: null,
  },
];

export const DEMO_VALUE_PROPS = [
  {
    title: "Shorter mean time to context",
    detail:
      "One Command Center pane surfaces metrics, logs, traces, and OTEL events together — hiring managers see the full story in minutes, not across four consoles.",
    stat: "~40% less",
    statLabel: "context gathering",
  },
  {
    title: "Safety by design",
    detail:
      "Human approval gates on remediation — aligned with how Citi and BofA change boards actually work.",
    stat: "100%",
    statLabel: "gated writes",
  },
  {
    title: "Audit-ready operations",
    detail:
      "Every agent action logged — supports SOX, change management, and post-incident review.",
    stat: "245+",
    statLabel: "automated tests",
  },
];

export const DEMO_LANDING = {
  eyebrow: "Personal SRE bot · R&D project",
  title: "SRE AI Copilot",
  subtitle:
    "Personal R&D platform exploring AI-assisted incident response — LangGraph agents, unified observability, " +
    "RAG runbooks, and human-gated remediation. Built independently of my Fortune-scale client work at Citi, BofA, Verizon, and Toyota.",
  tourCta: "Start 5-min SRE AI demo",
  tourSub: "Guided architecture walkthrough · stays on this page · no setup",
  fullDemoCta: "Open full interactive demo",
  fullDemoSub: "Requires read-only or admin access",
};
