import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  UserPlus,
  Users,
  Boxes,
  GitBranch,
  Rocket,
  History,
  BookOpen,
  Users2,
  HelpCircle,
  Sparkles,
  Shield,
  LayoutTemplate,
} from "lucide-react";
import { platformRepoUrl } from "../../constants/platform.js";
import { useAuth } from "../../context/AuthContext.jsx";
import { APP_VERSION } from "../../constants/version.js";
import Logo from "../ui/Logo.jsx";

const NAV_ICONS = {
  dashboard: LayoutDashboard,
  team: Users2,
  onboard: UserPlus,
  architect: Sparkles,
  users: Users,
  catalog: Boxes,
  blueprints: LayoutTemplate,
  pipelines: GitBranch,
  deploy: Rocket,
  history: History,
  docs: BookOpen,
  adminOps: Shield,
};

function buildNavSections(role) {
  const sections = [
    {
      label: "MY WORKSPACE",
      items: [
        { to: "/", label: "Dashboard", icon: "dashboard", end: true },
        { to: "/team", label: "My Team", icon: "team" },
      ],
    },
    {
      label: "Service Catalog",
      items: [
        {
          to: "/modules",
          label: "Catalog",
          icon: "catalog",
          subtitle: "AWS modules & services",
        },
        {
          to: "/blueprints",
          label: "Blueprints",
          icon: "blueprints",
          subtitle: "Pre-built stack templates",
        },
      ],
    },
  ];

  if (role !== "viewer") {
    sections.push({
      label: "PLATFORM OPS",
      items: [
        { to: "/pipelines", label: "Pipeline templates", icon: "pipelines" },
        {
          to: "/deploy",
          label: "Platform Infrastructure",
          icon: "deploy",
          badge: "Platform",
        },
      ],
    });
  }

  const governanceItems = [
    ...(role !== "viewer"
      ? [{ to: "/history", label: "History", icon: "history" }]
      : []),
  ];

  if (role === "admin") {
    governanceItems.unshift(
      {
        to: "/architect",
        label: "Architect",
        icon: "architect",
        highlight: true,
        helper: "AI",
      },
      {
        to: "/onboard",
        label: "Onboard",
        icon: "onboard",
        highlight: false,
        helper: "New team?",
      }
    );
    governanceItems.push({
      to: "/users",
      label: "Users",
      icon: "users",
      adminOnly: true,
      disabledTooltip: "User management requires admin role",
    });
    governanceItems.unshift({
      to: "/admin",
      label: "Admin Operations",
      icon: "adminOps",
      adminOnly: true,
      badge: "Admin",
      disabledTooltip: "Admin stack deploy requires platform admin role",
    });
  }

  sections.push({
    label: "Governance",
    items: governanceItems,
  });

  return sections;
}

function NavIcon({ name, active }) {
  const Icon = NAV_ICONS[name];
  if (!Icon) return null;
  return (
    <Icon
      size={16}
      strokeWidth={1.75}
      className={active ? "text-accent shrink-0" : "text-[var(--text-muted)] shrink-0"}
    />
  );
}

function NavItemLabel({ item, isActive, collapsed }) {
  const { label, badge, helper, subtitle } = item;
  if (collapsed) return null;

  return (
    <span className="flex-1 min-w-0">
      <span className="flex items-center gap-2">
        <span>{label}</span>
        {badge && (
          <span className="text-[9px] font-semibold uppercase tracking-wide px-1.5 py-0.5 rounded bg-[var(--bg-muted)] text-[var(--text-faint)] border border-[var(--border-subtle)]">
            {badge}
          </span>
        )}
        {helper && !isActive && (
          <span className="text-[9px] font-medium text-accent/80 ml-auto">{helper}</span>
        )}
      </span>
      {subtitle && (
        <span className="block text-[10px] text-[var(--text-faint)] truncate mt-0.5">
          {subtitle}
        </span>
      )}
    </span>
  );
}

function navItemClass({ isActive, highlight, disabled, collapsed }) {
  return `flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-all duration-200 ${
    collapsed ? "justify-center px-2" : ""
  } ${
    disabled
      ? "opacity-45 cursor-not-allowed text-[var(--text-faint)]"
      : isActive
        ? highlight
          ? "nav-active-glow text-[var(--cyan)] font-medium border border-[rgba(34,211,238,0.2)]"
          : "nav-active-glow bg-accent-muted text-accent font-medium"
        : highlight
          ? "text-[var(--text-primary)] hover:text-accent hover:bg-accent/5 border border-transparent hover:border-accent/20"
          : "text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)]"
  }`;
}

