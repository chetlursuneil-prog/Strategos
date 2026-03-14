"use client";

import React, { Suspense, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000/api/v1";

function VerifyEmailInner() {
  const params = useSearchParams();
  const token = useMemo(() => (params.get("token") || "").trim(), [params]);
  const [status, setStatus] = useState<"idle" | "loading" | "success" | "error">("idle");
  const [message, setMessage] = useState("");

  useEffect(() => {
    const verify = async () => {
      if (!token) {
        setStatus("error");
        setMessage("Missing verification token.");
        return;
      }
      setStatus("loading");
      try {
        const res = await fetch(`${API_BASE}/auth/verify-email`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ token }),
        });
        const body = await res.json().catch(() => ({}));
        if (!res.ok) {
          throw new Error(typeof body?.detail === "string" ? body.detail : `HTTP ${res.status}`);
        }
        const canLogin = Boolean(body?.data?.can_login);
        setStatus("success");
        setMessage(
          canLogin
            ? "Email verified successfully. You can now sign in."
            : "Email verified. Your account is now waiting for admin approval."
        );
      } catch (err: unknown) {
        setStatus("error");
        setMessage(err instanceof Error ? err.message : "Verification failed");
      }
    };
    verify();
  }, [token]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#060a14] px-4">
      <div className="w-full max-w-sm bg-[#0a0f1c] border border-[#1e293b] rounded-lg p-8">
        <h1 className="text-xl font-bold text-white">Verify Email</h1>
        {status === "loading" && <p className="text-xs text-gray-400 mt-4">Verifying your email...</p>}
        {status === "success" && <p className="text-xs text-green-400 mt-4">{message}</p>}
        {status === "error" && <p className="text-xs text-red-400 mt-4">{message}</p>}
        <p className="text-xs mt-6">
          <Link href="/login" className="text-amber-400 hover:underline">Back to login</Link>
        </p>
      </div>
    </div>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center bg-[#060a14] px-4">
          <div className="w-full max-w-sm bg-[#0a0f1c] border border-[#1e293b] rounded-lg p-8 text-xs text-gray-400">
            Loading verification...
          </div>
        </div>
      }
    >
      <VerifyEmailInner />
    </Suspense>
  );
}
