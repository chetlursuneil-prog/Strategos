"use client";

import React, { useEffect, useState, useCallback } from "react";
import { useAuth } from "@/lib/auth";
import GaugeChart from "@/components/ui/GaugeChart";
import TrendLineChart from "@/components/ui/TrendLineChart";
import Link from "next/link";

const API = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000/api/v1";

/* ─── Plain-English state descriptions ──────────────────────────────── */
const STATE_INFO: Record<string, { label: string; color: string; dot: string; headline: string; detail: string }> = {
  CRITICAL_ZONE: {
    label: "Critical",
    color: "text-red-400",
    dot: "bg-red-400",
    headline: "Your business is in a critical zone and needs immediate executive attention.",
    detail:
      "Multiple risk thresholds have been exceeded at the same time. The combination of cost pressures, margin compression, and high technical debt is creating compounding risk. Without intervention, performance is likely to deteriorate further.",
  },
  ELEVATED_RISK: {
    label: "Elevated Risk",
    color: "text-amber-400",
    dot: "bg-amber-400",
    headline: "The business is under pressure — not a crisis yet, but action is needed soon.",
    detail:
      "Some risk indicators have been triggered. The business is operating in a vulnerable zone where a few more adverse developments could quickly escalate. Addressing the key pressure points in the next 30–90 days is strongly advisable.",
  },
  NORMAL: {
    label: "Healthy",
    color: "text-green-400",
    dot: "bg-green-400",
    headline: "The business is operating within healthy parameters.",
    detail:
      "No risk thresholds have been breached. The core metrics are balanced and there is headroom for investment in growth and capability building. The focus should be on maintaining this position and locking in structural advantages.",
  },
};

