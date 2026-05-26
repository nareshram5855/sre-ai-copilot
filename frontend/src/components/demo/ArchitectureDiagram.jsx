import { useState } from "react";
import { MermaidDiagram } from "../docs/MermaidDiagram.jsx";
import { MERMAID } from "../docs/docsContent.js";

/** Canonical diagram keys — same source as EnterpriseDocsPage (/docs). */
export const ARCHITECTURE_DIAGRAMS = [
  {
    id: "systemContext",
    label: "System overview",
    title: "System Context",
    caption:
      "On-call engineers use one Command Center. Alerts and telemetry flow in; AI agents stay local unless external LLM is explicitly enabled.",
    chart: MERMAID.systemContext,
    tourHint: "Users, external observability, and the copilot core — one connected platform.",
  },
  {
    id: "containers",
    label: "Layers",
    title: "Container / Component View",
    caption:
      "Frontend panels call FastAPI routers. Specialist agents share RAG and persistence. Observability feeds proactive anomaly detection.",
    chart: MERMAID.containers,
    tourHint: "Six layers: UI, API, agents, stores, and the observability stack.",
  },
  {
    id: "observabilityPipeline",
    label: "Unified observe",
    title: "Observability Pipeline",
    caption:
      "Metrics, logs, and OTEL traces collected once — Prometheus, Loki, and anomaly watch feed a single Observe pane in the Command Center.",
    chart: MERMAID.observabilityPipeline,
    tourHint: "Prometheus metrics, Loki logs, and OTEL traces in one pane — no console hopping.",
  },
  {
    id: "incidentLifecycle",
    label: "Incident path",
    title: "Incident Lifecycle",
    caption:
      "From pod failure through triage, unified context gathering, human-approved remediation, and learning ingestion.",
    chart: MERMAID.incidentLifecycle,
    tourHint: "Alert → triage → live UI → gated fix → audit-ready resolution.",
  },
];

const DIAGRAM_BY_ID = Object.fromEntries(ARCHITECTURE_DIAGRAMS.map((d) => [d.id, d]));

export function ArchitectureDiagram({
  defaultDiagramId = "systemContext",
  activeDiagramId,
  onDiagramChange,
  compact = false,
  showTabs = true,
  sectionId = "architecture-diagram",
}) {
  const [internalId, setInternalId] = useState(defaultDiagramId);
  const selectedId = activeDiagramId ?? internalId;
  const active = DIAGRAM_BY_ID[selectedId] ?? ARCHITECTURE_DIAGRAMS[0];

  function select(id) {
    if (onDiagramChange) onDiagramChange(id);
    else setInternalId(id);
  }

  return (
    <div id={sectionId} className="arch-diagram scroll-mt-24">
      {showTabs && (
        <div
          className="arch-diagram-tabs flex gap-1.5 overflow-x-auto pb-2 -mx-1 px-1 resume-no-print"
          role="tablist"
          aria-label="Architecture diagram views"
        >
          {ARCHITECTURE_DIAGRAMS.map((d) => (
            <button
              key={d.id}
              type="button"
              role="tab"
              aria-selected={d.id === selectedId}
              onClick={() => select(d.id)}
              className={`arch-diagram-tab shrink-0 text-[10px] font-medium px-3 py-1.5 rounded-full border transition-all ${
                d.id === selectedId
                  ? "border-indigo-500/45 bg-indigo-950/40 text-indigo-200"
                  : "border-sre-border/50 text-gray-500 hover:text-gray-300 hover:border-indigo-500/25"
              }`}
            >
              {d.label}
            </button>
          ))}
        </div>
      )}

      <div
        id={active.id === "observabilityPipeline" ? "architecture-observe" : undefined}
        className="arch-diagram-frame"
      >
        <MermaidDiagram
          title={active.title}
          chart={active.chart}
          caption={compact ? undefined : active.caption}
        />
      </div>

      {!compact && active.tourHint && (
        <p className="arch-diagram-hint text-xs text-teal-300/85 leading-relaxed mt-3 max-w-2xl">
          {active.tourHint}
        </p>
      )}
    </div>
  );
}

export function ArchitectureDiagramMini({ diagramId = "observabilityPipeline" }) {
  const def = DIAGRAM_BY_ID[diagramId];
  if (!def) return null;
  return (
    <div className="arch-diagram-mini">
      <MermaidDiagram chart={def.chart} title={def.title} />
    </div>
  );
}
