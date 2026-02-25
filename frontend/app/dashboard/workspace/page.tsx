"use client";

import React, { useState, useRef, useEffect } from "react";
import { useAuth } from "@/lib/auth";
import GaugeChart from "@/components/ui/GaugeChart";
import MetricBarChart from "@/components/ui/MetricBarChart";
import RoadmapTimeline from "@/components/ui/RoadmapTimeline";
import Link from "next/link";

const API = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000/api/v1";

/* ─── Types ─────────────────────────────────────────────────────────── */
type Phase = "intro" | "gathering" | "confirming" | "analyzing" | "results" | "followup";

interface CollectedData {
  companyContext?: string;
  revenue?: number;
  cost?: number;
  margin?: number;
  technicalDebt?: number;
}

interface SnapshotType {
  state: string;
  rule_count: number;
  triggered_rule_count: number;
  score_breakdown: {
    total_score: number;
    coefficient_contributions: Array<{ name: string; contribution: number; mode: string }>;
  };
  restructuring_actions: Array<{
    template_name: string;
    payload: { owner?: string; horizon_days?: number };
  }>;
}

interface AnalysisResult {
  session_id: string;
  extracted_input: Record<string, number>;
  snapshot: SnapshotType;
  openclaw_insights?: Array<{
    agent_id: string;
    role: string;
    insight: string;
  }>;
}

interface AdvisorySkillsState {
  state?: string;
  total_score?: number;
}

interface AdvisorySkillsContrib {
  expression?: string;
  result?: boolean;
}

interface AdvisorySkillsRestructuring {
  template_name?: string;
  payload?: { owner?: string; horizon_days?: number };
}

interface Message {
  role: "advisor" | "user";
  text: string;
  result?: AnalysisResult;
  collectedData?: CollectedData;
}

type DataField = keyof Omit<CollectedData, "companyContext">;

/* ─── Extraction helper ─────────────────────────────────────────────── */
function parseMagnitude(num: string, unit: string): number {
  const v = parseFloat(num);
  const u = (unit || "").toLowerCase();
  if (u === "bn" || u === "billion" || u === "b") return v * 1000;
  return v; // already in millions
}

function extractFromText(text: string, standaloneTargetField?: DataField): Partial<CollectedData> {
  const t = text.toLowerCase().replace(/,/g, "");
  const out: Partial<CollectedData> = {};

  // ── Revenue: only extract when revenue context is present ──
  // Patterns that require explicit revenue context first
  const revContextPatterns = [
    /revenue[^\d$]*\$?\s*(\d+(?:\.\d+)?)\s*(m|million|bn|billion|b)?/i,
    /\$\s*(\d+(?:\.\d+)?)\s*(m|million|bn|billion|b)?\s*(?:in\s+)?revenue/i,
    /(\d+(?:\.\d+)?)\s*(m|million|bn|billion|b)?\s*(?:in\s+)?(?:revenue|turnover|sales)/i,
  ];
  for (const p of revContextPatterns) {
    const m = t.match(p);
    if (m) { out.revenue = parseMagnitude(m[1], m[2] || ""); break; }
  }

  // ── Cost: only extract when cost context is present ──
  const costContextPatterns = [
    /(?:operating\s+)?costs?\s+(?:at|of|around|is|are)\s+\$?\s*(\d+(?:\.\d+)?)\s*(m|million|bn|billion|b)?/i,
    /\$?\s*(\d+(?:\.\d+)?)\s*(m|million|bn|billion|b)?\s*(?:in\s+)?(?:operating\s+)?costs?/i,
    /(?:expenses?|opex|expenditure)\s+(?:of|at|around|is)?\s*\$?\s*(\d+(?:\.\d+)?)\s*(m|million|bn|billion|b)?/i,
    /\$?\s*(\d+(?:\.\d+)?)\s*(m|million|bn|billion|b)\s+(?:in\s+)?(?:costs?|opex|expenses?)/i,
  ];
  for (const p of costContextPatterns) {
    const m = t.match(p);
    if (m) { out.cost = parseMagnitude(m[1], m[2] || ""); break; }
  }

  // ── Standalone compact number (e.g. "1bn", "$800m")
  // By default assign to revenue; if a field was explicitly asked, bind to that field.
  if (out.revenue === undefined && out.cost === undefined) {
    const standaloneM = t.match(/^\s*\$?\s*(\d+(?:\.\d+)?)\s*(m|million|bn|billion|b)\s*$/i);
    if (standaloneM) {
      const value = parseMagnitude(standaloneM[1], standaloneM[2]);
      if (standaloneTargetField === "cost") out.cost = value;
      else out.revenue = value;
    }
  }

  // ── Margin: accept "23%", "23 percent", or bare number 0–100 with % context ──
  const marginPatterns = [
    /margin\s*(?:at|of|around|is|:)?\s*(\d+(?:\.\d+)?)\s*%?/i,
    /(\d+(?:\.\d+)?)\s*%\s*(?:operating\s+)?margin/i,
    /(\d+(?:\.\d+)?)\s*(?:%|percent)\s*(?:margin)?/i,
  ];
  for (const p of marginPatterns) {
    const m = t.match(p);
    if (m) {
      const v = parseFloat(m[1]);
      if (v >= 0 && v <= 100) { out.margin = v; break; }
    }
  }

  // ── Technical debt: numeric ──
  const debtPatterns = [
    /(?:technical\s+)?debt\s*(?:at|of|around|is|:)?\s*(\d+(?:\.\d+)?)\s*%?/i,
    /(\d+(?:\.\d+)?)\s*%\s*(?:technical\s+)?debt/i,
  ];
  for (const p of debtPatterns) {
    const m = t.match(p);
    if (m) { out.technicalDebt = parseFloat(m[1]); break; }
  }

  // ── Technical debt keyword fallback ──
  if (out.technicalDebt === undefined) {
    if (/very\s+high\s+(?:technical\s+)?debt|extremely\s+high\s+debt|huge\s+(?:technical\s+)?debt/.test(t)) out.technicalDebt = 92;
    else if (/high\s+(?:technical\s+)?debt|significant\s+(?:technical\s+)?debt|heavy\s+(?:technical\s+)?debt/.test(t)) out.technicalDebt = 78;
    else if (/moderate\s+(?:technical\s+)?debt|medium\s+(?:technical\s+)?debt|some\s+(?:technical\s+)?debt/.test(t)) out.technicalDebt = 50;
    else if (/low\s+(?:technical\s+)?debt|minimal\s+(?:technical\s+)?debt|little\s+(?:technical\s+)?debt|clean\s+stack/.test(t)) out.technicalDebt = 20;
  }

  return out;
}

