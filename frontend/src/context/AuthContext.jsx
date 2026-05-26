import { createContext, useContext, useState, useCallback } from "react";
import { ROLES } from "../config/roles.js";

const AuthContext = createContext(null);

const STORAGE_KEY = "sre_role";

function loadRole() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored && Object.values(ROLES).includes(stored)) return stored;
  } catch (_) {}
  return ROLES.recruiter;
}

export function AuthProvider({ children }) {
  const [role, setRoleState] = useState(loadRole);

  const setRole = useCallback((r) => {
    setRoleState(r);
    try { localStorage.setItem(STORAGE_KEY, r); } catch (_) {}
  }, []);

  const logout = useCallback(() => {
    setRole(ROLES.recruiter);
  }, [setRole]);

  return (
    <AuthContext.Provider value={{ role, setRole, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be inside AuthProvider");
  return ctx;
}
