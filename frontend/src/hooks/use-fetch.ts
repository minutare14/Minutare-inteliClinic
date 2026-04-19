"use client";

import { useState, useEffect, useCallback } from "react";

interface UseFetchResult<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

export function useFetch<T>(
  fetcher: () => Promise<T>,
  deps: unknown[] = []
): UseFetchResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  const refetch = useCallback(() => setTick((t) => t + 1), []);

  useEffect(() => {
    let cancelled = false;
    let timeoutId: ReturnType<typeof setTimeout>;

    setLoading(true);
    setError(null);

    const controller = new AbortController();

    const doFetch = async () => {
      // 20-second timeout per request
      timeoutId = setTimeout(() => controller.abort(), 20_000);
      try {
        const result = await fetcher();
        if (!cancelled) setData(result);
      } catch (e) {
        if (!cancelled) {
          if (e instanceof Error && e.name === "AbortError") {
            setError("Tempo esgotado — o servidor não respondeu");
          } else {
            setError(e instanceof Error ? e.message : "Erro ao carregar dados");
          }
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    doFetch();

    return () => {
      cancelled = true;
      clearTimeout(timeoutId);
      controller.abort();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tick, ...deps]);

  return { data, loading, error, refetch };
}
