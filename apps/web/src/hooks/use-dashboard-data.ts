"use client";

import { useEffect, useState } from "react";

import { loadCoreDashboardData } from "@/lib/app-data/loaders";
import type { CoreDashboardData } from "@/types/app-data";

interface DashboardDataState {
  data: CoreDashboardData | null;
  error: string | null;
  loading: boolean;
}

export function useDashboardData(): DashboardDataState {
  const [state, setState] = useState<DashboardDataState>({
    data: null,
    error: null,
    loading: true,
  });

  useEffect(() => {
    const controller = new AbortController();
    loadCoreDashboardData(controller.signal)
      .then((data) => setState({ data, error: null, loading: false }))
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          setState({
            data: null,
            error: error instanceof Error ? error.message : "Unknown data-loading failure",
            loading: false,
          });
        }
      });
    return () => controller.abort();
  }, []);

  return state;
}
