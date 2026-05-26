export function StatusPill({ label, status = "unknown", compact = false }) {
  const styles = {
    up: "bg-emerald-950/50 text-emerald-400 border-emerald-800/50",
    degraded: "bg-amber-950/50 text-amber-300 border-amber-800/50",
    down: "bg-red-950/50 text-red-400 border-red-800/50",
    unknown: "bg-gray-800/50 text-gray-500 border-gray-700/50",
    loading: "bg-amber-950/40 text-amber-400 border-amber-800/40",
  };

  const dots = {
    up: "bg-emerald-400",
    degraded: "bg-amber-400 animate-pulse",
    down: "bg-red-400 animate-pulse",
    unknown: "bg-gray-500",
    loading: "bg-amber-400 animate-pulse",
  };

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-md border font-medium ${
        compact ? "text-[10px] px-2 py-0.5" : "text-xs px-2.5 py-1"
      } ${styles[status] || styles.unknown}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${dots[status] || dots.unknown}`} />
      {label}
    </span>
  );
}
