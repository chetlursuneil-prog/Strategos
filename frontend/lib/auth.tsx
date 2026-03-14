"use client";

import React, { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from "react";
import type { User, UserRole } from "@/lib/types";

interface AuthCtx {
  user: User | null;
  token: string | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (payload: RegisterPayload) => Promise<RegisterResult>;
  logout: () => void;
}

interface RegisterPayload {
  name: string;
  email: string;
  password: string;
  companyName?: string;
  role?: UserRole;
}

interface RegisterResult {
  verificationRequired: boolean;
  approvalRequired: boolean;
  emailDelivery: string;
  verificationUrl?: string;
}

const AuthContext = createContext<AuthCtx>({
  user: null,
  token: null,
  loading: true,
  login: async () => {},
  register: async () => ({
    verificationRequired: true,
    approvalRequired: true,
    emailDelivery: "unknown",
  }),
  logout: () => {},
});

const STORAGE_USER_KEY = "strategos_user";
const STORAGE_TOKEN_KEY = "strategos_token";
const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000/api/v1";

interface AuthApiUser {
  id: string;
  email: string;
  name: string;
  role: UserRole;
  requested_role?: UserRole;
  approval_status?: string;
  email_verified?: boolean;
  tenant_id: string;
}

interface AuthSuccessResponse<TData = { token?: string; user: AuthApiUser }> {
  status: "success";
  data: TData;
}

function normalizeUser(apiUser: AuthApiUser): User {
  return {
    id: apiUser.id,
    email: apiUser.email,
    name: apiUser.name,
    role: apiUser.role,
    tenantId: apiUser.tenant_id,
  };
}

async function requestAuth(path: string, payload?: Record<string, unknown>, token?: string) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: payload ? "POST" : "GET",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    ...(payload ? { body: JSON.stringify(payload) } : {}),
  });

  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = typeof body?.detail === "string" ? body.detail : `HTTP ${res.status}`;
    throw new Error(detail);
  }
  return body as AuthSuccessResponse;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const persistAuth = useCallback((nextUser: User, nextToken: string) => {
    setUser(nextUser);
    setToken(nextToken);
    localStorage.setItem(STORAGE_USER_KEY, JSON.stringify(nextUser));
    localStorage.setItem(STORAGE_TOKEN_KEY, nextToken);
  }, []);

  const clearAuth = useCallback(() => {
    setUser(null);
    setToken(null);
    localStorage.removeItem(STORAGE_USER_KEY);
    localStorage.removeItem(STORAGE_TOKEN_KEY);
  }, []);

  useEffect(() => {
    (async () => {
      try {
        const rawUser = localStorage.getItem(STORAGE_USER_KEY);
        const rawToken = localStorage.getItem(STORAGE_TOKEN_KEY);
        if (!rawUser || !rawToken) {
          clearAuth();
          return;
        }

        const me = await requestAuth("/auth/me", undefined, rawToken);
        const parsed = normalizeUser(me.data.user);
        persistAuth(parsed, rawToken);
      } catch {
        clearAuth();
      } finally {
        setLoading(false);
      }
    })();
  }, [clearAuth, persistAuth]);

  const login = useCallback(async (email: string, password: string) => {
    const resp = await requestAuth("/auth/login", {
      email: email.trim().toLowerCase(),
      password,
    });
    const nextToken = resp.data.token;
    if (!nextToken) throw new Error("missing_auth_token");
    persistAuth(normalizeUser(resp.data.user), nextToken);
  }, [persistAuth]);

  const register = useCallback(async (payload: RegisterPayload) => {
    const resp = await requestAuth("/auth/register", {
      name: payload.name.trim(),
      email: payload.email.trim().toLowerCase(),
      password: payload.password,
      company_name: payload.companyName?.trim() || undefined,
      role: payload.role || "analyst",
    });
    const data = resp.data as {
      user: AuthApiUser;
      verification_required: boolean;
      approval_required: boolean;
      email_delivery?: string;
      verification_url?: string;
    };
    return {
      verificationRequired: Boolean(data.verification_required),
      approvalRequired: Boolean(data.approval_required),
      emailDelivery: data.email_delivery || "unknown",
      verificationUrl: data.verification_url,
    };
  }, []);

  const logout = useCallback(() => {
    clearAuth();
  }, [clearAuth]);

  return (
    <AuthContext.Provider value={{ user, token, loading, login, register, logout }}>
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
