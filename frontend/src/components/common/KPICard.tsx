'use client';

import React from 'react';
import { ArrowUpRight, ArrowDownRight, Minus, LucideIcon } from 'lucide-react';
import clsx from 'clsx';

export interface KPICardProps {
  title: string;
  value: string | number;
  unit?: string;
  trend?: 'up' | 'down' | 'stable';
  trendValue?: string;
  icon?: LucideIcon;
  color?: 'cyan' | 'navy' | 'emerald' | 'amber' | 'rose' | 'purple';
  description?: string;
  className?: string;
}

const colorStyles = {
  cyan: {
    iconBg: 'bg-cyan-500/10 text-cyan-400 border-cyan-500/20',
    highlight: 'text-cyan-400',
    border: 'hover:border-cyan-500/40',
  },
  navy: {
    iconBg: 'bg-navy-600/20 text-navy-200 border-navy-500/30',
    highlight: 'text-navy-200',
    border: 'hover:border-navy-400/40',
  },
  emerald: {
    iconBg: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
    highlight: 'text-emerald-400',
    border: 'hover:border-emerald-500/40',
  },
  amber: {
    iconBg: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
    highlight: 'text-amber-400',
    border: 'hover:border-amber-500/40',
  },
  rose: {
    iconBg: 'bg-rose-500/10 text-rose-400 border-rose-500/20',
    highlight: 'text-rose-400',
    border: 'hover:border-rose-500/40',
  },
  purple: {
    iconBg: 'bg-purple-500/10 text-purple-400 border-purple-500/20',
    highlight: 'text-purple-400',
    border: 'hover:border-purple-500/40',
  },
};

export function KPICard({
  title,
  value,
  unit,
  trend,
  trendValue,
  icon: Icon,
  color = 'cyan',
  description,
  className,
}: KPICardProps) {
  const selectedTheme = colorStyles[color] || colorStyles.cyan;

  return (
    <div
      className={clsx(
        'relative overflow-hidden rounded-xl border border-navy-800 bg-navy-900/60 p-5 shadow-lg backdrop-blur-md transition-all duration-300 hover:shadow-cyan-950/30',
        selectedTheme.border,
        className
      )}
    >
      {/* Background ambient gradient glow */}
      <div className="pointer-events-none absolute -right-6 -top-6 h-24 w-24 rounded-full bg-cyan-500/5 blur-2xl" />

      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs font-medium uppercase tracking-wider text-slate-400">
            {title}
          </p>
          <div className="mt-2 flex items-baseline gap-1.5">
            <span className="text-2xl font-bold tracking-tight text-white md:text-3xl">
              {value}
            </span>
            {unit && (
              <span className="text-sm font-medium text-slate-400">
                {unit}
              </span>
            )}
          </div>
        </div>

        {Icon && (
          <div
            className={clsx(
              'flex h-11 w-11 shrink-0 items-center justify-center rounded-lg border',
              selectedTheme.iconBg
            )}
          >
            <Icon className="h-5 w-5" />
          </div>
        )}
      </div>

      {(trend || description) && (
        <div className="mt-4 flex items-center justify-between border-t border-navy-800/80 pt-3 text-xs">
          {trend && (
            <div
              className={clsx(
                'flex items-center gap-1 font-medium',
                trend === 'up' && 'text-rose-400',
                trend === 'down' && 'text-emerald-400',
                trend === 'stable' && 'text-slate-400'
              )}
            >
              {trend === 'up' && <ArrowUpRight className="h-3.5 w-3.5" />}
              {trend === 'down' && <ArrowDownRight className="h-3.5 w-3.5" />}
              {trend === 'stable' && <Minus className="h-3.5 w-3.5" />}
              <span>{trendValue || (trend === 'up' ? 'Increasing' : trend === 'down' ? 'Decreasing' : 'Nominal')}</span>
            </div>
          )}
          {description && (
            <span className="text-slate-400 truncate max-w-[170px]" title={description}>
              {description}
            </span>
          )}
        </div>
      )}
    </div>
  );
}
