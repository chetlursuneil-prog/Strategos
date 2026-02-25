/* ── API client for STRATEGOS backend ── */

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000/api/v1";

async function request<T>(path: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...opts,
    headers: { "Content-Type": "application/json", ...opts?.headers },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body?.detail ? JSON.stringify(body.detail) : `HTTP ${res.status}`);
  }
  return res.json();
}

/* ── Sessions ── */

export async function createSession(tenantId: string, modelVersionId: string, name?: string) {
  return request<{ data: { session_id: string } }>("/sessions", {
    method: "POST",
    body: JSON.stringify({ tenant_id: tenantId, model_version_id: modelVersionId, name }),
  });
}

export async function listSessions(tenantId: string) {
  return request<{ data: { sessions: Array<Record<string, unknown>> } }>(
    `/sessions?tenant_id=${encodeURIComponent(tenantId)}`
  ).catch(() => ({ data: { sessions: [] } }));
}

export async function getSessionSnapshots(sessionId: string) {
  return request<{ data: Record<string, unknown> }>(`/sessions/${sessionId}/snapshots`);
}

export async function getSessionReplay(sessionId: string) {
  return request<{ data: { events: Array<Record<string, unknown>> } }>(`/sessions/${sessionId}/replay`);
}

/* ── Engine ── */

export async function runEngine(payload: {
  tenant_id: string;
  model_version_id: string;
  session_id?: string;
  input: Record<string, number>;
}) {
  return request<Record<string, unknown>>("/engine/run", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/* ── Natural-language intake ── */

export async function submitIntake(payload: {
  tenant_id: string;
  model_version_id: string;
  text: string;
}) {
  return request<{ data: Record<string, unknown> }>("/intake", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/* ── Model versions ── */

export async function listModelVersions(tenantId?: string) {
  const qs = tenantId ? `?tenant_id=${encodeURIComponent(tenantId)}` : "";
  return request<{ data: { model_versions: Array<Record<string, unknown>> } }>(`/models/versions${qs}`);
}

/* ── Reports ── */

export function getReportUrl(sessionId: string, format: "pdf" | "csv" = "pdf") {
  return `${API_BASE}/reports/${sessionId}?format=${format}`;
}

/* ── Health ── */

export async function checkHealth() {
  return request<{ status: string }>("/health");
}

/* ── Internal Admin: Agents ── */

export type AdminAgent = {
  id: string;
  role: string;
  skills: string[];
};

export async function listAdminAgents() {
  return request<{ data: { agents: AdminAgent[]; available_skills: string[] } }>("/admin/agents");
}

export async function createAdminAgent(payload: { id: string; role: string; skills: string[] }) {
  return request<{ data: { agent: AdminAgent } }>("/admin/agents", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function updateAdminAgentSkills(agentId: string, payload: { skills: string[] }) {
  return request<{ data: { agent: AdminAgent; unknown_skills?: string[] } }>(`/admin/agents/${encodeURIComponent(agentId)}/skills`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export async function deleteAdminAgent(agentId: string) {
  return request<{ data: { agent_id: string } }>(`/admin/agents/${encodeURIComponent(agentId)}`, {
    method: "DELETE",
  });
}
