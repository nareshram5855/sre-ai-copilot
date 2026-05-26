import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  Mail, Phone, MapPin, ExternalLink, Github, Linkedin,
  BookMarked, Link2, Cpu, Server, Sparkles,
  Shield, GitBranch, BarChart3, Award, Briefcase, Cloud, Workflow,
} from "lucide-react";
import { PageShell } from "../components/layout/PageShell.jsx";
import { ResumeHero } from "../components/resume/ResumeHero.jsx";
import { AdminStatsPanel } from "../components/resume/AdminStatsPanel.jsx";
import { LinkedInRecommendationsSection } from "../components/resume/LinkedInRecommendationCard.jsx";
import { DemoLauncher } from "../components/demo/DemoLauncher.jsx";
import { RecruiterAskPanel } from "../components/resume/RecruiterAskPanel.jsx";
import { RecruiterFeedbackPanel } from "../components/resume/RecruiterFeedbackPanel.jsx";
import { getRecruiterSessionId } from "../utils/recruiterSession.js";
import {
  RESUME_PROFILE,
  RESUME_SUMMARY,
  RESUME_SUMMARY_DETAILS,
  RESUME_SKILLS,
  RESUME_SKILL_MATRIX,
  RESUME_RECOMMENDATIONS,
  RESUME_LINKEDIN,
  RESUME_EXPERIENCE,
  RESUME_EDUCATION,
  RESUME_CERTIFICATIONS,
  RESUME_LINKS,
  RESUME_ACHIEVEMENTS,
} from "../data/resumeContent.js";

const LINK_ICONS = {
  github: Github,
  linkedin: Linkedin,
  docs: BookMarked,
  link: Link2,
};

const ACHIEVEMENT_ICONS = {
  shield: Shield,
  git: GitBranch,
  chart: BarChart3,
  spark: Sparkles,
};

function SectionTitle({ children, id }) {
  return (
    <h2
      id={id}
      className="text-[11px] font-bold text-gray-500 uppercase tracking-[0.15em] mb-3 scroll-mt-24"
    >
      {children}
    </h2>
  );
}

function ProficiencyBadge({ level }) {
  const colors = {
    Expert: "border-emerald-500/40 bg-emerald-950/30 text-emerald-300",
    Advanced: "border-indigo-500/40 bg-indigo-950/30 text-indigo-300",
  };
  return (
    <span
      className={`text-[10px] font-semibold uppercase tracking-wide px-2 py-0.5 rounded-full border ${
        colors[level] || colors.Advanced
      }`}
    >
      {level}
    </span>
  );
}

function SkillMatrixCard({ row }) {
  return (
    <div className="panel-card p-4 h-full flex flex-col">
      <div className="flex items-start justify-between gap-2 mb-2">
        <h3 className="text-sm font-semibold text-white leading-snug">{row.category}</h3>
        <ProficiencyBadge level={row.proficiency} />
      </div>
      {row.endorsedOnLinkedin && (
        <p className="text-[10px] text-blue-400/80 mb-2 flex items-center gap-1">
          <Linkedin size={10} />
          LinkedIn endorsed
        </p>
      )}
      <ul className="space-y-1 flex-1">
        {row.skills.map((skill) => (
          <li key={skill} className="text-[11px] text-gray-400 leading-relaxed flex gap-1.5">
            <span className="text-indigo-600 shrink-0">•</span>
            {skill}
          </li>
        ))}
      </ul>
    </div>
  );
}

function SkillPills({ items, accent = "indigo" }) {
  const color =
    accent === "emerald"
      ? "border-emerald-800/40 bg-emerald-950/20 text-emerald-300"
      : accent === "amber"
        ? "border-amber-800/40 bg-amber-950/20 text-amber-300"
        : "border-indigo-800/40 bg-indigo-950/20 text-indigo-300";
  return (
    <div className="flex flex-wrap gap-1.5">
      {items.map((skill) => (
        <span
          key={skill}
          className={`text-[11px] px-2.5 py-1 rounded-md border font-medium ${color}`}
        >
          {skill}
        </span>
      ))}
    </div>
  );
}

