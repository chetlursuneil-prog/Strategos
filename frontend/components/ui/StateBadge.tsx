"use client";

import React from "react";

interface Props {
  state: "NORMAL" | "ELEVATED_RISK" | "CRITICAL_ZONE" | string;
  size?: "sm" | "md" | "lg";
}

const config: Record<string, { bg: string; text: string; label: string }> = {
  NORMAL: { bg: "bg-green-900/40 border-green-600/40", text: "text-green-400", label: "NORMAL" },
  ELEVATED_RISK: { bg: "bg-yellow-900/40 border-yellow-600/40", text: "text-yellow-400", label: "ELEVATED RISK" },
  CRITICAL_ZONE: { bg: "bg-red-900/40 border-red-600/40", text: "text-red-400", label: "CRITICAL ZONE" },
};

export default function StateBadge({ state, size = "md" }: Props) {
  const c = config[state] || config.NORMAL;
  const sizing =
    size === "sm"
      ? "px-2 py-0.5 text-[10px]"
      : size === "lg"
      ? "px-4 py-2 text-base"
      : "px-3 py-1 text-xs";

  return (
    <span className={`inline-block rounded border font-semibold tracking-wider uppercase ${c.bg} ${c.text} ${sizing}`}>
      {c.label}
    </span>
  );
}
