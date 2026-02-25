"use client";

import React, { useEffect, useMemo, useState } from "react";

type Snapshot = {
  model_version: { id: string; name: string };
  rule_count: number;
  triggered_rule_count: number;
  conditions_evaluated: number;
  state: string;
  contributions: Array<{
    rule_id: string;
    condition_id: string;
    expression: string;
    result: boolean;
    error?: string | null;
  }>;
  scores?: Record<string, number>;
  score_breakdown?: Record<string, unknown>;
  restructuring_actions?: Array<Record<string, unknown>>;
};

type SessionSnapshots = {
  session_id: string;
  version: number;
  latest: unknown;
  history: Array<{ version: number; created_at: string; snapshot: unknown }>;
};

type ReplayEvent = {
  audit_log_id: string;
  created_at: string;
  action: string;
  payload: Record<string, unknown>;
};

type ModelVersionItem = {
  id: string;
  tenant_id: string;
  name: string;
  description?: string | null;
  is_active: boolean;
};

type RuleItem = {
  id: string;
  tenant_id: string;
  model_version_id: string;
  name: string;
  description?: string | null;
  is_active: boolean;
};

type StateItem = {
  id: string;
  tenant_id: string;
  name: string;
  description?: string | null;
};

type ThresholdItem = {
  id: string;
  state_definition_id: string;
  tenant_id: string;
  threshold: string;
};

type ScenarioKey = "CUSTOM" | "NORMAL" | "ELEVATED_RISK" | "CRITICAL_ZONE";

const SCENARIO_PRESETS: Record<Exclude<ScenarioKey, "CUSTOM">, Record<string, number>> = {
  NORMAL: {
    revenue: 1400,
    cost: 170,
    margin: 0.24,
    technical_debt: 35,
  },
  ELEVATED_RISK: {
    revenue: 980,
    cost: 255,
    margin: 0.16,
    technical_debt: 76,
  },
  CRITICAL_ZONE: {
    revenue: 640,
    cost: 335,
    margin: 0.08,
    technical_debt: 92,
  },
};

