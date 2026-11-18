'use client';

import React from 'react';
import clsx from 'clsx';
import { SystemStatus } from '@/types';

interface StatusBadgeProps {
  status: SystemStatus | 'connected' | 'delayed' | 'offline' | string;
  label?: string;
  showDot?: boolean;
  size?: 'sm' | 'md';
  className?: string;
}

const statusThemes: Record<
  string,
  {
    text: string;
    bg: string;
    border: string;
    dot: string;
    ping: string;
    label: string;
  }
> = {
  operational: {
    text: 'text-emerald-400',
    bg: 'bg-emerald-500/10',
    border: 'border-emerald-500/30',
    dot: 'bg-emerald-400',
    ping: 'bg-emerald-400',
    label: 'Operational',
  },
  connected: {
    text: 'text-emerald-400',
    bg: 'bg-emerald-500/10',
    border: 'border-emerald-500/30',
    dot: 'bg-emerald-400',
    ping: 'bg-emerald-400',
    label: 'Connected',
  },
  nominal: {
    text: 'text-cyan-400',
    bg: 'bg-cyan-500/10',
    border: 'border-cyan-500/30',
    dot: 'bg-cyan-400',
    ping: 'bg-cyan-400',
    label: 'Nominal',
  },
  delayed: {
    text: 'text-amber-400',
    bg: 'bg-amber-500/10',
    border: 'border-amber-500/30',
    dot: 'bg-amber-400',
    ping: 'bg-amber-400',
    label: 'Delayed',
  },
  degraded: {
    text: 'text-amber-400',
    bg: 'bg-amber-500/10',
    border: 'border-amber-500/30',
    dot: 'bg-amber-400',
    ping: 'bg-amber-400',
    label: 'Degraded',
  },
  offline: {
    text: 'text-rose-400',
    bg: 'bg-rose-500/10',
    border: 'border-rose-500/30',
    dot: 'bg-rose-400',
    ping: 'bg-rose-400',
    label: 'Offline',
  },
};

export function StatusBadge({
  status,
  label,
  showDot = true,
  size = 'md',
  className,
}: StatusBadgeProps) {
  const norm = (status || 'operational').toLowerCase();
  const theme = statusThemes[norm] || statusThemes.operational;
  const displayLabel = label || theme.label;

  return (
    <div
      className={clsx(
        'inline-flex items-center gap-1.5 rounded-full border font-medium',
        theme.bg,
        theme.border,
        theme.text,
        size === 'sm' ? 'px-2 py-0.5 text-[11px]' : 'px-2.5 py-1 text-xs',
        className
      )}
    >
      {showDot && (
        <span className="relative flex h-2 w-2">
          <span
            className={clsx(
              'absolute inline-flex h-full w-full animate-ping rounded-full opacity-75',
              theme.ping
            )}
          />
          <span
            className={clsx(
              'relative inline-flex h-2 w-2 rounded-full',
              theme.dot
            )}
          />
        </span>
      )}
      <span>{displayLabel}</span>
    </div>
  );
}
