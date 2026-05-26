import { useState } from "react";
import { Shield, Eye, User, Lock, ChevronRight, AlertCircle } from "lucide-react";
import { useAuth } from "../context/AuthContext.jsx";
import { ROLES, ADMIN_PASSWORD, READ_PASSWORD } from "../config/roles.js";

const ROLE_CARDS = [
  {
    role:        ROLES.recruiter,
    icon:        User,
    title:       "Recruiter / Guest",
    description: "Resume & candidate profile only",
    color:       "indigo",
    password:    false,
  },
  {
    role:        ROLES.read,
    icon:        Eye,
    title:       "Read-Only",
    description: "View all dashboards — no actions",
    color:       "blue",
    password:    true,
    hint:        READ_PASSWORD,
  },
  {
    role:        ROLES.admin,
    icon:        Shield,
    title:       "Admin / DevOps",
    description: "Full access — execute, approve, escalate",
    color:       "emerald",
    password:    true,
    hint:        ADMIN_PASSWORD,
  },
];

const COLOR = {
  indigo:  { ring: "border-indigo-500/50",  bg: "bg-indigo-500/10",  icon: "text-indigo-400",  btn: "bg-indigo-600 hover:bg-indigo-500" },
  blue:    { ring: "border-blue-500/50",    bg: "bg-blue-500/10",    icon: "text-blue-400",    btn: "bg-blue-600   hover:bg-blue-500"   },
  emerald: { ring: "border-emerald-500/50", bg: "bg-emerald-500/10", icon: "text-emerald-400", btn: "bg-emerald-700 hover:bg-emerald-600" },
};

export function LoginModal({ onClose }) {
  const { setRole } = useAuth();
  const [selected, setSelected]     = useState(null);
  const [password, setPassword]     = useState("");
  const [error, setError]           = useState("");
  const [submitting, setSubmitting] = useState(false);

  function pickCard(card) {
    setSelected(card);
    setPassword("");
    setError("");
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (!selected) return;
    setSubmitting(true);
    setError("");

    if (selected.password) {
      const correct = selected.role === ROLES.admin ? ADMIN_PASSWORD : READ_PASSWORD;
      if (password !== correct) {
        setError("Incorrect password.");
        setSubmitting(false);
        return;
      }
    }

    setRole(selected.role);
    setSubmitting(false);
    onClose?.();
  }

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
      <div
        className="w-full max-w-md rounded-2xl border border-white/10 shadow-2xl overflow-hidden"
        style={{ background: "linear-gradient(160deg, #0d0f1e 0%, #080a14 100%)" }}
      >
        {/* Header */}
        <div className="px-6 pt-6 pb-4 border-b border-white/[0.06]">
          <div className="flex items-center gap-3 mb-1">
            <div className="w-9 h-9 rounded-xl flex items-center justify-center"
              style={{ background: "linear-gradient(135deg,#6366f1,#4f46e5)", boxShadow: "0 4px 20px rgba(99,102,241,0.35)" }}>
              <Shield size={17} className="text-white" />
            </div>
            <div>
              <p className="text-[15px] font-bold text-white leading-none">SRE Copilot</p>
              <p className="text-[10px] text-gray-500 mt-0.5">Select your access level</p>
            </div>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="p-5 space-y-3">
          {/* Role cards */}
          {ROLE_CARDS.map((card) => {
            const c = COLOR[card.color];
            const active = selected?.role === card.role;
            const Icon = card.icon;
            return (
              <button
                type="button"
                key={card.role}
                onClick={() => pickCard(card)}
                className={`w-full flex items-center gap-4 p-4 rounded-xl border text-left transition-all ${
                  active
                    ? `${c.ring} ${c.bg}`
                    : "border-white/[0.07] hover:border-white/20 hover:bg-white/[0.03]"
                }`}
              >
                <div className={`w-10 h-10 rounded-lg flex items-center justify-center shrink-0 ${
                  active ? c.bg : "bg-white/[0.06]"
                }`}>
                  <Icon size={18} className={active ? c.icon : "text-gray-500"} />
                </div>
                <div className="flex-1 min-w-0">
                  <p className={`text-[13px] font-semibold ${active ? "text-white" : "text-gray-300"}`}>
                    {card.title}
                  </p>
                  <p className="text-[11px] text-gray-500 mt-0.5">{card.description}</p>
                </div>
                {card.password && (
                  <Lock size={13} className="text-gray-600 shrink-0" />
                )}
                {active && (
                  <ChevronRight size={15} className={c.icon + " shrink-0"} />
                )}
              </button>
            );
          })}

          {/* Password field — only when a password-protected role is selected */}
          {selected?.password && (
            <div className="pt-1">
              <label className="block text-[11px] text-gray-500 mb-1.5 font-medium">
                Password for {selected.title}
              </label>
              <input
                autoFocus
                type="password"
                value={password}
                onChange={(e) => { setPassword(e.target.value); setError(""); }}
                placeholder="Enter access password"
                className="w-full px-3 py-2.5 rounded-lg text-sm bg-white/[0.05] border border-white/10 text-white
                  placeholder-gray-600 focus:outline-none focus:border-indigo-500/60 focus:bg-white/[0.07] transition-all"
              />
              {error && (
                <p className="flex items-center gap-1.5 mt-1.5 text-[11px] text-red-400">
                  <AlertCircle size={11} /> {error}
                </p>
              )}
            </div>
          )}

          {/* Submit */}
          <button
            type="submit"
            disabled={!selected || submitting}
            className="w-full py-2.5 rounded-xl text-sm font-semibold text-white transition-all mt-1
              disabled:opacity-40 disabled:cursor-not-allowed
              bg-indigo-600 hover:bg-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/40"
          >
            {submitting ? "Verifying…" : selected ? `Continue as ${selected.title}` : "Select a role"}
          </button>

          <p className="text-center text-[10px] text-gray-700 pb-1">
            Role persists in this browser session
          </p>
        </form>
      </div>
    </div>
  );
}
