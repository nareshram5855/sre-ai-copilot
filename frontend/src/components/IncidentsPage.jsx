import { LiveIncidents } from "./LiveIncidents.jsx";
import { Radio } from "lucide-react";
import { PageHeader } from "./layout/PageHeader.jsx";
import { PageShell } from "./layout/PageShell.jsx";
import { StatusPill } from "./layout/StatusPill.jsx";

export function IncidentsPage({ initialIncidentKey = null, onOpenAudit = null }) {
  return (
    <PageShell>
      <PageHeader
        icon={Radio}
        title="Live Incidents"
        description="Auto-triaged alerts from AlertManager — deduplicated, sorted by severity. Live SSE stream with 60s polling fallback."
        badges={<StatusPill label="Live feed" status="up" />}
      />
      <LiveIncidents initialIncidentKey={initialIncidentKey} onOpenAudit={onOpenAudit} />
    </PageShell>
  );
}