/**
 * Infer soft context clues from descriptive first message.
 * Returns partial data that can seed the collected state.
 */
function inferFromContext(text: string): Partial<CollectedData> {
  const t = text.toLowerCase();
  const out: Partial<CollectedData> = {};

  // Margin inference from profit language
  if (/no\s+profit|loss[- ]making|at\s+a\s+loss|zero\s+margin|break.?even/.test(t)) out.margin = 2;
  else if (/thin\s+margin|wafer.thin|very\s+low\s+margin|barely\s+profit/.test(t)) out.margin = 5;
  else if (/low\s+margin|small\s+margin/.test(t)) out.margin = 8;
  else if (/healthy\s+margin|strong\s+margin|high\s+margin|good\s+margin/.test(t)) out.margin = 28;

  // Technical debt from language
  if (/huge\s+tech\s+debt|massive\s+tech\s+debt|legacy\s+(?:stack|systems?)|old\s+(?:infrastructure|system)|heavily\s+(?:outdated|legacy)/.test(t)) out.technicalDebt = 88;
  else if (/significant\s+tech\s+debt|high\s+tech\s+debt|lots\s+of\s+tech\s+debt/.test(t)) out.technicalDebt = 72;
  else if (/some\s+tech\s+debt|moderate\s+tech\s+debt/.test(t)) out.technicalDebt = 48;
  else if (/modern\s+stack|cloud.native|clean\s+(?:code|stack)|minimal\s+(?:debt|legacy)/.test(t)) out.technicalDebt = 18;

  // Cost pressure from language
  if (/huge\s+opex|massive\s+opex|very\s+high\s+costs?|enormous\s+costs?|bloated\s+costs?|high\s+opex/.test(t)) {
    // Flag high cost — will be used to ask more targeted question
    (out as Record<string, unknown>).__highCost = true;
  }

  return out;
}

/**
 * Apply a bare numeric answer to the first missing field, or to `targetField` if specified.
 */
function applyBareNumber(value: number, d: CollectedData, targetField?: string): Partial<CollectedData> {
  const field = targetField || getMissingFields(d)[0];
  if (!field) return {};
  if (field === "revenue") return { revenue: value < 10 ? value * 1000 : value }; // e.g. "1" → 1000M, "800" → 800M
  if (field === "cost") return { cost: value < 10 ? value * 1000 : value };
  if (field === "margin") return { margin: value };
  if (field === "technicalDebt") return { technicalDebt: value };
  return {};
}

function getMissingFields(d: CollectedData): Array<keyof Omit<CollectedData, "companyContext">> {
  const fields: Array<keyof Omit<CollectedData, "companyContext">> = ["revenue", "cost", "margin", "technicalDebt"];
  return fields.filter((f) => d[f] === undefined);
}

