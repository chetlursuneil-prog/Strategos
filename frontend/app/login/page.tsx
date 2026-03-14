"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { AuthProvider, useAuth } from "@/lib/auth";
import type { UserRole } from "@/lib/types";

function LoginForm() {
  const { login, register } = useAuth();
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [fullName, setFullName] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [requestedRole, setRequestedRole] = useState<UserRole>("analyst");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [actionUrl, setActionUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setNotice(null);
    setActionUrl(null);

    if (mode === "signup") {
      if (password.length < 8) {
        setError("Password must be at least 8 characters.");
        return;
      }
      if (password !== confirmPassword) {
        setError("Passwords do not match.");
        return;
      }
      if (!fullName.trim()) {
        setError("Please enter your full name.");
        return;
      }
    }

    setLoading(true);
    try {
      if (mode === "signup") {
        const result = await register({
          name: fullName,
          email,
          password,
          companyName: companyName || undefined,
          role: requestedRole,
        });
        setNotice(
          `Account created. Please verify your email${result.approvalRequired ? " and wait for admin approval" : ""} before signing in.`
        );
        if (result.verificationUrl) {
          setActionUrl(result.verificationUrl);
        }
        setMode("login");
        setPassword("");
        setConfirmPassword("");
      } else {
        await login(email, password);
        router.replace("/dashboard");
        return;
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Authentication failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#060a14] px-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-10">
          <h1 className="text-2xl font-bold text-white tracking-wide">STRATEGOS</h1>
          <p className="text-xs text-gray-500 mt-1 uppercase tracking-[0.2em]">
            Enterprise Transformation Intelligence
          </p>
        </div>

        <form onSubmit={handleSubmit} className="bg-[#0a0f1c] border border-[#1e293b] rounded-lg p-8 space-y-5">
          <div className="grid grid-cols-2 gap-2 bg-[#060a14] border border-[#1e293b] rounded-md p-1">
            <button
              type="button"
              onClick={() => {
                setMode("login");
                setError(null);
              }}
              className={`py-2 text-xs rounded font-medium transition-colors ${
                mode === "login" ? "bg-amber-500/90 text-[#060a14]" : "text-gray-400 hover:text-gray-200"
              }`}
            >
              Sign In
            </button>
            <button
              type="button"
              onClick={() => {
                setMode("signup");
                setError(null);
              }}
              className={`py-2 text-xs rounded font-medium transition-colors ${
                mode === "signup" ? "bg-amber-500/90 text-[#060a14]" : "text-gray-400 hover:text-gray-200"
              }`}
            >
              Create Account
            </button>
          </div>

          {mode === "signup" && (
            <>
              <div>
                <label className="block text-xs text-gray-500 uppercase tracking-wider mb-1.5">Full Name</label>
                <input
                  type="text"
                  required
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  className="w-full bg-[#060a14] border border-[#1e293b] rounded px-3 py-2.5 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-amber-500/50"
                  placeholder="Jane Smith"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 uppercase tracking-wider mb-1.5">Company (Optional)</label>
                <input
                  type="text"
                  value={companyName}
                  onChange={(e) => setCompanyName(e.target.value)}
                  className="w-full bg-[#060a14] border border-[#1e293b] rounded px-3 py-2.5 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-amber-500/50"
                  placeholder="Acme Telecom"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 uppercase tracking-wider mb-1.5">Requested Role</label>
                <select
                  value={requestedRole}
                  onChange={(e) => setRequestedRole(e.target.value as UserRole)}
                  className="w-full bg-[#060a14] border border-[#1e293b] rounded px-3 py-2.5 text-sm text-white focus:outline-none focus:border-amber-500/50"
                >
                  <option value="analyst">Analyst</option>
                  <option value="viewer">Viewer</option>
                  <option value="admin">Admin</option>
                </select>
              </div>
            </>
          )}

          <div>
            <label className="block text-xs text-gray-500 uppercase tracking-wider mb-1.5">Email</label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full bg-[#060a14] border border-[#1e293b] rounded px-3 py-2.5 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-amber-500/50"
              placeholder="you@company.com"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 uppercase tracking-wider mb-1.5">Password</label>
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full bg-[#060a14] border border-[#1e293b] rounded px-3 py-2.5 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-amber-500/50"
              placeholder="••••••••"
            />
          </div>

          {mode === "signup" && (
            <div>
              <label className="block text-xs text-gray-500 uppercase tracking-wider mb-1.5">Confirm Password</label>
              <input
                type="password"
                required
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                className="w-full bg-[#060a14] border border-[#1e293b] rounded px-3 py-2.5 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-amber-500/50"
                placeholder="••••••••"
              />
            </div>
          )}

          {error && <p className="text-xs text-red-400">{error}</p>}
          {notice && <p className="text-xs text-green-400">{notice}</p>}
          {actionUrl && (
            <a
              href={actionUrl}
              className="inline-block text-xs text-amber-400 hover:underline"
            >
              Verify now (email fallback link)
            </a>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 bg-amber-500/90 text-[#060a14] font-semibold rounded text-sm hover:bg-amber-500 transition-colors disabled:opacity-50"
          >
            {loading ? (mode === "signup" ? "Creating account..." : "Signing in...") : (mode === "signup" ? "Create Account" : "Sign In")}
          </button>

          <div className="text-[10px] text-gray-600 text-center space-y-0.5 pt-2">
            {mode === "signup" ? (
              <>
                <p>Your signup requires email verification and may require admin approval.</p>
                <p>Use at least 8 characters for your password.</p>
              </>
            ) : (
              <>
                <p>Sign in with your registered account.</p>
                <p>If you are new, switch to Create Account.</p>
                <p><a className="text-amber-400 hover:underline" href="/forgot-password">Forgot password?</a></p>
              </>
            )}
          </div>
        </form>

        <div className="text-center mt-6">
          <a href="/" className="text-xs text-gray-600 hover:text-gray-400 transition-colors">
            ← Back to homepage
          </a>
        </div>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <AuthProvider>
      <LoginForm />
    </AuthProvider>
  );
}
