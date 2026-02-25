"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  listAdminAgents,
  createAdminAgent,
  updateAdminAgentSkills,
  deleteAdminAgent,
  type AdminAgent,
} from "../../../lib/api";

const API = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000/api/v1";

export default function InternalAdminPortalPage() {
  const [tenantId, setTenantId] = useState("c6ff3608-37ba-41da-a6ba-f8ff12c0c2e3");
  const [command, setCommand] = useState("Show platform overview");
  const [response, setResponse] = useState<Record<string, unknown> | null>(null);
  const [demoTrace, setDemoTrace] = useState<Record<string, unknown> | null>(null);
  const [modelVersions, setModelVersions] = useState<Array<{ id: string; name: string }>>([]);
  const [rules, setRules] = useState<Array<{ id: string; name: string; description?: string | null; is_active: boolean }>>([]);
  const [selectedModelVersionId, setSelectedModelVersionId] = useState("");
  const [newRuleName, setNewRuleName] = useState("");
  const [newRuleDescription, setNewRuleDescription] = useState("");
  const [newRuleCondition, setNewRuleCondition] = useState("");
  const [newRuleImpact, setNewRuleImpact] = useState("");
  const [editingRuleId, setEditingRuleId] = useState<string | null>(null);
  const [editingName, setEditingName] = useState("");
  const [editingDescription, setEditingDescription] = useState("");
  const [agents, setAgents] = useState<AdminAgent[]>([]);
  const [availableSkills, setAvailableSkills] = useState<string[]>([]);
  const [newAgentId, setNewAgentId] = useState("");
  const [newAgentRole, setNewAgentRole] = useState("");
  const [newAgentSkills, setNewAgentSkills] = useState("");
  const [agentSkillDrafts, setAgentSkillDrafts] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const quickCommands = useMemo(
    () => [
      "Show platform overview",
      "Show all model versions",
      "Show all rules",
      "Show all sessions",
      "Show audit logs",
      "Help",
    ],
    []
  );

  const runCommand = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API}/admin/command`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tenant_id: tenantId, text: command }),
      });
      const json = await res.json();
      if (!res.ok) throw new Error(json?.detail || `HTTP ${res.status}`);
      const data = (json?.data || json) as Record<string, unknown>;
      setResponse(data);

      const action = data?.action;
      const rulesData = data?.rules;
      if (action === "list_rules" && Array.isArray(rulesData) && rulesData.length === 0) {
        setError(`No rules found for tenant ${tenantId}. Verify tenant/model context in the top input.`);
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Request failed");
    } finally {
      setLoading(false);
    }
  };

  const loadCrudData = useCallback(async () => {
    try {
      const [mvRes, ruleRes] = await Promise.all([
        fetch(`${API}/models/versions?tenant_id=${encodeURIComponent(tenantId)}`),
        fetch(`${API}/rules?tenant_id=${encodeURIComponent(tenantId)}&active_only=false`),
      ]);
      const mvJson = await mvRes.json().catch(() => ({}));
      const ruleJson = await ruleRes.json().catch(() => ({}));

      const mv = ((mvJson?.data || {}).model_versions || []) as Array<{ id: string; name: string; is_active?: boolean }>;
      const mappedMv = mv.map((m) => ({ id: m.id, name: m.name }));
      setModelVersions(mappedMv);

      if (!selectedModelVersionId && mappedMv.length > 0) {
        const active = mv.find((m) => m.is_active) || mv[0];
        setSelectedModelVersionId(active.id);
      }

      const rs = ((ruleJson?.data || {}).rules || []) as Array<{ id: string; name: string; description?: string | null; is_active: boolean }>;
      setRules(rs);
    } catch {
      setError("Unable to load model versions/rules. Verify backend is running at http://127.0.0.1:8000.");
    }
  }, [tenantId, selectedModelVersionId]);

  useEffect(() => {
    loadCrudData();
  }, [loadCrudData]);

  const loadAgentData = useCallback(async () => {
    try {
      const payload = await listAdminAgents();
      const loadedAgents = payload?.data?.agents || [];
      setAgents(loadedAgents);
      setAvailableSkills(payload?.data?.available_skills || []);
      setAgentSkillDrafts((prev) => {
        const next: Record<string, string> = { ...prev };
        loadedAgents.forEach((agent) => {
          if (typeof next[agent.id] === "undefined") {
            next[agent.id] = (agent.skills || []).join(", ");
          }
        });
        Object.keys(next).forEach((key) => {
          if (!loadedAgents.find((agent) => agent.id === key)) {
            delete next[key];
          }
        });
        return next;
      });
    } catch {
      setError("Unable to load agents/skills. Verify /api/v1/admin/agents is reachable.");
    }
  }, []);

  useEffect(() => {
    loadAgentData();
  }, [loadAgentData]);

  const parseSkillsInput = (text: string) =>
    text
      .split(",")
      .map((skill) => skill.trim())
      .filter(Boolean);

  const addAgent = async () => {
    if (!newAgentId.trim() || !newAgentRole.trim()) return;
    setLoading(true);
    setError(null);
    try {
      await createAdminAgent({
        id: newAgentId.trim(),
        role: newAgentRole.trim(),
        skills: parseSkillsInput(newAgentSkills),
      });
      setNewAgentId("");
      setNewAgentRole("");
      setNewAgentSkills("");
      await loadAgentData();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Create agent failed");
    } finally {
      setLoading(false);
    }
  };

  const saveAgentSkills = async (agentId: string) => {
    setLoading(true);
    setError(null);
    try {
      await updateAdminAgentSkills(agentId, { skills: parseSkillsInput(agentSkillDrafts[agentId] || "") });
      await loadAgentData();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Update skills failed");
    } finally {
      setLoading(false);
    }
  };

  const removeAgent = async (agentId: string) => {
    setLoading(true);
    setError(null);
    try {
      await deleteAdminAgent(agentId);
      await loadAgentData();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Remove agent failed");
    } finally {
      setLoading(false);
    }
  };

  const createRule = async () => {
    if (!selectedModelVersionId || !newRuleName.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const createRes = await fetch(`${API}/rules`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tenant_id: tenantId,
          model_version_id: selectedModelVersionId,
          name: newRuleName.trim(),
          description: newRuleDescription.trim() || null,
        }),
      });
      const createJson = await createRes.json().catch(() => ({}));
      if (!createRes.ok) throw new Error(createJson?.detail || `HTTP ${createRes.status}`);
      const ruleId = createJson?.data?.rule_id as string;

      if (ruleId && newRuleCondition.trim()) {
        await fetch(`${API}/rules/${ruleId}/conditions`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ tenant_id: tenantId, expression: newRuleCondition.trim() }),
        });
      }

      if (ruleId && newRuleImpact.trim()) {
        await fetch(`${API}/rules/${ruleId}/impacts`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ tenant_id: tenantId, impact: newRuleImpact.trim() }),
        });
      }

      setNewRuleName("");
      setNewRuleDescription("");
      setNewRuleCondition("");
      setNewRuleImpact("");
      await loadCrudData();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Create rule failed");
    } finally {
      setLoading(false);
    }
  };

  const startEdit = (rule: { id: string; name: string; description?: string | null }) => {
    setEditingRuleId(rule.id);
    setEditingName(rule.name || "");
    setEditingDescription(rule.description || "");
  };

  const saveEdit = async () => {
    if (!editingRuleId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API}/rules/${editingRuleId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: editingName.trim(), description: editingDescription.trim() }),
      });
      const json = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(json?.detail || `HTTP ${res.status}`);
      setEditingRuleId(null);
      await loadCrudData();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Update rule failed");
    } finally {
      setLoading(false);
    }
  };

  const removeRule = async (ruleId: string) => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API}/rules/${ruleId}`, { method: "DELETE" });
      const json = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(json?.detail || `HTTP ${res.status}`);
      await loadCrudData();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Delete rule failed");
    } finally {
      setLoading(false);
    }
  };

  const runFullDemoFlow = async () => {
    setLoading(true);
    setError(null);
    setDemoTrace(null);
    try {
      const inputText = "Demo run. Revenue: 1300M. Operating costs: 700M. Margin: 12%. Technical debt: 65%.";

      const intakeRes = await fetch(`${API}/intake`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tenant_id: tenantId, model_version_id: "", text: inputText }),
      });
      const intakeJson = await intakeRes.json();
      if (!intakeRes.ok) throw new Error(intakeJson?.detail || `Intake HTTP ${intakeRes.status}`);

      const sessionId = intakeJson?.data?.session_id as string;
      if (!sessionId) throw new Error("No session_id returned from intake");

      const [stateRes, contribRes, restructuringRes, overviewRes] = await Promise.all([
        fetch(`${API}/advisory/skills/state/${sessionId}`),
        fetch(`${API}/advisory/skills/contributions/${sessionId}`),
        fetch(`${API}/advisory/skills/restructuring/${sessionId}`),
        fetch(`${API}/admin/command`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ tenant_id: tenantId, text: "Show platform overview" }),
        }),
      ]);

      const stateJson = await stateRes.json().catch(() => ({}));
      const contribJson = await contribRes.json().catch(() => ({}));
      const restructuringJson = await restructuringRes.json().catch(() => ({}));
      const overviewJson = await overviewRes.json().catch(() => ({}));

      const trace = {
        status: "ok",
        started_at: new Date().toISOString(),
        tenant_id: tenantId,
        demo_input_text: inputText,
        step_1_intake: {
          session_id: sessionId,
          extracted_input: intakeJson?.data?.extracted_input,
          state: intakeJson?.data?.snapshot?.state,
          total_score: intakeJson?.data?.snapshot?.score_breakdown?.total_score,
        },
        step_2_openclaw_advisory: {
          state_endpoint_ok: stateRes.ok,
          contributions_endpoint_ok: contribRes.ok,
          restructuring_endpoint_ok: restructuringRes.ok,
          advisory_state: stateJson?.data?.state,
          contributions_count: Array.isArray(contribJson?.data?.contributions) ? contribJson.data.contributions.length : 0,
          restructuring_actions_count: Array.isArray(restructuringJson?.data?.restructuring_actions)
            ? restructuringJson.data.restructuring_actions.length
            : 0,
        },
        step_3_admin_overview: {
          endpoint_ok: overviewRes.ok,
          sessions: overviewJson?.data?.overview?.sessions,
          active_model_version: overviewJson?.data?.overview?.active_model_version,
          active_rules: overviewJson?.data?.overview?.active_rules,
        },
      };

      setDemoTrace(trace);
      setResponse(trace);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Demo flow failed");
    } finally {
      setLoading(false);
    }
  };

  const stepStatus = (() => {
    if (!demoTrace) return null;
    const intake = (demoTrace.step_1_intake || {}) as Record<string, unknown>;
    const advisory = (demoTrace.step_2_openclaw_advisory || {}) as Record<string, unknown>;
    const overview = (demoTrace.step_3_admin_overview || {}) as Record<string, unknown>;

    const intakeOk = Boolean(intake.session_id) && typeof intake.state === "string";
    const advisoryOk =
      advisory.state_endpoint_ok === true &&
      advisory.contributions_endpoint_ok === true &&
      advisory.restructuring_endpoint_ok === true;
    const adminOk = overview.endpoint_ok === true && typeof overview.sessions !== "undefined";

    return [
      { name: "1) STRATEGOS Intake", ok: intakeOk, detail: intakeOk ? `state: ${String(intake.state)}` : "failed" },
      {
        name: "2) OpenClaw Advisory",
        ok: advisoryOk,
        detail: advisoryOk
          ? `contrib: ${String(advisory.contributions_count ?? 0)}, actions: ${String(advisory.restructuring_actions_count ?? 0)}`
          : "one or more advisory calls failed",
      },
      {
        name: "3) Admin Overview",
        ok: adminOk,
        detail: adminOk ? `sessions: ${String(overview.sessions ?? 0)}, rules: ${String(overview.active_rules ?? 0)}` : "overview unavailable",
      },
    ];
  })();

  return (
    <div className="min-h-screen bg-[#030712] text-white p-8">
      <div className="max-w-6xl mx-auto space-y-6">
        <h1 className="text-2xl font-bold">STRATEGOS Internal Admin Portal</h1>
        <p className="text-sm text-gray-400">Internal-only control plane for platform operators. This is separate from customer-facing dashboard admin.</p>

        <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
          <input
            value={tenantId}
            onChange={(e) => setTenantId(e.target.value)}
            placeholder="Tenant UUID"
            className="md:col-span-3 bg-[#0a0f1c] border border-[#1e293b] rounded-xl px-4 py-3 text-sm"
          />
          <button
            onClick={() => setCommand("Show platform overview")}
            className="md:col-span-2 bg-[#0a0f1c] border border-[#1e293b] rounded-xl px-4 py-3 text-sm hover:border-amber-500/40"
          >
            Reset to Overview
          </button>
        </div>

        <div className="flex flex-wrap gap-2">
          {quickCommands.map((c) => (
            <button
              key={c}
              onClick={() => setCommand(c)}
              className="text-xs px-3 py-1.5 rounded border border-[#1e293b] text-gray-300 hover:border-amber-500/40"
            >
              {c}
            </button>
          ))}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-6 gap-4 items-start">
          <textarea
            value={command}
            onChange={(e) => setCommand(e.target.value)}
            rows={4}
            className="md:col-span-5 bg-[#0a0f1c] border border-[#1e293b] rounded-xl px-4 py-3 text-sm"
          />
          <button
            onClick={runCommand}
            disabled={loading || !command.trim()}
            className="md:col-span-1 bg-amber-500/90 text-[#060a14] font-semibold rounded-xl px-4 py-3 text-sm disabled:opacity-50"
          >
            {loading ? "Running…" : "Run"}
          </button>
        </div>

        <div className="border border-[#1e293b] rounded-xl bg-[#0a0f1c] p-4">
          <p className="text-sm font-semibold mb-2">One-click Validation</p>
          <p className="text-xs text-gray-500 mb-3">Runs full chain: STRATEGOS intake → OpenClaw advisory skills → admin overview.</p>
          <button
            onClick={runFullDemoFlow}
            disabled={loading}
            className="px-4 py-2 bg-[#0f172a] border border-[#1e293b] rounded-lg text-sm hover:border-amber-500/40 disabled:opacity-50"
          >
            {loading ? "Running full flow…" : "Run Full Demo Flow"}
          </button>
        </div>

        <div className="border border-[#1e293b] rounded-xl bg-[#0a0f1c] p-4 space-y-4">
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <div>
              <p className="text-sm font-semibold">Rule CRUD Console</p>
              <p className="text-xs text-gray-500">Create, update, and delete rules from the internal admin portal.</p>
            </div>
            <button
              onClick={loadCrudData}
              disabled={loading}
              className="px-3 py-1.5 text-xs border border-[#1e293b] rounded-lg hover:border-amber-500/40 disabled:opacity-50"
            >
              Refresh
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <select
              value={selectedModelVersionId}
              onChange={(e) => setSelectedModelVersionId(e.target.value)}
              className="bg-[#060a14] border border-[#1e293b] rounded-lg px-3 py-2 text-sm"
            >
              <option value="">Select model version</option>
              {modelVersions.map((mv) => (
                <option key={mv.id} value={mv.id}>{mv.name}</option>
              ))}
            </select>
            <input
              value={newRuleName}
              onChange={(e) => setNewRuleName(e.target.value)}
              placeholder="New rule name"
              className="bg-[#060a14] border border-[#1e293b] rounded-lg px-3 py-2 text-sm"
            />
            <input
              value={newRuleDescription}
              onChange={(e) => setNewRuleDescription(e.target.value)}
              placeholder="Rule description"
              className="bg-[#060a14] border border-[#1e293b] rounded-lg px-3 py-2 text-sm"
            />
            <input
              value={newRuleCondition}
              onChange={(e) => setNewRuleCondition(e.target.value)}
              placeholder="Condition (e.g. technical_debt > 70)"
              className="bg-[#060a14] border border-[#1e293b] rounded-lg px-3 py-2 text-sm"
            />
            <input
              value={newRuleImpact}
              onChange={(e) => setNewRuleImpact(e.target.value)}
              placeholder="Impact (e.g. 12 or state_impact +15)"
              className="bg-[#060a14] border border-[#1e293b] rounded-lg px-3 py-2 text-sm md:col-span-2"
            />
          </div>

          <button
            onClick={createRule}
            disabled={loading || !selectedModelVersionId || !newRuleName.trim()}
            className="px-4 py-2 text-sm bg-amber-500/90 text-[#060a14] rounded-lg font-semibold disabled:opacity-50"
          >
            Add Rule
          </button>

          <div className="space-y-2">
            {rules.map((rule) => (
              <div key={rule.id} className="border border-[#1e293b] rounded-lg p-3">
                {editingRuleId === rule.id ? (
                  <div className="space-y-2">
                    <input
                      value={editingName}
                      onChange={(e) => setEditingName(e.target.value)}
                      className="w-full bg-[#060a14] border border-[#1e293b] rounded px-2 py-1 text-sm"
                    />
                    <input
                      value={editingDescription}
                      onChange={(e) => setEditingDescription(e.target.value)}
                      className="w-full bg-[#060a14] border border-[#1e293b] rounded px-2 py-1 text-sm"
                    />
                    <div className="flex items-center gap-3">
                      <button onClick={saveEdit} disabled={loading} className="text-xs text-amber-400 hover:underline disabled:opacity-50">Save</button>
                      <button onClick={() => setEditingRuleId(null)} className="text-xs text-gray-400 hover:underline">Cancel</button>
                    </div>
                  </div>
                ) : (
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <p className="text-sm text-white font-medium">{rule.name}</p>
                      <p className="text-xs text-gray-500">{rule.description || "No description"}</p>
                      <p className={`text-[10px] mt-1 ${rule.is_active ? "text-green-400" : "text-gray-500"}`}>{rule.is_active ? "Active" : "Inactive"}</p>
                    </div>
                    <div className="flex items-center gap-3">
                      <button onClick={() => startEdit(rule)} className="text-xs text-amber-400 hover:underline">Edit</button>
                      <button onClick={() => removeRule(rule.id)} disabled={loading} className="text-xs text-red-400 hover:underline disabled:opacity-50">Delete</button>
                    </div>
                  </div>
                )}
              </div>
            ))}
            {rules.length === 0 && <p className="text-xs text-gray-500">No rules loaded for this tenant.</p>}
          </div>
        </div>

        <div className="border border-[#1e293b] rounded-xl bg-[#0a0f1c] p-4 space-y-4">
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <div>
              <p className="text-sm font-semibold">Agent & Skills Management</p>
              <p className="text-xs text-gray-500">Add or remove advisory agents and update skills for each agent.</p>
            </div>
            <button
              onClick={loadAgentData}
              disabled={loading}
              className="px-3 py-1.5 text-xs border border-[#1e293b] rounded-lg hover:border-amber-500/40 disabled:opacity-50"
            >
              Refresh
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <input
              value={newAgentId}
              onChange={(e) => setNewAgentId(e.target.value)}
              placeholder="Agent id (e.g. operations_advisor)"
              className="bg-[#060a14] border border-[#1e293b] rounded-lg px-3 py-2 text-sm"
            />
            <input
              value={newAgentRole}
              onChange={(e) => setNewAgentRole(e.target.value)}
              placeholder="Agent role"
              className="bg-[#060a14] border border-[#1e293b] rounded-lg px-3 py-2 text-sm"
            />
            <input
              value={newAgentSkills}
              onChange={(e) => setNewAgentSkills(e.target.value)}
              placeholder="Skills (comma-separated)"
              className="bg-[#060a14] border border-[#1e293b] rounded-lg px-3 py-2 text-sm"
            />
          </div>

          <button
            onClick={addAgent}
            disabled={loading || !newAgentId.trim() || !newAgentRole.trim()}
            className="px-4 py-2 text-sm bg-amber-500/90 text-[#060a14] rounded-lg font-semibold disabled:opacity-50"
          >
            Add Agent
          </button>

          {availableSkills.length > 0 && (
            <p className="text-xs text-gray-500">
              Available skills: {availableSkills.join(", ")}
            </p>
          )}

          <div className="space-y-2">
            {agents.map((agent) => (
              <div key={agent.id} className="border border-[#1e293b] rounded-lg p-3 space-y-2">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-sm text-white font-medium">{agent.id}</p>
                    <p className="text-xs text-gray-500">{agent.role}</p>
                  </div>
                  <button
                    onClick={() => removeAgent(agent.id)}
                    disabled={loading}
                    className="text-xs text-red-400 hover:underline disabled:opacity-50"
                  >
                    Remove
                  </button>
                </div>
                <input
                  value={agentSkillDrafts[agent.id] || ""}
                  onChange={(e) => setAgentSkillDrafts((prev) => ({ ...prev, [agent.id]: e.target.value }))}
                  className="w-full bg-[#060a14] border border-[#1e293b] rounded px-2 py-1 text-sm"
                  placeholder="Comma-separated skills"
                />
                <button
                  onClick={() => saveAgentSkills(agent.id)}
                  disabled={loading}
                  className="text-xs text-amber-400 hover:underline disabled:opacity-50"
                >
                  Save Skills
                </button>
              </div>
            ))}
            {agents.length === 0 && <p className="text-xs text-gray-500">No configured agents found.</p>}
          </div>
        </div>

        {error && <div className="text-red-400 text-sm">{error}</div>}

        <div className="border border-[#1e293b] rounded-xl bg-[#0a0f1c] p-4">
          <p className="text-sm font-semibold mb-3">Response</p>
          <pre className="text-xs text-gray-300 whitespace-pre-wrap break-words">{JSON.stringify(response, null, 2)}</pre>
        </div>

        {demoTrace && (
          <div className="border border-[#1e293b] rounded-xl bg-[#0a0f1c] p-4">
            <p className="text-sm font-semibold mb-3">Demo Trace</p>
            {stepStatus && (
              <div className="mb-4 space-y-2">
                {stepStatus.map((s) => (
                  <div key={s.name} className="flex items-center justify-between gap-4 border border-[#1e293b] rounded-lg px-3 py-2">
                    <div>
                      <p className="text-xs text-gray-200 font-medium">{s.name}</p>
                      <p className="text-[11px] text-gray-500">{s.detail}</p>
                    </div>
                    <span
                      className={`text-[10px] px-2 py-1 rounded-full border ${
                        s.ok
                          ? "text-green-300 border-green-700 bg-green-950/40"
                          : "text-red-300 border-red-700 bg-red-950/40"
                      }`}
                    >
                      {s.ok ? "PASS" : "FAIL"}
                    </span>
                  </div>
                ))}
              </div>
            )}
            <pre className="text-xs text-gray-300 whitespace-pre-wrap break-words">{JSON.stringify(demoTrace, null, 2)}</pre>
          </div>
        )}
      </div>
    </div>
  );
}