function SidebarNavItem({ item, collapsed, disabled, onNavClick }) {
  const { to, label, icon, end, highlight, disabledTooltip } = item;

  if (disabled) {
    return (
      <span
        className={navItemClass({ isActive: false, highlight, disabled: true, collapsed })}
        title={collapsed ? `${label} — ${disabledTooltip}` : disabledTooltip}
      >
        <NavIcon name={icon} active={false} />
        <NavItemLabel item={item} isActive={false} collapsed={collapsed} />
      </span>
    );
  }

  return (
    <NavLink
      to={to}
      end={end}
      onClick={onNavClick}
      className={({ isActive }) => navItemClass({ isActive, highlight, disabled: false, collapsed })}
      title={collapsed ? label : undefined}
    >
      {({ isActive }) => (
        <>
          <NavIcon name={icon} active={isActive} />
          <NavItemLabel item={item} isActive={isActive} collapsed={collapsed} />
        </>
      )}
    </NavLink>
  );
}

export default function Sidebar({ collapsed = false, mobileOpen = false, onClose }) {
  const { user } = useAuth();
  const role = user?.role ?? "viewer";
  const navSections = buildNavSections(role);

  return (
    <aside
      className={[
        // Mobile: fixed overlay drawer that slides in/out
        "fixed inset-y-0 left-0 z-40",
        // Desktop: relative, always visible
        "md:relative md:z-auto md:translate-x-0",
        "shrink-0 flex flex-col border-r border-[var(--border-subtle)]",
        "bg-[var(--bg-surface)] backdrop-blur-xl transition-transform duration-300 ease-in-out",
        collapsed ? "md:w-16" : "w-[var(--sidebar-width)]",
        // Mobile slide: open → visible, closed → off-screen left
        mobileOpen ? "translate-x-0" : "-translate-x-full",
      ].join(" ")}
    >
      <div className={`px-4 py-5 border-b border-[var(--border-subtle)] ${collapsed ? "px-2 flex justify-center" : ""}`}>
        {collapsed ? (
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-accent to-violet-600 flex items-center justify-center">
            <svg viewBox="0 0 24 24" fill="none" className="w-4 h-4" aria-hidden>
              <path d="M12 3L4 8v8l8 5 8-5V8l-8-5z" stroke="white" strokeWidth="1.5" strokeLinejoin="round" />
            </svg>
          </div>
        ) : (
          <Logo size="sm" />
        )}
      </div>

      <nav className="flex-1 py-4 overflow-y-auto">
        {navSections.map((section) => (
          <div key={section.label} className="mb-5">
            {!collapsed && (
              <p className="px-4 mb-2 text-[10px] font-semibold uppercase tracking-widest text-[var(--text-faint)]">
                {section.label}
              </p>
            )}
            <div className="space-y-0.5 px-2">
              {section.items.map((item) => (
                <SidebarNavItem
                  key={item.to}
                  item={item}
                  collapsed={collapsed}
                  onNavClick={onClose}
                  disabled={
                    item.adminOnly
                      ? role !== "admin"
                      : item.disabledForRoles?.includes(role)
                  }
                />
              ))}
            </div>
          </div>
        ))}
      </nav>

      {!collapsed && (
        <div className="px-4 py-4 border-t border-[var(--border-subtle)] space-y-2">
          <NavLink
            to="/docs"
            className="flex items-center gap-2 text-[11px] text-[var(--text-faint)] hover:text-[var(--text-muted)] transition-colors"
          >
            <HelpCircle size={14} className="shrink-0" />
            <span>Help & guides</span>
          </NavLink>
          <a
            href={platformRepoUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 text-[11px] text-[var(--text-faint)] hover:text-[var(--text-muted)] transition-colors group"
          >
            <svg viewBox="0 0 24 24" className="w-3.5 h-3.5 fill-current shrink-0" aria-hidden>
              <path d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" />
            </svg>
            <span>Open source on GitHub</span>
          </a>
          <p className="text-[10px] text-[var(--text-faint)]">v{APP_VERSION} · MIT License</p>
        </div>
      )}
    </aside>
  );
}

export { buildNavSections as NAV_SECTIONS };
