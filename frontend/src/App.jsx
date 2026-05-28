import { useState, useCallback, useEffect, useMemo } from "react";
import { useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { IncidentsPage } from "./components/IncidentsPage.jsx";
import { RunbookPanel } from "./components/RunbookPanel.jsx";
import { IncidentAnalysisPanel } from "./components/IncidentAnalysisPanel.jsx";
import { AnomalyWatchPanel } from "./components/AnomalyWatchPanel.jsx";
import { CommandCenterPanel } from "./components/CommandCenterPanel.jsx";
import { AuditPanel } from "./components/AuditPanel.jsx";
import { ProfilerPanel } from "./components/ProfilerPanel.jsx";
import { EnterpriseDocsPage } from "./pages/EnterpriseDocsPage.jsx";
import { ResumePage } from "./pages/ResumePage.jsx";
import { DemoPage } from "./pages/DemoPage.jsx";
import { NavDrawer } from "./components/NavDrawer.jsx";
import { ChatWidget } from "./components/ChatWidget.jsx";
import { AppTopBar } from "./components/layout/AppTopBar.jsx";
import { DemoTourOverlay } from "./components/demo/DemoTourOverlay.jsx";
import { PATH_TO_VIEW, VIEW_TO_PATH } from "./config/nav.js";
import { useAuth } from "./context/AuthContext.jsx";
import { canViewPage } from "./config/roles.js";
import { startDemoTour } from "./utils/demoTour.js";
import {
  isObserveDemoActive,
  parseObserveDemoFromSearchParams,
  startObserveDemo,
  getObserveDemoService,
} from "./utils/demoObserve.js";

export default function App() {
  const location = useLocation();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { role, setRole } = useAuth();

  const observeDemoActive = isObserveDemoActive(searchParams);

  const initialView = useMemo(() => {
    const v = PATH_TO_VIEW[location.pathname] || "dashboard";
    return canViewPage(role, v) ? v : "resume";
  }, [location.pathname, role]);

  const [activeView, setActiveView] = useState(initialView);
  const [analyzeService, setAnalyzeService] = useState(() => searchParams.get("service") || null);
  const [selectedIncidentKey, setSelectedIncidentKey] = useState(() => searchParams.get("incident") || null);
  const [auditExecutionId, setAuditExecutionId] = useState(() => searchParams.get("execution_id") || "");
  const [navOpen, setNavOpen] = useState(false);

  // Keep view in sync with browser URL; redirect to resume if role can't access it
  useEffect(() => {
    const v = PATH_TO_VIEW[location.pathname] || "dashboard";
    if (!canViewPage(role, v)) {
      navigate("/resume", { replace: true });
    } else {
      setActiveView(v);
    }
  }, [location.pathname, role, navigate]);

  // Keep query-param state in sync when the URL changes
  useEffect(() => {
    setAnalyzeService(searchParams.get("service") || null);
    setSelectedIncidentKey(searchParams.get("incident") || null);
    setAuditExecutionId(searchParams.get("execution_id") || "");
  }, [searchParams]);

  useEffect(() => {
    const onTourStart = () => startDemoTour(navigate, setRole);
    window.addEventListener("sre-demo-tour-start", onTourStart);
    return () => window.removeEventListener("sre-demo-tour-start", onTourStart);
  }, [navigate, setRole]);

  // Observability demo entry: /?demo=observe or /observe?demo=1&service=...
  useEffect(() => {
    const demoParam = searchParams.get("demo");
    if (demoParam === "observe" && location.pathname === "/") {
      startObserveDemo(navigate, setRole, getObserveDemoService(searchParams));
      return;
    }
    if (parseObserveDemoFromSearchParams(searchParams)) {
      try {
        sessionStorage.setItem("sreai.observeDemoActive", "1");
      } catch (_) {}
      if (role === "recruiter") {
        setRole("read");
      }
      if (location.pathname === "/") {
        navigate(`/observe?demo=1&service=${encodeURIComponent(getObserveDemoService(searchParams))}`, { replace: true });
      }
    }
  }, [searchParams, location.pathname, navigate, setRole, role]);

  useEffect(() => {
    const onObserveStart = (ev) => {
      startObserveDemo(navigate, setRole, ev.detail?.service);
    };
    window.addEventListener("sre-observe-demo-start", onObserveStart);
    return () => window.removeEventListener("sre-observe-demo-start", onObserveStart);
  }, [navigate, setRole]);

  // Railway: DEMO_MODE=observability auto-enters observe demo when no other route set
  useEffect(() => {
    if (location.pathname !== "/" && location.pathname !== "/resume") return;
    if (parseObserveDemoFromSearchParams(searchParams)) return;
    let cancelled = false;
    fetch("/api/v1/demo/status")
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (cancelled || !d?.observe_demo) return;
        if (location.pathname === "/" || (location.pathname === "/resume" && !searchParams.has("tour"))) {
          startObserveDemo(navigate, setRole);
        }
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [location.pathname, navigate, searchParams, setRole]);

  const openAnalysis = useCallback((serviceName) => {
    setAnalyzeService(serviceName);
    setNavOpen(false);
    const qs = serviceName ? `?service=${encodeURIComponent(serviceName)}` : "";
    navigate(`/analyze${qs}`);
  }, [navigate]);

  const syncAnalyzeService = useCallback((serviceName) => {
    setAnalyzeService(serviceName);
    const qs = serviceName ? `?service=${encodeURIComponent(serviceName)}` : "";
    if (location.pathname === "/analyze") {
      navigate(`/analyze${qs}`, { replace: true });
    }
  }, [location.pathname, navigate]);

  const openIncident = useCallback((incidentKey) => {
    setNavOpen(false);
    const qs = incidentKey ? `?incident=${encodeURIComponent(incidentKey)}` : "";
    navigate(`/incidents${qs}`);
  }, [navigate]);

  const openAuditFor = useCallback((executionId) => {
    setNavOpen(false);
    const qs = executionId ? `?execution_id=${encodeURIComponent(executionId)}` : "";
    navigate(`/audit${qs}`);
  }, [navigate]);

  const handleViewChange = useCallback((view) => {
    setNavOpen(false);
    const path = VIEW_TO_PATH[view] || "/";
    if (location.pathname !== path) {
      navigate(path);
    } else {
      setActiveView(view);
    }
  }, [location.pathname, navigate]);

  return (
    <div className="flex flex-col h-screen overflow-hidden bg-sre-bg">
      <AppTopBar
        activeView={activeView}
        onBurger={() => setNavOpen((v) => !v)}
        navOpen={navOpen}
        observeDemoActive={observeDemoActive}
        observeDemoService={getObserveDemoService(searchParams)}
      />

      <NavDrawer
        activeView={activeView}
        onViewChange={handleViewChange}
        open={navOpen}
        onClose={() => setNavOpen(false)}
        observeDemoActive={observeDemoActive}
      />

      <main className="flex-1 overflow-auto">
        {activeView === "dashboard" && (
          <CommandCenterPanel
            onAnalyzeService={openAnalysis}
            onViewChange={handleViewChange}
            onOpenIncident={openIncident}
          />
        )}
        {activeView === "observe" && (
          <AnomalyWatchPanel
            onAnalyzeService={openAnalysis}
            observeDemoActive={observeDemoActive}
            demoService={getObserveDemoService(searchParams)}
          />
        )}
        {activeView === "incidents" && <IncidentsPage initialIncidentKey={selectedIncidentKey} onOpenAudit={openAuditFor} />}
        {activeView === "analyze" && (
          <IncidentAnalysisPanel
            initialService={analyzeService}
            onServiceChange={syncAnalyzeService}
          />
        )}
        {activeView === "runbooks" && <RunbookPanel />}
        {activeView === "audit" && <AuditPanel initialExecutionId={auditExecutionId} />}
        {activeView === "profiler" && <ProfilerPanel />}
        {activeView === "docs" && <EnterpriseDocsPage />}
        {activeView === "resume" && <ResumePage />}
        {activeView === "demo" && <DemoPage />}
      </main>

      {activeView !== "resume" && activeView !== "demo" && !observeDemoActive && <ChatWidget />}
      <DemoTourOverlay />
    </div>
  );
}
