import { useMemo, useEffect } from "react";
import { useNavigate, useSearchParams, useLocation } from "react-router-dom";
import {
  ChevronLeft, ChevronRight, X, Sparkles, AlertTriangle,
  GitBranch, Building2, Layers, Activity, MessageCircle,
} from "lucide-react";
import { useAuth } from "../../context/AuthContext.jsx";
import { DEMO_TOUR_STEPS } from "../../data/demoTourContent.js";
import {
  endDemoTour,
  getTourStepDef,
  getTourStepFromSearchParams,
  goToTourStep,
  highlightTourSection,
  isDemoTourActive,
  scrollToTourSection,
  clearTourSectionHighlight,
} from "../../utils/demoTour.js";
import { openRecruiterChat } from "../../utils/recruiterChatEvents.js";

const STEP_ICONS = {
  problem: AlertTriangle,
  layers: Layers,
  flow: GitBranch,
  observe: Activity,
  enterprise: Building2,
};

export function DemoTourOverlay() {
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const { setRole } = useAuth();

  const step = getTourStepFromSearchParams(searchParams);
  const onResume = location.pathname === "/resume";
  const active = isDemoTourActive() && step > 0 && onResume;
  const def = useMemo(() => getTourStepDef(step), [step]);

  useEffect(() => {
    if (!active || !def) return undefined;
    document.body.classList.add("demo-tour-active");
    return () => document.body.classList.remove("demo-tour-active");
  }, [active, def]);

  useEffect(() => {
    if (!active || !def?.sectionId) return undefined;
    const timer = window.setTimeout(() => {
      scrollToTourSection(def.sectionId);
      highlightTourSection(def.sectionId);
    }, 120);
    return () => {
      window.clearTimeout(timer);
      clearTourSectionHighlight();
    };
  }, [active, def?.sectionId, step]);

  if (!active || !def) return null;

  const Icon = STEP_ICONS[def.icon] || Sparkles;
  const isFirst = step === 1;
  const isLast = step === DEMO_TOUR_STEPS.length;

  function handleNext() {
    if (isLast) {
      endDemoTour(navigate, setRole, { returnToResume: true });
      window.setTimeout(() => openRecruiterChat(), 300);
      return;
    }
    goToTourStep(navigate, step + 1);
  }

  function handleBack() {
    if (isFirst) return;
    goToTourStep(navigate, step - 1);
  }

  return (
    <div
      className="demo-tour-overlay fixed inset-x-0 bottom-0 z-[70] pointer-events-none px-3 sm:px-4 pb-3 sm:pb-4"
      role="dialog"
      aria-label={`Architecture tour step ${step} of ${DEMO_TOUR_STEPS.length}`}
    >
      <div className="demo-tour-panel pointer-events-auto mx-auto max-w-3xl rounded-2xl border border-teal-500/25 bg-[rgba(10,14,28,0.96)] shadow-2xl shadow-black/50 backdrop-blur-xl overflow-hidden relative">
        <div className="demo-tour-panel-glow pointer-events-none absolute inset-0" aria-hidden="true" />

        <div className="relative p-4 sm:p-5">
          <div className="flex items-start justify-between gap-3 mb-3">
            <div className="flex items-center gap-2 min-w-0">
              <div className="demo-tour-step-icon shrink-0">
                <Icon size={16} className="text-teal-300" />
              </div>
              <div className="min-w-0">
                <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-teal-400/90">
                  HM tour · Step {step} of {DEMO_TOUR_STEPS.length}
                </p>
                <h3 className="text-base sm:text-lg font-bold text-white truncate">{def.title}</h3>
              </div>
            </div>
            <button
              type="button"
              onClick={() => endDemoTour(navigate, setRole)}
              className="demo-tour-control shrink-0 p-2 rounded-lg text-stone-500 hover:text-stone-200"
              aria-label="Exit tour"
            >
              <X size={16} />
            </button>
          </div>

          <div className="flex gap-1 mb-4">
            {DEMO_TOUR_STEPS.map((s) => (
              <span
                key={s.step}
                className={`demo-tour-dot h-1 flex-1 rounded-full transition-colors ${
                  s.step <= step ? "bg-teal-400/80" : "bg-stone-700/60"
                }`}
              />
            ))}
          </div>

          <p className="text-sm sm:text-[15px] font-semibold text-white leading-snug mb-2">
            {def.headline}
          </p>
          <p className="text-[13px] text-stone-400 leading-relaxed mb-3">{def.body}</p>

          <div className="rounded-xl border border-indigo-500/20 bg-indigo-950/25 px-3 py-2.5 mb-4">
            <p className="text-[12px] text-indigo-200/95 leading-relaxed">
              <span className="font-semibold text-indigo-300">Why it matters: </span>
              {def.hmHook}
            </p>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3">
            <span className="text-[10px] font-medium text-stone-500 px-2 py-1 rounded-full border border-stone-700/50 bg-stone-900/40">
              {def.badge}
            </span>
            <div className="flex items-center gap-2 ml-auto">
              {!isFirst && (
                <button type="button" onClick={handleBack} className="demo-tour-btn demo-tour-btn--ghost">
                  <ChevronLeft size={14} />
                  Back
                </button>
              )}
              <button
                type="button"
                onClick={() => endDemoTour(navigate, setRole)}
                className="demo-tour-btn demo-tour-btn--ghost hidden sm:inline-flex"
              >
                Exit tour
              </button>
              <button type="button" onClick={handleNext} className="demo-tour-btn demo-tour-btn--primary">
                {isLast ? (
                  <>
                    <MessageCircle size={14} />
                    Finish & chat with Naresh
                  </>
                ) : (
                  <>
                    Next
                    <ChevronRight size={14} />
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
