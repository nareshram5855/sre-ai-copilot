import { useCallback, useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Play, Radio, Loader2, ChevronUp, Layers } from "lucide-react";
import { useAuth } from "../../context/AuthContext.jsx";
import { DEMO_METRICS, FEATURED_PROJECT } from "../../data/resumeContent.js";
import {
  dispatchDemoExpand,
  shouldAutoExpandDemo,
  startDemoTour,
} from "../../utils/demoTour.js";
import { ArchitectureExplainer, HeroTechStack } from "./ArchitectureExplainer.jsx";

function oneLineSummary(text, maxLen = 140) {
  const trimmed = text.replace(/\s+/g, " ").trim();
  if (trimmed.length <= maxLen) return trimmed;
  return `${trimmed.slice(0, maxLen).trim()}…`;
}

export function DemoLauncher() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { setRole } = useAuth();
  const [live, setLive] = useState(null);
  const [demoExpanded, setDemoExpanded] = useState(() => shouldAutoExpandDemo(searchParams));

  useEffect(() => {
    let cancelled = false;
    fetch("/api/v1/demo/status")
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (!cancelled) setLive(d?.live ?? false);
      })
      .catch(() => {
        if (!cancelled) setLive(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (shouldAutoExpandDemo(searchParams)) {
      setDemoExpanded(true);
    }
  }, [searchParams]);

  const scrollToFeatured = useCallback(() => {
    window.requestAnimationFrame(() => {
      document.getElementById("featured-project")?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }, []);

  const handleExpand = useCallback(() => {
    setDemoExpanded(true);
    navigate({ pathname: "/resume", search: "?demo=1", hash: "featured-project" }, { replace: true });
    scrollToFeatured();
  }, [navigate, scrollToFeatured]);

  const handleCollapse = useCallback(() => {
    setDemoExpanded(false);
    if (searchParams.get("demo") === "1" || searchParams.has("tour")) {
      navigate("/resume", { replace: true });
    }
  }, [navigate, searchParams]);

  useEffect(() => {
    const onExpand = () => {
      setDemoExpanded(true);
      scrollToFeatured();
    };
    window.addEventListener("sre-demo-expand", onExpand);
    return () => window.removeEventListener("sre-demo-expand", onExpand);
  }, [scrollToFeatured]);

  function handleStartTour() {
    setDemoExpanded(true);
    startDemoTour(navigate, setRole);
  }

  return (
    <section id="featured-project">
      <div className="flex flex-wrap items-end justify-between gap-3 mb-3">
        <h2 className="text-[11px] font-bold text-gray-500 uppercase tracking-[0.15em] scroll-mt-24">
          Flagship project — live demo
        </h2>
        {live === null ? (
          <Loader2 size={12} className="animate-spin text-stone-500 resume-no-print" />
        ) : (
          <span
            className={`inline-flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wide px-2 py-0.5 rounded-full border ${
              live
                ? "border-emerald-500/30 text-emerald-300 bg-emerald-950/30"
                : "border-amber-500/25 text-amber-200 bg-amber-950/20"
            }`}
          >
            <Radio size={9} className={live ? "animate-pulse" : ""} />
            {live ? "Live stack" : "Mock OK"}
          </span>
        )}
      </div>

      <div className="demo-launcher panel-card relative overflow-hidden border-indigo-800/25">
        <div className="demo-launcher-glow pointer-events-none absolute inset-0" aria-hidden="true" />
        <div className="relative p-5 sm:p-6">
          {!demoExpanded ? (
            <div className="demo-launcher-teaser">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="text-lg sm:text-xl font-bold text-white">{FEATURED_PROJECT.name}</h3>
                    {FEATURED_PROJECT.badge && (
                      <span className="demo-launcher-teaser-badge shrink-0">{FEATURED_PROJECT.badge}</span>
                    )}
                  </div>
                  <p className="text-xs text-indigo-300/90 mt-1">{FEATURED_PROJECT.role}</p>
                  <p className="text-[11px] text-gray-500 font-mono mt-0.5">{FEATURED_PROJECT.period}</p>
                </div>
              </div>

              <p className="text-sm text-gray-300 leading-relaxed mt-3 max-w-2xl">
                {oneLineSummary(FEATURED_PROJECT.summary, 180)}
              </p>

              <div className="grid grid-cols-3 gap-2 mt-4">
                {DEMO_METRICS.map((m) => (
                  <div
                    key={m.label}
                    className="demo-launcher-teaser-metric rounded-lg border border-sre-border/45 bg-sre-bg/35 px-2.5 py-2 text-center"
                  >
                    <p className="text-sm font-bold text-white font-mono">{m.value}</p>
                    <p className="text-[9px] text-stone-500 mt-0.5 leading-snug">{m.label}</p>
                  </div>
                ))}
              </div>

              <HeroTechStack compact className="mt-3" />

              <div className="flex flex-col sm:flex-row flex-wrap gap-2.5 mt-5 resume-no-print">
                <button
                  type="button"
                  onClick={handleExpand}
                  className="demo-cta-primary inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl text-xs sm:text-sm font-semibold text-white"
                >
                  <Layers size={15} />
                  View demo &amp; architecture
                </button>
                <button
                  type="button"
                  onClick={handleStartTour}
                  className="demo-launcher-card demo-launcher-card--primary inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl border text-xs sm:text-sm font-semibold text-white transition-all"
                >
                  <Play size={14} className="text-teal-300 fill-teal-300/30" />
                  5-min HM tour
                </button>
              </div>
            </div>
          ) : (
            <>
              <div className="flex justify-end mb-2 resume-no-print">
                <button
                  type="button"
                  onClick={handleCollapse}
                  className="inline-flex items-center gap-1 text-[11px] font-medium text-stone-500 hover:text-stone-300 transition-colors"
                  aria-expanded="true"
                >
                  <ChevronUp size={14} />
                  Collapse demo docs
                </button>
              </div>

              <ArchitectureExplainer onStartTour={handleStartTour} />

              {/* Quick tour CTA — visible above fold on mobile after hero metrics */}
              <div className="mt-6 pt-4 border-t border-sre-border/30 resume-no-print sm:hidden">
                <button
                  type="button"
                  onClick={handleStartTour}
                  className="demo-launcher-card demo-launcher-card--primary group w-full text-left rounded-xl border p-4 transition-all"
                >
                  <Play size={18} className="text-teal-300 mb-2" />
                  <p className="text-sm font-semibold text-white">5-min HM tour</p>
                  <p className="text-[11px] text-stone-400 mt-1 leading-snug">
                    Architecture walkthrough · stays on this page
                  </p>
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </section>
  );
}