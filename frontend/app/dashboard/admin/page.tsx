"use client";

import React, { useEffect, useState, useRef } from "react";
import { useAuth, useRequireRole } from "@/lib/auth";

const API = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000/api/v1";

/* ─── Types ───────────────────────────────────────────────────────── */
interface CmdResult {
  action: string;
  message: string;
  [key: string]: unknown;
}

interface OverviewData {
  model_versions: number;
  active_model_version: { id: string | null; name: string | null };
  active_rules: number;
  sessions: number;
  state_definitions: number;
  audit_events: number;
  recent_activity: Array<{ action: string; actor: string; created_at: string | null }>;
}

interface ChatMsg {
  role: "user" | "system";
  text: string;
  data?: CmdResult;
}

/* ─── Sub-components ──────────────────────────────────────────────── */

function OverviewCards({ data }: { data: OverviewData }) {
  const cards = [
    { label: "Model Versions", value: data.model_versions },
    { label: "Active Model", value: data.active_model_version?.name || "None" },
    { label: "Active Rules", value: data.active_rules },
    { label: "Sessions", value: data.sessions },
    { label: "State Definitions", value: data.state_definitions },
    { label: "Audit Events", value: data.audit_events },
  ];
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mt-3">
      {cards.map((c) => (
        <div key={c.label} className="bg-[#060a14] border border-[#1e293b] rounded-lg p-4">
          <p className="text-[10px] text-gray-500 uppercase tracking-wider">{c.label}</p>
          <p className="text-lg font-bold text-white mt-1">{String(c.value)}</p>
        </div>
      ))}
    </div>
  );
}

function RecentActivity({ items }: { items: Array<{ action: string; actor: string; created_at: string | null }> }) {
  if (!items.length) return <p className="text-gray-600 text-xs mt-2">No recent activity.</p>;
  return (
    <div className="mt-3 space-y-1.5">
      <p className="text-[10px] text-gray-500 uppercase tracking-wider">Recent Activity</p>
      {items.map((a, i) => (
        <div key={i} className="flex items-center gap-3 text-xs bg-[#060a14] border border-[#1e293b] rounded px-3 py-2">
          <span className="w-2 h-2 rounded-full bg-amber-400 flex-shrink-0" />
          <span className="text-white font-medium">{a.action}</span>
          <span className="text-gray-500">by {a.actor || "system"}</span>
          <span className="ml-auto text-gray-600 text-[10px]">
            {a.created_at ? new Date(a.created_at).toLocaleString() : "—"}
          </span>
        </div>
      ))}
    </div>
  );
}

function ModelVersionList({ versions }: { versions: Array<Record<string, unknown>> }) {
  if (!versions.length) return <p className="text-gray-600 text-xs mt-2">No model versions found.</p>;
  return (
    <div className="mt-3 space-y-2">
      {versions.map((v) => (
        <div key={v.id as string} className="bg-[#060a14] border border-[#1e293b] rounded-lg p-4 flex items-center justify-between">
          <div>
            <p className="text-white font-medium text-sm">{v.name as string}</p>
            <p className="text-gray-500 text-xs mt-0.5">{(v.description as string) || "No description"}</p>
            <p className="text-gray-600 text-[10px] mt-1 font-mono">
              {(v.id as string).slice(0, 12)}… · {v.created_at ? new Date(v.created_at as string).toLocaleDateString() : "—"}
            </p>
          </div>
          <span className={`text-xs font-medium px-3 py-1 rounded-full ${
            v.is_active
              ? "bg-green-900/40 text-green-400 border border-green-800/50"
              : "bg-gray-800/40 text-gray-500 border border-gray-700/50"
          }`}>
            {v.is_active ? "● Active" : "Inactive"}
          </span>
        </div>
      ))}
    </div>
  );
}

