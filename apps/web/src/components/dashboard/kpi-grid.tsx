import { KpiCard } from "@/components/dashboard/kpi-card";
import { buildNetworkKpis } from "@/lib/dashboard/kpis";
import type { CoreDashboardData } from "@/types/app-data";

export function KpiGrid({ data }: { data: CoreDashboardData }) {
  return (
    <section className="kpi-grid" aria-label="Network performance indicators">
      {buildNetworkKpis(data).map((item) => (
        <KpiCard item={item} key={item.label} />
      ))}
    </section>
  );
}