// Keep old name for compatibility
const getMissing = getMissingFields;

function applyFieldHintFromText(text: string, targetField?: string): Partial<CollectedData> {
  if (!targetField) return {};
  const t = text.toLowerCase().trim();

  if (targetField === "technicalDebt") {
    if (/very\s+high|extremely\s+high|huge|massive/.test(t)) return { technicalDebt: 90 };
    if (/high|significant|heavy/.test(t)) return { technicalDebt: 75 };
    if (/moderate|medium|some/.test(t)) return { technicalDebt: 50 };
    if (/low|minimal|little/.test(t)) return { technicalDebt: 20 };
  }

  if (targetField === "margin" || targetField === "technicalDebt") {
    const numeric = t.match(/(\d+(?:\.\d+)?)/);
    if (numeric) {
      const value = parseFloat(numeric[1]);
      if (!Number.isNaN(value) && value >= 0 && value <= 100) {
        return targetField === "margin" ? { margin: value } : { technicalDebt: value };
      }
    }
  }

  if (targetField === "revenue" || targetField === "cost") {
    const compact = t.match(/^\$?\s*(\d+(?:\.\d+)?)\s*(m|million|bn|billion|b)\s*$/i);
    if (compact) {
      const value = parseMagnitude(compact[1], compact[2]);
      return targetField === "revenue" ? { revenue: value } : { cost: value };
    }
  }

  return {};
}

function askForField(field: string, d: CollectedData): string {
  const hasAny = d.revenue !== undefined || d.cost !== undefined || d.margin !== undefined || d.technicalDebt !== undefined;
  const prefix = hasAny ? "Got it. " : "";
  switch (field) {
    case "revenue":
      return `${prefix}What is the company's annual revenue? A rough figure is fine — for example "1bn", "800 million", or "$1.5B".`;
    case "cost":
      return `${prefix}What are the total annual operating costs? Just a rough figure — e.g. "700m" or "$1.2bn".`;
    case "margin":
      return `${prefix}What is the operating margin — the percentage of revenue left after costs? For example: "18" or "roughly 22%".`;
    case "technicalDebt":
      return `${prefix}How significant is the technical debt? A rough percentage is fine, or just say "very high", "moderate", or "low".`;
    default:
      return `${prefix}Could you give me a bit more detail on the ${field}?`;
  }
}

function formatCurrency(val: number): string {
  if (val >= 1000) return `$${(val / 1000).toFixed(1)}B`;
  return `$${val}M`;
}

