"use client";

import React, { useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000/api/v1";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [resetUrl, setResetUrl] = useState<string | null>(null);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setMessage(null);
    setResetUrl(null);
    try {
      const res = await fetch(`${API_BASE}/auth/password/forgot`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(typeof body?.detail === "string" ? body.detail : `HTTP ${res.status}`);
      }
      setMessage("If your account exists, a reset link has been sent.");
      if (body?.data?.reset_url) setResetUrl(String(body.data.reset_url));
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#060a14] px-4">
      <div className="w-full max-w-sm bg-[#0a0f1c] border border-[#1e293b] rounded-lg p-8">
        <h1 className="text-xl font-bold text-white">Forgot Password</h1>
        <p className="text-xs text-gray-500 mt-2">Enter your email to receive a password reset link.</p>
        <form onSubmit={onSubmit} className="mt-5 space-y-4">
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full bg-[#060a14] border border-[#1e293b] rounded px-3 py-2.5 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-amber-500/50"
            placeholder="you@company.com"
          />
          {error && <p className="text-xs text-red-400">{error}</p>}
          {message && <p className="text-xs text-green-400">{message}</p>}
          {resetUrl && (
            <a href={resetUrl} className="text-xs text-amber-400 hover:underline">
              Reset now (email fallback link)
            </a>
          )}
          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 bg-amber-500/90 text-[#060a14] font-semibold rounded text-sm hover:bg-amber-500 transition-colors disabled:opacity-50"
          >
            {loading ? "Sending..." : "Send Reset Link"}
          </button>
        </form>
      </div>
    </div>
  );
}
