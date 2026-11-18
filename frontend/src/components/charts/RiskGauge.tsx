'use client';

import React from 'react';
import { RiskLevel } from '@/types';
import { ShieldCheck, ShieldAlert, AlertTriangle } from 'lucide-react';

export interface RiskGaugeProps {
  score: number; // 0 to 100
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
  level = 'low',
  size = 220,
  title = 'AI Risk Probability',
  subtitle,
  showConfidence = false,
  confidencePct = 90,
  className = '',
}: RiskGaugeProps) {
  // Constrain score between 0 and 100
  const normalizedScore = Math.max(0, Math.min(100, score));

  // Determine color based on level or score
  const getColor = () => {
    if (level === 'very_high' || normalizedScore >= 80) return '#ef4444'; // red
    if (level === 'high' || normalizedScore >= 65) return '#f97316'; // orange
    if (level === 'moderate' || normalizedScore >= 45) return '#f59e0b'; // amber
    return '#22c55e'; // green
  };

  const color = getColor();

  // SVG Gauge calculations (semi-circle from 180 to 0 degrees)
  const strokeWidth = 14;
  const radius = (size - strokeWidth * 2) / 2;
  const circumference = Math.PI * radius; // semi circle perimeter
  const strokeDashoffset = circumference - (normalizedScore / 100) * circumference;

  // Calculate needle angle (-90deg to +90deg)
  const angle = (normalizedScore / 100) * 180 - 90;

  return (
    <div
      className={`relative flex flex-col items-center justify-center rounded-xl border border-navy-800 bg-navy-900/60 p-5 shadow-lg backdrop-blur-md ${className}`}
    >
      {title && (
        <div className="mb-2 text-center">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-300">
            {title}
          </h4>
          {subtitle && <p className="text-[11px] text-slate-400 mt-0.5">{subtitle}</p>}
        </div>
      )}

      <div className="relative flex items-center justify-center" style={{ width: size, height: size * 0.62 }}>
        <svg
          width={size}
          height={size * 0.65}
          viewBox={`0 0 ${size} ${size * 0.65}`}
          className="overflow-visible"
        >
          <defs>
            <linearGradient id="gaugeGradient" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#22c55e" />
              <stop offset="40%" stopColor="#f59e0b" />
              <stop offset="70%" stopColor="#f97316" />
              <stop offset="100%" stopColor="#ef4444" />
            </linearGradient>
            <filter id="gaugeGlow" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="3" result="blur" />
              <feComposite in="SourceGraphic" in2="blur" operator="over" />
            </filter>
          </defs>

          {/* Background track (semi circle arc) */}
          <path
            d={`M ${strokeWidth}, ${size * 0.58} A ${radius} ${radius} 0 0 1 ${size - strokeWidth}, ${size * 0.58}`}
            fill="none"
            stroke="#1e3a5f"
            strokeWidth={strokeWidth}
            strokeLinecap="round"
          />

          {/* Value Progress Arc */}
          <path
            d={`M ${strokeWidth}, ${size * 0.58} A ${radius} ${radius} 0 0 1 ${size - strokeWidth}, ${size * 0.58}`}
            fill="none"
            stroke="url(#gaugeGradient)"
            strokeWidth={strokeWidth}
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={strokeDashoffset}
            className="transition-all duration-1000 ease-out"
          />

          {/* Needle / Pivot Indicator */}
          <g transform={`translate(${size / 2}, ${size * 0.58}) rotate(${angle})`}>
            <polygon
              points="-4,0 4,0 0,-70"
              fill={color}
              className="transition-transform duration-700 ease-out"
              filter="url(#gaugeGlow)"
            />
            <circle cx="0" cy="0" r="7" fill="#0f2744" stroke={color} strokeWidth="3" />
          </g>
        </svg>

        {/* Center Readout Text */}
        <div className="absolute bottom-0 flex flex-col items-center">
          <span className="text-3xl font-extrabold tracking-tight text-white font-mono">
            {normalizedScore}%
          </span>
          <span
            className="mt-0.5 text-[11px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full"
            style={{
              color,
              backgroundColor: `${color}18`,
              border: `1px solid ${color}40`,
            }}
          >
            {level === 'very_high'
              ? 'Very High Risk'
              : level === 'high'
              ? 'High Risk'
              : level === 'moderate'
              ? 'Moderate Risk'
              : 'Low Risk'}
          </span>
        </div>
      </div>

      {showConfidence && (
        <div className="mt-4 flex items-center justify-between w-full border-t border-navy-800/80 pt-2.5 text-xs text-slate-400">
          <span className="flex items-center gap-1">
            <ShieldCheck className="h-3.5 w-3.5 text-cyan-400" />
            Model Confidence
          </span>
          <span className="font-semibold text-cyan-300">{confidencePct}%</span>
        </div>
      )}
    </div>
  );
}

export default RiskGauge;
