import { Mail, Phone, MapPin, Printer, Sparkles, MessageCircle } from "lucide-react";
import { ProfessionalEngineerIcon } from "../icons/ProfessionalEngineerIcon.jsx";
import { RESUME_PROFILE, RESUME_STATS, RECRUITER_EMPLOYER_QUICK_ASK } from "../../data/resumeContent.js";
import { openRecruiterChat, dispatchRecruiterQuickAsk } from "../../utils/recruiterChatEvents.js";
import { dispatchDemoExpand } from "../../utils/demoTour.js";

export { dispatchRecruiterQuickAsk } from "../../utils/recruiterChatEvents.js";

const STAT_PROMPTS = {
  Experience: "Summarize my 8+ years of enterprise SRE experience in 4 bullets",
  Enterprise: "Which Fortune-scale clients have I supported and in what roles?",
  Certification: "Where have I applied AWS DevOps Pro skills in production?",
  Portfolio: "Explain the SRE AI Copilot portfolio — separate from client work",
};

const STAT_EXPAND_DEMO = new Set(["Portfolio"]);

export function ResumeHero({ viewStats, onPrint }) {
  return (
    <header className="resume-hero panel-card relative overflow-hidden resume-no-print">
      <div className="resume-hero-glow pointer-events-none absolute inset-0" aria-hidden="true" />
      <div className="relative p-4 sm:p-6 md:p-7">
        <div className="flex items-start justify-between gap-3 flex-wrap mb-4">
          <div className="flex items-center gap-2.5">
            <div className="resume-hero-icon-wrap shrink-0">
              <ProfessionalEngineerIcon size={22} className="text-teal-300" />
            </div>
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <span className="inline-flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wide px-2 py-0.5 rounded-full border border-emerald-500/35 bg-emerald-950/40 text-emerald-200">
                  <span className="resume-hero-live-dot" />
                  Open to SRE roles
                </span>
                <span className="text-[10px] px-2 py-0.5 rounded-full border border-indigo-500/30 bg-indigo-950/30 text-indigo-300 font-medium hidden sm:inline">
                  AWS DevOps Pro
                </span>
                {viewStats?.unique_views > 0 && (
                  <span className="text-[10px] text-gray-500">{viewStats.unique_views} profile views</span>
                )}
              </div>
              <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-teal-400/90 mt-2">
                Site Reliability · Cloud · AI Platform
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onPrint}
            className="inline-flex items-center gap-1.5 text-xs text-gray-400 hover:text-white px-2.5 py-1.5 rounded-lg border border-sre-border/60 hover:border-indigo-500/40 hover:bg-indigo-950/20 transition-colors"
            title="Print or save as PDF"
          >
            <Printer size={14} />
            <span className="hidden sm:inline">PDF</span>
          </button>
        </div>

        <h1 className="text-2xl sm:text-3xl md:text-[2rem] font-bold text-white tracking-tight leading-tight">
          {RESUME_PROFILE.name}
        </h1>
        <p className="text-base sm:text-lg text-indigo-300/95 font-medium mt-1">{RESUME_PROFILE.title}</p>
        <p className="text-sm text-gray-400 mt-2 leading-relaxed max-w-2xl">{RESUME_PROFILE.tagline}</p>

        <ul className="flex flex-wrap gap-x-4 gap-y-2 mt-4 text-sm text-gray-400">
          <li className="flex items-center gap-1.5">
            <MapPin size={13} className="text-teal-500/80 shrink-0" />
            <span className="text-xs">{RESUME_PROFILE.location}</span>
          </li>
          <li className="flex items-center gap-1.5">
            <Mail size={13} className="text-teal-500/80 shrink-0" />
            <a href={`mailto:${RESUME_PROFILE.email}`} className="text-xs hover:text-teal-300 transition-colors break-all">
              {RESUME_PROFILE.email}
            </a>
          </li>
          <li className="flex items-center gap-1.5">
            <Phone size={13} className="text-teal-500/80 shrink-0" />
            <a href={`tel:${RESUME_PROFILE.phone}`} className="text-xs hover:text-teal-300 transition-colors">
              {RESUME_PROFILE.phone}
            </a>
          </li>
        </ul>

        <div className="mt-5 flex flex-wrap gap-2">
          {RECRUITER_EMPLOYER_QUICK_ASK.map((item) => (
            <button
              key={item.label}
              type="button"
              onClick={() => {
                if (item.jd) {
                  openRecruiterChat();
                  window.dispatchEvent(new CustomEvent("sre-recruiter-jd-template"));
                } else {
                  dispatchRecruiterQuickAsk(item.question);
                }
              }}
              className="resume-hero-chip inline-flex items-center gap-1.5 text-[11px] font-medium px-3 py-1.5 rounded-full border border-teal-500/20 bg-teal-950/25 text-stone-300 hover:text-white hover:border-teal-400/35 hover:bg-teal-950/40 transition-all active:scale-[0.98]"
            >
              {item.jd ? <Sparkles size={12} className="text-teal-400" /> : <MessageCircle size={12} className="text-teal-400/80" />}
              {item.label}
            </button>
          ))}
        </div>

        <div className="mt-5 grid grid-cols-2 sm:grid-cols-4 gap-2">
          {RESUME_STATS.map((s) => {
            const prompt = STAT_PROMPTS[s.label];
            return (
              <button
                key={s.label}
                type="button"
                onClick={() => {
                  if (STAT_EXPAND_DEMO.has(s.label)) {
                    dispatchDemoExpand();
                  } else if (prompt) {
                    dispatchRecruiterQuickAsk(prompt);
                  }
                }}
                disabled={!prompt}
                className="resume-hero-stat text-left rounded-xl border border-sre-border/50 bg-sre-bg/30 px-3 py-2.5 hover:border-teal-500/25 hover:bg-teal-950/15 transition-all disabled:cursor-default disabled:hover:border-sre-border/50 disabled:hover:bg-sre-bg/30 group"
                title={prompt ? "Ask Naresh about this" : undefined}
              >
                <p className="text-lg font-bold text-white font-mono group-hover:text-teal-100 transition-colors">{s.value}</p>
                <p className="text-[10px] font-semibold text-gray-300 mt-0.5">{s.label}</p>
                <p className="text-[9px] text-gray-600 leading-snug">{s.sub}</p>
              </button>
            );
          })}
        </div>

        <button
          type="button"
          onClick={() => openRecruiterChat()}
          className="mt-5 w-full flex items-center justify-center gap-2 text-xs font-medium text-teal-300/90 py-2 rounded-xl border border-dashed border-teal-500/25 hover:border-teal-400/40 hover:bg-teal-950/20 transition-colors"
        >
          <MessageCircle size={14} className="text-teal-400" />
          Chat with Naresh live — verified answers, first person
        </button>
      </div>
    </header>
  );
}
