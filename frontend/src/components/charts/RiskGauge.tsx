"use client";

import React, { useId } from "react";
import { RiskLevel } from "@/types";
import { ShieldCheck } from "lucide-react";

export interface RiskGaugeProps {
  score: number;
  level?: RiskLevel;
  size?: number;
  title?: string;
  subtitle?: string;
  showConfidence?: boolean;
  confidencePct?: number;
  className?: string;
}

export function RiskGauge({
  score,
  level = "low",
  size = 220,
  title = "Overall Risk Score",
  subtitle,
  showConfidence = false,
  confidencePct,
  className = "",
}: RiskGaugeProps) {
  // Generate unique SVG IDs to prevent conflicts between multiple gauges.
  const uniqueId = useId().replace(/:/g, "");

  const gradientId = `gaugeGradient-${uniqueId}`;
  const glowId = `gaugeGlow-${uniqueId}`;

  // Keep the score between 0 and 100.
  const normalizedScore = Math.max(
    0,
    Math.min(100, Number.isFinite(score) ? score : 0),
  );

  // Determine gauge color based on the risk level.
  const getColor = () => {
    if (level === "very_high" || normalizedScore >= 80) {
      return "#ef4444";
    }

    if (level === "high" || normalizedScore >= 65) {
      return "#f97316";
    }

    if (level === "moderate" || normalizedScore >= 45) {
      return "#f59e0b";
    }

    return "#22c55e";
  };

  const color = getColor();

  // SVG gauge calculations.
  const strokeWidth = 14;
  const radius = (size - strokeWidth * 2) / 2;
  const circumference = Math.PI * radius;

  const strokeDashoffset =
    circumference - (normalizedScore / 100) * circumference;

  // Needle rotation from -90 to +90 degrees.
  const angle = (normalizedScore / 100) * 180 - 90;

  // Needle length adjusts with gauge size.
  const needleLength = radius * 0.78;

  // Optional confidence value.
  const normalizedConfidence =
    confidencePct === undefined
      ? null
      : Math.max(0, Math.min(100, confidencePct));

  // Risk level label.
  const riskLabel =
    level === "very_high"
      ? "Very High Risk"
      : level === "high"
        ? "High Risk"
        : level === "moderate"
          ? "Moderate Risk"
          : "Low Risk";

  return (
    <div
      className={`relative flex flex-col items-center justify-center rounded-xl border border-navy-800 bg-navy-900/60 p-5 shadow-lg backdrop-blur-md ${className}`}
    >
      {/* Gauge Title */}
      {title && (
        <div className="mb-2 text-center">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-300">
            {title}
          </h4>

          {subtitle && (
            <p className="mt-0.5 text-[11px] text-slate-400">{subtitle}</p>
          )}
        </div>
      )}

      {/* Gauge Visualization */}
      <div
        className="relative flex items-center justify-center"
        style={{
          width: size,
          height: size * 0.62,
        }}
      >
        <svg
          width={size}
          height={size * 0.65}
          viewBox={`0 0 ${size} ${size * 0.65}`}
          className="overflow-visible"
          role="img"
          aria-label={`Overall risk score ${normalizedScore} out of 100. ${riskLabel}.`}
        >
          <defs>
            {/* Gauge Color Gradient */}
            <linearGradient id={gradientId} x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#22c55e" />
              <stop offset="40%" stopColor="#f59e0b" />
              <stop offset="70%" stopColor="#f97316" />
              <stop offset="100%" stopColor="#ef4444" />
            </linearGradient>

            {/* Needle Glow */}
            <filter id={glowId} x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="3" result="blur" />

              <feComposite in="SourceGraphic" in2="blur" operator="over" />
            </filter>
          </defs>

          {/* Background Gauge Track */}
          <path
            d={`M ${strokeWidth}, ${size * 0.58} A ${radius} ${radius} 0 0 1 ${size - strokeWidth}, ${size * 0.58}`}
            fill="none"
            stroke="#1e3a5f"
            strokeWidth={strokeWidth}
            strokeLinecap="round"
          />

          {/* Progress Gauge Arc */}
          <path
            d={`M ${strokeWidth}, ${size * 0.58} A ${radius} ${radius} 0 0 1 ${size - strokeWidth}, ${size * 0.58}`}
            fill="none"
            stroke={`url(#${gradientId})`}
            strokeWidth={strokeWidth}
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={strokeDashoffset}
            className="transition-all duration-1000 ease-out"
          />

          {/* Needle and Pivot */}
          <g
            transform={`translate(${size / 2}, ${size * 0.58}) rotate(${angle})`}
          >
            <polygon
              points={`-4,0 4,0 0,-${needleLength}`}
              fill={color}
              filter={`url(#${glowId})`}
            />

            <circle
              cx="0"
              cy="0"
              r="7"
              fill="#0f2744"
              stroke={color}
              strokeWidth="3"
            />
          </g>
        </svg>

        {/* Center Score Display */}
        <div className="absolute bottom-0 flex flex-col items-center">
          <span className="font-mono text-3xl font-extrabold tracking-tight text-white">
            {Number.isInteger(normalizedScore)
              ? normalizedScore
              : normalizedScore.toFixed(1)}
            <span className="text-base font-semibold text-slate-400">/100</span>
          </span>

          {/* Risk Level Badge */}
          <span
            className="mt-0.5 rounded-full px-2 py-0.5 text-[11px] font-bold uppercase tracking-wider"
            style={{
              color,
              backgroundColor: `${color}18`,
              border: `1px solid ${color}40`,
            }}
          >
            {riskLabel}
          </span>
        </div>
      </div>

      {/* Optional Model Confidence */}
      {showConfidence && normalizedConfidence !== null && (
        <div className="mt-4 flex w-full items-center justify-between border-t border-navy-800/80 pt-2.5 text-xs text-slate-400">
          <span className="flex items-center gap-1">
            <ShieldCheck className="h-3.5 w-3.5 text-cyan-400" />
            Model Confidence
          </span>

          <span className="font-semibold text-cyan-300">
            {normalizedConfidence}%
          </span>
        </div>
      )}
    </div>
  );
}

export default RiskGauge;