export default function DashboardHome() {
  const { user } = useAuth();
  const [sessions, setSessions] = useState<Array<Record<string, unknown>>>([]);
  const [latestSnapshot, setLatestSnapshot] = useState<Record<string, unknown> | null>(null);
  const [latestBoardInsights, setLatestBoardInsights] = useState<Array<Record<string, unknown>>>([]);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    if (!user) return;
    setLoading(true);
    try {
      const sessRes = await fetch(`${API}/sessions?tenant_id=${user.tenantId}`).then((r) =>
        r.ok ? r.json() : { data: { sessions: [] } }
      );
      const sessItems: Array<Record<string, unknown>> = sessRes?.data?.sessions || [];
      setSessions(sessItems);

      if (sessItems.length > 0) {
        const latestId = sessItems[0].id as string;
        try {
          const snapRes = await fetch(`${API}/sessions/${latestId}/snapshots`);
          const snapData = await snapRes.json();
          setLatestSnapshot(snapData?.data?.latest || null);

          const insightRes = await fetch(`${API}/advisory/skills/board_insights/${latestId}`);
          if (insightRes.ok) {
            const insightData = await insightRes.json();
            setLatestBoardInsights((insightData?.data?.insights || []) as Array<Record<string, unknown>>);
          } else {
            setLatestBoardInsights([]);
          }
        } catch {
          setLatestBoardInsights([]);
        }
      }
    } catch {
      /* silent */
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const state = (latestSnapshot?.state as string) || "NORMAL";
  const totalScore = ((latestSnapshot?.score_breakdown as Record<string, unknown>)?.total_score as number) || 0;
  const ruleCount = (latestSnapshot?.rule_count as number) || 0;
  const triggeredCount = (latestSnapshot?.triggered_rule_count as number) || 0;
  const stateInfo = STATE_INFO[state] || STATE_INFO.NORMAL;

  const scoreLabel =
    totalScore === 0 ? "no data yet"
    : totalScore < 40 ? "very low — the business is in excellent shape"
    : totalScore < 70 ? "moderate — healthy with some areas to watch"
    : totalScore < 100 ? "elevated — proactive action is advisable"
    : totalScore < 140 ? "high — significant transformation pressure"
    : "very high — urgent restructuring required";

  const trendData = sessions
    .slice(0, 8)
    .reverse()
    .map((s, i) => ({
      label: `S${i + 1}`,
      score: (s.total_score as number) || totalScore,
    }));

  const latestSession = sessions[0];

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white">Enterprise Overview</h1>
        <p className="text-sm text-gray-500 mt-1">
          Welcome back, {user?.name}. Here is where your enterprise stands right now.
        </p>
      </div>

      {loading ? (
        <div className="text-gray-500 text-sm py-16 text-center">Loading your enterprise data…</div>
      ) : sessions.length === 0 ? (
        /* ── No data yet ── */
        <div className="bg-[#0a0f1c] border border-[#1e293b] rounded-xl p-10 text-center space-y-4">
          <p className="text-white text-lg font-semibold">No diagnostics run yet</p>
          <p className="text-gray-400 text-sm max-w-md mx-auto leading-relaxed">
            To see your enterprise health dashboard, start by running a diagnostic. Just describe your
            company in plain English — revenue, costs, margins, and technical debt — and STRATEGOS will
            do the rest.
          </p>
          <Link
            href="/dashboard/workspace"
            className="inline-block mt-2 px-6 py-3 bg-amber-500/90 text-[#060a14] font-semibold rounded-xl text-sm hover:bg-amber-500 transition-colors"
          >
            Run your first diagnostic →
          </Link>
        </div>
      ) : (
        <>
          {/* ── Health summary narrative ── */}
          <div className={`rounded-xl border p-6 ${
            state === "CRITICAL_ZONE" ? "bg-red-950/20 border-red-800/40"
            : state === "ELEVATED_RISK" ? "bg-amber-950/20 border-amber-800/40"
            : "bg-green-950/20 border-green-800/40"
          }`}>
            <div className="flex items-center gap-3 mb-3">
              <span className={`w-2.5 h-2.5 rounded-full ${stateInfo.dot} flex-shrink-0`} />
              <span className={`text-base font-bold ${stateInfo.color}`}>{stateInfo.headline}</span>
            </div>
            <p className="text-sm text-gray-300 leading-relaxed">{stateInfo.detail}</p>
            {latestSession && (
              <p className="text-xs text-gray-500 mt-3">
                Based on your most recent diagnostic
                {latestSession.created_at ? ` on ${new Date(latestSession.created_at as string).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" })}` : ""}.
                {" "}<Link href="/dashboard/workspace" className="text-amber-400 hover:underline">Run a new diagnostic →</Link>
              </p>
            )}
          </div>

          {/* ── Four key metrics ── */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* Status */}
            <div className="bg-[#0a0f1c] border border-[#1e293b] rounded-xl p-5">
              <p className="text-[10px] text-gray-500 uppercase tracking-wider font-medium">Overall Status</p>
              <p className={`text-xl font-bold mt-2 ${stateInfo.color}`}>{stateInfo.label}</p>
              <p className="text-xs text-gray-500 mt-1 leading-relaxed">
                {state === "CRITICAL_ZONE" ? "Immediate action required"
                  : state === "ELEVATED_RISK" ? "Proactive intervention needed"
                  : "No immediate concerns"}
              </p>
            </div>

            {/* Score */}
            <div className="bg-[#0a0f1c] border border-[#1e293b] rounded-xl p-5">
              <p className="text-[10px] text-gray-500 uppercase tracking-wider font-medium">Transformation Score</p>
              <p className="text-xl font-bold text-amber-400 mt-2">{totalScore > 0 ? totalScore.toFixed(0) : "—"} <span className="text-sm text-gray-500 font-normal">/ 200</span></p>
              <p className="text-xs text-gray-500 mt-1 leading-relaxed capitalize">{scoreLabel}</p>
            </div>

            {/* Rules */}
            <div className="bg-[#0a0f1c] border border-[#1e293b] rounded-xl p-5">
              <p className="text-[10px] text-gray-500 uppercase tracking-wider font-medium">Risk Signals</p>
              <p className={`text-xl font-bold mt-2 ${triggeredCount > 0 ? "text-amber-400" : "text-green-400"}`}>
                {triggeredCount} <span className="text-sm text-gray-500 font-normal">of {ruleCount}</span>
              </p>
              <p className="text-xs text-gray-500 mt-1 leading-relaxed">
                {triggeredCount === 0
                  ? "All risk rules clear"
                  : triggeredCount === 1
                  ? "One risk threshold breached"
                  : `${triggeredCount} risk thresholds breached`}
              </p>
            </div>

            {/* Sessions */}
            <div className="bg-[#0a0f1c] border border-[#1e293b] rounded-xl p-5">
              <p className="text-[10px] text-gray-500 uppercase tracking-wider font-medium">Diagnostics Run</p>
              <p className="text-xl font-bold text-white mt-2">{sessions.length}</p>
              <p className="text-xs text-gray-500 mt-1 leading-relaxed">
                {sessions.length === 1 ? "1 session on record" : `${sessions.length} sessions on record`}
              </p>
            </div>
          </div>

          {/* ── Gauge + explanation ── */}
          <div className="grid lg:grid-cols-3 gap-6">
            <div className="bg-[#0a0f1c] border border-[#1e293b] rounded-xl p-6 flex flex-col items-center gap-3">
              <p className="text-xs text-gray-500 uppercase tracking-wider font-medium self-start">
                Transformation Intensity
              </p>
              <GaugeChart value={totalScore} max={200} label="Score" size={170} />
              <p className="text-xs text-gray-400 text-center leading-relaxed">
                This gauge measures the overall pressure on the business to transform. The higher the score, the more urgent the need for structural change.
              </p>
              <p className="text-[10px] text-gray-500 text-center">
                Below 70 = manageable · 70–120 = action needed · Above 120 = urgent
              </p>
            </div>

            {/* Trend */}
            <div className="lg:col-span-2 bg-[#0a0f1c] border border-[#1e293b] rounded-xl p-6">
              <p className="text-xs text-gray-500 uppercase tracking-wider font-medium mb-1">Score Trend</p>
              <p className="text-sm text-gray-400 mb-4 leading-relaxed">
                This chart shows how the transformation score has moved across your last {trendData.length} diagnostic session{trendData.length !== 1 ? "s" : ""}.
                A rising trend means pressure is increasing — a falling trend means your improvement initiatives are working.
              </p>
              {trendData.length > 1 ? (
                <TrendLineChart data={trendData} height={180} />
              ) : (
                <div className="text-gray-600 text-sm text-center py-10">
                  Run more sessions in the{" "}
                  <Link href="/dashboard/workspace" className="text-amber-400 hover:underline">Workspace</Link>{" "}
                  to see how your score changes over time.
                </div>
              )}
            </div>
          </div>

          {latestBoardInsights.length > 0 && (
            <div className="bg-[#0a0f1c] border border-[#1e293b] rounded-xl p-6">
              <p className="text-xs text-gray-500 uppercase tracking-wider font-medium">OpenClaw Agent Insights</p>
              <p className="text-sm text-gray-400 mt-2 mb-4 leading-relaxed">
                Strategy, risk, architecture, and financial agent perspectives for your latest session.
              </p>
              <div className="grid md:grid-cols-2 gap-3">
                {latestBoardInsights.map((ins, idx) => (
                  <div key={idx} className="bg-[#060a14] border border-[#1e293b] rounded-lg p-4">
                    <p className="text-xs text-amber-400 font-medium">{String(ins.agent_id || "agent").replace(/_/g, " ")}</p>
                    <p className="text-[11px] text-gray-500 mt-0.5">{String(ins.role || "")}</p>
                    <p className="text-sm text-gray-300 mt-2 leading-relaxed">{String(ins.insight || "")}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* ── Recent sessions ── */}
          <div className="bg-[#0a0f1c] border border-[#1e293b] rounded-xl p-6">
            <div className="flex items-center justify-between mb-1">
              <p className="text-xs text-gray-500 uppercase tracking-wider font-medium">Recent Diagnostic Sessions</p>
              <Link href="/dashboard/sessions" className="text-xs text-amber-400 hover:underline">View all →</Link>
            </div>
            <p className="text-sm text-gray-400 mb-4 leading-relaxed">
              Each row below represents a diagnostic you have run. Click on any session to see the full breakdown of what was found and what was recommended.
            </p>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-gray-500 text-xs uppercase border-b border-[#1e293b]">
                    <th className="text-left py-2 pr-4">Session name</th>
                    <th className="text-left py-2 pr-4">Date</th>
                    <th className="text-left py-2">Outcome</th>
                  </tr>
                </thead>
                <tbody>
                  {sessions.slice(0, 5).map((s) => {
                    const sState = s.state as string | undefined;
                    const sInfo = STATE_INFO[sState || "NORMAL"] || STATE_INFO.NORMAL;
                    return (
                      <tr key={s.id as string} className="border-b border-[#1e293b]/50 hover:bg-white/[0.02] transition-colors">
                        <td className="py-3 pr-4">
                          <Link href={`/dashboard/sessions/${s.id}`} className="text-white hover:text-amber-400 transition-colors">
                            {(s.name as string) || "Untitled Session"}
                          </Link>
                        </td>
                        <td className="py-3 pr-4 text-gray-500 text-xs">
                          {s.created_at ? new Date(s.created_at as string).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" }) : "—"}
                        </td>
                        <td className="py-3">
                          <span className={`text-xs font-medium ${sInfo.color}`}>{sInfo.label}</span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* ── Quick actions with descriptions ── */}
          <div className="grid sm:grid-cols-3 gap-4">
            <Link href="/dashboard/workspace" className="bg-[#0a0f1c] border border-[#1e293b] rounded-xl p-5 hover:border-amber-500/30 transition-colors group">
              <p className="text-sm font-semibold text-white group-hover:text-amber-400 transition-colors">Run a New Diagnostic</p>
              <p className="text-sm text-gray-500 mt-2 leading-relaxed">Describe your company in plain language and get a full analysis in minutes — no forms, no spreadsheets.</p>
            </Link>
            <Link href="/dashboard/compare" className="bg-[#0a0f1c] border border-[#1e293b] rounded-xl p-5 hover:border-amber-500/30 transition-colors group">
              <p className="text-sm font-semibold text-white group-hover:text-amber-400 transition-colors">Compare Scenarios</p>
              <p className="text-sm text-gray-500 mt-2 leading-relaxed">See two different situations side-by-side — useful for evaluating "what if we did X instead of Y".</p>
            </Link>
            <Link href="/dashboard/downloads" className="bg-[#0a0f1c] border border-[#1e293b] rounded-xl p-5 hover:border-amber-500/30 transition-colors group">
              <p className="text-sm font-semibold text-white group-hover:text-amber-400 transition-colors">Download a Report</p>
              <p className="text-sm text-gray-500 mt-2 leading-relaxed">Export a board-ready executive summary or raw data from any diagnostic session.</p>
            </Link>
          </div>
        </>
      )}
    </div>
  );
}

