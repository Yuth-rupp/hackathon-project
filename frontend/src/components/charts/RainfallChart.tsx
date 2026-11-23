"use client";

import React from "react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Cell,
} from "recharts";

export interface RainfallChartProps {
  data: any[];
  xKey?: string;
  yKey?: string;
  title?: string;
  subtitle?: string;
  unit?: string;
  height?: number | string;
  className?: string;
}

export function RainfallChart({
  data,
  xKey = "time",
  yKey = "precipitation_mm",
  title = "Hourly Precipitation",
  subtitle,
  unit = "mm",
  height = 260,
  className = "",
}: RainfallChartProps) {
  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      const entry = payload[0];
      let formattedTime = label;
      try {
        const d = new Date(label);
        if (!isNaN(d.getTime())) {
          formattedTime = d.toLocaleTimeString("en-US", {
            hour: "numeric",
            hour12: true,
            month: "short",
            day: "numeric",
          });
        }
      } catch {
        // use label
      }

      return (
        <div className="rounded-lg border border-navy-800 bg-navy-950/95 p-2.5 shadow-xl backdrop-blur-md text-xs">
          <p className="text-slate-400 mb-1">{formattedTime}</p>
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-cyan-400"></span>
            <span className="font-semibold text-white">
              {Number(entry.value ?? 0).toFixed(1)} {unit}
              {Number(entry.value ?? 0) === 0 && (
                <span className="ml-1 font-normal text-slate-400">
                  (none forecast)
                </span>
              )}
            </span>
          </div>
        </div>
      );
    }
    return null;
  };

  return (
    <div
      className={`rounded-xl border border-navy-800 bg-navy-900/60 p-5 shadow-lg backdrop-blur-md ${className}`}
    >
      {(title || subtitle) && (
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold uppercase tracking-wider text-white">
              {title}
            </h3>
            {subtitle && (
              <p className="text-xs text-slate-400 mt-0.5">{subtitle}</p>
            )}
          </div>
          <span className="text-xs font-mono text-cyan-400 bg-cyan-950/50 border border-cyan-800/60 px-2 py-0.5 rounded">
            {unit}
          </span>
        </div>
      )}

      <div style={{ width: "100%", height }}>
        {data && data.length > 0 ? (
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={data}
              margin={{ top: 10, right: 10, left: -20, bottom: 0 }}
            >
              <defs>
                <linearGradient
                  id="rainBarGradient"
                  x1="0"
                  y1="0"
                  x2="0"
                  y2="1"
                >
                  <stop offset="0%" stopColor="#38bdf8" stopOpacity={0.9} />
                  <stop offset="100%" stopColor="#0284c7" stopOpacity={0.3} />
                </linearGradient>
                <linearGradient
                  id="heavyRainBarGradient"
                  x1="0"
                  y1="0"
                  x2="0"
                  y2="1"
                >
                  <stop offset="0%" stopColor="#f59e0b" stopOpacity={0.9} />
                  <stop offset="100%" stopColor="#b45309" stopOpacity={0.4} />
                </linearGradient>
              </defs>

              <CartesianGrid
                strokeDasharray="3 3"
                stroke="#1e3a5f"
                strokeOpacity={0.5}
                vertical={false}
              />

              <XAxis
                dataKey={xKey}
                tickLine={false}
                interval={2}
                stroke="#64748b"
                tick={{ fill: "#94a3b8", fontSize: 10 }}
                tickFormatter={(val) => {
                  try {
                    const d = new Date(val);
                    if (!isNaN(d.getTime())) {
                      if (d.getHours() === 0) {
                        return d.toLocaleDateString("en-US", {
                          month: "short",
                          day: "numeric",
                        });
                      }
                      return `${String(d.getHours()).padStart(2, "0")}:00`;
                    }
                  } catch {
                    // ignore
                  }
                  return val;
                }}
              />

              <YAxis
                tickLine={false}
                stroke="#64748b"
                tick={{ fill: "#94a3b8", fontSize: 10 }}
                domain={
                  unit === "%"
                    ? [0, 100]
                    : [
                        0,
                        (max: number) => Math.max(1, Math.ceil(max * 10) / 10),
                      ]
                }
              />

              <Tooltip content={<CustomTooltip />} />

              <Bar dataKey={yKey} radius={[3, 3, 0, 0]} minPointSize={3}>
                {data.map((entry, index) => {
                  const val = Number(entry[yKey] || 0);
                  const isHeavy = unit === "%" ? val >= 60 : val > 15;
                  return (
                    <Cell
                      key={`cell-${index}`}
                      fill={
                        val === 0
                          ? "#334155"
                          : isHeavy
                            ? "url(#heavyRainBarGradient)"
                            : "url(#rainBarGradient)"
                      }
                    />
                  );
                })}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <div className="flex h-full w-full items-center justify-center text-sm text-slate-500">
            No precipitation recorded
          </div>
        )}
      </div>
    </div>
  );
}

export default RainfallChart;
