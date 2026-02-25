/* ── Shared TypeScript types for STRATEGOS SaaS ── */

export type UserRole = "admin" | "analyst" | "viewer";

export interface User {
  id: string;
  email: string;
  name: string;
  role: UserRole;
  tenantId: string;
}

export interface Contribution {
  rule_id: string;
  condition_id: string;
  expression: string;
  result: boolean;
  error?: string | null;
}

export interface CoefficientContribution {
  name: string;
  mode: "scalar" | "formula";
  input: number | null;
  coefficient: number | null;
  formula: string | null;
  contribution: number;
  error: string | null;
}

export interface ScoreBreakdown {
  weighted_input_score: number;
  rule_impact_score: number;
  total_score: number;
  coefficient_contributions: CoefficientContribution[];
}

export interface RestructuringAction {
  restructuring_rule_id: string;
  template_id: string;
  template_name: string;
  payload: Record<string, unknown>;
}

export interface EngineSnapshot {
  model_version: { id: string; name: string; tenant_id: string };
  rule_count: number;
  triggered_rule_count: number;
  conditions_evaluated: number;
  state: "NORMAL" | "ELEVATED_RISK" | "CRITICAL_ZONE";
  contributions: Contribution[];
  scores: Record<string, number>;
  score_breakdown: ScoreBreakdown;
  restructuring_actions: RestructuringAction[];
}

export interface SessionListItem {
  id: string;
  tenant_id: string;
  model_version_id: string;
  name: string | null;
  created_at: string;
  state?: string;
  total_score?: number;
}

export interface SessionDetail {
  session_id: string;
  version: number;
  latest: EngineSnapshot | null;
  history: Array<{
    version: number;
    created_at: string;
    snapshot: EngineSnapshot;
  }>;
}

export interface ModelVersion {
  id: string;
  tenant_id: string;
  name: string;
  description?: string | null;
  is_active: boolean;
}

export interface IntakeResponse {
  session_id: string;
  extracted_input: Record<string, number>;
  snapshot: EngineSnapshot;
  advisory_summary: string;
}
