"use client";

import React from "react";

interface Props {
  value: number;
  max?: number;
  label?: string;
  size?: number;
}

export default function GaugeChart({ value, max = 200, label, size = 160 }: Props) {
  const pct = Math.min(Math.max(value / max, 0), 1);
  const angle = pct * 180;
  const r = size / 2 - 16;
  const cx = size / 2;
  const cy = size / 2 + 8;

  const x1 = cx - r;
  const x2 = cx + r;

  // arc endpoint
  const rad = ((180 - angle) * Math.PI) / 180;
  const ax = cx + r * Math.cos(rad);
  const ay = cy - r * Math.sin(rad);
  const largeArc = angle > 180 ? 1 : 0;

  const color = pct < 0.4 ? "#22c55e" : pct < 0.7 ? "#eab308" : "#ef4444";

  return (
    <div className="flex flex-col items-center">
      <svg width={size} height={size / 2 + 24} viewBox={`0 0 ${size} ${size / 2 + 24}`}>
        {/* background arc */}
        <path
          d={`M ${x1} ${cy} A ${r} ${r} 0 0 1 ${x2} ${cy}`}
          fill="none"
          stroke="#1e293b"
          strokeWidth={10}
          strokeLinecap="round"
        />
        {/* value arc */}
        <path
          d={`M ${x1} ${cy} A ${r} ${r} 0 ${largeArc} 1 ${ax} ${ay}`}
          fill="none"
          stroke={color}
          strokeWidth={10}
          strokeLinecap="round"
        />
        <text x={cx} y={cy - 8} textAnchor="middle" className="fill-white text-xl font-bold">
          {value.toFixed(1)}
        </text>
      </svg>
      {label && <span className="text-xs text-gray-500 mt-1">{label}</span>}
    </div>
  );
}
