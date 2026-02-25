"use client";

import React from "react";

interface Phase {
  name: string;
  owner: string;
  horizon: string;
  status?: "pending" | "active" | "complete";
}

interface Props {
  phases: Phase[];
}

const statusColor: Record<string, string> = {
  pending: "bg-gray-700 border-gray-600",
  active: "bg-amber-900/40 border-amber-600/50",
  complete: "bg-green-900/40 border-green-600/50",
};

export default function RoadmapTimeline({ phases }: Props) {
  return (
    <div className="relative flex flex-col gap-4 pl-6">
      {/* vertical line */}
      <div className="absolute left-2.5 top-1 bottom-1 w-px bg-[#1e293b]" />
      {phases.map((p, i) => (
        <div key={i} className="relative flex gap-4 items-start">
          <div className="absolute -left-3.5 top-1.5 w-3 h-3 rounded-full bg-amber-500 border-2 border-[#0a0f1c] z-10" />
          <div className={`flex-1 rounded-lg border p-4 ${statusColor[p.status || "pending"]}`}>
            <div className="flex items-center justify-between mb-1">
              <span className="text-sm font-semibold text-white">{p.name}</span>
              <span className="text-[10px] uppercase text-gray-400 tracking-wider">{p.horizon}</span>
            </div>
            <span className="text-xs text-gray-500">Owner: {p.owner}</span>
          </div>
        </div>
      ))}
    </div>
  );
}
