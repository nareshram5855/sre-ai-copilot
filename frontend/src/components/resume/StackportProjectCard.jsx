import { ExternalLink, Github, Layers, Shield, Cpu, GitBranch, Cloud, GitPullRequest, Zap, ArrowRight } from "lucide-react";
import { STACKPORT_PROJECT } from "../../data/resumeContent.js";

const HIGHLIGHT_ICONS = [Layers, Cpu, Shield, Cloud, GitBranch, Layers, GitPullRequest, Zap];

export function StackportProjectCard() {
  const p = STACKPORT_PROJECT;

  return (
    <section id="stackport-project" className="mt-6">
      <div className="flex flex-wrap items-end justify-between gap-3 mb-3">
        <h2 className="text-[11px] font-bold text-gray-500 uppercase tracking-[0.15em]">
          Platform engineering project — live demo
        </h2>
        <a
          href={p.demoUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wide px-2 py-0.5 rounded-full border border-emerald-500/30 text-emerald-300 bg-emerald-950/30 hover:bg-emerald-950/50 transition-colors resume-no-print"
        >
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
          Live demo
        </a>
      </div>

      <div className="panel-card relative overflow-hidden border-violet-800/25">
        <div
          className="pointer-events-none absolute inset-0 opacity-30"
          style={{ background: "radial-gradient(ellipse at 20% 50%, rgba(139,92,246,0.12), transparent 70%)" }}
          aria-hidden
        />

        <div className="relative p-5 sm:p-6">
          {/* Header */}
          <div className="flex flex-wrap items-start justify-between gap-3 mb-4">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <h3 className="text-lg sm:text-xl font-bold text-white">{p.name}</h3>
                <span className="text-[10px] font-semibold uppercase tracking-wide px-2 py-0.5 rounded-full border border-violet-500/30 bg-violet-950/30 text-violet-300 shrink-0">
                  {p.badge}
                </span>
              </div>
              <p className="text-xs text-violet-300/90 mt-1">{p.role}</p>
              <p className="text-[11px] text-gray-500 font-mono mt-0.5">{p.period}</p>
            </div>
          </div>

          {/* Summary */}
          <p className="text-sm text-gray-300 leading-relaxed max-w-2xl mb-4">{p.summary}</p>

          {/* Metrics */}
          <div className="grid grid-cols-3 gap-2 mb-5">
            {p.metrics.map((m) => (
              <div key={m.label} className="rounded-lg border border-sre-border/45 bg-sre-bg/35 px-2.5 py-2 text-center">
                <p className="text-sm font-bold text-white font-mono">{m.value}</p>
                <p className="text-[9px] text-stone-500 mt-0.5 leading-snug">{m.label}</p>
              </div>
            ))}
          </div>

          {/* ── AI AutoFix spotlight ───────────────────────────────────────── */}
          {p.autofixFlow && (
            <div className="mb-5 rounded-xl border border-amber-500/20 bg-amber-950/10 p-4">
              <div className="flex items-center gap-2 mb-3">
                <GitPullRequest size={15} className="text-amber-400 shrink-0" />
                <p className="text-sm font-semibold text-white">AI AutoFix — GitOps Patch Bot</p>
                <span className="text-[9px] font-semibold uppercase tracking-wide px-1.5 py-0.5 rounded border border-amber-500/25 text-amber-300 bg-amber-950/30 ml-auto shrink-0">
                  Built-in
                </span>
              </div>
              <p className="text-[11px] text-gray-400 mb-3 leading-relaxed">
                When a GitHub Actions pipeline fails, the portal reads the broken config, asks AI to generate
                a minimal patch, creates a branch, commits, and opens a PR — one click, human review required.
              </p>
              {/* Flow steps */}
              <div className="flex flex-wrap items-center gap-1">
                {p.autofixFlow.map((step, i) => (
                  <div key={i} className="flex items-center gap-1">
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-950/40 border border-amber-500/15 text-amber-200/80 whitespace-nowrap">
                      {step}
                    </span>
                    {i < p.autofixFlow.length - 1 && (
                      <ArrowRight size={10} className="text-amber-500/40 shrink-0" />
                    )}
                  </div>
                ))}
              </div>
              <p className="text-[10px] text-stone-500 mt-2">
                Hard-blocked from patching: <code className="text-stone-400">*.tfstate</code>,{" "}
                <code className="text-stone-400">credentials</code>, <code className="text-stone-400">.env</code>,{" "}
                <code className="text-stone-400">private_key</code> — secrets never touched.
              </p>
            </div>
          )}

          {/* Highlights grid — all except autofix (shown above) */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-4">
            {p.highlights
              .filter(h => !h.label.includes("AutoFix"))
              .map((h, i) => {
                const Icon = HIGHLIGHT_ICONS[i] ?? Layers;
                return (
                  <div key={h.label} className="rounded-lg border border-sre-border/40 bg-sre-bg/25 p-3">
                    <div className="flex items-center gap-2 mb-1">
                      <Icon size={13} className="text-violet-400 shrink-0" />
                      <p className="text-xs font-semibold text-white">{h.label}</p>
                    </div>
                    <p className="text-[11px] text-gray-400 leading-relaxed">{h.detail}</p>
                  </div>
                );
              })}
          </div>

          {/* Tech stack */}
          <div className="flex flex-wrap gap-1.5 mb-5">
            {p.techStackCategories.map((cat) =>
              cat.tools.map((tool) => (
                <span
                  key={`${cat.category}-${tool}`}
                  className="text-[10px] px-2 py-0.5 rounded-md border border-sre-border/40 bg-sre-bg/30 text-stone-400 font-mono"
                >
                  {tool}
                </span>
              ))
            )}
          </div>

          {/* CTAs */}
          <div className="flex flex-wrap gap-2.5 resume-no-print">
            <a
              href={p.demoUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs sm:text-sm font-semibold text-white transition-all"
              style={{ background: "linear-gradient(135deg, #7c3aed 0%, #4f46e5 100%)" }}
            >
              <ExternalLink size={14} />
              Open live demo
            </a>
            <a
              href={p.repoUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl border border-sre-border/50 bg-sre-bg/40 text-xs sm:text-sm font-semibold text-gray-200 hover:border-violet-500/40 hover:text-white transition-all"
            >
              <Github size={14} />
              {p.repoLabel}
            </a>
          </div>
        </div>
      </div>
    </section>
  );
}
