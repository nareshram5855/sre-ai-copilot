// Role-based access control

export const ROLES = {
  recruiter: "recruiter",
  read:      "read",
  admin:     "admin",
};

export const ROLE_META = {
  recruiter: { label: "Recruiter",   color: "text-violet-300",  badge: "bg-violet-500/20 text-violet-300 border-violet-500/30" },
  read:      { label: "Read-Only",   color: "text-blue-300",    badge: "bg-blue-500/20   text-blue-300   border-blue-500/30"   },
  admin:     { label: "Admin",       color: "text-emerald-300", badge: "bg-emerald-500/20 text-emerald-300 border-emerald-500/30" },
};

// Views each role may access. "*" = all.
export const ROLE_VIEWS = {
  recruiter: ["resume", "demo"],
  read:      "*",
  admin:     "*",
};

// Whether the role may trigger mutating actions (execute, approve, escalate).
export const ROLE_CAN_ACT = {
  recruiter: false,
  read:      false,
  admin:     true,
};

export function canViewPage(role, view) {
  const allowed = ROLE_VIEWS[role];
  if (allowed === "*") return true;
  return allowed?.includes(view) ?? false;
}

export function canAct(role) {
  return ROLE_CAN_ACT[role] ?? false;
}

// Simple demo password — not security, just a UX gate for recruiters.
export const ADMIN_PASSWORD = "devops2024";
export const READ_PASSWORD  = "readonly";
