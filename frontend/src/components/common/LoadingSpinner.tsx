'use client';

import React from 'react';
import clsx from 'clsx';
import { Loader2 } from 'lucide-react';

interface LoadingSpinnerProps {
  size?: 'sm' | 'md' | 'lg';
  message?: string;
  className?: string;
  fullHeight?: boolean;
}

export function LoadingSpinner({
  size = 'md',
  message,
  className,
  fullHeight = false,
}: LoadingSpinnerProps) {
  const sizeMap = {
    sm: 'h-4 w-4',
    md: 'h-7 w-7',
    lg: 'h-10 w-10',
  };

  return (
    <div
      className={clsx(
        'flex flex-col items-center justify-center gap-3 p-4 text-slate-400',
        fullHeight ? 'min-h-[300px]' : '',
        className
      )}
    >
      <div className="relative">
        <Loader2
          className={clsx('animate-spin text-cyan-400', sizeMap[size])}
        />
        <div className="absolute inset-0 rounded-full bg-cyan-400/20 blur-md animate-pulse" />
      </div>
      {message && (
        <p className="text-xs font-medium tracking-wide text-slate-300">
          {message}
        </p>
      )}
    </div>
  );
}
