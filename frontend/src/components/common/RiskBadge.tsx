'use client';

import React from 'react';
import clsx from 'clsx';
import { RiskLevel } from '@/types';
import { ShieldCheck, AlertCircle, AlertTriangle, Flame } from 'lucide-react';

interface RiskBadgeProps {
  level: RiskLevel | string;
  score?: number;
  size?: 'sm' | 'md' | 'lg';
  showIcon?: boolean;
  className?: string;
}

const levelConfig: Record<
  string,
  {
    label: string;
    labelKm: string;
    badgeClass: string;
    dotClass: string;
    icon: React.ComponentType<{ className?: string }>;
  }
> = {
  low: {
    label: 'Low Risk',
    labelKm: 'ហានិភ័យទាប',
    badgeClass: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
    dotClass: 'bg-emerald-400',
    icon: ShieldCheck,
  },
  moderate: {
    label: 'Moderate Risk',
    labelKm: 'ហានិភ័យមធ្យម',
    badgeClass: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
    dotClass: 'bg-amber-400',
    icon: AlertCircle,
  },
  high: {
    label: 'High Risk',
    labelKm: 'ហានិភ័យខ្ពស់',
    badgeClass: 'bg-orange-500/15 text-orange-400 border-orange-500/30',
    dotClass: 'bg-orange-400',
    icon: AlertTriangle,
  },
  very_high: {
    label: 'Very High Risk',
    labelKm: 'ហានិភ័យខ្ពស់បំផុត',
    badgeClass: 'bg-rose-500/20 text-rose-400 border-rose-500/40 animate-pulse',
    dotClass: 'bg-rose-400',
    icon: Flame,
  },
};

export function RiskBadge({
  level,
  score,
  size = 'md',
  showIcon = true,
  className,
}: RiskBadgeProps) {
  const normLevel = (level || 'low').toLowerCase().replace(' ', '_');
  const config = levelConfig[normLevel] || levelConfig.low;
  const Icon = config.icon;

  const sizeClasses = {
    sm: 'text-xs px-2 py-0.5 gap-1',
    md: 'text-xs px-2.5 py-1 gap-1.5',
    lg: 'text-sm px-3.5 py-1.5 gap-2 font-semibold',
  };

  return (
    <span
      className={clsx(
        'inline-flex items-center rounded-full border font-medium tracking-wide transition-all shadow-sm',
        config.badgeClass,
        sizeClasses[size],
        className
      )}
    >
      {showIcon && <Icon className={size === 'lg' ? 'h-4 w-4' : 'h-3.5 w-3.5'} />}
      <span>{config.label}</span>
      {typeof score === 'number' && (
        <span className="ml-0.5 opacity-80">({Math.round(score)}%)</span>
      )}
    </span>
  );
}