function ResumeLink({ link, navigate }) {
  const Icon = LINK_ICONS[link.icon] || ExternalLink;
  const isInternal = link.internal || link.url.startsWith("/");

  function handleClick(e) {
    if (isInternal) {
      e.preventDefault();
      navigate(link.url);
    }
  }

  return (
    <a
      href={isInternal ? link.url : link.url}
      onClick={handleClick}
      target={isInternal ? undefined : "_blank"}
      rel={isInternal ? undefined : "noopener noreferrer"}
      className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-sre-border bg-sre-bg/60 text-xs text-gray-300 hover:text-white hover:border-indigo-500/40 hover:bg-indigo-950/20 transition-all resume-no-print"
    >
      <Icon size={14} className="text-indigo-400 shrink-0" />
      {link.label}
      {!isInternal && <ExternalLink size={11} className="text-gray-600" />}
    </a>
  );
}

export function ResumePage() {
  const navigate = useNavigate();
  const [summaryExpanded, setSummaryExpanded] = useState(false);
  const [viewStats, setViewStats] = useState(null);
  const [recruiterEngaged, setRecruiterEngaged] = useState(false);
  const [recruiterChatLoading, setRecruiterChatLoading] = useState(false);
  const [showAdmin, setShowAdmin] = useState(
    () => new URLSearchParams(window.location.search).has("admin")
  );

  useEffect(() => {
    const sessionId = getRecruiterSessionId();
    const viewedKey = "sreai.recruiterViewRecorded";

    async function trackView() {
      try {
        if (window.sessionStorage.getItem(viewedKey) !== "1") {
          const res = await fetch("/api/v1/recruiter/view", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ session_id: sessionId }),
          });
          if (res.ok) {
            window.sessionStorage.setItem(viewedKey, "1");
            setViewStats(await res.json());
            return;
          }
        }
        const statsRes = await fetch("/api/v1/recruiter/stats");
        if (statsRes.ok) {
          setViewStats(await statsRes.json());
        }
      } catch {
        /* non-blocking analytics */
      }
    }

    trackView();
  }, []);

  function handlePrint() {
    window.print();
  }

  return (
    <PageShell constrained className={`pb-16 resume-page ${recruiterChatLoading ? "recruiter-page-active" : ""}`}>
      <article className="resume-document space-y-5 sm:space-y-6 max-w-4xl">
        {/* Print-only header (interactive hero hidden when printing) */}
        <div className="hidden print:block mb-6 pb-4 border-b border-gray-300">
          <h1 className="text-2xl font-bold text-black">{RESUME_PROFILE.name}</h1>
          <p className="text-base text-gray-700 mt-1">{RESUME_PROFILE.title}</p>
          <p className="text-sm text-gray-600 mt-2">{RESUME_PROFILE.email} · {RESUME_PROFILE.phone}</p>
        </div>

        <ResumeHero viewStats={viewStats} onPrint={handlePrint} />

        {/* Key achievements */}
        <section>
          <SectionTitle id="achievements">Key achievements</SectionTitle>
          <div className="grid gap-3 grid-cols-1 sm:grid-cols-2">
            {RESUME_ACHIEVEMENTS.map((a) => {
              const Icon = ACHIEVEMENT_ICONS[a.icon] || Award;
              return (
                <div key={a.title} className="panel-card p-4 flex gap-3">
                  <div className="p-2 rounded-lg bg-indigo-950/40 border border-indigo-800/30 h-fit shrink-0">
                    <Icon size={16} className="text-indigo-400" />
                  </div>
                  <div>
                    <h3 className="text-sm font-semibold text-white">{a.title}</h3>
                    <p className="text-xs text-gray-400 mt-1 leading-relaxed">{a.detail}</p>
                  </div>
                </div>
              );
            })}
          </div>
        </section>

        {/* Summary */}
        <section>
          <SectionTitle id="summary">Executive summary</SectionTitle>
          <div className="panel-card p-5">
            <p className="text-sm text-gray-300 leading-relaxed">{RESUME_SUMMARY}</p>
            {RESUME_SUMMARY_DETAILS?.length > 0 && (
              <div className="mt-4 pt-4 border-t border-sre-border/60">
                <button
                  type="button"
                  onClick={() => setSummaryExpanded((v) => !v)}
                  className="inline-flex items-center gap-1.5 text-xs font-semibold text-indigo-300 hover:text-indigo-200 transition-colors resume-no-print"
                  aria-expanded={summaryExpanded}
                >
                  {summaryExpanded ? "Hide" : "Show"} full professional summary
                  <span className="text-[10px] text-gray-500 font-normal">
                    ({RESUME_SUMMARY_DETAILS.length} points)
                  </span>
                </button>
                <ul className={`mt-3 space-y-2 ${summaryExpanded ? "" : "hidden print:block"}`}>
                    {RESUME_SUMMARY_DETAILS.map((point) => (
                      <li key={point.slice(0, 48)} className="text-sm text-gray-400 flex gap-2 leading-relaxed">
                        <span className="text-indigo-600 shrink-0 mt-1.5">•</span>
                        {point}
                      </li>
                    ))}
                </ul>
              </div>
            )}
          </div>
        </section>

        {/* Endorsed skills — skill matrix grid */}
        <section>
          <SectionTitle id="skill-matrix">Endorsed skills</SectionTitle>
          <p className="text-xs text-gray-500 mb-4 leading-relaxed">
            {RESUME_LINKEDIN.sourceNote}{" "}
            <a
              href={RESUME_LINKEDIN.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-indigo-400 hover:text-indigo-300 inline-flex items-center gap-1"
            >
              View LinkedIn
              <ExternalLink size={10} />
            </a>
            {" · "}
            {RESUME_LINKEDIN.connections} connections · {RESUME_LINKEDIN.followers} followers
          </p>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {RESUME_SKILL_MATRIX.map((row) => (
              <SkillMatrixCard key={row.category} row={row} />
            ))}
          </div>
        </section>

        <LinkedInRecommendationsSection
          recommendations={RESUME_RECOMMENDATIONS}
          linkedin={RESUME_LINKEDIN}
        />

        {/* Core competencies (summary pills) */}
        <section>
          <SectionTitle id="skills">Core competencies</SectionTitle>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="panel-card p-4">
              <div className="flex items-center gap-2 mb-3">
                <Server size={15} className="text-emerald-400" />
                <h3 className="text-sm font-semibold text-white">SRE & Platform</h3>
              </div>
              <SkillPills items={RESUME_SKILLS.sre} accent="emerald" />
            </div>
            <div className="panel-card p-4">
              <div className="flex items-center gap-2 mb-3">
                <Cloud size={15} className="text-sky-400" />
                <h3 className="text-sm font-semibold text-white">Cloud & Multi-cloud</h3>
              </div>
              <SkillPills items={RESUME_SKILLS.cloud} accent="indigo" />
            </div>
            <div className="panel-card p-4">
              <div className="flex items-center gap-2 mb-3">
                <Workflow size={15} className="text-violet-400" />
                <h3 className="text-sm font-semibold text-white">CI/CD & GitOps</h3>
              </div>
              <SkillPills items={RESUME_SKILLS.cicd} accent="indigo" />
            </div>
            <div className="panel-card p-4">
              <div className="flex items-center gap-2 mb-3">
                <BarChart3 size={15} className="text-cyan-400" />
                <h3 className="text-sm font-semibold text-white">Observability</h3>
              </div>
              <SkillPills items={RESUME_SKILLS.observability} accent="emerald" />
            </div>
            <div className="panel-card p-4">
              <div className="flex items-center gap-2 mb-3">
                <Sparkles size={15} className="text-indigo-400" />
                <h3 className="text-sm font-semibold text-white">AI & Automation</h3>
              </div>
              <SkillPills items={RESUME_SKILLS.ai} accent="indigo" />
            </div>
            <div className="panel-card p-4">
              <div className="flex items-center gap-2 mb-3">
                <Cpu size={15} className="text-amber-400" />
                <h3 className="text-sm font-semibold text-white">Languages & Tools</h3>
              </div>
              <SkillPills items={RESUME_SKILLS.languages} accent="amber" />
            </div>
          </div>
        </section>

        <DemoLauncher />

        {/* Experience */}
        <section>
          <SectionTitle id="experience">Professional experience</SectionTitle>
          <div className="space-y-4">
            {RESUME_EXPERIENCE.map((job) => (
              <div key={`${job.company}-${job.period}`} className="panel-card p-5">
                <div className="flex flex-wrap items-baseline justify-between gap-2 mb-1">
                  <h3 className="text-sm font-semibold text-white">{job.role}</h3>
                  <span className="text-xs text-gray-500 font-mono">{job.period}</span>
                </div>
                <p className="text-xs text-indigo-300 mb-2">
                  {job.company}
                  {job.location && <span className="text-gray-600"> · {job.location}</span>}
                </p>
                {job.description && (
                  <p className="text-xs text-gray-500 mb-3 leading-relaxed">{job.description}</p>
                )}
                <ul className="space-y-1.5">
                  {job.bullets.map((bullet) => (
                    <li key={bullet} className="text-sm text-gray-400 flex gap-2 leading-relaxed">
                      <span className="text-indigo-600 shrink-0 mt-1.5">•</span>
                      {bullet}
                    </li>
                  ))}
                </ul>
                {job.environment && (
                  <p className="mt-3 pt-3 border-t border-sre-border/40 text-[10px] text-gray-600 leading-relaxed">
                    <span className="font-semibold uppercase tracking-wide text-gray-500">Environment: </span>
                    {job.environment}
                  </p>
                )}
              </div>
            ))}
          </div>
        </section>

        {/* Education & Certifications */}
        <div className="grid gap-5 sm:grid-cols-2">
          <section>
            <SectionTitle id="education">Education</SectionTitle>
            <div className="space-y-3">
              {RESUME_EDUCATION.map((edu) => (
                <div key={edu.institution} className="panel-card p-4">
                  <h3 className="text-sm font-semibold text-white">{edu.degree}</h3>
                  <p className="text-xs text-indigo-300 mt-0.5">{edu.institution}</p>
                  <p className="text-xs text-gray-500 mt-1">{edu.period}</p>
                </div>
              ))}
            </div>
          </section>

          <section>
            <SectionTitle id="certifications">Certifications</SectionTitle>
            <div className="space-y-3">
              {RESUME_CERTIFICATIONS.map((cert) => (
                <div key={cert.name} className="panel-card p-4 border-amber-800/20 bg-amber-950/10">
                  <div className="flex items-start gap-2">
                    <Award size={16} className="text-amber-400 shrink-0 mt-0.5" />
                    <div>
                      <h3 className="text-sm font-semibold text-white">{cert.name}</h3>
                      <p className="text-xs text-gray-400 mt-0.5">{cert.issuer}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </section>
        </div>

        {/* Links */}
        <section>
          <SectionTitle id="links">Connect</SectionTitle>
          <div className="flex flex-wrap gap-2">
            {RESUME_LINKS.map((link) => (
              <ResumeLink key={link.label} link={link} navigate={navigate} />
            ))}
          </div>
        </section>
      </article>

      <RecruiterAskPanel
        onEngaged={() => setRecruiterEngaged(true)}
        onLoadingChange={setRecruiterChatLoading}
      />

      <RecruiterFeedbackPanel engaged={recruiterEngaged} />

      {showAdmin && <AdminStatsPanel onClose={() => setShowAdmin(false)} />}
    </PageShell>
  );
}
