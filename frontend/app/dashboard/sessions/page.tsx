"use client";

import React, { useEffect, useState, useCallback } from "react";
import { useAuth } from "@/lib/auth";
import StateBadge from "@/components/ui/StateBadge";
import Link from "next/link";

const API = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000/api/v1";

interface SessionRow {
  id: string;
  name: string | null;
  created_at: string;
  state?: string;
  total_score?: number;
}

export default function SessionsPage() {
  const { user } = useAuth();
  const [sessions, setSessions] = useState<SessionRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const fetchSessions = useCallback(async () => {
    if (!user) return;
    setLoading(true);
    try {
      const res = await fetch(`${API}/sessions?tenant_id=${user.tenantId}`);
      const data = await res.json();
      const items = (data?.data?.sessions || []) as SessionRow[];
      // Try to enrich with snapshot state
      const enriched: SessionRow[] = [];
      for (const s of items.slice(0, 30)) {
        try {
          const snapRes = await fetch(`${API}/sessions/${s.id}/snapshots`);
          const snapData = await snapRes.json();
          const latest = snapData?.data?.latest;
          enriched.push({
            ...s,
            state: latest?.state || undefined,
            total_score: latest?.score_breakdown?.total_score || undefined,
          });
        } catch {
          enriched.push(s);
        }
      }
      setSessions(enriched);
    } catch {
      /* silent */
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => {
    fetchSessions();
  }, [fetchSessions]);

  const deleteSession = async (sessionId: string) => {
    if (!user) return;
    setDeletingId(sessionId);
    try {
      await fetch(`${API}/sessions/${sessionId}?tenant_id=${encodeURIComponent(user.tenantId)}`, {
        method: "DELETE",
      });
      await fetchSessions();
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">Sessions</h1>
          <p className="text-xs text-gray-500 mt-0.5">All transformation diagnostic sessions</p>
          <p className="text-[11px] text-gray-600 mt-1">Use the Delete action in each row to remove a session.</p>
        </div>
        <Link
          href="/dashboard/workspace"
          className="px-4 py-2 bg-amber-500/90 text-[#060a14] font-semibold rounded text-xs hover:bg-amber-500 transition-colors"
        >
          + New Session
        </Link>
      </div>

      {loading ? (
        <div className="text-gray-500 text-sm py-12 text-center">Loading sessions…</div>
      ) : sessions.length === 0 ? (
        <div className="text-gray-600 text-sm py-12 text-center">
          No sessions found.{" "}
          <Link href="/dashboard/workspace" className="text-amber-400 hover:underline">
            Create your first session
          </Link>.
        </div>
      ) : (
        <div className="bg-[#0a0f1c] border border-[#1e293b] rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-gray-500 text-xs uppercase border-b border-[#1e293b]">
                <th className="text-left p-4">Name</th>
                <th className="text-left p-4">State</th>
                <th className="text-left p-4">Score</th>
                <th className="text-left p-4">Created</th>
                <th className="text-right p-4"></th>
              </tr>
            </thead>
            <tbody>
              {sessions.map((s) => (
                <tr key={s.id} className="border-b border-[#1e293b]/50 hover:bg-white/[0.02] transition-colors">
                  <td className="p-4 text-white font-medium">{s.name || "Untitled"}</td>
                  <td className="p-4">
                    {s.state ? <StateBadge state={s.state} size="sm" /> : <span className="text-gray-600">—</span>}
                  </td>
                  <td className="p-4 text-gray-400 font-mono text-xs">
                    {s.total_score != null ? s.total_score.toFixed(2) : "—"}
                  </td>
                  <td className="p-4 text-gray-500 text-xs">
                    {s.created_at ? new Date(s.created_at).toLocaleString() : "—"}
                  </td>
                  <td className="p-4 text-right">
                    <div className="flex items-center justify-end gap-3">
                      <Link
                        href={`/dashboard/sessions/${s.id}`}
                        className="text-xs text-amber-400 hover:underline"
                      >
                        View →
                      </Link>
                      <button
                        onClick={() => deleteSession(s.id)}
                        disabled={deletingId === s.id}
                        className="text-xs text-red-400 hover:underline disabled:opacity-40"
                      >
                        {deletingId === s.id ? "Deleting…" : "Delete"}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
