"use client";

import React from "react";

interface Props {
  label: string;
  value: string | number;
  sub?: string;
  color?: string; // accent-gold | green-400 | red-400 | blue-400
}

export default function KPICard({ label, value, sub, color = "accent-gold" }: Props) {
  const colorMap: Record<string, string> = {
    "accent-gold": "text-amber-400",
    "green-400": "text-green-400",
    "red-400": "text-red-400",
    "blue-400": "text-blue-400",
    "amber-400": "text-amber-400",
  };
  const textColor = colorMap[color] || "text-amber-400";

  return (
    <div className="bg-[#131a2b] border border-[#1e293b] rounded-lg p-5 flex flex-col gap-1">
      <span className="text-xs text-gray-500 uppercase tracking-wider font-medium">{label}</span>
      <span className={`text-2xl font-bold ${textColor}`}>{value}</span>
      {sub && <span className="text-xs text-gray-500">{sub}</span>}
    </div>
  );
}
