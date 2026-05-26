import { useRef, useState, useEffect } from "react";
import { Activity, Database, Radio, GitBranch, Server, ExternalLink } from "lucide-react";

export const METRIC_META = {
  error_rate:      { label: "Error Rate",   unit: "/s",    fmt: (v) => `${v.toFixed(4)}/s`,       warn: 0.05,  crit: 0.5,   spark_color: "#f87171" },
  request_rate:    { label: "Request Rate", unit: "/s",    fmt: (v) => `${v.toFixed(2)}/s`,        warn: null,  crit: null,  spark_color: "#60a5fa" },
  latency_p99_ms:  { label: "P99 Latency",  unit: "ms",   fmt: (v) => `${v.toFixed(0)}ms`,        warn: 500,   crit: 2000,  spark_color: "#fb923c" },
  latency_p50_ms:  { label: "P50 Latency",  unit: "ms",   fmt: (v) => `${v.toFixed(0)}ms`,        warn: 200,   crit: 1000,  spark_color: "#a78bfa" },
  db_errors:       { label: "DB Errors",    unit: "",      fmt: (v) => v.toFixed(0),               warn: 1,     crit: 10,    spark_color: "#f87171" },
  pool_exhaustion: { label: "Pool Exhaust", unit: "",      fmt: (v) => v.toFixed(0),               warn: 1,     crit: 5,     spark_color: "#f87171" },
  memory_bytes:    { label: "Heap",         unit: "MB",    fmt: (v) => `${(v / 1e6).toFixed(1)}MB`,  warn: 80e6,  crit: 100e6, spark_color: "#34d399" },
  jvm_heap_used:   { label: "JVM Heap",     unit: "MB",    fmt: (v) => `${(v / 1e6).toFixed(1)}MB`,  warn: 60e6,  crit: 80e6,  spark_color: "#34d399" },
  jvm_heap_limit:  { label: "JVM Max",      unit: "MB",    fmt: (v) => `${(v / 1e6).toFixed(1)}MB`,  warn: null,  crit: null,  spark_color: "#6b7280" },
  jvm_cpu:         { label: "JVM CPU",      unit: "%",     fmt: (v) => `${(v * 100).toFixed(1)}%`,   warn: 0.6,   crit: 0.8,   spark_color: "#fb923c" },
  jvm_threads:     { label: "Threads",      unit: "",      fmt: (v) => v.toFixed(0),               warn: null,  crit: null,  spark_color: "#60a5fa" },
  jvm_gc_count:    { label: "GC Count",     unit: "",      fmt: (v) => v.toFixed(0),               warn: 10,    crit: 20,    spark_color: "#a78bfa" },
};

export function metricHealth(name, v) {
  const m = METRIC_META[name];
  if (!m || v === undefined) return "normal";
  if (m.crit !== null && v >= m.crit) return "critical";
  if (m.warn !== null && v >= m.warn) return "warning";
  return "normal";
}

const H = {
  normal:   { card: "border-gray-800 bg-gray-900/40",          val: "text-emerald-400", dot: "bg-emerald-500" },
  warning:  { card: "border-yellow-800/50 bg-yellow-950/20",   val: "text-yellow-300",  dot: "bg-yellow-400" },
  critical: { card: "border-red-800/50 bg-red-950/20",         val: "text-red-400",     dot: "bg-red-500 animate-pulse" },
};

