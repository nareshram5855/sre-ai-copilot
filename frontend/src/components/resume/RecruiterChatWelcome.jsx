import {
  Building2, Briefcase, Radio, Car, FileText, Sparkles, ShieldCheck, Play,
} from "lucide-react";
import { RESUME_PROFILE, RECRUITER_EMPLOYER_QUICK_ASK } from "../../data/resumeContent.js";
import { dispatchDemoTourStart } from "../../utils/demoTour.js";

const TOPIC_META = {
  "Citi IAM": { label: "Citigroup", sub: "IAM · EKS · GitOps", icon: Building2, accent: "teal" },
  BofA: { label: "Bank of America", sub: "Platform · CI/CD", icon: Briefcase, accent: "indigo" },
  Verizon: { label: "Verizon", sub: "Kubernetes · cloud", icon: Radio, accent: "violet" },
  Toyota: { label: "Toyota", sub: "Data platform · AWS", icon: Car, accent: "emerald" },
  "Check role fit": {
    label: "Check role fit",
    sub: "Share requirements — I'll map my skills honestly",
    icon: FileText,
    accent: "amber",
    jd: true,
  },
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

export function RecruiterChatWelcome({ onAsk, onJdTemplate, loading = false }) {
  return (
    <div className="recruiter-chat-welcome mx-auto max-w-2xl pb-1">
      <div className="recruiter-chat-welcome-hero text-center px-2 sm:px-4">
        <h3 className="text-lg sm:text-xl font-bold text-white tracking-tight">
          Hi — I&apos;m {RESUME_PROFILE.name.split(" ")[0]} 👋
        </h3>
        <p className="text-[13px] text-stone-400 mt-2 leading-relaxed max-w-sm mx-auto">
          Ask about my client work, or paste a job description below to check fit.
        </p>
        <span className="recruiter-welcome-badge mt-3 inline-flex">
          <ShieldCheck size={11} className="text-emerald-400" />
          Verified profile · first person
        </span>
      </div>

      <div className="mt-5 sm:mt-6">
        <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-stone-500 mb-2.5 px-0.5">
          Quick start
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
                <p className="text-[10px] text-stone-500 mt-0.5 leading-snug">{topic.sub}</p>
              </button>
            );
          })}
        </div>
      </div>

      <div className="mt-5 resume-no-print">
        <button
          type="button"
          disabled={loading}
          onClick={() => dispatchDemoTourStart()}
          className="recruiter-welcome-tour-banner w-full flex items-center gap-2.5 rounded-xl border px-3 py-2.5 text-left transition-all disabled:opacity-45"
        >
          <span className="shrink-0 w-8 h-8 rounded-lg flex items-center justify-center bg-teal-950/50 border border-teal-500/30">
            <Play size={15} className="text-teal-300 fill-teal-300/30" />
          </span>
          <span className="min-w-0 flex-1">
            <p className="text-[13px] font-semibold text-white">5-min hiring manager tour</p>
            <p className="text-[10px] text-stone-500 mt-0.5">
              Architecture walkthrough · incidents · enterprise safety
            </p>
          </span>
          <Sparkles size={13} className="shrink-0 text-teal-400/60" />
        </button>
      </div>
    </div>
  );
}
