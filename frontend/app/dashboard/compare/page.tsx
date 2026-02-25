"use client";

import React, { useEffect, useState, useCallback } from "react";
import { useAuth } from "@/lib/auth";
import StateBadge from "@/components/ui/StateBadge";
import MetricBarChart from "@/components/ui/MetricBarChart";

const API = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000/api/v1";

interface SessionOption {
  id: string;
  name: string;
  state?: string;
  totalScore?: number;
  coefficients?: Array<{ name: string; contribution: number }>;
}

export default function ComparePage() {
  const { user } = useAuth();
  const [sessions, setSessions] = useState<SessionOption[]>([]);
  const [selectedA, setSelectedA] = useState("");
  const [selectedB, setSelectedB] = useState("");
  const [loading, setLoading] = useState(true);

  const fetchSessions = useCallback(async () => {
    if (!user) return;
    setLoading(true);
    try {
      const res = await fetch(`${API}/sessions?tenant_id=${user.tenantId}`);
      const data = await res.json();
      const items = (data?.data?.sessions || []) as Array<Record<string, unknown>>;

      const enriched: SessionOption[] = [];
      for (const s of items.slice(0, 20)) {
        try {
          const snapRes = await fetch(`${API}/sessions/${s.id}/snapshots`);
          const snapData = await snapRes.json();
          const latest = snapData?.data?.latest as Record<string, unknown> | undefined;
          const sb = (latest?.score_breakdown || {}) as Record<string, unknown>;
          const coeffs = (sb.coefficient_contributions || []) as Array<Record<string, unknown>>;
          enriched.push({
            id: s.id as string,
            name: (s.name as string) || "Untitled",
            state: latest?.state as string | undefined,
            totalScore: sb.total_score as number | undefined,
            coefficients: coeffs.map((c) => ({
              name: c.name as string,
              contribution: c.contribution as number,
            })),
          });
        } catch {
          enriched.push({ id: s.id as string, name: (s.name as string) || "Untitled" });
        }
      }
      setSessions(enriched);
      if (enriched.length >= 2) {
        setSelectedA(enriched[0].id);
        setSelectedB(enriched[1].id);
      }
    } catch {
      /* silent */
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => {
    fetchSessions();
  }, [fetchSessions]);

  const a = sessions.find((s) => s.id === selectedA);
  const b = sessions.find((s) => s.id === selectedB);

  // Delta chart
  const deltaData: Array<{ name: string; value: number }> = [];
  if (a?.coefficients && b?.coefficients) {
    const bMap = new Map(b.coefficients.map((c) => [c.name, c.contribution]));
    for (const ac of a.coefficients) {
      const bVal = bMap.get(ac.name) || 0;
      deltaData.push({ name: ac.name, value: Math.abs(ac.contribution - bVal) });
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-white">Scenario Comparison</h1>
        <p className="text-xs text-gray-500 mt-0.5">
          Compare two transformation sessions side-by-side
        </p>
      </div>

      {loading ? (
        <div className="text-gray-500 text-sm py-12 text-center">Loading sessions…</div>
      ) : sessions.length < 2 ? (
        <div className="text-gray-600 text-sm py-12 text-center">
          Need at least 2 sessions to compare. Run diagnostics in the Workspace first.
        </div>
      ) : (
        <>
          {/* Selectors */}
          <div className="grid md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs text-gray-500 uppercase tracking-wider mb-1.5">Session A</label>
              <select
                value={selectedA}
                onChange={(e) => setSelectedA(e.target.value)}
                className="w-full bg-[#0a0f1c] border border-[#1e293b] rounded px-3 py-2.5 text-sm text-white focus:outline-none focus:border-amber-500/50"
              >
                {sessions.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name} {s.state ? `(${s.state})` : ""}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-500 uppercase tracking-wider mb-1.5">Session B</label>
              <select
                value={selectedB}
                onChange={(e) => setSelectedB(e.target.value)}
                className="w-full bg-[#0a0f1c] border border-[#1e293b] rounded px-3 py-2.5 text-sm text-white focus:outline-none focus:border-amber-500/50"
              >
                {sessions.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name} {s.state ? `(${s.state})` : ""}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Comparison cards */}
          {a && b && (
            <div className="space-y-6">
              {/* State comparison */}
              <div className="grid md:grid-cols-2 gap-4">
                <div className="bg-[#0a0f1c] border border-[#1e293b] rounded-lg p-6 text-center">
                  <p className="text-xs text-gray-500 uppercase tracking-wider mb-3">Session A</p>
                  <p className="text-white font-semibold mb-2">{a.name}</p>
                  {a.state && <StateBadge state={a.state} size="md" />}
                  <p className="text-2xl font-bold text-amber-400 mt-3">
                    {a.totalScore?.toFixed(2) || "—"}
                  </p>
                </div>
                <div className="bg-[#0a0f1c] border border-[#1e293b] rounded-lg p-6 text-center">
                  <p className="text-xs text-gray-500 uppercase tracking-wider mb-3">Session B</p>
                  <p className="text-white font-semibold mb-2">{b.name}</p>
                  {b.state && <StateBadge state={b.state} size="md" />}
                  <p className="text-2xl font-bold text-amber-400 mt-3">
                    {b.totalScore?.toFixed(2) || "—"}
                  </p>
                </div>
              </div>

              {/* Score delta */}
              {a.totalScore != null && b.totalScore != null && (
                <div className="bg-[#0a0f1c] border border-[#1e293b] rounded-lg p-6">
                  <h3 className="text-xs text-gray-500 uppercase tracking-wider font-medium mb-2">
                    Score Delta
                  </h3>
                  <p className="text-lg font-bold">
                    <span className={a.totalScore > b.totalScore ? "text-red-400" : "text-green-400"}>
                      {a.totalScore > b.totalScore ? "+" : ""}
                      {(a.totalScore - b.totalScore).toFixed(2)}
                    </span>
                    <span className="text-xs text-gray-500 ml-2">
                      ({a.state} → {b.state})
                    </span>
                  </p>
                </div>
              )}

              {/* Metric delta chart */}
              {deltaData.length > 0 && (
                <div className="bg-[#0a0f1c] border border-[#1e293b] rounded-lg p-6">
                  <h3 className="text-xs text-gray-500 uppercase tracking-wider font-medium mb-4">
                    Metric Contribution Delta
                  </h3>
                  <MetricBarChart data={deltaData} height={220} />
                </div>
              )}

              {/* Detailed comparison table */}
              {a.coefficients && b.coefficients && (
                <div className="bg-[#0a0f1c] border border-[#1e293b] rounded-lg p-6">
                  <h3 className="text-xs text-gray-500 uppercase tracking-wider font-medium mb-4">
                    Metric-by-Metric Comparison
                  </h3>
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="text-gray-500 uppercase border-b border-[#1e293b]">
                          <th className="text-left py-2 pr-4">Metric</th>
                          <th className="text-right py-2 pr-4">Session A</th>
                          <th className="text-right py-2 pr-4">Session B</th>
                          <th className="text-right py-2">Delta</th>
                        </tr>
                      </thead>
                      <tbody>
                        {a.coefficients.map((ac) => {
                          const bVal = b.coefficients?.find((bc) => bc.name === ac.name)?.contribution || 0;
                          const delta = ac.contribution - bVal;
                          return (
                            <tr key={ac.name} className="border-b border-[#1e293b]/50">
                              <td className="py-2 pr-4 text-gray-400">{ac.name}</td>
                              <td className="py-2 pr-4 text-right font-mono text-white">
                                {ac.contribution.toFixed(2)}
                              </td>
                              <td className="py-2 pr-4 text-right font-mono text-white">
                                {bVal.toFixed(2)}
                              </td>
                              <td
                                className={`py-2 text-right font-mono ${
                                  delta > 0 ? "text-red-400" : delta < 0 ? "text-green-400" : "text-gray-500"
                                }`}
                              >
                                {delta > 0 ? "+" : ""}
                                {delta.toFixed(2)}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
