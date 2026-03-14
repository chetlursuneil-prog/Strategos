"use client";

import React, { useEffect, useState } from "react";
import { useAuth, useRequireRole } from "@/lib/auth";
import type { UserRole } from "@/lib/types";

const API = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000/api/v1";

type PendingUser = {
  id: string;
  email: string;
  name: string;
  role: UserRole;
  requested_role?: UserRole;
  approval_status?: string;
  email_verified?: boolean;
};

export default function AccessApprovalsPage() {
  const { token } = useAuth();
  const isAdmin = useRequireRole("admin");
  const [pendingUsers, setPendingUsers] = useState<PendingUser[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadPending = async () => {
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API}/auth/admin/pending-users`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(typeof body?.detail === "string" ? body.detail : `HTTP ${res.status}`);
      }
      setPendingUsers((body?.data?.pending_users || []) as PendingUser[]);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadPending();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const approve = async (userId: string, role: UserRole) => {
    if (!token) return;
    await fetch(`${API}/auth/admin/users/${encodeURIComponent(userId)}/approve`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ role }),
    });
    await loadPending();
  };

  const reject = async (userId: string) => {
    if (!token) return;
    await fetch(`${API}/auth/admin/users/${encodeURIComponent(userId)}/reject`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
    });
    await loadPending();
  };

  if (!isAdmin) {
    return (
      <div className="py-12 text-center">
        <div className="bg-red-900/20 border border-red-800/40 rounded-lg p-8 max-w-md mx-auto">
          <p className="text-red-400 font-medium">Access Denied</p>
          <p className="text-gray-500 text-sm mt-2">Admin role required.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold text-white">Access Approvals</h1>
        <p className="text-sm text-gray-500 mt-1">Approve or reject pending sign-up requests.</p>
      </div>

      {error && <p className="text-sm text-red-400">{error}</p>}
      {loading && <p className="text-sm text-gray-500">Loading requests...</p>}

      <div className="space-y-3">
        {pendingUsers.length === 0 ? (
          <div className="bg-[#0a0f1c] border border-[#1e293b] rounded-lg p-4 text-sm text-gray-500">
            No pending approval requests.
          </div>
        ) : (
          pendingUsers.map((u) => (
            <div key={u.id} className="bg-[#0a0f1c] border border-[#1e293b] rounded-lg p-4">
              <p className="text-white text-sm font-medium">{u.name}</p>
              <p className="text-xs text-gray-500 mt-0.5">{u.email}</p>
              <p className="text-xs text-gray-400 mt-1">
                Requested role: <span className="text-amber-400">{u.requested_role || u.role}</span>
                {" · "}
                Email verified: <span className={u.email_verified ? "text-green-400" : "text-red-400"}>{u.email_verified ? "yes" : "no"}</span>
              </p>
              <div className="mt-3 flex flex-wrap items-center gap-2">
                {(["admin", "analyst", "viewer"] as UserRole[]).map((r) => (
                  <button
                    key={r}
                    onClick={() => approve(u.id, r)}
                    className="px-3 py-1.5 text-xs rounded bg-green-900/30 border border-green-700/40 text-green-300 hover:bg-green-900/50"
                  >
                    Approve as {r}
                  </button>
                ))}
                <button
                  onClick={() => reject(u.id)}
                  className="px-3 py-1.5 text-xs rounded bg-red-900/30 border border-red-700/40 text-red-300 hover:bg-red-900/50"
                >
                  Reject
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
