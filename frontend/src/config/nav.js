export const VIEW_LABELS = {
  dashboard: "Command Center",
  observe:   "Observe",
  incidents: "Incidents",
  analyze:   "Incident Analysis",
  runbooks:  "Playbooks",
  audit:     "Audit Log",
  profiler:  "App Profiler",
  docs:      "Architecture",
  resume:    "Resume",
  demo:      "Demo Hub",
};

// Deep-link routing — bidirectional map between react-router paths and views.
export const PATH_TO_VIEW = {
  "/":          "dashboard",
  "/observe":   "observe",
  "/incidents": "incidents",
  "/analyze":   "analyze",
  "/playbooks": "runbooks",
  "/audit":     "audit",
  "/profiler":  "profiler",
  "/docs":      "docs",
  "/resume":    "resume",
  "/demo":      "demo",
};

export const VIEW_TO_PATH = {
  dashboard: "/",
  observe:   "/observe",
  incidents: "/incidents",
  analyze:   "/analyze",
  runbooks:  "/playbooks",
  audit:     "/audit",
  profiler:  "/profiler",
  docs:      "/docs",
  resume:    "/resume",
  demo:      "/demo",
};