export default function Page() {
  const defaultApi = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000/api/v1";
  const [apiBase, setApiBase] = useState(defaultApi);

  const [tenantId, setTenantId] = useState("");

  const [modelVersionId, setModelVersionId] = useState("");
  const [modelVersionName, setModelVersionName] = useState("mv-local");
  const [modelVersionDescription, setModelVersionDescription] = useState("Local model version");

  const [ruleName, setRuleName] = useState("Revenue Risk Rule");
  const [ruleDescription, setRuleDescription] = useState("Detect low revenue");
  const [ruleExpression, setRuleExpression] = useState("revenue < 1000");
  const [ruleImpact, setRuleImpact] = useState("2.5");
  const [createdRuleId, setCreatedRuleId] = useState("");

  const [stateName, setStateName] = useState("ELEVATED_RISK");
  const [stateDescription, setStateDescription] = useState("Elevated risk state");
  const [thresholdValue, setThresholdValue] = useState("2");
  const [createdStateId, setCreatedStateId] = useState("");
  const [selectedRuleId, setSelectedRuleId] = useState("");
  const [selectedStateId, setSelectedStateId] = useState("");

  const [modelVersions, setModelVersions] = useState<ModelVersionItem[]>([]);
  const [rules, setRules] = useState<RuleItem[]>([]);
  const [states, setStates] = useState<StateItem[]>([]);
  const [thresholds, setThresholds] = useState<ThresholdItem[]>([]);

  const [inputJson, setInputJson] = useState('{"revenue": 800, "margin": 0.15}');
  const [selectedScenario, setSelectedScenario] = useState<ScenarioKey>("CUSTOM");
  const [lastRunScenario, setLastRunScenario] = useState<ScenarioKey>("CUSTOM");
  const [sessionId, setSessionId] = useState("");
  const [sessionSnapshots, setSessionSnapshots] = useState<SessionSnapshots | null>(null);
  const [replayEvents, setReplayEvents] = useState<ReplayEvent[]>([]);
  const [selectedAuditId, setSelectedAuditId] = useState("");
  const [auditReplayResult, setAuditReplayResult] = useState<Record<string, unknown> | null>(null);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionResult, setActionResult] = useState<string | null>(null);
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [lastRunAt, setLastRunAt] = useState<string | null>(null);

  const parsedInput = useMemo(() => {
    try {
      return JSON.parse(inputJson);
    } catch {
      return null;
    }
  }, [inputJson]);

  const replayComparisonRows = useMemo(() => {
    if (!auditReplayResult) {
      return [] as Array<{ field: string; stored: string; replayed: string; match: boolean }>;
    }

    const storedPayload = (auditReplayResult.stored_payload || {}) as Record<string, unknown>;
    const replaySnapshot = (auditReplayResult.replay_snapshot || {}) as Record<string, unknown>;
    const replayScoreBreakdown = (replaySnapshot.score_breakdown || {}) as Record<string, unknown>;
    const replayModelVersion = ((replaySnapshot.model_version as Record<string, unknown> | undefined) || {});

    const asText = (value: unknown): string => {
      if (value === null || value === undefined) {
        return "-";
      }
      if (typeof value === "string") {
        return value;
      }
      if (typeof value === "number" || typeof value === "boolean") {
        return String(value);
      }
      try {
        return JSON.stringify(value);
      } catch {
        return String(value);
      }
    };

    const rows = [
      {
        field: "model_version_id",
        stored: asText(storedPayload.model_version_id),
        replayed: asText(replayModelVersion.id),
      },
      {
        field: "state",
        stored: asText(storedPayload.state),
        replayed: asText(replaySnapshot.state),
      },
      {
        field: "total_score",
        stored: asText(storedPayload.total_score),
        replayed: asText(replayScoreBreakdown.total_score),
      },
      {
        field: "error",
        stored: asText(storedPayload.error),
        replayed: asText(auditReplayResult.replay_error),
      },
      {
        field: "input",
        stored: asText(storedPayload.input),
        replayed: asText(storedPayload.input),
      },
    ];

    return rows.map((row) => ({ ...row, match: row.stored === row.replayed }));
  }, [auditReplayResult]);

  const callApi = async (path: string, method: "GET" | "POST" | "PATCH", body?: unknown) => {
    const resp = await fetch(`${apiBase}${path}`, {
      method,
      headers: { "Content-Type": "application/json" },
      body: body ? JSON.stringify(body) : undefined,
    });
    const payload = await resp.json();
    if (!resp.ok) {
      throw new Error(payload?.detail ? JSON.stringify(payload.detail) : `HTTP ${resp.status}`);
    }
    return payload;
  };

  const refreshModelVersions = async () => {
    if (!tenantId) {
      setModelVersions([]);
      return;
    }
    const payload = await callApi(`/models/versions?tenant_id=${encodeURIComponent(tenantId)}`, "GET");
    setModelVersions((payload?.data?.model_versions || []) as ModelVersionItem[]);
  };

  const refreshRules = async (currentModelVersionId?: string) => {
    const mv = currentModelVersionId || modelVersionId;
    if (!mv) {
      setRules([]);
      return;
    }
    const payload = await callApi(`/rules?model_version_id=${encodeURIComponent(mv)}&active_only=false`, "GET");
    const allRules = (payload?.data?.rules || []) as RuleItem[];
    const filtered = tenantId ? allRules.filter((r) => r.tenant_id === tenantId) : allRules;
    setRules(filtered);
  };

  const refreshStates = async () => {
    if (!tenantId) {
      setStates([]);
      return;
    }
    const payload = await callApi(`/states?tenant_id=${encodeURIComponent(tenantId)}`, "GET");
    setStates((payload?.data?.states || []) as StateItem[]);
  };

  const refreshThresholds = async (stateId?: string) => {
    const sid = stateId || selectedStateId;
    if (!sid) {
      setThresholds([]);
      return;
    }
    const payload = await callApi(`/states/${encodeURIComponent(sid)}/thresholds`, "GET");
    setThresholds((payload?.data?.thresholds || []) as ThresholdItem[]);
  };

  const refreshCatalog = async () => {
    setError(null);
    try {
      await refreshModelVersions();
      await refreshRules();
      await refreshStates();
      await refreshThresholds();
      setActionResult("Catalog refreshed.");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to refresh catalog.");
    }
  };

  useEffect(() => {
    setActionResult(null);
    setError(null);
    if (tenantId) {
      void refreshModelVersions();
      void refreshStates();
    } else {
      setModelVersions([]);
      setStates([]);
      setRules([]);
      setThresholds([]);
    }
  }, [tenantId]);

  useEffect(() => {
    if (modelVersionId) {
      void refreshRules(modelVersionId);
    } else {
      setRules([]);
    }
  }, [modelVersionId]);

  useEffect(() => {
    if (selectedStateId) {
      void refreshThresholds(selectedStateId);
    } else {
      setThresholds([]);
    }
  }, [selectedStateId]);

  const runEngine = async (inputOverride?: Record<string, number>, scenarioOverride?: ScenarioKey) => {
    setError(null);
    setActionResult(null);
    const inputPayload = inputOverride ?? parsedInput;
    if (!inputPayload || typeof inputPayload !== "object") {
      setError("Input JSON is invalid.");
      return;
    }
    setLoading(true);
    try {
      const resp = await fetch(`${apiBase}/engine/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ model_version_id: modelVersionId || undefined, tenant_id: tenantId || undefined, session_id: sessionId || undefined, input: inputPayload }),
      });

      const body = await resp.json();
      if (!resp.ok) {
        const detail = body?.detail ? JSON.stringify(body.detail) : `HTTP ${resp.status}`;
        throw new Error(detail);
      }
      setSnapshot(body as Snapshot);
      setLastRunScenario(scenarioOverride || selectedScenario);
      setLastRunAt(new Date().toISOString());
    } catch (err: any) {
      setError(err?.message || "Failed to run engine.");
      setSnapshot(null);
    } finally {
      setLoading(false);
    }
  };

  const applyScenarioPreset = (scenario: Exclude<ScenarioKey, "CUSTOM">) => {
    setInputJson(JSON.stringify(SCENARIO_PRESETS[scenario], null, 2));
    setSelectedScenario(scenario);
    setActionResult(`Scenario preset loaded: ${scenario}`);
    setError(null);
  };

  const runScenarioPreset = async (scenario: Exclude<ScenarioKey, "CUSTOM">) => {
    const payload = SCENARIO_PRESETS[scenario];
    setSelectedScenario(scenario);
    setInputJson(JSON.stringify(payload, null, 2));
    await runEngine(payload, scenario);
  };

  const handleInputJsonChange = (value: string) => {
    setInputJson(value);
    setSelectedScenario("CUSTOM");
  };

  const loadSessionSnapshots = async () => {
    setError(null);
    setActionResult(null);
    setAuditReplayResult(null);
    if (!sessionId) {
      setError("Enter a session ID first.");
      return;
    }
    try {
      const payload = await callApi(`/sessions/${encodeURIComponent(sessionId)}/snapshots`, "GET");
      setSessionSnapshots((payload?.data || null) as SessionSnapshots | null);
      setActionResult("Session snapshots loaded.");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load session snapshots.");
    }
  };

  const loadSessionReplay = async () => {
    setError(null);
    setActionResult(null);
    setAuditReplayResult(null);
    if (!sessionId) {
      setError("Enter a session ID first.");
      return;
    }
    try {
      const payload = await callApi(`/sessions/${encodeURIComponent(sessionId)}/replay`, "GET");
      const events = (payload?.data?.events || []) as ReplayEvent[];
      setReplayEvents(events);
      setSelectedAuditId(events[0]?.audit_log_id || "");
      setActionResult(`Loaded ${events.length} replay event(s).`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load session replay.");
    }
  };

  const replaySelectedAudit = async () => {
    setError(null);
    setActionResult(null);
    if (!selectedAuditId) {
      setError("Select an audit event first.");
      return;
    }
    try {
      const payload = await callApi(`/sessions/replay/audit/${encodeURIComponent(selectedAuditId)}`, "GET");
      setAuditReplayResult((payload?.data || null) as Record<string, unknown> | null);
      setActionResult(`Loaded replay for audit ${selectedAuditId}.`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to replay selected audit.");
    }
  };

  const createModelVersion = async () => {
    setError(null);
    setActionResult(null);
    try {
      const payload = await callApi("/models/versions", "POST", {
        tenant_id: tenantId,
        name: modelVersionName,
        description: modelVersionDescription,
        is_active: true,
      });
      const id = payload?.data?.model_version_id as string;
      if (id) {
        setModelVersionId(id);
      }
      setActionResult(`Model version created: ${id || "(no id)"}`);
      await refreshModelVersions();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to create model version.");
    }
  };

  const createRuleFlow = async () => {
    setError(null);
    setActionResult(null);
    try {
      const ruleResp = await callApi("/rules", "POST", {
        tenant_id: tenantId,
        model_version_id: modelVersionId,
        name: ruleName,
        description: ruleDescription,
      });
      const ruleId = ruleResp?.data?.rule_id as string;
      if (!ruleId) {
        throw new Error("Rule ID not returned");
      }
      setCreatedRuleId(ruleId);
      setSelectedRuleId(ruleId);

      await callApi(`/rules/${ruleId}/conditions`, "POST", {
        tenant_id: tenantId,
        expression: ruleExpression,
      });
      await callApi(`/rules/${ruleId}/impacts`, "POST", {
        tenant_id: tenantId,
        impact: ruleImpact,
      });
      setActionResult(`Rule created and configured: ${ruleId}`);
      await refreshRules();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to create rule.");
    }
  };

  const createStateFlow = async () => {
    setError(null);
    setActionResult(null);
    try {
      const stateResp = await callApi("/states", "POST", {
        tenant_id: tenantId,
        name: stateName,
        description: stateDescription,
      });
      const stateId = stateResp?.data?.state_definition_id as string;
      if (!stateId) {
        throw new Error("State ID not returned");
      }
      setCreatedStateId(stateId);
      setSelectedStateId(stateId);
      await callApi(`/states/${stateId}/thresholds`, "POST", {
        tenant_id: tenantId,
        threshold: thresholdValue,
      });
      setActionResult(`State created and threshold added: ${stateId}`);
      await refreshStates();
      await refreshThresholds(stateId);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to create state.");
    }
  };

  const activateSelectedModelVersion = async () => {
    setError(null);
    setActionResult(null);
    if (!modelVersionId) {
      setError("Select a model version first.");
      return;
    }
    try {
      await callApi(`/models/versions/${modelVersionId}/activate`, "PATCH");
      setActionResult(`Model version activated: ${modelVersionId}`);
      await refreshModelVersions();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to activate model version.");
    }
  };

  const deactivateSelectedRule = async () => {
    setError(null);
    setActionResult(null);
    if (!selectedRuleId) {
      setError("Select a rule first.");
      return;
    }
    try {
      await callApi(`/rules/${selectedRuleId}/deactivate`, "PATCH");
      setActionResult(`Rule deactivated: ${selectedRuleId}`);
      await refreshRules();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to deactivate rule.");
    }
  };

  return (
    <main style={{ padding: 40, fontFamily: "Inter, system-ui, sans-serif", background: "#0b1020", color: "#e6eef8", minHeight: "100vh" }}>
      <div style={{ maxWidth: 980, margin: "0 auto" }}>
        <h1 style={{ fontSize: 36, marginBottom: 8 }}>STRATEGOS</h1>
        <p style={{ opacity: 0.85 }}>Deterministic engine runner + model/rule/state authoring.</p>

        <section style={{ marginTop: 24, border: "1px solid #223", borderRadius: 8, padding: 16 }}>
          <h2 style={{ marginTop: 0, fontSize: 18 }}>Workspace Context</h2>
          <div style={{ display: "grid", gap: 10 }}>
            <label>
              Tenant ID
              <input
                value={tenantId}
                onChange={(e) => setTenantId(e.target.value)}
                placeholder="UUID"
                style={{ width: "100%", padding: 8, marginTop: 4 }}
              />
            </label>
            <button onClick={refreshCatalog} style={{ padding: "10px 14px", cursor: "pointer" }}>Refresh Catalog</button>
          </div>
          <p style={{ marginBottom: 0, opacity: 0.8 }}>Use the same tenant for model versions, rules, and states.</p>
        </section>

        <section style={{ marginTop: 24, border: "1px solid #223", borderRadius: 8, padding: 16 }}>
          <h2 style={{ marginTop: 0, fontSize: 18 }}>Model Version Authoring</h2>
          <div style={{ display: "grid", gap: 10 }}>
            <label>
              Model Version Name
              <input value={modelVersionName} onChange={(e) => setModelVersionName(e.target.value)} style={{ width: "100%", padding: 8, marginTop: 4 }} />
            </label>
            <label>
              Description
              <input value={modelVersionDescription} onChange={(e) => setModelVersionDescription(e.target.value)} style={{ width: "100%", padding: 8, marginTop: 4 }} />
            </label>
            <button onClick={createModelVersion} style={{ padding: "10px 14px", cursor: "pointer" }}>Create Active Model Version</button>
            <label>
              Existing Model Versions
              <select
                value={modelVersionId}
                onChange={(e) => setModelVersionId(e.target.value)}
                style={{ width: "100%", padding: 8, marginTop: 4 }}
              >
                <option value="">Select model version</option>
                {modelVersions.map((mv) => (
                  <option key={mv.id} value={mv.id}>
                    {mv.name} ({mv.is_active ? "active" : "inactive"})
                  </option>
                ))}
              </select>
            </label>
            <button onClick={activateSelectedModelVersion} style={{ padding: "10px 14px", cursor: "pointer" }}>Activate Selected Model Version</button>
          </div>
        </section>

        <section style={{ marginTop: 24, border: "1px solid #223", borderRadius: 8, padding: 16 }}>
          <h2 style={{ marginTop: 0, fontSize: 18 }}>Rule Authoring</h2>
          <div style={{ display: "grid", gap: 10 }}>
            <label>
              Model Version ID
              <input value={modelVersionId} onChange={(e) => setModelVersionId(e.target.value)} style={{ width: "100%", padding: 8, marginTop: 4 }} />
            </label>
            <label>
              Rule Name
              <input value={ruleName} onChange={(e) => setRuleName(e.target.value)} style={{ width: "100%", padding: 8, marginTop: 4 }} />
            </label>
            <label>
              Rule Description
              <input value={ruleDescription} onChange={(e) => setRuleDescription(e.target.value)} style={{ width: "100%", padding: 8, marginTop: 4 }} />
            </label>
            <label>
              Condition Expression
              <input value={ruleExpression} onChange={(e) => setRuleExpression(e.target.value)} style={{ width: "100%", padding: 8, marginTop: 4 }} />
            </label>
            <label>
              Impact Score
              <input value={ruleImpact} onChange={(e) => setRuleImpact(e.target.value)} style={{ width: "100%", padding: 8, marginTop: 4 }} />
            </label>
            <button onClick={createRuleFlow} style={{ padding: "10px 14px", cursor: "pointer" }}>Create Rule + Condition + Impact</button>
            <label>
              Existing Rules
              <select value={selectedRuleId} onChange={(e) => setSelectedRuleId(e.target.value)} style={{ width: "100%", padding: 8, marginTop: 4 }}>
                <option value="">Select rule</option>
                {rules.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.name} ({r.is_active ? "active" : "inactive"})
                  </option>
                ))}
              </select>
            </label>
            <button onClick={deactivateSelectedRule} style={{ padding: "10px 14px", cursor: "pointer" }}>Deactivate Selected Rule</button>
            {createdRuleId && <p style={{ margin: 0, opacity: 0.85 }}>Last rule ID: {createdRuleId}</p>}
          </div>
        </section>

        <section style={{ marginTop: 24, border: "1px solid #223", borderRadius: 8, padding: 16 }}>
          <h2 style={{ marginTop: 0, fontSize: 18 }}>State & Threshold Authoring</h2>
          <div style={{ display: "grid", gap: 10 }}>
            <label>
              State Name
              <input value={stateName} onChange={(e) => setStateName(e.target.value)} style={{ width: "100%", padding: 8, marginTop: 4 }} />
            </label>
            <label>
              State Description
              <input value={stateDescription} onChange={(e) => setStateDescription(e.target.value)} style={{ width: "100%", padding: 8, marginTop: 4 }} />
            </label>
            <label>
              Threshold
              <input value={thresholdValue} onChange={(e) => setThresholdValue(e.target.value)} style={{ width: "100%", padding: 8, marginTop: 4 }} />
            </label>
            <button onClick={createStateFlow} style={{ padding: "10px 14px", cursor: "pointer" }}>Create State + Threshold</button>
            <label>
              Existing States
              <select value={selectedStateId} onChange={(e) => setSelectedStateId(e.target.value)} style={{ width: "100%", padding: 8, marginTop: 4 }}>
                <option value="">Select state</option>
                {states.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </select>
            </label>
            {thresholds.length > 0 && (
              <div style={{ border: "1px solid #223", borderRadius: 6, padding: 8 }}>
                <p style={{ marginTop: 0, marginBottom: 8 }}>Thresholds</p>
                <ul style={{ marginTop: 0, marginBottom: 0 }}>
                  {thresholds.map((t) => (
                    <li key={t.id}>{t.threshold}</li>
                  ))}
                </ul>
              </div>
            )}
            {createdStateId && <p style={{ margin: 0, opacity: 0.85 }}>Last state ID: {createdStateId}</p>}
          </div>
        </section>

        <section style={{ marginTop: 24, border: "1px solid #223", borderRadius: 8, padding: 16 }}>
          <h2 style={{ marginTop: 0, fontSize: 18 }}>Run Engine</h2>
          <div style={{ display: "grid", gap: 10 }}>
            <label>
              API Base
              <input value={apiBase} onChange={(e) => setApiBase(e.target.value)} style={{ width: "100%", padding: 8, marginTop: 4 }} />
            </label>
            <label>
              Model Version ID (optional)
              <input value={modelVersionId} onChange={(e) => setModelVersionId(e.target.value)} style={{ width: "100%", padding: 8, marginTop: 4 }} />
            </label>
            <label>
              Session ID (optional, enables versioned snapshots)
              <input value={sessionId} onChange={(e) => setSessionId(e.target.value)} style={{ width: "100%", padding: 8, marginTop: 4 }} />
            </label>
            <label>
              Scenario Preset
              <div style={{ display: "flex", gap: 8, marginTop: 4, flexWrap: "wrap" }}>
                <select
                  value={selectedScenario}
                  onChange={(e) => {
                    const scenario = e.target.value as ScenarioKey;
                    setSelectedScenario(scenario);
                    if (scenario !== "CUSTOM") {
                      applyScenarioPreset(scenario);
                    }
                  }}
                  style={{ flex: 1, padding: 8 }}
                >
                  <option value="CUSTOM">CUSTOM</option>
                  <option value="NORMAL">NORMAL</option>
                  <option value="ELEVATED_RISK">ELEVATED_RISK</option>
                  <option value="CRITICAL_ZONE">CRITICAL_ZONE</option>
                </select>
                <button
                  onClick={() => {
                    if (selectedScenario === "CUSTOM") {
                      setActionResult("Using custom input payload.");
                      setError(null);
                      return;
                    }
                    applyScenarioPreset(selectedScenario);
                  }}
                  style={{ padding: "10px 14px", cursor: "pointer" }}
                >
                  Load
                </button>
                <button onClick={() => void runScenarioPreset("NORMAL")} disabled={loading} style={{ padding: "10px 14px", cursor: "pointer" }}>
                  Run NORMAL
                </button>
                <button onClick={() => void runScenarioPreset("ELEVATED_RISK")} disabled={loading} style={{ padding: "10px 14px", cursor: "pointer" }}>
                  Run ELEVATED_RISK
                </button>
                <button onClick={() => void runScenarioPreset("CRITICAL_ZONE")} disabled={loading} style={{ padding: "10px 14px", cursor: "pointer" }}>
                  Run CRITICAL_ZONE
                </button>
              </div>
            </label>
            <label>
              Input JSON
              <textarea value={inputJson} onChange={(e) => handleInputJsonChange(e.target.value)} rows={5} style={{ width: "100%", padding: 8, marginTop: 4, fontFamily: "ui-monospace, Menlo, monospace" }} />
            </label>
            <button onClick={() => void runEngine()} disabled={loading} style={{ padding: "10px 14px", cursor: "pointer" }}>
              {loading ? "Running..." : "Run Deterministic Engine"}
            </button>
            {error && <p style={{ color: "#ff9a9a", margin: 0 }}>Error: {error}</p>}
            {actionResult && <p style={{ color: "#b7f3c1", margin: 0 }}>{actionResult}</p>}
          </div>
        </section>

        <section style={{ marginTop: 24, border: "1px solid #223", borderRadius: 8, padding: 16 }}>
          <h2 style={{ marginTop: 0, fontSize: 18 }}>Replay Console</h2>
          <div style={{ display: "grid", gap: 10 }}>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <button onClick={loadSessionSnapshots} style={{ padding: "10px 14px", cursor: "pointer" }}>Load Session Snapshots</button>
              <button onClick={loadSessionReplay} style={{ padding: "10px 14px", cursor: "pointer" }}>Load Session Replay Events</button>
            </div>

            {sessionSnapshots && (
              <div style={{ border: "1px solid #223", borderRadius: 6, padding: 8 }}>
                <p style={{ marginTop: 0, marginBottom: 6 }}>Snapshot Version: {sessionSnapshots.version}</p>
                <p style={{ marginTop: 0, marginBottom: 0 }}>History Entries: {sessionSnapshots.history?.length || 0}</p>
              </div>
            )}

            <label>
              Replay Event (Audit Log ID)
              <select value={selectedAuditId} onChange={(e) => setSelectedAuditId(e.target.value)} style={{ width: "100%", padding: 8, marginTop: 4 }}>
                <option value="">Select replay event</option>
                {replayEvents.map((ev) => (
                  <option key={ev.audit_log_id} value={ev.audit_log_id}>
                    {ev.audit_log_id} ({ev.created_at})
                  </option>
                ))}
              </select>
            </label>

            <button onClick={replaySelectedAudit} style={{ padding: "10px 14px", cursor: "pointer" }}>Replay Selected Audit Event</button>

            {auditReplayResult && (
              <div style={{ border: "1px solid #223", borderRadius: 6, padding: 8 }}>
                <p style={{ marginTop: 0, marginBottom: 8 }}>Replay Comparison</p>
                <div style={{ overflowX: "auto" }}>
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                    <thead>
                      <tr>
                        <th style={{ textAlign: "left", borderBottom: "1px solid #334", padding: 6 }}>Field</th>
                        <th style={{ textAlign: "left", borderBottom: "1px solid #334", padding: 6 }}>Stored (Audit)</th>
                        <th style={{ textAlign: "left", borderBottom: "1px solid #334", padding: 6 }}>Replayed</th>
                        <th style={{ textAlign: "left", borderBottom: "1px solid #334", padding: 6 }}>Match</th>
                      </tr>
                    </thead>
                    <tbody>
                      {replayComparisonRows.map((row) => (
                        <tr key={row.field}>
                          <td style={{ borderBottom: "1px solid #223", padding: 6 }}>{row.field}</td>
                          <td style={{ borderBottom: "1px solid #223", padding: 6, wordBreak: "break-word" }}>{row.stored}</td>
                          <td style={{ borderBottom: "1px solid #223", padding: 6, wordBreak: "break-word" }}>{row.replayed}</td>
                          <td style={{ borderBottom: "1px solid #223", padding: 6 }}>{row.match ? "Yes" : "No"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <p style={{ marginTop: 12, marginBottom: 8 }}>Raw Replay Payload</p>
                <pre style={{ margin: 0, whiteSpace: "pre-wrap", wordBreak: "break-word", fontSize: 12 }}>{JSON.stringify(auditReplayResult, null, 2)}</pre>
              </div>
            )}
          </div>
        </section>

        {snapshot && (
          <section style={{ marginTop: 24, border: "1px solid #223", borderRadius: 8, padding: 16 }}>
            <h2 style={{ marginTop: 0, fontSize: 18 }}>Snapshot</h2>
            <p style={{ margin: "4px 0" }}>Model: {snapshot.model_version?.name} ({snapshot.model_version?.id})</p>
            <p style={{ margin: "4px 0" }}>State: <strong>{snapshot.state}</strong></p>
            <p style={{ margin: "4px 0" }}>Scenario: {lastRunScenario}</p>
            {lastRunAt && <p style={{ margin: "4px 0" }}>Last run (UTC): {lastRunAt}</p>}
            <p style={{ margin: "4px 0" }}>
              Rules: {snapshot.triggered_rule_count}/{snapshot.rule_count} triggered, {snapshot.conditions_evaluated} conditions evaluated
            </p>

            <h3 style={{ marginTop: 16, fontSize: 16 }}>Contributions</h3>
            {snapshot.contributions?.length ? (
              <div style={{ overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse" }}>
                  <thead>
                    <tr>
                      <th style={{ textAlign: "left", borderBottom: "1px solid #334", padding: 6 }}>Rule</th>
                      <th style={{ textAlign: "left", borderBottom: "1px solid #334", padding: 6 }}>Expression</th>
                      <th style={{ textAlign: "left", borderBottom: "1px solid #334", padding: 6 }}>Result</th>
                      <th style={{ textAlign: "left", borderBottom: "1px solid #334", padding: 6 }}>Error</th>
                    </tr>
                  </thead>
                  <tbody>
                    {snapshot.contributions.map((c) => (
                      <tr key={c.condition_id}>
                        <td style={{ borderBottom: "1px solid #223", padding: 6 }}>{c.rule_id}</td>
                        <td style={{ borderBottom: "1px solid #223", padding: 6 }}>{c.expression}</td>
                        <td style={{ borderBottom: "1px solid #223", padding: 6 }}>{String(c.result)}</td>
                        <td style={{ borderBottom: "1px solid #223", padding: 6 }}>{c.error || "-"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p>No contributions yet.</p>
            )}
          </section>
        )}
      </div>
    </main>
  );
}
