"use client";

import React from "react";

interface HeatCell {
  label: string;
  value: number; // 0–1 intensity
}

interface Props {
  rows: string[];
  cols: string[];
  cells: number[][]; // rows × cols
}

function color(v: number) {
  if (v < 0.3) return "bg-green-900/60 text-green-400";
  if (v < 0.6) return "bg-yellow-900/50 text-yellow-400";
  return "bg-red-900/50 text-red-400";
}

export default function RiskHeatmap({ rows, cols, cells }: Props) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr>
            <th className="p-2 text-left text-gray-500"></th>
            {cols.map((c) => (
              <th key={c} className="p-2 text-center text-gray-500 uppercase tracking-wider font-medium">
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, ri) => (
            <tr key={row}>
              <td className="p-2 text-gray-400 font-medium whitespace-nowrap">{row}</td>
              {cols.map((_, ci) => {
                const v = cells[ri]?.[ci] ?? 0;
                return (
                  <td key={ci} className={`p-2 text-center rounded ${color(v)}`}>
                    {(v * 100).toFixed(0)}%
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
