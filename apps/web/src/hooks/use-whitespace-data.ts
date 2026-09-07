"use client";

import { useEffect, useState } from "react";

import { loadWhitespaceData } from "@/lib/app-data/loaders";
import type { WhitespaceData } from "@/types/app-data";

export function useWhitespaceData(enabled: boolean): {
  data: WhitespaceData | null;
  error: string | null;
  loading: boolean;
} {
  const [data, setData] = useState<WhitespaceData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!enabled || data) return;
    const controller = new AbortController();
    setLoading(true);
    loadWhitespaceData(controller.signal)
      .then((value) => {
        setData(value);
        setError(null);
      })
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) {
          setError(reason instanceof Error ? reason.message : "Whitespace data failed to load");
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [data, enabled]);

  return { data, error, loading };
}
