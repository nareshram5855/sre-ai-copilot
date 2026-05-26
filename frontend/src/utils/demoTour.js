import { ROLES } from "../config/roles.js";
import { DEMO_TOUR_STEPS } from "../data/demoTourContent.js";

export const TOUR_ACTIVE_KEY = "sreai.demoTourActive";
export const TOUR_HIGHLIGHT_CLASS = "demo-tour-section-highlight";

export function isDemoTourActive() {
  try {
    return sessionStorage.getItem(TOUR_ACTIVE_KEY) === "1";
  } catch (_) {
    return false;
  }
}

export function getTourStepFromSearchParams(searchParams) {
  const raw = searchParams?.get?.("tour") ?? searchParams;
  const n = parseInt(typeof raw === "string" ? raw : "", 10);
  if (!Number.isFinite(n) || n < 1 || n > DEMO_TOUR_STEPS.length) return 0;
  return n;
}

export function getTourStepDef(step) {
  return DEMO_TOUR_STEPS.find((s) => s.step === step) ?? null;
}

export function buildTourUrl(stepDef) {
  if (!stepDef) return "/resume";
  return `/resume?tour=${stepDef.step}`;
}

export function scrollToTourSection(sectionId, { behavior = "smooth" } = {}) {
  if (!sectionId) return;
  document.getElementById(sectionId)?.scrollIntoView({ behavior, block: "center" });
}

export function highlightTourSection(sectionId) {
  document.querySelectorAll(`.${TOUR_HIGHLIGHT_CLASS}`).forEach((el) => {
    el.classList.remove(TOUR_HIGHLIGHT_CLASS);
  });
  if (!sectionId) return;
  document.getElementById(sectionId)?.classList.add(TOUR_HIGHLIGHT_CLASS);
}

export function clearTourSectionHighlight() {
  document.querySelectorAll(`.${TOUR_HIGHLIGHT_CLASS}`).forEach((el) => {
    el.classList.remove(TOUR_HIGHLIGHT_CLASS);
  });
}

/** Begin architecture tour on /resume — step 1. */
export function startDemoTour(navigate, setRole) {
  try {
    sessionStorage.setItem(TOUR_ACTIVE_KEY, "1");
  } catch (_) {}
  setRole(ROLES.recruiter);
  navigate(buildTourUrl(DEMO_TOUR_STEPS[0]));
}

export function endDemoTour(navigate, setRole, { returnToResume = true } = {}) {
  try {
    sessionStorage.removeItem(TOUR_ACTIVE_KEY);
  } catch (_) {}
  clearTourSectionHighlight();
  setRole(ROLES.recruiter);
  navigate(returnToResume ? "/resume" : "/demo", { replace: true });
}

export function goToTourStep(navigate, step) {
  const def = getTourStepDef(step);
  if (!def) return;
  navigate(buildTourUrl(def));
}

export function shouldAutoExpandDemo(searchParams) {
  if (!searchParams) return false;
  const get = typeof searchParams.get === "function" ? searchParams.get.bind(searchParams) : () => null;
  const has = typeof searchParams.has === "function" ? searchParams.has.bind(searchParams) : () => false;
  return get("demo") === "1" || has("tour");
}

/** Expand the featured-project demo section on /resume (scroll into view). */
export function dispatchDemoExpand() {
  window.dispatchEvent(new CustomEvent("sre-demo-expand"));
}

/** Close chat (if open), expand demo docs, and start the architecture tour. */
export function dispatchDemoTourStart() {
  window.dispatchEvent(new CustomEvent("sre-recruiter-close"));
  dispatchDemoExpand();
  window.dispatchEvent(new CustomEvent("sre-demo-tour-start"));
}
