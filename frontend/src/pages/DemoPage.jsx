import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Play, BookOpen, Github, ChevronDown, ChevronUp, Sparkles, Radio,
  Shield, ExternalLink, Loader2,
} from "lucide-react";
import { PageShell } from "../components/layout/PageShell.jsx";
import { useAuth } from "../context/AuthContext.jsx";
import { DEMO_LANDING, DEMO_VALUE_PROPS, DEMO_TOUR_STEPS } from "../data/demoTourContent.js";
import { DEMO_METRICS, FEATURED_PROJECT, TECH_STACK_COMPARISON } from "../data/resumeContent.js";
import { HeroTechStack } from "../components/demo/ArchitectureExplainer.jsx";
import { startDemoTour } from "../utils/demoTour.js";

function DemoStatusBadge() {
  const [status, setStatus] = useState(null);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/v1/demo/status")
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (!cancelled) setStatus(data);
      })
      .catch(() => {
        if (!cancelled) setStatus({ mode: "mock", live: false });
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (!status) {
    return (
      <span className="inline-flex items-center gap-1.5 text-[10px] text-stone-500">
        <Loader2 size={11} className="animate-spin" />
        Checking stack…
      </span>
    );
  }

  return (
    <span
      className={`inline-flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wide px-2.5 py-1 rounded-full border ${
        status.live
          ? "border-emerald-500/35 bg-emerald-950/40 text-emerald-300"
          : "border-amber-500/30 bg-amber-950/30 text-amber-200"
      }`}
    >
      <Radio size={10} className={status.live ? "animate-pulse" : ""} />
      {status.live ? "Live stack" : "Mock mode"}
    </span>
  );
}

function StackComparison() {
  const [open, setOpen] = useState(false);

  return (
    <div className="demo-stack-compare panel-card overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between gap-3 px-4 py-3.5 text-left hover:bg-white/[0.02] transition-colors"
      >
        <span className="text-sm font-semibold text-white">Enterprise experience vs this demo</span>
        {open ? <ChevronUp size={16} className="text-stone-500" /> : <ChevronDown size={16} className="text-stone-500" />}
      </button>
      {open && (
        <div className="grid md:grid-cols-2 gap-px bg-sre-border/40 border-t border-sre-border/40">
          <div className="bg-sre-surface/80 p-4">
            <p className="text-[10px] font-bold uppercase tracking-wide text-teal-400/90 mb-3">
              Client work (Citi · BofA · Verizon · Toyota)
            </p>
            <ul className="space-y-2.5">
              {TECH_STACK_COMPARISON.enterprise.map((row) => (
                <li key={row.category}>
                  <p className="text-[11px] font-semibold text-stone-200">{row.category}</p>
                  <p className="text-[10px] text-stone-500 mt-0.5 leading-relaxed">{row.tools}</p>
                </li>
              ))}
            </ul>
          </div>
          <div className="bg-indigo-950/20 p-4">
            <p className="text-[10px] font-bold uppercase tracking-wide text-indigo-300/90 mb-3">
              This portfolio demo
            </p>
            <ul className="space-y-2.5">
              {TECH_STACK_COMPARISON.demo.map((row) => (
                <li key={row.category}>
                  <p className="text-[11px] font-semibold text-stone-200">{row.category}</p>
                  <p className="text-[10px] text-stone-500 mt-0.5 leading-relaxed">{row.tools}</p>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </div>
  );
}

export function DemoPage() {
  const navigate = useNavigate();
  const { setRole } = useAuth();

  return (
    <PageShell constrained className="pb-20 demo-page">
      <div className="demo-landing-hero panel-card relative overflow-hidden p-6 sm:p-8 mb-6">
        <div className="demo-landing-glow pointer-events-none absolute inset-0" aria-hidden="true" />
        <div className="relative">
          <div className="flex flex-wrap items-center gap-2 mb-4">
            <span className="text-[10px] font-bold uppercase tracking-[0.18em] text-teal-400/90">
              {DEMO_LANDING.eyebrow}
            </span>
            <DemoStatusBadge />
          </div>
          <h1 className="text-2xl sm:text-3xl font-bold text-white tracking-tight">{DEMO_LANDING.title}</h1>
          <p className="text-sm sm:text-base text-stone-400 mt-3 leading-relaxed max-w-2xl">{DEMO_LANDING.subtitle}</p>

          <div className="grid grid-cols-3 gap-2 mt-6">
            {DEMO_METRICS.map((m) => (
              <div
                key={m.label}
                className="demo-metric-pill rounded-xl border border-stone-700/45 bg-stone-900/30 px-3 py-2.5 text-center"
              >
                <p className="text-lg font-bold text-white font-mono">{m.value}</p>
                <p className="text-[10px] text-stone-500 mt-0.5 leading-snug">{m.label}</p>
              </div>
            ))}
          </div>

          <HeroTechStack className="mt-4" />

          <div className="flex flex-col sm:flex-row flex-wrap gap-3 mt-8">
            <button
              type="button"
              onClick={() => startDemoTour(navigate, setRole)}
              className="demo-cta-primary inline-flex items-center justify-center gap-2 px-5 py-3 rounded-xl text-sm font-semibold text-white"
            >
              <Play size={16} className="fill-current" />
              {DEMO_LANDING.tourCta}
            </button>
            <button
              type="button"
              onClick={() => navigate("/")}
              className="demo-cta-secondary inline-flex items-center justify-center gap-2 px-5 py-3 rounded-xl text-sm font-medium text-stone-300 border border-stone-600/40 hover:border-teal-500/30 hover:text-white transition-all"
            >
              <Sparkles size={15} className="text-teal-400" />
              {DEMO_LANDING.fullDemoCta}
            </button>
          </div>
          <p className="text-[11px] text-stone-500 mt-2">{DEMO_LANDING.tourSub}</p>
        </div>
      </div>

      <section className="mb-6">
        <h2 className="text-[11px] font-bold text-gray-500 uppercase tracking-[0.15em] mb-3">
          What hiring managers evaluate
        </h2>
        <div className="grid gap-3 sm:grid-cols-3">
          {DEMO_VALUE_PROPS.map((v) => (
            <div key={v.title} className="panel-card p-4 h-full flex flex-col">
              <p className="text-2xl font-bold text-teal-300 font-mono">{v.stat}</p>
              <p className="text-[10px] font-semibold uppercase tracking-wide text-stone-500 mt-0.5">{v.statLabel}</p>
              <p className="text-sm font-semibold text-white mt-3">{v.title}</p>
              <p className="text-[12px] text-stone-400 mt-1.5 leading-relaxed flex-1">{v.detail}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="mb-6">
        <h2 className="text-[11px] font-bold text-gray-500 uppercase tracking-[0.15em] mb-3">
          Architecture tour (5 steps · stays on resume)
        </h2>
        <ol className="demo-tour-path space-y-2">
          {DEMO_TOUR_STEPS.map((step) => (
            <li
              key={step.step}
              className="flex items-center gap-3 rounded-xl border border-sre-border/50 bg-sre-bg/30 px-4 py-3"
            >
              <span className="demo-tour-path-num shrink-0 w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold text-teal-300 border border-teal-500/30 bg-teal-950/30">
                {step.step}
              </span>
              <div className="min-w-0">
                <span className="text-sm text-stone-300">{step.title}</span>
                <p className="text-[11px] text-stone-500 mt-0.5 leading-snug">{step.headline}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>

      <StackComparison />

      <div className="flex flex-wrap gap-2 mt-6">
        <button
          type="button"
          onClick={() => navigate("/docs")}
          className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium text-indigo-200 bg-indigo-600/20 border border-indigo-500/30 hover:bg-indigo-600/30 transition-all"
        >
          <BookOpen size={13} />
          Architecture docs
        </button>
        <a
          href={FEATURED_PROJECT.repoUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium text-stone-300 border border-sre-border hover:border-indigo-500/40 hover:text-white transition-all"
        >
          <Github size={13} />
          Source code
          <ExternalLink size={10} className="text-stone-600" />
        </a>
        <button
          type="button"
          onClick={() => navigate("/resume")}
          className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium text-teal-300/90 border border-teal-500/20 hover:bg-teal-950/20 transition-all"
        >
          <Shield size={13} />
          Back to resume
        </button>
      </div>
    </PageShell>
  );
}
