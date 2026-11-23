'use client';

import { useState, useEffect, useCallback, useRef } from 'react';

export interface UseApiOptions {
  autoRefreshInterval?: number; // In milliseconds, e.g. 60000 for 1 min
  immediate?: boolean; // Default true
}

export interface UseApiResult<T> {
  data: T | null;
  loading: boolean;
  error: Error | null;
  refetch: () => Promise<void>;
  lastFetched: Date | null;
}

export function useApi<T>(
  fetchFn: () => Promise<T>,
  deps: any[] = [],
  options: UseApiOptions = {}
): UseApiResult<T> {
  const { autoRefreshInterval, immediate = true } = options;
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState<boolean>(immediate);
  const [error, setError] = useState<Error | null>(null);
  const [lastFetched, setLastFetched] = useState<Date | null>(null);

  const fetchFnRef = useRef(fetchFn);
  useEffect(() => {
    fetchFnRef.current = fetchFn;
  });

  const execute = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await fetchFnRef.current();
      setData(result);
      setLastFetched(new Date());
    } catch (err: any) {
      console.error('useApi hook execution error:', err);
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setLoading(false);
    }
  }, []);

  // Initial and dependency-triggered fetch
  useEffect(() => {
    let isMounted = true;

    if (immediate) {
      execute();
    }

    // Auto-refresh interval if set
    let timer: NodeJS.Timeout | null = null;
    if (autoRefreshInterval && autoRefreshInterval > 0) {
      timer = setInterval(() => {
        if (isMounted) {
          execute();
        }
      }, autoRefreshInterval);
    }

    return () => {
      isMounted = false;
      if (timer) clearInterval(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, execute, autoRefreshInterval, immediate]);

  return {
    data,
    loading,
    error,
    refetch: execute,
    lastFetched,
  };
}