/* ─── Inline analysis narrative with charts ──────────────────────────── */
function AnalysisNarrative({ result }: { result: AnalysisResult }) {
  const snap = result.snapshot;
  const engineInput = result.extracted_input || {};
  const openclawInsights = result.openclaw_insights || [];
  const state = snap.state;
  const sb = snap.score_breakdown || { total_score: 0, coefficient_contributions: [] };
  const totalScore = sb.total_score || 0;
  const triggered = snap.triggered_rule_count || 0;
  const ruleCount = snap.rule_count || 0;
  const actions = snap.restructuring_actions || [];
  const coeffs = sb.coefficient_contributions || [];

  const stateMap: Record<string, { label: string; color: string; border: string; bg: string; summary: string; urgency: string }> = {
    CRITICAL_ZONE: {
      label: "Critical — Immediate Executive Action Required",
      color: "text-red-400",
      border: "border-red-800/40",
      bg: "bg-red-950/30",
      summary: "Multiple risk thresholds have been breached at the same time. This is not a single problem — it is a compounding set of pressures that, if left unaddressed, will accelerate deterioration.",
      urgency: "This situation requires a CEO/CFO-level response now, not in the next quarter.",
    },
    ELEVATED_RISK: {
      label: "Elevated Risk — Proactive Intervention Recommended",
      color: "text-amber-400",
      border: "border-amber-800/40",
      bg: "bg-amber-950/30",
      summary: "Some warning signals have been triggered. The business is not in crisis, but it is operating in a vulnerable zone where a few adverse developments could quickly tip into critical territory.",
      urgency: "A targeted action plan within the next 30–90 days is strongly advisable.",
    },
    NORMAL: {
      label: "Healthy — Maintain Momentum and Optimise",
      color: "text-green-400",
      border: "border-green-800/40",
      bg: "bg-green-950/30",
      summary: "The core metrics are within healthy parameters. There are no immediate transformation emergencies, and the business has the headroom to invest in future growth and capability building.",
      urgency: "Focus on continuous improvement and locking in structural advantages.",
    },
  };

  const info = stateMap[state] || stateMap.NORMAL;

  const scoreLabel =
    totalScore < 40 ? "low" : totalScore < 70 ? "moderate" : totalScore < 100 ? "elevated" : totalScore < 140 ? "high" : "very high";

  // Build bar chart data with readable labels
  const barData = coeffs.map((c) => ({
    name: c.name.replace(/_/g, " ").replace(/\b\w/g, (l) => l.toUpperCase()),
    value: Math.abs(c.contribution || 0),
    positive: (c.contribution || 0) >= 0,
  }));

  // Plain-English contribution explanations
  const contribText = coeffs.map((c) => {
    const val = c.contribution || 0;
    const absVal = Math.abs(val);
    const impact = absVal > 50 ? "very strongly" : absVal > 25 ? "significantly" : absVal > 10 ? "moderately" : "slightly";
    if (c.name === "revenue") {
      return val > 30
        ? `Revenue is a positive driver — the scale of the business provides a solid foundation, contributing ${val.toFixed(0)} points to the overall score.`
        : `Revenue is contributing positively (+${val.toFixed(0)}), though there is room to grow this further.`;
    }
    if (c.name === "cost") {
      return val < 0
        ? `Operating costs are the biggest headwind — they are dragging the score down ${impact} (${val.toFixed(0)} points). Reducing costs would have an immediate knock-on improvement.`
        : `Cost levels are within range and contributing a small positive (+${val.toFixed(0)}).`;
    }
    if (c.name === "margin") {
      return val < 5
        ? `Margins are wafer-thin, contributing almost nothing (+${val.toFixed(2)}). This means the business has almost no buffer to absorb unexpected shocks.`
        : `Margins are contributing ${impact} to the score (+${val.toFixed(2)}), reflecting a reasonable level of profitability.`;
    }
    if (c.name === "composite_stress") {
      return val > 30
        ? `The combined stress from costs and technical debt is compounding the risk ${impact} — adding ${val.toFixed(0)} points of pressure. These two factors together are amplifying each other's impact.`
        : `The composite stress indicator is at a manageable level (${val.toFixed(0)} points), suggesting costs and technical debt are not yet spiralling together.`;
    }
    return `${c.name.replace(/_/g, " ")} is contributing ${val > 0 ? "+" : ""}${val.toFixed(0)} points to the overall score.`;
  });

  // Action explanations
  const actionItems = actions.map((a) => {
    const p = a.payload || {};
    const horizon = p.horizon_days ? `${p.horizon_days} days` : "90 days";
    const owner = p.owner || "Executive Team";
    const name = a.template_name || "";
    if (name.includes("portfolio")) {
      return { title: "Portfolio Rationalisation", owner, horizon, description: "Review and streamline the product and service portfolio. Identify which offerings consume resources without adequate return, and consider consolidating or retiring underperformers. This frees up capital and management attention for the areas that matter most." };
    }
    if (name.includes("cost")) {
      return { title: "Cost Containment Programme", owner, horizon, description: "Implement a structured cost reduction initiative led by the CFO. Map the largest cost drivers, set efficiency targets — a 10–15% reduction in operating costs would meaningfully improve margins and reduce risk exposure." };
    }
    if (/modern/.test(name)) {
      return { title: "Technology Modernisation", owner, horizon, description: "Launch a phased programme to reduce technical debt. Start with the legacy systems causing the most operational friction. Reducing technical debt will lower maintenance overhead and unlock the ability to move faster." };
    }
    return { title: name.replace(/_/g, " ").replace(/\b\w/g, (l) => l.toUpperCase()), owner, horizon, description: "Execute the recommended transformation initiative with cross-functional leadership and clear accountability." };
  });

  const roadmapPhases = actionItems.map((a) => ({
    name: a.title,
    owner: a.owner,
    horizon: a.horizon,
    status: "pending" as const,
  }));

  return (
    <div className="space-y-7 mt-3">
      {/* Overall state verdict */}
      <div className={`rounded-xl border p-5 ${info.bg} ${info.border}`}>
        <p className={`text-sm font-semibold ${info.color}`}>{info.label}</p>
        <p className="text-sm text-gray-300 mt-2 leading-relaxed">{info.summary}</p>
        <p className={`text-sm font-medium mt-3 ${info.color}`}>{info.urgency}</p>
      </div>

      {/* Engine input transparency */}
      <div className="rounded-xl border border-[#1e293b] bg-[#060a14] p-4">
        <p className="text-sm font-semibold text-white">Input used by STRATEGOS engine</p>
        <p className="text-xs text-gray-500 mt-1">These are the final normalized values processed by the deterministic run.</p>
        <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-2 text-sm text-gray-300">
          <p>• Revenue: {typeof engineInput.revenue === "number" ? formatCurrency(engineInput.revenue) : "n/a"}</p>
          <p>• Operating costs: {typeof engineInput.cost === "number" ? formatCurrency(engineInput.cost) : "n/a"}</p>
          <p>• Margin: {typeof engineInput.margin === "number" ? `${(engineInput.margin <= 1 ? engineInput.margin * 100 : engineInput.margin).toFixed(2)}%` : "n/a"}</p>
          <p>• Technical debt: {typeof engineInput.technical_debt === "number" ? `${engineInput.technical_debt.toFixed(2)}%` : "n/a"}</p>
        </div>
      </div>

      {/* OpenClaw multi-agent insights */}
      {openclawInsights.length > 0 && (
        <div className="rounded-xl border border-[#1e293b] bg-[#060a14] p-4">
          <p className="text-sm font-semibold text-white">OpenClaw Advisory Agents</p>
          <p className="text-xs text-gray-500 mt-1">Insights from strategy, risk, architecture, financial, and synthesis agents.</p>
          <div className="mt-3 space-y-2">
            {openclawInsights.map((insight, idx) => (
              <div key={`${insight.agent_id}-${idx}`} className="border border-[#1e293b] rounded-lg p-3">
                <p className="text-xs text-amber-400 font-medium">{insight.agent_id.replace(/_/g, " ")}</p>
                <p className="text-[11px] text-gray-500 mt-0.5">{insight.role}</p>
                <p className="text-sm text-gray-300 mt-1">{insight.insight}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Score + gauge */}
      <div>
        <p className="text-sm text-gray-300 leading-relaxed">
          The overall <strong className="text-white">Transformation Intensity Score</strong> is{" "}
          <span className={`font-bold text-base ${info.color}`}>{totalScore.toFixed(0)}</span> out of 200 —
          which represents a <strong className="text-white">{scoreLabel}</strong> level of transformation pressure.
          The gauge below shows where this sits on the spectrum.
        </p>
        <div className="mt-4 flex justify-center">
          <GaugeChart value={totalScore} max={200} label="Transformation Intensity" size={160} />
        </div>
        <p className="text-[11px] text-gray-500 text-center mt-2">
          Scores below 70 = manageable · 70–120 = action required · above 120 = urgent restructuring needed
        </p>
      </div>

      {/* What is driving this */}
      <div>
        <p className="text-sm font-semibold text-white mb-2">What is driving this score?</p>
        <p className="text-sm text-gray-400 leading-relaxed mb-4">
          The chart below shows how much each factor in the business is contributing to the overall score.
          Taller bars mean bigger impact. Some factors push the score up (costs, debt), others are strengths
          that help hold it down (revenue, margins).
        </p>
        <MetricBarChart data={barData} height={180} />
        <div className="mt-4 space-y-3">
          {contribText.map((txt, i) => (
            <div key={i} className="flex gap-3 items-start">
              <span className={`mt-1.5 w-2 h-2 rounded-full flex-shrink-0 ${(coeffs[i]?.contribution || 0) < 0 ? "bg-green-400" : "bg-amber-400"}`} />
              <p className="text-sm text-gray-400 leading-relaxed">{txt}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Risk rules */}
      <div className={`rounded-xl border p-4 ${triggered > 0 ? "border-amber-800/40 bg-amber-950/20" : "border-[#1e293b] bg-[#060a14]"}`}>
        <p className={`text-sm font-semibold ${triggered > 0 ? "text-amber-400" : "text-green-400"}`}>
          {triggered > 0
            ? `${triggered} of ${ruleCount} risk diagnostics have flagged a concern`
            : `All ${ruleCount} risk diagnostics are clear`}
        </p>
        <p className="text-sm text-gray-400 mt-2 leading-relaxed">
          {triggered === 0
            ? "None of the internal risk rules have been triggered. The business is operating within all monitored thresholds — a good sign."
            : triggered === 1
            ? `One specific area has crossed a risk threshold. This is a targeted concern rather than a systemic problem — but it should not be ignored.`
            : triggered >= ruleCount
            ? `All monitored risk thresholds have been breached simultaneously. This level of multi-point failure is the strongest possible signal for urgent intervention.`
            : `${triggered} areas have crossed risk thresholds at the same time. When multiple rules trigger together, the risks tend to compound each other — meaning the overall impact is greater than the sum of the parts.`}
        </p>
      </div>

      {/* Recommendations */}
      {actionItems.length > 0 && (
        <div>
          <p className="text-sm font-semibold text-white mb-3">What we recommend</p>
          <div className="space-y-3">
            {actionItems.map((a, i) => (
              <div key={i} className="bg-[#060a14] border border-[#1e293b] rounded-xl p-5">
                <div className="flex items-start justify-between gap-4 flex-wrap">
                  <div className="flex-1 min-w-0">
                    <p className="text-white font-semibold text-sm">{a.title}</p>
                    <p className="text-gray-400 text-sm mt-2 leading-relaxed">{a.description}</p>
                  </div>
                  <div className="text-right flex-shrink-0 space-y-1">
                    <p className="text-[10px] text-gray-500 uppercase tracking-wider">Owner</p>
                    <p className="text-xs text-gray-300 font-medium">{a.owner}</p>
                    <p className="text-[10px] text-gray-500 uppercase tracking-wider mt-2">Timeframe</p>
                    <p className="text-xs text-amber-400 font-medium">{a.horizon}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
          {roadmapPhases.length > 0 && (
            <div className="mt-5">
              <p className="text-xs text-gray-500 uppercase tracking-wider mb-3">Implementation timeline</p>
              <RoadmapTimeline phases={roadmapPhases} />
            </div>
          )}
        </div>
      )}

      {/* Session link */}
      {result.session_id && (
        <Link href={`/dashboard/sessions/${result.session_id}`} className="inline-flex items-center gap-1 text-xs text-amber-400 hover:underline">
          View full session audit trail →
        </Link>
      )}

      <p className="text-sm text-gray-500 italic border-t border-[#1e293b] pt-4">
        Would you like to explore how the picture changes under a different scenario? For example, I can model what happens if you reduce costs by 15%, or what improving margin to 20% would look like.
      </p>
    </div>
  );
}

/* ─── Typing bubble ──────────────────────────────────────────────────── */
function TypingBubble() {
  return (
    <div className="flex justify-start">
      <div className="bg-[#0a0f1c] border border-[#1e293b] rounded-xl px-5 py-4 text-sm text-gray-400">
        <div className="flex gap-1.5 items-center">
          <span className="w-2 h-2 rounded-full bg-amber-400/60 animate-bounce" style={{ animationDelay: "0ms" }} />
          <span className="w-2 h-2 rounded-full bg-amber-400/60 animate-bounce" style={{ animationDelay: "150ms" }} />
          <span className="w-2 h-2 rounded-full bg-amber-400/60 animate-bounce" style={{ animationDelay: "300ms" }} />
        </div>
      </div>
    </div>
  );
}

/* ─── Main page ──────────────────────────────────────────────────────── */
export default function WorkspacePage() {
  const { user } = useAuth();
  const [phase, setPhase] = useState<Phase>("intro");
  const [collected, setCollected] = useState<CollectedData>({});
  const [lastAskedField, setLastAskedField] = useState<string | undefined>(undefined);
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "advisor",
      text: "Hello. I'm your STRATEGOS transformation advisor.\n\nTell me about the company you'd like to assess — the sector, the scale, and what's prompting the review. I'll ask for a few numbers, run a diagnostic, and give you a clear picture of where things stand.",
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => setTimeout(() => endRef.current?.scrollIntoView({ behavior: "smooth" }), 80);

  useEffect(() => { scrollToBottom(); }, [messages, loading]);

  const addAdvisorMessage = (text: string, result?: AnalysisResult, data?: CollectedData) => {
    setMessages((prev) => [...prev, { role: "advisor", text, result, collectedData: data }]);
  };

  const runAnalysis = async (data: CollectedData) => {
    setPhase("analyzing");
    setLoading(true);
    try {
      const bodyText = [
        data.companyContext || "Enterprise diagnostic",
        `Revenue: ${data.revenue}M`,
        `Operating costs: ${data.cost}M`,
        `Margin: ${data.margin}%`,
        `Technical debt: ${data.technicalDebt}%`,
      ].join(". ");

      const res = await fetch(`${API}/intake`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tenant_id: user!.tenantId,
          model_version_id: "",
          text: bodyText,
        }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err?.detail || `HTTP ${res.status}`);
      }

      const json = await res.json();
      const d = json?.data || json;

      let boardInsights: Array<{ agent_id: string; role: string; insight: string }> = [];

      if (d.session_id) {
        try {
          const boardRes = await fetch(`${API}/advisory/skills/board_insights/${d.session_id}`);
          if (boardRes.ok) {
            const boardJson = await boardRes.json();
            boardInsights = ((boardJson?.data || {}).insights || []) as Array<{ agent_id: string; role: string; insight: string }>;
          }
        } catch {
          boardInsights = [];
        }
      }

      setMessages((prev) => [
        ...prev,
        {
          role: "advisor",
          text: `Here is what the data is telling me.`,
          result: {
            session_id: d.session_id,
            extracted_input: d.extracted_input,
            snapshot: d.snapshot,
            openclaw_insights: boardInsights,
          },
        },
      ]);

      // Advisory-board interpretation pass (OpenClaw skills-compatible endpoints)
      if (d.session_id) {
        try {
          const [stateRes, contribRes, restructRes] = await Promise.all([
            fetch(`${API}/advisory/skills/state/${d.session_id}`),
            fetch(`${API}/advisory/skills/contributions/${d.session_id}`),
            fetch(`${API}/advisory/skills/restructuring/${d.session_id}`),
          ]);

          if (stateRes.ok && contribRes.ok && restructRes.ok) {
            const stateJson = await stateRes.json();
            const contribJson = await contribRes.json();
            const restructJson = await restructRes.json();

            const stateData = (stateJson?.data || {}) as AdvisorySkillsState;
            const contributions = ((contribJson?.data || {}).contributions || []) as AdvisorySkillsContrib[];
            const restructuring = ((restructJson?.data || {}).restructuring_actions || []) as AdvisorySkillsRestructuring[];

            const triggeredExpr = contributions.filter((c) => c.result).map((c) => c.expression).filter(Boolean) as string[];
            const topActions = restructuring.slice(0, 3).map((a) => {
              const owner = a.payload?.owner || "Executive Team";
              const horizon = a.payload?.horizon_days ? `${a.payload.horizon_days}d` : "90d";
              return `${(a.template_name || "action").replace(/_/g, " ")} (${owner}, ${horizon})`;
            });

            const boardLines: string[] = [
              "OpenClaw Advisory Board Brief",
              "",
              `• State: ${stateData.state || "UNKNOWN"}${typeof stateData.total_score === "number" ? ` (score ${stateData.total_score.toFixed(1)})` : ""}`,
              `• Triggered diagnostics: ${triggeredExpr.length > 0 ? triggeredExpr.join("; ") : "none"}`,
              `• Recommended execution focus: ${topActions.length > 0 ? topActions.join("; ") : "no restructuring actions returned"}`,
              "• Next step: confirm owners and launch a 30/60/90 day execution cadence.",
            ];

            addAdvisorMessage(boardLines.join("\n"));
          }
        } catch {
          // Keep deterministic analysis path healthy even if advisory endpoints are unavailable.
        }
      }

      setPhase("followup");
    } catch (err: unknown) {
      addAdvisorMessage(
        `I ran into a problem connecting to the analysis engine: ${err instanceof Error ? err.message : "Unknown error"}. Please make sure the backend is running and try again.`
      );
      setPhase("gathering");
    } finally {
      setLoading(false);
    }
  };

  const handleMessage = async (userText: string) => {
    if (!user || loading) return;
    const trimmed = userText.trim();
    if (!trimmed) return;

    setMessages((prev) => [...prev, { role: "user", text: trimmed }]);
    setInput("");
    scrollToBottom();

    if (phase === "intro" || phase === "gathering") {
      // 1. Extract structured data from text
      let freshlyExtracted = extractFromText(trimmed, lastAskedField as DataField | undefined);

      const hintedExtract = applyFieldHintFromText(trimmed, lastAskedField);
      if (Object.keys(hintedExtract).length > 0) {
        freshlyExtracted = { ...freshlyExtracted, ...hintedExtract };
      }

      // 2. If nothing was extracted and a field was specifically asked, try bare number
      if (Object.keys(freshlyExtracted).length === 0 && lastAskedField) {
        const bareNum = trimmed.replace(/[%$,]/g, "").trim();
        const asNumber = parseFloat(bareNum);
        if (!isNaN(asNumber) && /^\$?[\d.,]+%?$/.test(trimmed.trim())) {
          freshlyExtracted = applyBareNumber(asNumber, collected, lastAskedField);
        }
      }

      // 3. On first message, also run context inference for descriptive clues
      let updated: CollectedData = { ...collected, ...freshlyExtracted };
      if (phase === "intro") {
        updated.companyContext = trimmed;
        const inferred = inferFromContext(trimmed);
        // Only use inferred values for fields not already parsed from text
        for (const [k, v] of Object.entries(inferred)) {
          if (k.startsWith("__")) continue;
          const key = k as keyof CollectedData;
          if (updated[key] === undefined) (updated as Record<string, unknown>)[key] = v;
        }
      }

      setCollected(updated);
      const missing = getMissing(updated);

      if (missing.length === 0) {
        const rev = formatCurrency(updated.revenue!);
        const cost = formatCurrency(updated.cost!);
        setPhase("confirming");
        setLastAskedField(undefined);
        addAdvisorMessage(
          `Perfect — here is what I am working with:\n\n• Revenue: ${rev}\n• Operating costs: ${cost}\n• Margin: ${updated.margin}%\n• Technical debt: ${updated.technicalDebt}%\n\nRunning the diagnostic now…`,
          undefined,
          updated
        );
        setTimeout(() => runAnalysis(updated), 1000);
      } else {
        setPhase("gathering");
        const nextField = missing[0];
        setLastAskedField(nextField);
        setTimeout(() => {
          addAdvisorMessage(askForField(nextField, updated));
        }, 300);
      }

    } else if (phase === "followup") {
      // Try to extract updated numbers from the follow-up
      let freshData = extractFromText(trimmed, lastAskedField as DataField | undefined);
      const hintedFollowup = applyFieldHintFromText(trimmed, lastAskedField);
      if (Object.keys(hintedFollowup).length > 0) {
        freshData = { ...freshData, ...hintedFollowup };
      }
      // Bare number fallback in followup too
      if (Object.keys(freshData).length === 0 && lastAskedField) {
        const bareNum = trimmed.replace(/[%$,]/g, "").trim();
        const asNumber = parseFloat(bareNum);
        if (!isNaN(asNumber) && /^\$?[\d.,]+%?$/.test(trimmed.trim())) {
          freshData = applyBareNumber(asNumber, collected, lastAskedField);
        }
      }
      if (Object.keys(freshData).length > 0) {
        const updated: CollectedData = { ...collected, ...freshData };
        setCollected(updated);
        const rev = formatCurrency(updated.revenue!);
        const cost = formatCurrency(updated.cost!);
        addAdvisorMessage(
          `Re-running the analysis with updated figures:\n\n• Revenue: ${rev}\n• Operating costs: ${cost}\n• Margin: ${updated.margin}%\n• Technical debt: ${updated.technicalDebt}%`
        );
        setTimeout(() => runAnalysis(updated), 800);
      } else if (/(?:yes|please|go ahead|sure|do it)/i.test(trimmed)) {
        addAdvisorMessage(
          "Describe the scenario you want to explore — for example: 'What if operating costs drop to $600M?' or 'Same company with 25% margin'. I will re-run the diagnostic immediately."
        );
      } else {
        addAdvisorMessage(
          "You can describe a new scenario — for example 'What if we cut costs by 20%' or 'Model with technical debt at 40%' — and I will run a fresh diagnostic. Or ask me anything about the results."
        );
      }
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || loading) return;
    handleMessage(input);
  };

  return (
    <div className="flex flex-col h-[calc(100vh-5rem)]">
      {/* Header */}
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">STRATEGOS Advisor</h1>
          <p className="text-xs text-gray-500 mt-0.5">
            Your personal transformation intelligence advisor — powered by deterministic AI
          </p>
        </div>
        {phase !== "intro" && phase !== "gathering" && (
          <button
            onClick={() => {
              setPhase("intro");
              setCollected({});
              setLastAskedField(undefined);
              setMessages([{
                role: "advisor",
                text: "Let's start a fresh diagnostic. Tell me about the company or situation you would like to evaluate.",
              }]);
            }}
            className="text-xs text-gray-500 hover:text-amber-400 border border-[#1e293b] px-3 py-1.5 rounded-lg transition-colors"
          >
            New session
          </button>
        )}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto space-y-5 pr-1 pb-4">
        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
            <div
              className={`rounded-xl p-4 text-sm leading-relaxed ${
                msg.role === "user"
                  ? "max-w-[80%] bg-amber-500/10 border border-amber-500/20 text-white"
                  : "w-full max-w-[92%] bg-[#0a0f1c] border border-[#1e293b] text-gray-300"
              }`}
            >
              {msg.role === "advisor" && (
                <div className="flex items-center gap-2 mb-2.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
                  <span className="text-[10px] text-gray-500 uppercase tracking-wider font-medium">STRATEGOS Advisor</span>
                </div>
              )}
              <p className="whitespace-pre-wrap">{msg.text}</p>
              {msg.result && <AnalysisNarrative result={msg.result} />}
            </div>
          </div>
        ))}

        {loading && <TypingBubble />}
        <div ref={endRef} />
      </div>

      {/* Input */}
      <form onSubmit={handleSubmit} className="mt-3 flex gap-3">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={
            phase === "intro"
              ? "Describe the company or situation…"
              : phase === "gathering"
              ? "Type your answer…"
              : phase === "followup"
              ? "Ask a follow-up or describe a new scenario…"
              : "…"
          }
          className="flex-1 bg-[#0a0f1c] border border-[#1e293b] rounded-xl px-4 py-3 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-amber-500/40 transition-colors"
          disabled={loading || phase === "confirming" || phase === "analyzing"}
        />
        <button
          type="submit"
          disabled={loading || !input.trim() || phase === "confirming" || phase === "analyzing"}
          className="px-6 py-3 bg-amber-500/90 text-[#060a14] font-semibold rounded-xl text-sm hover:bg-amber-500 transition-colors disabled:opacity-40"
        >
          Send
        </button>
      </form>
    </div>
  );
}

