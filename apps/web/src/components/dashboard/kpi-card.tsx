import type { KpiValue } from "@/lib/dashboard/kpis";

export function KpiCard({ item }: { item: KpiValue }) {
  return (
    <article className={`kpi-card kpi-${item.tone}`}>
      <p>{item.label}</p>
      <strong>{item.value}</strong>
      <span>{item.detail}</span>
    </article>
  );
}
