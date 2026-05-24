import { LiveIncidents } from "./LiveIncidents.jsx";
import { Activity } from "lucide-react";

export function IncidentsPage() {
  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="mb-6 pb-5 border-b border-sre-border flex items-start justify-between">
        <div>
          <h1 className="text-lg font-semibold text-white tracking-tight">Live Incidents</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Auto-triaged by AI as alerts fire · Deduped · Sorted by severity · Refreshes every 15s
          </p>
        </div>
        <div className="flex items-center gap-1.5 text-xs text-green-400 bg-green-950/40 border border-green-800/50 rounded-md px-2.5 py-1">
          <Activity size={12} className="animate-pulse" />
          Live
        </div>
      </div>
      <LiveIncidents />
    </div>
  );
}
