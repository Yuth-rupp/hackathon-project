"use client";

import React from "react";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from "recharts";

export interface SeriesConfig {
  key: string;
  name: string;
  color?: string;
  type?: "area" | "line";
  strokeDasharray?: string;
  fillOpacity?: number;
}

export interface TimeSeriesChartProps {
  data: any[];
  xKey?: string;
  yKeys?: (string | SeriesConfig)[];
  colors?: string[];
  title?: string;
  subtitle?: string;
  unit?: string;
  height?: number | string;
  showGrid?: boolean;
  showLegend?: boolean;
  className?: string;
}

const DEFAULT_COLORS = ["#06b6d4", "#3b82f6", "#10b981", "#f59e0b", "#8b5cf6"];

export function TimeSeriesChart({
  data,
  xKey = "date",
  yKeys = ["value"],
  colors = DEFAULT_COLORS,
  title,
  subtitle,
  unit = "",
  height = 320,
  showGrid = true,
  showLegend = true,
  className = "",
}: TimeSeriesChartProps) {
  // Normalize yKeys into SeriesConfig array
  const seriesList: SeriesConfig[] = yKeys.map((item, idx) => {
    if (typeof item === "string") {
      return {
        key: item,
        name: item.replace(/_/g, " ").toUpperCase(),
        color: colors[idx % colors.length],
        type: "area",
      };
    }
    return {
      ...item,
      color: item.color || colors[idx % colors.length],
      type: item.type || "area",
    };
  });

  // Custom Dark Tooltip
  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      let formattedDate = label;
      try {
        const d = new Date(label);
        if (!isNaN(d.getTime())) {
          formattedDate = d.toLocaleDateString("en-US", {
            month: "short",
            day: "numeric",
            year: "numeric",
          });
        }
      } catch {
        // use raw
      }

      return (
        <div className="rounded-lg border border-navy-800 bg-navy-950/95 p-3 shadow-xl backdrop-blur-md">
          <p className="text-xs font-semibold text-slate-300 mb-1.5 border-b border-navy-800 pb-1">
            {formattedDate}
          </p>
          <div className="space-y-1">
            {payload.map((entry: any, index: number) => (
              <div
                key={`tip-${index}`}
                className="flex items-center justify-between gap-4 text-xs"
              >
                <span className="flex items-center gap-1.5 text-slate-400">
                  <span
                    className="inline-block h-2 w-2 rounded-full"
                    style={{ backgroundColor: entry.color }}
                  />
                  {entry.name}:
                </span>
                <span className="font-semibold text-white">
                  {typeof entry.value === "number"
                    ? entry.value.toLocaleString(undefined, {
                        maximumFractionDigits: 2,
                      })
                    : entry.value}{" "}
                  {unit}
                </span>
              </div>
            ))}
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
        <div className="mb-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-1">
          <div>
            {title && (
              <h3 className="text-sm font-semibold uppercase tracking-wider text-white">
                {title}
              </h3>
            )}
            {subtitle && (
              <p className="text-xs text-slate-400 mt-0.5">{subtitle}</p>
            )}
          </div>
          {unit && (
            <span className="text-xs font-mono text-cyan-400 bg-cyan-950/50 border border-cyan-800/60 px-2 py-0.5 rounded self-start">
              Unit: {unit}
            </span>
          )}
        </div>
      )}

      <div style={{ width: "100%", height }}>
        {data && data.length > 0 ? (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart
              data={data}
              margin={{ top: 10, right: 10, left: -15, bottom: 0 }}
            >
              <defs>
                {seriesList.map((series, idx) => (
                  <linearGradient
                    key={`gradient-${series.key}-${idx}`}
                    id={`gradient-${series.key}`}
                    x1="0"
                    y1="0"
                    x2="0"
                    y2="1"
                  >
                    <stop
                      offset="5%"
                      stopColor={series.color}
                      stopOpacity={0.4}
                    />
                    <stop
                      offset="95%"
                      stopColor={series.color}
                      stopOpacity={0.0}
                    />
                  </linearGradient>
                ))}
              </defs>

              {showGrid && (
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke="#1e3a5f"
                  strokeOpacity={0.6}
                />
              )}

              <XAxis
                dataKey={xKey}
                tickLine={false}
                stroke="#64748b"
                tick={{ fill: "#94a3b8", fontSize: 11 }}
                tickFormatter={(val) => {
                  try {
                    const d = new Date(val);
                    if (!isNaN(d.getTime())) {
                      return `${d.getMonth() + 1}/${d.getDate()}`;
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
                tick={{ fill: "#94a3b8", fontSize: 11 }}
                domain={["auto", "auto"]}
              />

              <Tooltip content={<CustomTooltip />} />

              {showLegend && (
                <Legend
                  verticalAlign="top"
                  align="right"
                  wrapperStyle={{ paddingBottom: "10px", fontSize: "12px" }}
                />
              )}

              {seriesList.map((series) =>
                series.type === "line" ? (
                  <Line
                    key={series.key}
                    type="monotone"
                    dataKey={series.key}
                    name={series.name}
                    stroke={series.color}
                    strokeWidth={2}
                    strokeDasharray={series.strokeDasharray}
                    // With only 1-2 readings a line is invisible, so show dots.
                    dot={
                      data.length <= 2 ? { r: 4, fill: series.color } : false
                    }
                    activeDot={{ r: 5 }}
                    connectNulls
                    isAnimationActive={false}
                  />
                ) : (
                  <Area
                    key={series.key}
                    type="monotone"
                    dataKey={series.key}
                    name={series.name}
                    stroke={series.color}
                    strokeWidth={2}
                    strokeDasharray={series.strokeDasharray}
                    fillOpacity={series.fillOpacity ?? 1}
                    fill={`url(#gradient-${series.key})`}
                    dot={
                      data.length <= 2 ? { r: 4, fill: series.color } : false
                    }
                    isAnimationActive={false}
                  />
                ),
              )}
            </AreaChart>
          </ResponsiveContainer>
        ) : (
          <div className="flex h-full w-full items-center justify-center text-sm text-slate-500">
            No hydrological time-series data available
          </div>
        )}
      </div>
    </div>
  );
}

export default TimeSeriesChart;
