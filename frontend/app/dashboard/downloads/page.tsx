"use client";

import React, { useEffect, useState, useCallback } from "react";
import { useAuth } from "@/lib/auth";

const API = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000/api/v1";

interface SessionItem {
  id: string;
  name: string | null;
  created_at: string;
}

type Format = "pdf" | "csv";

export default function DownloadsPage() {
  const { user } = useAuth();
  const [sessions, setSessions] = useState<SessionItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [downloading, setDownloading] = useState<string>("");

  const fetchSessions = useCallback(async () => {
    if (!user) return;
    setLoading(true);
    try {
      const res = await fetch(`${API}/sessions?tenant_id=${user.tenantId}`);
      const data = await res.json();
      setSessions((data?.data?.sessions || []) as SessionItem[]);
    } catch {
      /* silent */
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => { fetchSessions(); }, [fetchSessions]);

  const triggerDownload = async (session: SessionItem, format: Format) => {
    const key = `${session.id}-${format}`;
    setDownloading(key);
    try {
      const res = await fetch(`${API}/reports/${session.id}?format=${format}`);
      if (!res.ok) throw new Error(`Server returned ${res.status}`);
      const blob = await res.blob();
      const ext = format === "pdf" ? "txt" : "csv"; // backend returns plain text report
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `strategos-report-${session.name || session.id}.${ext}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      alert(`Download failed: ${err instanceof Error ? err.message : "Unknown error"}. Make sure the backend is running.`);
    } finally {
      setDownloading("");
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-white">Download Centre</h1>
        <p className="text-xs text-gray-500 mt-0.5">
          Export board-ready executive reports and data exports from completed diagnostics
        </p>
      </div>

      {/* Format guide */}
      <div className="grid sm:grid-cols-3 gap-4">
        {[
          { label: "Executive Report", desc: "Full narrative with score breakdown, risk flags, and recommended actions", ext: "TXT" },
          { label: "Data Export", desc: "Raw metric scores, coefficient contributions, and rule trigger details", ext: "CSV" },
          { label: "Board Summary", desc: "One-page executive brief — print-ready for board distribution", ext: "TXT" },
        ].map((f) => (
          <div key={f.label} className="bg-[#0a0f1c] border border-[#1e293b] rounded-lg p-4">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-[10px] px-1.5 py-0.5 bg-amber-500/10 text-amber-400 rounded font-mono">{f.ext}</span>
              <span className="text-sm font-semibold text-white">{f.label}</span>
            </div>
            <p className="text-xs text-gray-500">{f.desc}</p>
          </div>
        ))}
      </div>

      {loading ? (
        <div className="text-gray-500 text-sm py-12 text-center">Loading sessions…</div>
      ) : sessions.length === 0 ? (
        <div className="bg-[#0a0f1c] border border-[#1e293b] rounded-lg py-16 text-center space-y-2">
          <p className="text-gray-400 text-sm font-medium">No sessions available for export</p>
          <p className="text-gray-600 text-xs">Run a diagnostic in the Workspace first, then come back here to download your reports.</p>
        </div>
      ) : (
        <div className="bg-[#0a0f1c] border border-[#1e293b] rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-gray-500 text-xs uppercase border-b border-[#1e293b]">
                <th className="text-left p-4">Session</th>
                <th className="text-left p-4">Created</th>
                <th className="text-right p-4">Downloads</th>
              </tr>
            </thead>
            <tbody>
              {sessions.map((s) => (
                <tr key={s.id} className="border-b border-[#1e293b]/50 hover:bg-white/[0.02]">
                  <td className="p-4 text-white font-medium">{s.name || "Untitled Session"}</td>
                  <td className="p-4 text-gray-500 text-xs">
                    {s.created_at ? new Date(s.created_at).toLocaleDateString() : "—"}
                  </td>
                  <td className="p-4 text-right space-x-2">
                    <button
                      onClick={() => triggerDownload(s, "pdf")}
                      disabled={downloading === `${s.id}-pdf`}
                      className="inline-block px-3 py-1 border border-amber-500/30 text-amber-400 rounded text-xs hover:bg-amber-500/10 transition-colors disabled:opacity-40 disabled:cursor-wait"
                    >
                      {downloading === `${s.id}-pdf` ? "…" : "Report"}
                    </button>
                    <button
                      onClick={() => triggerDownload(s, "csv")}
                      disabled={downloading === `${s.id}-csv`}
                      className="inline-block px-3 py-1 border border-[#1e293b] text-gray-400 rounded text-xs hover:border-gray-500 hover:text-white transition-colors disabled:opacity-40 disabled:cursor-wait"
                    >
                      {downloading === `${s.id}-csv` ? "…" : "CSV"}
                    </button>
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
