"use client";

import React from "react";
import {
  RadarChart as ReRadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  ResponsiveContainer,
  Tooltip,
} from "recharts";

interface Props {
  data: Array<{ metric: string; value: number; fullMark?: number }>;
  height?: number;
}

export default function RadarMetricChart({ data, height = 280 }: Props) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <ReRadarChart data={data} outerRadius="70%">
        <PolarGrid stroke="#1e293b" />
        <PolarAngleAxis dataKey="metric" tick={{ fill: "#94a3b8", fontSize: 11 }} />
        <PolarRadiusAxis tick={{ fill: "#64748b", fontSize: 10 }} axisLine={false} />
        <Tooltip
          contentStyle={{ background: "#0f172a", border: "1px solid #1e293b", borderRadius: 8, fontSize: 12 }}
        />
        <Radar name="Score" dataKey="value" stroke="#eab308" fill="#eab308" fillOpacity={0.2} />
      </ReRadarChart>
    </ResponsiveContainer>
  );
}