export function Sparkline({ points, color = "#22c55e", height = 28, width = 80 }) {
  if (!points || points.length < 2) return <div style={{ width, height }} />;
  const vals = points.map((p) => p[1]);
  const min = Math.min(...vals);
  const max = Math.max(...vals);
  const range = max - min || 0.001;
  const pad = 2;
  const xs = points.map((_, i) => pad + (i / (points.length - 1)) * (width - pad * 2));
  const ys = vals.map((v) => pad + (1 - (v - min) / range) * (height - pad * 2));
  const d = xs.map((x, i) => `${i === 0 ? "M" : "L"}${x.toFixed(1)},${ys[i].toFixed(1)}`).join(" ");
  const area = `${d} L${xs[xs.length - 1].toFixed(1)},${height} L${xs[0].toFixed(1)},${height} Z`;
  const gradId = `sg-${color.replace("#", "")}`;
  return (
    <svg width={width} height={height} className="overflow-visible">
      <defs>
        <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.3" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={area} fill={`url(#${gradId})`} />
      <path d={d} fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function MetricCard({ name, value, sparkPoints }) {
  const meta = METRIC_META[name] || { label: name, fmt: (v) => v.toFixed(4), spark_color: "#6b7280" };
  const health = metricHealth(name, value);
  const c = H[health];
  return (
    <div className={`rounded-lg border px-3 pt-2 pb-1.5 flex flex-col gap-0.5 ${c.card} relative overflow-hidden`}>
      <div className="flex items-center justify-between">
        <span className="text-[11px] text-gray-500 truncate">{meta.label}</span>
        <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${c.dot}`} />
      </div>
      <span className={`text-sm font-data font-bold ${c.val}`}>{meta.fmt(value)}</span>
      <div className="mt-0.5">
        <Sparkline
          points={sparkPoints || []}
          color={health === "normal" ? meta.spark_color : health === "warning" ? "#fbbf24" : "#f87171"}
          height={22}
          width={90}
        />
      </div>
    </div>
  );
}

const TOOL_ICONS = {
  Prometheus: Activity,
  Loki: Database,
  "OTel Collector": Radio,
  Promtail: GitBranch,
};

export function StackCard({ tool }) {
  const Icon = TOOL_ICONS[tool.name] || Server;
  const statusColor =
    tool.status === "up" ? "text-emerald-400 bg-emerald-900/30 border-emerald-800/40" :
    tool.status === "down" ? "text-red-400 bg-red-900/30 border-red-800/40" :
    "text-gray-500 bg-gray-800/30 border-gray-700/40";
  const dotColor =
    tool.status === "up" ? "bg-emerald-400" :
    tool.status === "down" ? "bg-red-400 animate-pulse" : "bg-gray-500";
  const statsEntries = Object.entries(tool.stats || {});

  return (
    <div className="flex items-start gap-3 px-3 py-2.5 rounded-lg border border-gray-800 bg-gray-900/40 hover:bg-gray-900/60 transition-colors group">
      <div className="w-7 h-7 rounded-md bg-gray-800 flex items-center justify-center shrink-0 mt-0.5">
        <Icon size={13} className="text-gray-400" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-0.5">
          <span className="text-xs font-semibold text-gray-200">{tool.name}</span>
          <span className={`flex items-center gap-1 text-[10px] px-1.5 rounded border font-medium ${statusColor}`}>
            <span className={`w-1 h-1 rounded-full ${dotColor}`} />
            {tool.status}
          </span>
        </div>
        <p className="text-[10px] text-gray-600 truncate mb-1">{tool.role}</p>
        {tool.ui_path && (
          <a href={`${tool.endpoint}${tool.ui_path}`} target="_blank" rel="noreferrer" className="text-[10px] text-indigo-400 hover:text-indigo-300 inline-flex items-center gap-1">
            Open <ExternalLink size={10} />
          </a>
        )}
        {statsEntries.length > 0 && (
          <div className="flex gap-2 mt-1.5 flex-wrap">
            {statsEntries.map(([k, v]) => (
              <span key={k} className="text-[10px] text-gray-600">
                <span className="text-gray-400 font-mono">{v}</span> {k.replace(/_/g, " ")}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export const WATCH_METRICS = [
  "error_rate", "request_rate", "latency_p99_ms", "latency_p50_ms",
  "db_errors", "pool_exhaustion", "jvm_heap_used", "jvm_cpu", "jvm_gc_count",
];

/* ─── Grafana-style chart panel ─────────────────────────────────────────── */

function fmtAxisVal(v) {
  if (v >= 1e9) return `${(v / 1e9).toFixed(1)}G`;
  if (v >= 1e6) return `${(v / 1e6).toFixed(1)}M`;
  if (v >= 1e3) return `${(v / 1e3).toFixed(1)}k`;
  if (v >= 100) return v.toFixed(0);
  if (v >= 10)  return v.toFixed(1);
  return v.toFixed(2);
}

function fmtTime(ts) {
  return new Date(ts * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function GrafanaSparkline({ metricName, points, color, warn, crit, width, height = 90 }) {
  if (!points || points.length < 2) {
    return (
      <div style={{ height }} className="flex items-center justify-center text-[10px] text-gray-700">
        No timeseries data
      </div>
    );
  }

  const W = Math.max(width || 280, 80);
  const H = height;
  const PAD = { t: 6, r: 8, b: 20, l: 40 };
  const cW = W - PAD.l - PAD.r;
  const cH = H - PAD.t - PAD.b;

  const vals = points.map((p) => p[1]);
  const maxVal = Math.max(Math.max(...vals), warn || 0, crit || 0) * 1.15 || 1;

  const px = (i) => PAD.l + (i / (points.length - 1)) * cW;
  const py = (v) => PAD.t + (1 - v / maxVal) * cH;

  const xs = points.map((_, i) => px(i));
  const ys = vals.map((v) => py(v));
  const linePath = xs.map((x, i) => `${i === 0 ? "M" : "L"}${x.toFixed(1)},${ys[i].toFixed(1)}`).join(" ");
  const areaPath = `${linePath} L${xs[xs.length - 1].toFixed(1)},${(PAD.t + cH).toFixed(1)} L${xs[0].toFixed(1)},${(PAD.t + cH).toFixed(1)} Z`;

  const gradId = `gs_${(metricName || "m").replace(/[^a-z]/gi, "_")}_${W}`;
  const warnY = warn && warn < maxVal ? py(warn) : null;
  const critY = crit && crit < maxVal ? py(crit) : null;
  const yTicks = [0, 0.5, 1].map((t) => ({ y: PAD.t + (1 - t) * cH, val: maxVal * t }));

  return (
    <svg width={W} height={H} className="block">
      <defs>
        <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.35" />
          <stop offset="100%" stopColor={color} stopOpacity="0.02" />
        </linearGradient>
      </defs>

      {/* horizontal grid */}
      {yTicks.map((t, i) => (
        <line key={i} x1={PAD.l} y1={t.y.toFixed(1)} x2={W - PAD.r} y2={t.y.toFixed(1)} stroke="#1e2233" strokeWidth="1" />
      ))}

      {/* threshold lines */}
      {warnY !== null && (
        <line x1={PAD.l} y1={warnY.toFixed(1)} x2={W - PAD.r} y2={warnY.toFixed(1)}
          stroke="#eab308" strokeWidth="1" strokeDasharray="4,3" opacity="0.85" />
      )}
      {critY !== null && (
        <line x1={PAD.l} y1={critY.toFixed(1)} x2={W - PAD.r} y2={critY.toFixed(1)}
          stroke="#ef4444" strokeWidth="1" strokeDasharray="4,3" opacity="0.85" />
      )}

      {/* area fill + line */}
      <path d={areaPath} fill={`url(#${gradId})`} />
      <path d={linePath} fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />

      {/* Y-axis labels */}
      {yTicks.map((t, i) => (
        <text key={i} x={PAD.l - 4} y={(t.y + 3.5).toFixed(1)} textAnchor="end"
          fontSize="9" fill="#4b5563" fontFamily="monospace">
          {fmtAxisVal(t.val)}
        </text>
      ))}

      {/* X-axis time labels */}
      <text x={PAD.l} y={H - 3} textAnchor="start" fontSize="9" fill="#374151" fontFamily="sans-serif">
        {fmtTime(points[0][0])}
      </text>
      <text x={W - PAD.r} y={H - 3} textAnchor="end" fontSize="9" fill="#374151" fontFamily="sans-serif">
        {fmtTime(points[points.length - 1][0])}
      </text>

      {/* Y-axis border */}
      <line x1={PAD.l} y1={PAD.t} x2={PAD.l} y2={PAD.t + cH} stroke="#2d3148" strokeWidth="1" />
    </svg>
  );
}

export function ChartPanel({ name, value, sparkPoints, className = "" }) {
  const ref = useRef(null);
  const [w, setW] = useState(300);

  useEffect(() => {
    if (!ref.current) return;
    const ro = new ResizeObserver(([e]) => setW(Math.floor(e.contentRect.width)));
    ro.observe(ref.current);
    return () => ro.disconnect();
  }, []);

  const meta = METRIC_META[name] || {
    label: name, fmt: (v) => String(v?.toFixed(4) ?? "—"),
    spark_color: "#6b7280", warn: null, crit: null,
  };
  const health = value !== undefined ? metricHealth(name, value) : "normal";
  const color = health === "critical" ? "#f87171" : health === "warning" ? "#fbbf24" : meta.spark_color;

  const C = {
    card:  { normal: "border-gray-800/80 bg-gray-900/30", warning: "border-yellow-800/50 bg-yellow-950/15", critical: "border-red-800/60 bg-red-950/20" },
    val:   { normal: "text-emerald-400",  warning: "text-yellow-300",  critical: "text-red-400" },
    badge: {
      normal:   "text-emerald-400 bg-emerald-900/30 border-emerald-800/40",
      warning:  "text-yellow-300 bg-yellow-900/30 border-yellow-800/40",
      critical: "text-red-400 bg-red-900/30 border-red-800/40",
    },
  };

  return (
    <div ref={ref} className={`rounded-xl border ${C.card[health]} flex flex-col overflow-hidden ${className}`}>
      <div className="flex items-start justify-between px-4 pt-3 pb-1.5 gap-2">
        <div className="min-w-0">
          <p className="text-[10px] font-semibold text-gray-500 uppercase tracking-widest">{meta.label}</p>
          {value !== undefined ? (
            <p className={`text-2xl font-bold font-mono leading-tight mt-0.5 ${C.val[health]}`}>
              {meta.fmt(value)}
            </p>
          ) : (
            <p className="text-sm text-gray-600 mt-0.5">No data</p>
          )}
        </div>
        <span className={`shrink-0 mt-0.5 text-[10px] px-1.5 py-0.5 rounded border font-semibold uppercase ${C.badge[health]}`}>
          {health}
        </span>
      </div>
      <div className="px-1 pb-1">
        <GrafanaSparkline
          metricName={name}
          points={sparkPoints || []}
          color={color}
          warn={meta.warn}
          crit={meta.crit}
          width={w - 8}
          height={90}
        />
      </div>
    </div>
  );
}
