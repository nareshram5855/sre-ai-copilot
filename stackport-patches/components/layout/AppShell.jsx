import { useState } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { Menu } from "lucide-react";
import Dashboard from "../../pages/Dashboard.jsx";
import Deploy from "../../pages/Deploy.jsx";
import HistoryPage from "../../pages/History.jsx";
import Modules from "../../pages/Modules.jsx";
import Blueprints from "../../pages/Blueprints.jsx";
import Pipelines from "../../pages/Pipelines.jsx";
import Docs from "../../pages/Docs.jsx";
import MyTeam from "../../pages/MyTeam.jsx";
import Onboard from "../../pages/Onboard.jsx";
import Architect from "../../pages/Architect.jsx";
import UsersPage from "../../pages/Users.jsx";
import AdminOperations from "../../pages/AdminOperations.jsx";
import { FloatingAIButton, FloatingAIPanel } from "../ai/FloatingAI.jsx";
import { useAuth } from "../../context/AuthContext.jsx";
import { getToken } from "../../utils/api.js";
import { ProductAnnouncement } from "../visual/PlatformTrustSection.jsx";
import Sidebar from "./Sidebar.jsx";
import TopHeader from "./TopHeader.jsx";
import Logo from "../ui/Logo.jsx";
import UserMenu from "../ui/UserMenu.jsx";

export default function AppShell() {
  const { user, logout } = useAuth();
  const location = useLocation();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  if (!getToken() || !user) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return (
    <div className="flex h-screen overflow-hidden bg-[var(--bg-base)]">
      {/* Mobile backdrop */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/60 z-30 md:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      <Sidebar mobileOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Mobile top bar — hamburger + logo + user avatar */}
        <div className="flex md:hidden items-center gap-3 px-4 h-14 border-b border-[var(--border-subtle)] bg-[var(--bg-surface)] shrink-0 z-20">
          <button
            onClick={() => setSidebarOpen((v) => !v)}
            className="p-2 rounded-lg text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)] transition-colors"
            aria-label="Open navigation"
          >
            <Menu size={22} />
          </button>
          <Logo size="sm" />
          <div className="ml-auto">
            <UserMenu user={user} onLogout={logout} />
          </div>
        </div>

        {/* Desktop top header — hidden on mobile */}
        <div className="hidden md:block">
          <TopHeader user={user} onLogout={logout} />
        </div>

        {/* Demo banner — single scrollable line on mobile */}
        {import.meta.env.VITE_DEMO_MODE === "true" && (
          <div className="flex items-center gap-2 px-4 py-2 bg-accent-muted border-b border-accent/20 text-xs text-accent font-medium overflow-x-auto whitespace-nowrap shrink-0">
            <span>🚀 Live Demo — mock data, no real AWS</span>
            <span className="text-[var(--text-faint)]">·</span>
            <a
              href="https://github.com/nareshram5855/infra-platform"
              target="_blank"
              rel="noopener noreferrer"
              className="underline hover:text-accent-hover shrink-0"
            >
              View source on GitHub
            </a>
            <span className="text-[var(--text-faint)]">·</span>
            <span className="text-[var(--text-muted)] shrink-0">AI wizard disabled in demo</span>
          </div>
        )}

        <ProductAnnouncement />

        <main className="flex-1 overflow-y-auto app-canvas">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/team" element={<MyTeam />} />
            <Route path="/deploy" element={<Deploy />} />
            <Route path="/pipelines" element={<Pipelines />} />
            <Route path="/catalog" element={<Navigate to="/modules" replace />} />
            <Route path="/modules" element={<Modules />} />
            <Route path="/blueprints" element={<Blueprints />} />
            <Route path="/history" element={<HistoryPage />} />
            <Route path="/onboard" element={<Onboard />} />
            <Route path="/architect" element={<Architect />} />
            <Route path="/users" element={<UsersPage />} />
            <Route path="/admin" element={<AdminOperations />} />
            <Route path="/docs" element={<Docs />} />
          </Routes>
        </main>
      </div>

      <FloatingAIPanel />
      <FloatingAIButton />
    </div>
  );
}
