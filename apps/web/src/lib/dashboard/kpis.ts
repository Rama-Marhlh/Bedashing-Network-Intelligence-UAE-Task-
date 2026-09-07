import type { CoreDashboardData } from "@/types/app-data";

export interface KpiValue {
  label: string;
  value: string;
  detail: string;
  tone: "neutral" | "positive" | "warning" | "critical";
}

const integer = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });

export function buildNetworkKpis(data: CoreDashboardData): KpiValue[] {
  const { network, competition } = data.summary;
  return [
    {
      label: "Total branches",
      value: integer.format(network.branch_count),
      detail: "Current UAE portfolio",
      tone: "neutral",
    },
    {
      label: "Protect",
      value: integer.format(network.recommendations.PROTECT),
      detail: "Strong external-market signal",
      tone: "positive",
    },
    {
      label: "Hold",
      value: integer.format(network.recommendations.HOLD),
      detail: "Maintain and monitor",
      tone: "warning",
    },
    {
      label: "Shrink / review",
      value: integer.format(network.recommendations.SHRINK),
      detail: "Internal commercial review only",
      tone: "critical",
    },
    {
      label: "Observed competitors",
      value: integer.format(competition.observed_unique_competitors),
      detail: "Public-market observations",
      tone: "neutral",
    },
    ...(["GROW", "WATCH", "SKIP"] as const).map((label) => ({
      label,
      value: integer.format(data.summary.growth.recommendations[label]),
      detail: "Whitespace recommendation",
      tone: (label === "GROW"
        ? "positive"
        : label === "WATCH"
          ? "warning"
          : "neutral") as KpiValue["tone"],
    })),
  ];
}
