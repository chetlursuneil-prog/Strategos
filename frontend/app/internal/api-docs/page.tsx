"use client";

import React, { useEffect, useMemo, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000/api/v1";

type OpenApiPathItem = Record<string, { summary?: string; description?: string }>;

export default function InternalApiDocsPage() {
  const [paths, setPaths] = useState<Record<string, OpenApiPathItem>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const run = async () => {
      setLoading(true);
      setError(null);
      try {
        const base = API.replace(/\/api\/v1$/i, "");
        const res = await fetch(`${base}/api/v1/openapi.json`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json = await res.json();
        setPaths((json?.paths || {}) as Record<string, OpenApiPathItem>);
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : "Failed to load OpenAPI");
      } finally {
        setLoading(false);
      }
    };
    run();
  }, []);

  const rows = useMemo(() => {
    const out: Array<{ method: string; path: string; summary: string }> = [];
    for (const [path, item] of Object.entries(paths)) {
      for (const [method, operation] of Object.entries(item || {})) {
        out.push({ method: method.toUpperCase(), path, summary: operation?.summary || operation?.description || "" });
      }
    }
    return out.sort((a, b) => a.path.localeCompare(b.path) || a.method.localeCompare(b.method));
  }, [paths]);

  const backendRoot = API.replace(/\/api\/v1$/i, "");

  return (
    <div className="min-h-screen bg-[#030712] text-white p-8">
      <div className="max-w-6xl mx-auto space-y-6">
        <h1 className="text-2xl font-bold">STRATEGOS Internal API Docs</h1>
        <p className="text-sm text-gray-400">Internal reference for all backend endpoints. This is for platform/admin use.</p>
        <div className="flex flex-wrap gap-3 text-sm">
          <a href={`${backendRoot}/api/v1/docs`} target="_blank" rel="noreferrer" className="px-3 py-2 rounded border border-[#1e293b] hover:border-amber-500/40">Open Swagger UI</a>
          <a href={`${backendRoot}/api/v1/redoc`} target="_blank" rel="noreferrer" className="px-3 py-2 rounded border border-[#1e293b] hover:border-amber-500/40">Open ReDoc</a>
          <a href={`${backendRoot}/api/v1/openapi.json`} target="_blank" rel="noreferrer" className="px-3 py-2 rounded border border-[#1e293b] hover:border-amber-500/40">Open OpenAPI JSON</a>
        </div>

        {loading && <p className="text-gray-400">Loading endpoint catalog…</p>}
        {error && <p className="text-red-400">{error}</p>}

        {!loading && !error && (
          <div className="border border-[#1e293b] rounded-xl overflow-hidden">
            <div className="grid grid-cols-12 bg-[#0a0f1c] text-xs uppercase tracking-wider text-gray-500 px-4 py-3">
              <div className="col-span-2">Method</div>
              <div className="col-span-6">Path</div>
              <div className="col-span-4">Summary</div>
            </div>
            {rows.map((r, i) => (
              <div key={`${r.method}-${r.path}-${i}`} className="grid grid-cols-12 px-4 py-3 text-sm border-t border-[#0f172a]">
                <div className="col-span-2 text-amber-400 font-semibold">{r.method}</div>
                <div className="col-span-6 text-gray-200">{r.path}</div>
                <div className="col-span-4 text-gray-400">{r.summary || "-"}</div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
