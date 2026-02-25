"use client";

import React, { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from "react";
import type { User, UserRole } from "@/lib/types";

interface AuthCtx {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthCtx>({
  user: null,
  loading: true,
  login: async () => {},
  logout: () => {},
});

const STORAGE_KEY = "strategos_user";
const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000/api/v1";

/* Demo users — replace with real Supabase Auth or JWT in production */
const DEMO_USERS: Record<string, { password: string; user: User }> = {
  "admin@strategos.dev": {
    password: "strategos",
    user: {
      id: "u-admin-001",
      email: "admin@strategos.dev",
      name: "Platform Admin",
      role: "admin",
      tenantId: "70e9df95-26cd-49e3-96b9-04f1116c0505",
    },
  },
  "analyst@strategos.dev": {
    password: "strategos",
    user: {
      id: "u-analyst-001",
      email: "analyst@strategos.dev",
      name: "Strategy Analyst",
      role: "analyst",
      tenantId: "70e9df95-26cd-49e3-96b9-04f1116c0505",
    },
  },
  "viewer@strategos.dev": {
    password: "strategos",
    user: {
      id: "u-viewer-001",
      email: "viewer@strategos.dev",
      name: "Board Viewer",
      role: "viewer",
      tenantId: "70e9df95-26cd-49e3-96b9-04f1116c0505",
    },
  },
};

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const alignTenantWithBackend = useCallback(async (candidate: User): Promise<User> => {
    try {
      const res = await fetch(`${API_BASE}/advisory/skills/model_versions?active_only=true`);
      if (!res.ok) return candidate;
      const json = await res.json();
      const modelVersions = (json?.data?.model_versions || []) as Array<{ tenant_id?: string }>;
      const backendTenant = modelVersions[0]?.tenant_id;
      if (!backendTenant || backendTenant === candidate.tenantId) return candidate;
      return { ...candidate, tenantId: backendTenant };
    } catch {
      return candidate;
    }
  }, []);

  useEffect(() => {
    (async () => {
      try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw) as User;
        const aligned = await alignTenantWithBackend(parsed);
        setUser(aligned);
        localStorage.setItem(STORAGE_KEY, JSON.stringify(aligned));
      }
      } catch { /* ignore */ }
      setLoading(false);
    })();
  }, [alignTenantWithBackend]);

  const login = useCallback(async (email: string, password: string) => {
    const entry = DEMO_USERS[email.toLowerCase().trim()];
    if (!entry || entry.password !== password) {
      throw new Error("Invalid credentials");
    }
    const aligned = await alignTenantWithBackend(entry.user);
    setUser(aligned);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(aligned));
  }, [alignTenantWithBackend]);

  const logout = useCallback(() => {
    setUser(null);
    localStorage.removeItem(STORAGE_KEY);
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}

export function useRequireRole(...roles: UserRole[]) {
  const { user } = useAuth();
  return user ? roles.includes(user.role) : false;
}
