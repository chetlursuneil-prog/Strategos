"use client";

import React, { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import StateBadge from "@/components/ui/StateBadge";
import GaugeChart from "@/components/ui/GaugeChart";
import KPICard from "@/components/ui/KPICard";
import MetricBarChart from "@/components/ui/MetricBarChart";
import RadarMetricChart from "@/components/ui/RadarMetricChart";
import RiskHeatmap from "@/components/ui/RiskHeatmap";
import RoadmapTimeline from "@/components/ui/RoadmapTimeline";
import TrendLineChart from "@/components/ui/TrendLineChart";
import Link from "next/link";

const API = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000/api/v1";

const METRIC_LABELS: Record<string, string> = {
  margin: "operating margin",
  technical_debt: "technical debt",
  cost: "operating costs",
  revenue: "revenue",
  revenue_growth_yoy_pct: "revenue growth (YoY)",
  customer_churn_pct: "customer churn",
  lead_time_days: "delivery lead time",
  change_failure_rate_pct: "change failure rate",
  p1_incidents_per_month: "P1 incidents per month",
  cyber_findings_open_high: "high-severity cyber findings",
  regulatory_findings_open: "regulatory findings",
  critical_role_attrition_pct: "critical-role attrition",
  vendor_concentration_pct: "vendor concentration",
  top_customer_concentration_pct: "top-customer concentration",
  cloud_adoption_pct: "cloud adoption",
  automation_coverage_pct: "automation coverage",
  cash_conversion_cycle_days: "cash conversion cycle",
};

const PLAIN_RULE_MAP: Record<string, string> = {
  "margin < 0.12": "Operating margin is below 12%",
  "technical_debt > 65": "Technical debt is above 65%",
  "cost > (revenue * 0.82)": "Operating costs exceed 82% of revenue",
  "revenue_growth_yoy_pct < 3": "Revenue growth is below 3% YoY",
  "customer_churn_pct > 2.8": "Customer churn is above 2.8%",
  "(lead_time_days > 14) or (change_failure_rate_pct > 20)":
    "Delivery lead time exceeds 14 days or change failure rate is above 20%",
  "p1_incidents_per_month > 5": "P1 incidents exceed 5 per month",
  "(cyber_findings_open_high > 10) or (regulatory_findings_open > 5)":
    "High-severity cyber findings exceed 10 or regulatory findings exceed 5",
  "critical_role_attrition_pct > 12": "Critical-role attrition is above 12%",
  "(vendor_concentration_pct > 50) or (top_customer_concentration_pct > 40)":
    "Vendor concentration exceeds 50% or top-customer concentration exceeds 40%",
  "(cloud_adoption_pct < 40) and (automation_coverage_pct < 40)":
    "Cloud adoption is below 40% and automation coverage is below 40%",
  "cash_conversion_cycle_days > 80": "Cash conversion cycle is above 80 days",
};

function toPlainEnglishRule(expression: string): string {
  const raw = (expression || "").trim();
  if (!raw) return "Rule condition not available";

  const direct = PLAIN_RULE_MAP[raw];
  if (direct) return direct;

  let text = raw;
  for (const [metric, label] of Object.entries(METRIC_LABELS)) {
    const token = new RegExp(`\\b${metric}\\b`, "g");
    text = text.replace(token, label);
  }

  text = text
    .replace(/>=/g, " is at least ")
    .replace(/<=/g, " is at most ")
    .replace(/>/g, " is above ")
    .replace(/</g, " is below ")
    .replace(/\band\b/gi, "and")
    .replace(/\bor\b/gi, "or")
    .replace(/\s+/g, " ")
    .trim();

  if (text.length > 0) {
    return text.charAt(0).toUpperCase() + text.slice(1);
  }
  return raw;
}

function sourceToLabel(source: string): string {
  if (!source) return "Not available";
  if (source === "explicit_input") return "Provided directly by user";
  if (source === "parsed_text") return "Parsed from user text";
  if (source === "qualitative_override") return "Inferred from qualitative wording";
  if (source.startsWith("profile_default:")) {
    const profile = source.split(":")[1] || "default";
    return `Filled by ${profile} default profile`;
  }
  return source;
}

function sourceSummaryForExpression(expression: string, metricSource: Record<string, string>): string {
  const knownMetrics = new Set(Object.keys(METRIC_LABELS));
  const tokens = ((expression || "").match(/\b[a-z_][a-z0-9_]*\b/g) || [])
    .filter((token) => knownMetrics.has(token));
  const uniqueMetrics = [...new Set(tokens)];
  if (uniqueMetrics.length === 0) return "Not available";

  const labels = uniqueMetrics.map((metric) => {
    const source = metricSource[metric] || "";
    return `${METRIC_LABELS[metric]}: ${sourceToLabel(source)}`;
  });
  return labels.join(" | ");
}

export default function SessionDetailPage() {
  const params = useParams();
  const sessionId = params.id as string;
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [replayPayload, setReplayPayload] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchSession = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/sessions/${sessionId}/snapshots`);
      const json = await res.json();
      setData(json?.data || null);

      const replayRes = await fetch(`${API}/sessions/${sessionId}/replay`);
      const replayJson = await replayRes.json().catch(() => ({}));
      const events = (replayJson?.data?.events || []) as Array<Record<string, unknown>>;
      const latestEvent = events.length > 0 ? events[events.length - 1] : null;
      const payload = (latestEvent?.payload || null) as Record<string, unknown> | null;
      setReplayPayload(payload);
    } catch {
      /* silent */
      setReplayPayload(null);
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    fetchSession();
  }, [fetchSession]);

  if (loading) {
    return <div className="text-gray-500 text-sm py-12 text-center">Loading session…</div>;
  }

  if (!data || !data.latest) {
    return (
      <div className="text-gray-600 text-sm py-12 text-center">
        No snapshot data for this session.{" "}
        <Link href="/dashboard/sessions" className="text-amber-400 hover:underline">
          Back to sessions
        </Link>
      </div>
    );
  }

  const snap = data.latest as Record<string, unknown>;
  const sb = (snap.score_breakdown || {}) as Record<string, unknown>;
  const totalScore = (sb.total_score as number) || 0;
  const weightedScore = (sb.weighted_input_score as number) || 0;
  const ruleImpact = (sb.rule_impact_score as number) || 0;
  const coeffs = (sb.coefficient_contributions || []) as Array<Record<string, unknown>>;
  const contribs = (snap.contributions || []) as Array<Record<string, unknown>>;
  const restructuring = (snap.restructuring_actions || []) as Array<Record<string, unknown>>;
  const state = (snap.state as string) || "NORMAL";
  const history = (data.history || []) as Array<Record<string, unknown>>;
  const replay = replayPayload || {};
  const metricSource = ((replay.metric_source || {}) as Record<string, string>) || {};
  const assumptionProfile = (replay.assumption_profile as string) || "balanced";

  // Bar chart data
  const barData = coeffs.map((c) => ({
    name: c.name as string,
    value: Math.abs(c.contribution as number),
  }));

  // Radar chart data
  const radarData = coeffs.map((c) => ({
    metric: c.name as string,
    value: Math.abs(c.contribution as number),
    fullMark: 100,
  }));

  // Trend from version history
  const trendData = history.map((h, i) => {
    const s = (h.snapshot || {}) as Record<string, unknown>;
    const ssb = (s.score_breakdown || {}) as Record<string, unknown>;
    return { label: `v${i + 1}`, score: (ssb.total_score as number) || 0 };
  });

  // Risk heatmap
  const ruleRows = contribs.map((c) => {
    const expression = String(c.expression || "");
    const triggered = Boolean(c.result);
    return {
      expression,
      ruleText: toPlainEnglishRule(expression),
      triggered,
    };
  });
  const riskRows = ruleRows.map((r) => r.ruleText);
  const riskCells = ruleRows.map((r) => (r.triggered ? [1, 0] : [0, 1]));

  // Restructuring phases
  const phases = restructuring.map((a) => {
    const payload = (a.payload || {}) as Record<string, unknown>;
    return {
      name: (a.template_name as string) || "Action",
      owner: (payload.owner as string) || "Transformation Office",
      horizon: (payload.horizon as string) || "90 days",
      status: "pending" as const,
    };
  });

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <Link href="/dashboard/sessions" className="text-xs text-gray-500 hover:text-gray-300 transition-colors">
            ← Sessions
          </Link>
          <h1 className="text-xl font-bold text-white mt-1">Session Detail</h1>
          <p className="text-xs text-gray-500 font-mono">{sessionId}</p>
        </div>
        <StateBadge state={state} size="lg" />
      </div>

      {/* KPI row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KPICard label="Total Score" value={totalScore.toFixed(2)} color="accent-gold" />
        <KPICard label="Weighted Input" value={weightedScore.toFixed(2)} color="blue-400" />
        <KPICard label="Rule Impact" value={ruleImpact.toFixed(2)} color="amber-400" />
        <KPICard
          label="Rules Triggered"
          value={`${snap.triggered_rule_count || 0}/${snap.rule_count || 0}`}
          color={state === "CRITICAL_ZONE" ? "red-400" : "green-400"}
        />
      </div>

      {/* Charts row */}
      <div className="grid lg:grid-cols-3 gap-6">
        {/* Gauge */}
        <div className="bg-[#0a0f1c] border border-[#1e293b] rounded-lg p-6 flex flex-col items-center gap-4">
          <h3 className="text-xs text-gray-500 uppercase tracking-wider font-medium self-start">
            Modernization Intensity
          </h3>
          <GaugeChart value={totalScore} max={200} label="Composite" size={180} />
        </div>

        {/* Bar chart */}
        <div className="bg-[#0a0f1c] border border-[#1e293b] rounded-lg p-6">
          <h3 className="text-xs text-gray-500 uppercase tracking-wider font-medium mb-4">
            Metric Contributions
          </h3>
          {barData.length > 0 ? (
            <MetricBarChart data={barData} height={200} />
          ) : (
            <p className="text-gray-600 text-xs text-center py-8">No coefficient data</p>
          )}
        </div>

        {/* Radar */}
        <div className="bg-[#0a0f1c] border border-[#1e293b] rounded-lg p-6">
          <h3 className="text-xs text-gray-500 uppercase tracking-wider font-medium mb-4">
            Capability Maturity
          </h3>
          {radarData.length >= 3 ? (
            <RadarMetricChart data={radarData} height={220} />
          ) : (
            <p className="text-gray-600 text-xs text-center py-8">Need ≥3 metrics</p>
          )}
        </div>
      </div>

      {/* Second row */}
      <div className="grid lg:grid-cols-2 gap-6">
        {/* Risk heatmap */}
        <div className="bg-[#0a0f1c] border border-[#1e293b] rounded-lg p-6">
          <h3 className="text-xs text-gray-500 uppercase tracking-wider font-medium mb-4">
            Risk Heatmap
          </h3>
          {riskRows.length > 0 ? (
            <RiskHeatmap rows={riskRows} cols={["Triggered", "Not Triggered"]} cells={riskCells} rowHeaderLabel="Risk Rule" />
          ) : (
            <p className="text-gray-600 text-xs text-center py-8">No rule data</p>
          )}
        </div>

        {/* Trend */}
        <div className="bg-[#0a0f1c] border border-[#1e293b] rounded-lg p-6">
          <h3 className="text-xs text-gray-500 uppercase tracking-wider font-medium mb-4">
            Score Trend
          </h3>
          {trendData.length > 1 ? (
            <TrendLineChart data={trendData} height={200} />
          ) : (
            <p className="text-gray-600 text-xs text-center py-8">Run more versions to see trend</p>
          )}
        </div>
      </div>

      {/* Restructuring roadmap */}
      {phases.length > 0 && (
        <div className="bg-[#0a0f1c] border border-[#1e293b] rounded-lg p-6">
          <h3 className="text-xs text-gray-500 uppercase tracking-wider font-medium mb-4">
            Restructuring Roadmap
          </h3>
          <RoadmapTimeline phases={phases} />
        </div>
      )}

      {/* AI Executive Summary */}
      <div className="bg-[#0a0f1c] border border-[#1e293b] rounded-lg p-6">
        <h3 className="text-xs text-gray-500 uppercase tracking-wider font-medium mb-4">
          AI Executive Summary
        </h3>
        <div className="text-sm text-gray-300 leading-relaxed space-y-3">
          <p>
            STRATEGOS classified this enterprise as <strong className="text-white">{state}</strong> with a composite
            transformation score of <strong className="text-amber-400">{totalScore.toFixed(2)}</strong>.
          </p>
          {Number(snap.triggered_rule_count) > 0 && (
            <p>
              {String(snap.triggered_rule_count)} of {String(snap.rule_count)} diagnostic rules were triggered,
              contributing a rule impact score of {ruleImpact.toFixed(2)} to the composite.
            </p>
          )}
          {coeffs.length > 0 && (
            <p>
              Key metric drivers:{" "}
              {coeffs
                .filter((c) => (c.contribution as number) !== 0)
                .sort((a, b) => Math.abs(b.contribution as number) - Math.abs(a.contribution as number))
                .slice(0, 3)
                .map((c) => `${c.name} (${(c.contribution as number).toFixed(2)})`)
                .join(", ")}
              .
            </p>
          )}
          {phases.length > 0 && (
            <p>
              CRITICAL_ZONE triggered {phases.length} restructuring directive(s):{" "}
              {phases.map((p) => p.name).join(", ")}.
            </p>
          )}
        </div>
      </div>

      {/* Contributions detail */}
      <div className="bg-[#0a0f1c] border border-[#1e293b] rounded-lg p-6">
        <h3 className="text-xs text-gray-500 uppercase tracking-wider font-medium mb-4">
          Rule Condition Detail
        </h3>
        <div className="mb-4 rounded-lg border border-[#1e293b] bg-[#060a14] p-3">
          <p className="text-xs text-gray-300">
            Missing numeric inputs are automatically filled using the{" "}
            <span className="text-amber-400 font-semibold">{assumptionProfile}</span> assumption profile during intake.
            The source column below shows whether each metric was user-provided, parsed, inferred, or defaulted.
          </p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-gray-500 uppercase border-b border-[#1e293b]">
                <th className="text-left py-2 pr-4">Rule Triggered</th>
                <th className="text-left py-2 pr-4">Result</th>
                <th className="text-left py-2 pr-4">Source</th>
                <th className="text-left py-2">Error</th>
              </tr>
            </thead>
            <tbody>
              {contribs.map((c, i) => (
                <tr key={i} className="border-b border-[#1e293b]/50">
                  <td className="py-2 pr-4 text-gray-300">{toPlainEnglishRule(String(c.expression || ""))}</td>
                  <td className="py-2 pr-4">
                    <span className={c.result ? "text-red-400" : "text-green-400"}>
                      {c.result ? "TRIGGERED" : "OK"}
                    </span>
                  </td>
                  <td className="py-2 pr-4 text-gray-400">{sourceSummaryForExpression(String(c.expression || ""), metricSource)}</td>
                  <td className="py-2 text-gray-600">{(c.error as string) || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Actions */}
      <div className="flex gap-3 flex-wrap">
        <a
          href={`${API}/reports/${sessionId}?format=pdf`}
          target="_blank"
          rel="noopener noreferrer"
          className="px-4 py-2 bg-amber-500/90 text-[#060a14] font-semibold rounded text-xs hover:bg-amber-500 transition-colors"
        >
          Download PDF Report
        </a>
        <a
          href={`${API}/reports/${sessionId}?format=csv`}
          target="_blank"
          rel="noopener noreferrer"
          className="px-4 py-2 border border-[#1e293b] text-gray-400 rounded text-xs hover:border-gray-500 hover:text-white transition-colors"
        >
          Export CSV
        </a>
        <Link
          href="/dashboard/compare"
          className="px-4 py-2 border border-[#1e293b] text-gray-400 rounded text-xs hover:border-gray-500 hover:text-white transition-colors"
        >
          Compare Sessions
        </Link>
      </div>
    </div>
  );
}
