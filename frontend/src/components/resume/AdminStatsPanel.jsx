import { useState, useEffect } from "react";
import { X, Eye, Users, MessageSquare, TrendingUp, Clock, Calendar, Bot, Play, FileDown } from "lucide-react";

const SESSION_KEY = "sreai.adminToken";

export function AdminStatsPanel({ onClose }) {
  const [token, setToken] = useState("");
  const [stats, setStats] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const saved = sessionStorage.getItem(SESSION_KEY);
    if (saved) fetchStats(saved);
  }, []);

  async function fetchStats(t) {
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`/api/v1/recruiter/admin/stats?token=${encodeURIComponent(t)}`);
      if (res.status === 401) {
        sessionStorage.removeItem(SESSION_KEY);
        setError("Invalid token. Use the ADMIN_TOKEN environment variable from Railway.");
        return;
      }
      if (res.status === 503) {
        let msg = "Analytics not configured on server (ADMIN_TOKEN missing)";
        try { const b = await res.json(); if (b?.detail) msg = String(b.detail); } catch { /* ignore */ }
        setError(msg);
        return;
      }
      if (!res.ok) {
        let msg = `Failed to load stats (${res.status})`;
        try { const b = await res.json(); if (b?.detail) msg = String(b.detail); } catch { /* ignore */ }
        setError(msg);
        return;
      }
      setStats(await res.json());
      sessionStorage.setItem(SESSION_KEY, t);
    } catch {
      setError("Network error");
    } finally {
      setLoading(false);
    }
  }

  function handleSubmit(e) {
    e.preventDefault();
    if (token.trim()) fetchStats(token.trim());
  }

  function signOut() {
    setStats(null);
    setToken("");
    sessionStorage.removeItem(SESSION_KEY);
  }

  const funnel = stats?.engagement_funnel ?? {};
  const totalViews = stats?.total_views ?? 0;

  return (
    <div
      className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="bg-sre-surface border border-sre-border rounded-2xl w-full max-w-lg shadow-2xl max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-sre-border sticky top-0 bg-sre-surface z-10">
          <div>
            <h2 className="text-white font-semibold text-sm">Resume Analytics</h2>
            <p className="text-gray-500 text-[11px] mt-0.5">Admin only · not visible to visitors</p>
          </div>
          <button onClick={onClose} className="text-gray-500 hover:text-white transition-colors p-1">
            <X size={16} />
          </button>
        </div>

        <div className="p-6">
          {!stats ? (
            <form onSubmit={handleSubmit} className="space-y-3">
              <p className="text-gray-400 text-xs mb-4">
                Enter your <code className="text-indigo-400 bg-indigo-950/30 px-1 rounded">ADMIN_TOKEN</code> to view profile analytics.
              </p>
              <input
                type="password"
                placeholder="Admin token"
                value={token}
                onChange={(e) => setToken(e.target.value)}
                className="w-full bg-sre-bg border border-sre-border rounded-lg px-4 py-2.5 text-white text-sm placeholder-gray-600 focus:outline-none focus:border-indigo-500 transition-colors"
                autoFocus
              />
              {error && <p className="text-red-400 text-xs">{error}</p>}
              <button
                type="submit"
                disabled={loading || !token.trim()}
                className="w-full bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 text-white rounded-lg py-2.5 text-sm font-semibold transition-colors"
              >
                {loading ? "Verifying…" : "View analytics"}
              </button>
            </form>
          ) : (
            <div className="space-y-6">

              {/* Traffic cards */}
              <div>
                <SectionLabel icon={Eye}>Traffic</SectionLabel>
                <div className="grid grid-cols-2 gap-3">
                  <StatCard icon={Eye} label="Total views" value={stats.total_views} accent="indigo" />
                  <StatCard icon={Users} label="Unique visitors" value={stats.unique_views} accent="emerald" />
                  <StatCard icon={TrendingUp} label="Today" value={stats.today_views} accent="sky" />
                  <StatCard icon={MessageSquare} label="Feedback" value={stats.feedback_count} accent="amber" />
                </div>
              </div>

              {/* Engagement funnel */}
              <div>
                <SectionLabel icon={TrendingUp}>Engagement funnel</SectionLabel>
                <div className="space-y-2">
                  <FunnelRow icon={Eye} label="Page views" count={totalViews} max={totalViews} color="indigo" />
                  <FunnelRow icon={Bot} label="Opened chat" count={funnel.chat_opened ?? 0} max={totalViews} color="teal" />
                  <FunnelRow icon={MessageSquare} label="Asked a question" count={funnel.question_asked ?? 0} max={totalViews} color="violet" />
                  <FunnelRow icon={Play} label="Started AI demo" count={funnel.demo_started ?? 0} max={totalViews} color="sky" />
                  <FunnelRow icon={FileDown} label="Downloaded PDF" count={funnel.pdf_clicked ?? 0} max={totalViews} color="amber" />
                </div>
              </div>

              {/* Questions asked */}
              {stats.recent_questions?.length > 0 && (
                <div>
                  <SectionLabel icon={Bot}>Questions recruiters asked</SectionLabel>
                  <div className="space-y-1.5 max-h-48 overflow-y-auto">
                    {stats.recent_questions.map((q, i) => (
                      <div key={i} className="bg-sre-bg rounded-lg px-3 py-2">
                        <p className="text-gray-200 text-[11px] leading-relaxed">{q.question}</p>
                        <p className="text-gray-600 text-[9px] mt-1 font-mono">
                          {q.session_id} · {formatTime(q.asked_at)}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Daily breakdown */}
              {stats.daily_views?.length > 0 && (
                <div>
                  <SectionLabel icon={Calendar}>Last 7 days</SectionLabel>
                  <div className="space-y-1">
                    {stats.daily_views.map((d) => (
                      <div key={d.day} className="flex items-center gap-3">
                        <span className="text-gray-600 text-[10px] font-mono w-20 shrink-0">{d.day}</span>
                        <div className="flex-1 bg-sre-bg rounded-full h-1.5 overflow-hidden">
                          <div
                            className="bg-indigo-500 h-full rounded-full transition-all"
                            style={{ width: `${Math.min(100, (d.views / Math.max(...stats.daily_views.map(x => x.views), 1)) * 100)}%` }}
                          />
                        </div>
                        <span className="text-gray-400 text-[10px] w-4 text-right">{d.views}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Recent visitors */}
              {(stats.recent_visitors ?? stats.recent_sessions)?.length > 0 && (
                <div>
                  <SectionLabel icon={Clock}>Recent visitors</SectionLabel>
                  <div className="space-y-1 max-h-36 overflow-y-auto">
                    {(stats.recent_visitors ?? stats.recent_sessions).map((s, i) => (
                      <div key={i} className="flex items-center justify-between bg-sre-bg rounded-lg px-3 py-1.5 gap-2">
                        <span className="text-gray-500 text-[10px] font-mono truncate">
                          {s.country_code || "—"} · {s.visitor_id || s.session_id}
                          {s.device_class ? <span className="text-gray-600 ml-1.5">· {s.device_class}</span> : null}
                        </span>
                        <span className="text-gray-600 text-[10px] shrink-0">{formatTime(s.last_seen)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <button
                onClick={signOut}
                className="w-full text-gray-600 hover:text-gray-400 text-xs py-1.5 transition-colors border-t border-sre-border pt-3"
              >
                Sign out
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function SectionLabel({ icon: Icon, children }) {
  return (
    <p className="text-gray-500 text-[10px] uppercase tracking-wider mb-2 flex items-center gap-1.5">
      <Icon size={10} /> {children}
    </p>
  );
}

function FunnelRow({ icon: Icon, label, count, max, color }) {
  const pct = max > 0 ? Math.min(100, (count / max) * 100) : 0;
  const barColors = {
    indigo: "bg-indigo-500", teal: "bg-teal-500", violet: "bg-violet-500",
    sky: "bg-sky-500", amber: "bg-amber-500",
  };
  const textColors = {
    indigo: "text-indigo-400", teal: "text-teal-400", violet: "text-violet-400",
    sky: "text-sky-400", amber: "text-amber-400",
  };
  return (
    <div className="flex items-center gap-3">
      <Icon size={11} className={`shrink-0 ${textColors[color]}`} />
      <span className="text-gray-400 text-[11px] w-32 shrink-0">{label}</span>
      <div className="flex-1 bg-sre-bg rounded-full h-1.5 overflow-hidden">
        <div className={`${barColors[color]} h-full rounded-full transition-all`} style={{ width: `${pct}%` }} />
      </div>
      <span className={`text-[11px] font-semibold w-6 text-right ${textColors[color]}`}>{count}</span>
      {max > 0 && <span className="text-gray-600 text-[10px] w-8">{Math.round(pct)}%</span>}
    </div>
  );
}

function StatCard({ icon: Icon, label, value, accent }) {
  const styles = {
    indigo: "text-indigo-400 bg-indigo-950/30 border-indigo-800/30",
    emerald: "text-emerald-400 bg-emerald-950/30 border-emerald-800/30",
    sky: "text-sky-400 bg-sky-950/30 border-sky-800/30",
    amber: "text-amber-400 bg-amber-950/30 border-amber-800/30",
  };
  return (
    <div className={`rounded-xl border p-3.5 ${styles[accent]}`}>
      <div className="flex items-center gap-1.5 mb-2 opacity-75">
        <Icon size={12} />
        <span className="text-[10px] uppercase tracking-wide">{label}</span>
      </div>
      <p className="text-2xl font-bold">{value ?? "—"}</p>
    </div>
  );
}

function formatTime(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("en-US", {
      month: "short", day: "numeric",
      hour: "2-digit", minute: "2-digit",
    });
  } catch {
    return iso.slice(0, 16);
  }
}
