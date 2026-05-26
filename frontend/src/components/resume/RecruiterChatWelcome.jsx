import {
  Building2, Briefcase, Radio, Car, FileText, Sparkles, ShieldCheck, MessageCircle, Play,
} from "lucide-react";
import { RESUME_PROFILE, RESUME_STATS, RECRUITER_EMPLOYER_QUICK_ASK } from "../../data/resumeContent.js";
import { dispatchDemoTourStart } from "../../utils/demoTour.js";

const TOPIC_META = {
  "Citi IAM": { label: "Citigroup", sub: "IAM · EKS · GitOps", icon: Building2, accent: "teal" },
  BofA: { label: "Bank of America", sub: "Platform · CI/CD", icon: Briefcase, accent: "indigo" },
  Verizon: { label: "Verizon", sub: "Kubernetes · cloud", icon: Radio, accent: "violet" },
  Toyota: { label: "Toyota", sub: "Data platform · AWS", icon: Car, accent: "emerald" },
  "Paste JD": { label: "Paste a JD", sub: "Strong · Partial · Gap", icon: FileText, accent: "amber", jd: true },
};

const EMPLOYER_TOPICS = RECRUITER_EMPLOYER_QUICK_ASK.map((item) => ({
  ...TOPIC_META[item.label],
  question: item.question,
  jd: item.jd,
}));

const ACCENT = {
  teal: "border-teal-500/25 bg-teal-950/25 hover:border-teal-400/40 hover:bg-teal-950/40 text-teal-300",
  indigo: "border-indigo-500/25 bg-indigo-950/25 hover:border-indigo-400/40 hover:bg-indigo-950/40 text-indigo-300",
  violet: "border-violet-500/25 bg-violet-950/25 hover:border-violet-400/40 hover:bg-violet-950/40 text-violet-300",
  emerald: "border-emerald-500/25 bg-emerald-950/25 hover:border-emerald-400/40 hover:bg-emerald-950/40 text-emerald-300",
  amber: "border-amber-500/25 bg-amber-950/25 hover:border-amber-400/40 hover:bg-amber-950/40 text-amber-200",
};

export function RecruiterChatWelcome({ starters = [], onAsk, onJdTemplate, loading = false }) {
  return (
    <div className="recruiter-chat-welcome mx-auto max-w-2xl pb-2">
      <div className="recruiter-chat-welcome-hero text-center px-2 sm:px-4">
        <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-teal-400/90">
          Verified live profile
        </p>
        <h3 className="text-xl sm:text-[1.35rem] font-bold text-white mt-2 tracking-tight">
          Hi — I&apos;m {RESUME_PROFILE.name.split(" ")[0]} 👋
        </h3>
        <p className="text-[13px] sm:text-sm text-stone-400 mt-2.5 leading-[1.65] max-w-md mx-auto">
          Ask like a recruiter or hiring manager — client work, on-call stories, JD fit, or this demo.
          First-person answers from my verified resume, not generic AI filler.
        </p>

        <div className="flex flex-wrap items-center justify-center gap-2 mt-4">
          <span className="recruiter-welcome-badge">
            <ShieldCheck size={11} className="text-emerald-400" />
            Verified employers
          </span>
          <span className="recruiter-welcome-badge">
            <MessageCircle size={11} className="text-teal-400" />
            First person
          </span>
          <span className="recruiter-welcome-badge">
            <Sparkles size={11} className="text-indigo-400" />
            RAG-backed
          </span>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mt-5">
          {RESUME_STATS.map((s) => (
            <div key={s.label} className="recruiter-welcome-stat">
              <p className="text-base font-bold text-white font-mono leading-none">{s.value}</p>
              <p className="text-[10px] font-semibold text-stone-300 mt-1">{s.label}</p>
              <p className="text-[9px] text-stone-500 leading-snug mt-0.5">{s.sub}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="mt-6 sm:mt-7">
        <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-stone-500 mb-2.5 px-0.5">
          Jump in by client or role
        </p>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
          {EMPLOYER_TOPICS.map((topic) => {
            const Icon = topic.icon;
            return (
              <button
                key={topic.label}
                type="button"
                disabled={loading}
                onClick={() => (topic.jd ? onJdTemplate() : onAsk(topic.question))}
                className={`recruiter-welcome-topic group text-left rounded-xl border p-3 transition-all active:scale-[0.98] disabled:opacity-45 ${ACCENT[topic.accent]}`}
              >
                <Icon size={16} className="mb-2 opacity-90 group-hover:scale-105 transition-transform" />
                <p className="text-[13px] font-semibold text-stone-100 leading-tight">{topic.label}</p>
                <p className="text-[10px] text-stone-500 mt-0.5">{topic.sub}</p>
              </button>
            );
          })}
        </div>
      </div>

      <div className="mt-6 sm:mt-7 resume-no-print">
        <button
          type="button"
          disabled={loading}
          onClick={() => dispatchDemoTourStart()}
          className="recruiter-welcome-tour-banner w-full flex items-center gap-3 rounded-xl border p-3.5 sm:p-4 text-left transition-all disabled:opacity-45"
        >
          <span className="shrink-0 w-10 h-10 rounded-xl flex items-center justify-center bg-teal-950/50 border border-teal-500/30">
            <Play size={18} className="text-teal-300 fill-teal-300/30" />
          </span>
          <span className="min-w-0 flex-1">
            <p className="text-sm font-semibold text-white">5-minute hiring manager tour</p>
            <p className="text-[11px] text-stone-400 mt-0.5 leading-snug">
              Architecture walkthrough — how incidents flow, MTTR impact, and enterprise safety patterns
            </p>
          </span>
          <Sparkles size={14} className="shrink-0 text-teal-400/70" />
        </button>
      </div>

      {starters.length > 0 && (
        <div className="mt-6 sm:mt-7">
          <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-stone-500 mb-2.5 px-0.5">
            Hiring manager starters
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {starters.map((q, i) => (
              <button
                key={q}
                type="button"
                disabled={loading}
                onClick={() => onAsk(q)}
                title={q}
                className="recruiter-welcome-starter group text-left rounded-xl border border-stone-700/45 bg-stone-900/30 px-3 py-2.5 text-[12px] leading-snug text-stone-300 hover:text-white hover:border-teal-500/30 hover:bg-teal-950/20 transition-all disabled:opacity-45"
                style={{ animationDelay: `${i * 0.04}s` }}
              >
                <Sparkles size={11} className="inline mr-1.5 text-teal-400/70 -mt-0.5 group-hover:text-teal-300" />
                {q}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
