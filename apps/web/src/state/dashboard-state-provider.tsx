"use client";

import { createContext, useContext, useReducer } from "react";

import {
  createInitialDashboardState,
  dashboardReducer,
  type DashboardAction,
  type DashboardState,
} from "@/state/dashboard-state";

interface DashboardStateContextValue {
  state: DashboardState;
  dispatch: React.Dispatch<DashboardAction>;
}

const DashboardStateContext = createContext<DashboardStateContextValue | null>(null);

export function DashboardStateProvider({ children }: { children: React.ReactNode }) {
  const [state, dispatch] = useReducer(dashboardReducer, "overview", createInitialDashboardState);
  return (
    <DashboardStateContext.Provider value={{ state, dispatch }}>
      {children}
    </DashboardStateContext.Provider>
  );
}

export function useDashboardState() {
  const value = useContext(DashboardStateContext);
  if (!value) throw new Error("useDashboardState must be used inside DashboardStateProvider");
  return value;
}
