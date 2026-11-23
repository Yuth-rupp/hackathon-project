'use client';

import React, { useMemo } from 'react';
import { Clock } from 'lucide-react';
import clsx from 'clsx';
import { formatDistanceToNow, parseISO } from 'date-fns';

interface DataFreshnessProps {
  timestamp?: string | Date | null;
  label?: string;
  showIcon?: boolean;
  className?: string;
}

export function DataFreshness({
  timestamp,
  label = 'Updated',
  showIcon = true,
  className,
}: DataFreshnessProps) {
  const { relativeTime, statusColor, titleTime } = useMemo(() => {
    if (!timestamp) {
      return {
        relativeTime: 'Live / Synchronized',
        statusColor: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30',
        titleTime: 'Just now',
      };
    }

    try {
      const date = typeof timestamp === 'string' ? parseISO(timestamp) : timestamp;
      const diffMs = Date.now() - date.getTime();
      const diffMinutes = Math.floor(diffMs / 60000);

      const rel = formatDistanceToNow(date, { addSuffix: true });
      const full = date.toLocaleString();

      if (diffMinutes < 15) {
        return {
          relativeTime: rel,
          statusColor: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30',
          titleTime: full,
        };
      } else if (diffMinutes < 60) {
        return {
          relativeTime: rel,
          statusColor: 'text-amber-400 bg-amber-500/10 border-amber-500/30',
          titleTime: full,
        };
      } else {
        return {
          relativeTime: rel,
          statusColor: 'text-rose-400 bg-rose-500/10 border-rose-500/30',
          titleTime: full,
        };
      }
    } catch {
      return {
        relativeTime: 'Just now',
        statusColor: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30',
        titleTime: '',
      };
    }
  }, [timestamp]);

  return (
    <div
      title={titleTime}
      className={clsx(
        'inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-xs font-medium backdrop-blur-sm',
        statusColor,
        className
      )}
    >
      {showIcon && <Clock className="h-3 w-3" />}
      <span>
        {label} {relativeTime}
      </span>
    </div>
  );
}
