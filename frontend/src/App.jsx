import { useState } from "react";
import { AlertPanel } from "./components/AlertPanel.jsx";
import { RunbookPanel } from "./components/RunbookPanel.jsx";
import { RCAPanel } from "./components/RCAPanel.jsx";
import { IncidentsPage } from "./components/IncidentsPage.jsx";
import { IncidentAnalysisPanel } from "./components/IncidentAnalysisPanel.jsx";
import { Sidebar } from "./components/Sidebar.jsx";
import { ChatWidget } from "./components/ChatWidget.jsx";

export default function App() {
  const [activeView, setActiveView] = useState("triage");

  return (
    <div className="flex h-screen overflow-hidden bg-sre-bg">
      <Sidebar activeView={activeView} onViewChange={setActiveView} />
      <main className="flex-1 overflow-auto">
        {activeView === "triage"    && <AlertPanel />}
        {activeView === "incidents" && <IncidentsPage />}
        {activeView === "runbooks"  && <RunbookPanel />}
        {activeView === "rca"       && <RCAPanel />}
        {activeView === "analyze"   && <IncidentAnalysisPanel />}
      </main>
      <ChatWidget />
    </div>
  );
}
