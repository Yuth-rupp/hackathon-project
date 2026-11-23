"use client";

import React from "react";
import {
  ResponsiveContainer,
  ComposedChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  Cell,
} from "recharts";

export interface HourlyRainPoint {
  time: string;
  precipitation_mm: number | null;
  precipitation_probability_pct: number | null;
}

export interface HourlyRainChartProps {
  data: HourlyRainPoint[];
  title?: string;
  subtitle?: string;
  height?: number;
  className?: string;
}

function formatHour(value: string): string {
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;

  if (d.getHours() === 0) {
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  }

  return `${String(d.getHours()).padStart(2, "0")}:00`;
}

function formatFullTime(value: string): string {
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;

  return d.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    hour12: true,
  });
}

function HourTooltip({ active, payload, label }: any) {
  if (!active || !payload || payload.length === 0) return null;

  const point: HourlyRainPoint = payload[0].payload;
  const rain = point.precipitation_mm;
  const chance = point.precipitation_probability_pct;

  return (
    <div className="rounded-lg border border-navy-800 bg-navy-950/95 p-2.5 text-xs shadow-xl backdrop-blur-md">
      <p className="mb-1 text-slate-400">{formatFullTime(label)}</p>

      <p className="flex items-center gap-2 text-white">
        <span className="h-2 w-2 rounded-full bg-cyan-400" />
        Rain amount:{" "}
        <span className="font-semibold">
          {rain === null || rain === undefined ? "—" : `${rain.toFixed(1)} mm`}
        </span>
      </p>

      <p className="mt-0.5 flex items-center gap-2 text-white">
        <span className="h-2 w-2 rounded-full bg-amber-400" />
        Rain chance:{" "}
        <span className="font-semibold">
          {chance === null || chance === undefined
            ? "—"
            : `${Math.round(chance)}%`}
        </span>
      </p>
    </div>
  );
}

export function HourlyRainChart({
  data,
  title = "Hourly Rain Forecast (Next 48 Hours)",
  subtitle = "Bars: expected rain per hour (mm). Line: chance of rain for every hour (%).",
  height = 320,
  className = "",
}: HourlyRainChartProps) {
  return (
    <div
      className={`rounded-xl border border-navy-800 bg-navy-900/60 p-5 shadow-lg backdrop-blur-md ${className}`}
    >
      <div className="mb-4">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-white">
          {title}
        </h3>
        {subtitle && (
          <p className="mt-0.5 text-xs text-slate-400">{subtitle}</p>
        )}
      </div>

      <div style={{ width: "100%", height }}>
        {data && data.length > 0 ? (
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart
              data={data}
              margin={{ top: 10, right: 10, left: -10, bottom: 0 }}
            >
              <defs>
                <linearGradient id="hrBar" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#38bdf8" stopOpacity={0.9} />
                  <stop offset="100%" stopColor="#0284c7" stopOpacity={0.35} />
                </linearGradient>
              </defs>

              <CartesianGrid
                strokeDasharray="3 3"
                stroke="#1e3a5f"
                strokeOpacity={0.5}
                vertical={false}
              />

              <XAxis
                dataKey="time"
                tickLine={false}
                interval={2}
                stroke="#64748b"
                tick={{ fill: "#94a3b8", fontSize: 10 }}
                tickFormatter={formatHour}
              />

              {/* Left axis: rain amount */}
              <YAxis
                yAxisId="mm"
                tickLine={false}
                stroke="#64748b"
                tick={{ fill: "#94a3b8", fontSize: 10 }}
                domain={[
                  0,
                  (max: number) => Math.max(1, Math.ceil(max * 10) / 10),
                ]}
                unit=" mm"
              />

              {/* Right axis: rain chance */}
              <YAxis
                yAxisId="pct"
                orientation="right"
                tickLine={false}
                stroke="#64748b"
                tick={{ fill: "#fbbf24", fontSize: 10 }}
                domain={[0, 100]}
                unit="%"
              />

              <Tooltip content={<HourTooltip />} />

              <Legend
                verticalAlign="top"
                height={28}
                iconType="circle"
                wrapperStyle={{ fontSize: 11, color: "#94a3b8" }}
              />

              <Bar
                yAxisId="mm"
                dataKey="precipitation_mm"
                name="Rain amount (mm)"
                radius={[3, 3, 0, 0]}
                minPointSize={3}
              >
                {data.map((entry, index) => (
                  <Cell
                    key={`bar-${index}`}
                    fill={
                      (entry.precipitation_mm ?? 0) === 0
                        ? "#334155"
                        : "url(#hrBar)"
                    }
                  />
                ))}
              </Bar>

              <Line
                yAxisId="pct"
                type="monotone"
                dataKey="precipitation_probability_pct"
                name="Rain chance (%)"
                stroke="#fbbf24"
                strokeWidth={2}
                dot={{ r: 2.5, fill: "#fbbf24", strokeWidth: 0 }}
                activeDot={{ r: 5 }}
                connectNulls
              />
            </ComposedChart>
          </ResponsiveContainer>
        ) : (
          <div className="flex h-full w-full items-center justify-center text-sm text-slate-500">
            No hourly forecast records are available.
          </div>
        )}
      </div>
    </div>
  );
}

export default HourlyRainChart;
