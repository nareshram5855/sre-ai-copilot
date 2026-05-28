import {
  OBSERVE_DEMO_DEFAULT_SERVICE,
  OBSERVE_DEMO_SERVICES,
} from "../data/demoObserveContent.js";

export const OBSERVE_DEMO_ACTIVE_KEY = "sreai.observeDemoActive";

const OBSERVE_DEMO_VIEWS = new Set(["dashboard", "observe", "resume"]);

export function parseObserveDemoFromSearchParams(searchParams) {
  if (!searchParams) return false;
  const get =
    typeof searchParams.get === "function"
      ? searchParams.get.bind(searchParams)
      : () => null;
  const demo = get("demo");
  if (demo === "observe") return true;
  if (demo === "1" && (get("service") || window.location.pathname === "/observe")) {
    return true;
  }
  return false;
}

export function isObserveDemoActive(searchParams) {
  if (parseObserveDemoFromSearchParams(searchParams)) return true;
  try {
    return sessionStorage.getItem(OBSERVE_DEMO_ACTIVE_KEY) === "1";
  } catch (_) {
    return false;
  }
}

export function canAccessInObserveDemo(view) {
  return isObserveDemoActive() && OBSERVE_DEMO_VIEWS.has(view);
}

export function getObserveDemoService(searchParams) {
  const get =
    typeof searchParams?.get === "function"
      ? searchParams.get.bind(searchParams)
      : () => null;
  const svc = get?.("service");
  if (svc && OBSERVE_DEMO_SERVICES.includes(svc)) return svc;
  return OBSERVE_DEMO_DEFAULT_SERVICE;
}

export function buildObserveDemoUrl(service = OBSERVE_DEMO_DEFAULT_SERVICE) {
  return `/observe?demo=1&service=${encodeURIComponent(service)}`;
}

/** Enter observability demo — read-only platform access without password. */
export function startObserveDemo(navigate, setRole, service = OBSERVE_DEMO_DEFAULT_SERVICE) {
  try {
    sessionStorage.setItem(OBSERVE_DEMO_ACTIVE_KEY, "1");
  } catch (_) {}
  setRole("read");
  navigate(buildObserveDemoUrl(service));
}

export function endObserveDemo(navigate, setRole) {
  try {
    sessionStorage.removeItem(OBSERVE_DEMO_ACTIVE_KEY);
  } catch (_) {}
  setRole("recruiter");
  navigate("/resume", { replace: true });
}

export function filterObserveDemoServices(services) {
  if (!Array.isArray(services)) return [];
  const allowed = new Set(OBSERVE_DEMO_SERVICES);
  const filtered = services.filter((s) => allowed.has(s.name));
  return filtered.length > 0 ? filtered : services.slice(0, 1);
}

export function dispatchObserveDemoStart(service) {
  window.dispatchEvent(
    new CustomEvent("sre-observe-demo-start", { detail: { service } })
  );
}