function RuleList({ rules }: { rules: Array<Record<string, unknown>> }) {
  if (!rules.length) return <p className="text-gray-600 text-xs mt-2">No rules found.</p>;
  return (
    <div className="mt-3 space-y-2">
      {rules.map((r) => {
        const conditions = (r.conditions || []) as Array<Record<string, unknown>>;
        const impacts = (r.impacts || []) as Array<Record<string, unknown>>;
        return (
          <div key={r.id as string} className={`bg-[#060a14] border rounded-lg p-4 ${r.is_active ? "border-[#1e293b]" : "border-red-900/30 opacity-60"}`}>
            <div className="flex items-center justify-between mb-2">
              <p className="text-white font-medium text-sm">{r.name as string}</p>
              <span className={`text-[10px] font-medium px-2 py-0.5 rounded ${r.is_active ? "bg-green-900/40 text-green-400" : "bg-red-900/40 text-red-400"}`}>
                {r.is_active ? "Active" : "Deactivated"}
              </span>
            </div>
            {(r.description as string) && <p className="text-gray-500 text-xs mb-2">{r.description as string}</p>}
            {conditions.length > 0 && (
              <div className="mb-1.5">
                <p className="text-[10px] text-gray-500 uppercase tracking-wider">Conditions</p>
                {conditions.map((c) => (
                  <p key={c.id as string} className="text-xs text-amber-300 font-mono mt-0.5">
                    {c.is_active ? "✓" : "✗"} {c.expression as string}
                  </p>
                ))}
              </div>
            )}
            {impacts.length > 0 && (
              <div>
                <p className="text-[10px] text-gray-500 uppercase tracking-wider">Impacts</p>
                {impacts.map((im) => (
                  <p key={im.id as string} className="text-xs text-blue-300 font-mono mt-0.5">→ {im.impact as string}</p>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

function StateList({ states }: { states: Array<Record<string, unknown>> }) {
  if (!states.length) return <p className="text-gray-600 text-xs mt-2">No state definitions found.</p>;
  const colorMap: Record<string, string> = {
    NORMAL: "text-green-400 border-green-800/40",
    ELEVATED_RISK: "text-amber-400 border-amber-800/40",
    CRITICAL_ZONE: "text-red-400 border-red-800/40",
  };
  return (
    <div className="mt-3 space-y-2">
      {states.map((s) => {
        const thresholds = (s.thresholds || []) as Array<Record<string, unknown>>;
        const name = s.name as string;
        const cls = colorMap[name] || "text-gray-400 border-[#1e293b]";
        return (
          <div key={s.id as string} className={`bg-[#060a14] border rounded-lg p-4 ${cls.split(" ")[1] || "border-[#1e293b]"}`}>
            <p className={`font-semibold text-sm ${cls.split(" ")[0]}`}>{name}</p>
            {(s.description as string) && <p className="text-gray-500 text-xs mt-0.5">{s.description as string}</p>}
            {thresholds.length > 0 && (
              <div className="mt-2">
                <p className="text-[10px] text-gray-500 uppercase tracking-wider">Thresholds</p>
                {thresholds.map((t) => (
                  <p key={t.id as string} className="text-xs text-gray-300 font-mono mt-0.5">{t.threshold as string}</p>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

function AuditList({ logs }: { logs: Array<Record<string, unknown>> }) {
  if (!logs.length) return <p className="text-gray-600 text-xs mt-2">No audit events found.</p>;
  return (
    <div className="mt-3 space-y-1.5">
      {logs.map((log, i) => {
        const payload = (log.payload || {}) as Record<string, unknown>;
        return (
          <div key={i} className="bg-[#060a14] border border-[#1e293b] rounded-lg p-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className={`w-2 h-2 rounded-full flex-shrink-0 ${(log.action as string) === "ENGINE_RUN" ? "bg-amber-400" : "bg-blue-400"}`} />
                <span className="text-white font-medium text-xs">{log.action as string}</span>
                <span className="text-gray-500 text-xs">by {(log.actor as string) || "system"}</span>
              </div>
              <span className="text-gray-600 text-[10px]">
                {log.created_at ? new Date(log.created_at as string).toLocaleString() : "—"}
              </span>
            </div>
            {payload.state != null && (
              <p className="text-[10px] text-gray-500 mt-1">
                State: <span className="text-gray-300">{String(payload.state)}</span>
                {payload.total_score != null && (
                  <>{" "}· Score: <span className="text-amber-400">{String(payload.total_score)}</span></>
                )}
              </p>
            )}
            {payload.original_text != null && (
              <p className="text-[10px] text-gray-500 mt-0.5 truncate max-w-md">
                Input: {String(payload.original_text).slice(0, 100)}
              </p>
            )}
          </div>
        );
      })}
    </div>
  );
}

function HelpSection({ commands }: { commands: Array<{ category: string; examples: string[] }> }) {
  return (
    <div className="mt-3 space-y-3">
      {commands.map((cat) => (
        <div key={cat.category} className="bg-[#060a14] border border-[#1e293b] rounded-lg p-4">
          <p className="text-amber-400 font-medium text-xs uppercase tracking-wider mb-2">{cat.category}</p>
          <div className="space-y-1">
            {cat.examples.map((ex, i) => (
              <p key={i} className="text-gray-300 text-xs font-mono">
                <span className="text-gray-500">›</span> {ex}
              </p>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function SessionList({ sessions }: { sessions: Array<Record<string, unknown>> }) {
  if (!sessions.length) return <p className="text-gray-600 text-xs mt-2">No sessions found.</p>;
  return (
    <div className="mt-3 space-y-1.5">
      {sessions.map((s) => (
        <div key={s.id as string} className="bg-[#060a14] border border-[#1e293b] rounded px-3 py-2 flex items-center justify-between text-xs">
          <span className="text-white font-medium">{(s.name as string) || "Untitled"}</span>
          <span className="text-gray-600 text-[10px]">{s.created_at ? new Date(s.created_at as string).toLocaleString() : "—"}</span>
        </div>
      ))}
    </div>
  );
}

/* ─── Response renderer ───────────────────────────────────────────── */
function CommandResponse({ data }: { data: CmdResult }) {
  const { action } = data;
  if (action === "platform_overview") {
    const ov = data.overview as OverviewData;
    return (
      <>
        <OverviewCards data={ov} />
        <RecentActivity items={ov.recent_activity || []} />
      </>
    );
  }
  if (action === "list_model_versions") return <ModelVersionList versions={(data.model_versions || []) as Array<Record<string, unknown>>} />;
  if (action === "list_rules") return <RuleList rules={(data.rules || []) as Array<Record<string, unknown>>} />;
  if (action === "list_states") return <StateList states={(data.states || []) as Array<Record<string, unknown>>} />;
  if (action === "list_audit_logs") return <AuditList logs={(data.audit_logs || []) as Array<Record<string, unknown>>} />;
  if (action === "list_sessions") return <SessionList sessions={(data.sessions || []) as Array<Record<string, unknown>>} />;
  if (action === "help") return <HelpSection commands={(data.commands || []) as Array<{ category: string; examples: string[] }>} />;
  return null;
}

/* ─── Quick action buttons ────────────────────────────────────────── */
const QUICK_ACTIONS = [
  { label: "Platform Overview", command: "Show platform overview" },
  { label: "Model Versions", command: "Show all model versions" },
  { label: "Rules", command: "Show all rules" },
  { label: "States", command: "Show state definitions" },
  { label: "Sessions", command: "Show all sessions" },
  { label: "Audit Logs", command: "Show audit logs" },
  { label: "Help", command: "Help" },
];

/* ─── Main Page ───────────────────────────────────────────────────── */
export default function AdminPage() {
  const { user } = useAuth();
  const isAdmin = useRequireRole("admin");
  const [messages, setMessages] = useState<ChatMsg[]>([
    {
      role: "system",
      text: "Welcome to the Admin Command Center. Manage your STRATEGOS platform using natural language.\n\nTry:\n• \"Show platform overview\"\n• \"Create a new model version called Q2 Strategy\"\n• \"Show all rules\"\n• \"Show audit logs\"\n\nOr type \"help\" for the full command list.",
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    setTimeout(() => endRef.current?.scrollIntoView({ behavior: "smooth" }), 100);
  };

  // Auto-load overview on mount
  useEffect(() => {
    if (user && isAdmin) {
      runCommand("Show platform overview", true);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, isAdmin]);

  const runCommand = async (cmd: string, silent = false) => {
    if (!user) return;

    if (!silent) {
      setMessages((prev) => [...prev, { role: "user", text: cmd }]);
    }
    setLoading(true);
    scrollToBottom();

    try {
      const res = await fetch(`${API}/admin/command`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tenant_id: user.tenantId, text: cmd }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(String(err?.detail || `HTTP ${res.status}`));
      }

      const json = await res.json();
      const data = (json?.data || json) as CmdResult;

      setMessages((prev) => [
        ...prev,
        { role: "system", text: data.message || "Done.", data },
      ]);
    } catch (err: unknown) {
      setMessages((prev) => [
        ...prev,
        {
          role: "system",
          text: `Error: ${err instanceof Error ? err.message : "Request failed"}. Make sure the backend is running.`,
        },
      ]);
    } finally {
      setLoading(false);
      scrollToBottom();
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || loading) return;
    const cmd = input.trim();
    setInput("");
    runCommand(cmd);
  };

  if (!isAdmin) {
    return (
      <div className="py-12 text-center">
        <div className="bg-red-900/20 border border-red-800/40 rounded-lg p-8 max-w-md mx-auto">
          <p className="text-red-400 font-medium">Access Denied</p>
          <p className="text-gray-500 text-sm mt-2">Admin role required to access this portal.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-[calc(100vh-5rem)]">
      {/* Header */}
      <div className="mb-4">
        <h1 className="text-xl font-bold text-white">Admin Command Center</h1>
        <p className="text-xs text-gray-500 mt-0.5">
          Manage models, rules, states, and platform settings using natural language
        </p>
      </div>

      {/* Quick action bar */}
      <div className="flex flex-wrap gap-2 mb-4">
        {QUICK_ACTIONS.map((qa) => (
          <button
            key={qa.label}
            onClick={() => runCommand(qa.command)}
            disabled={loading}
            className="text-[11px] px-3 py-1.5 bg-[#0a0f1c] border border-[#1e293b] text-gray-400 rounded-full hover:text-amber-400 hover:border-amber-500/30 transition-colors disabled:opacity-40"
          >
            {qa.label}
          </button>
        ))}
      </div>

      {/* Message area */}
      <div className="flex-1 overflow-y-auto space-y-4 pr-2 pb-4">
        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
            <div
              className={`max-w-[90%] rounded-lg p-4 text-sm ${
                msg.role === "user"
                  ? "bg-amber-500/10 border border-amber-500/20 text-white"
                  : "bg-[#0a0f1c] border border-[#1e293b] text-gray-300"
              }`}
            >
              {msg.role === "system" && (
                <div className="flex items-center gap-2 mb-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
                  <span className="text-[10px] text-gray-500 uppercase tracking-wider font-medium">STRATEGOS Admin</span>
                </div>
              )}
              <p className="whitespace-pre-wrap">{msg.text}</p>
              {msg.data ? <CommandResponse data={msg.data} /> : null}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex justify-start">
            <div className="bg-[#0a0f1c] border border-[#1e293b] rounded-lg p-4 text-sm text-gray-500">
              <span className="animate-pulse">Processing command…</span>
            </div>
          </div>
        )}
        <div ref={endRef} />
      </div>

      {/* Input area */}
      <form onSubmit={handleSubmit} className="mt-4 flex gap-3">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder='Type a command, e.g. "Create a rule called Revenue Warning when revenue drops below 500"'
          className="flex-1 bg-[#0a0f1c] border border-[#1e293b] rounded-lg px-4 py-3 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-amber-500/50"
          disabled={loading}
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          className="px-6 py-3 bg-amber-500/90 text-[#060a14] font-semibold rounded-lg text-sm hover:bg-amber-500 transition-colors disabled:opacity-40"
        >
          Run
        </button>
      </form>
    </div>
  );
}
