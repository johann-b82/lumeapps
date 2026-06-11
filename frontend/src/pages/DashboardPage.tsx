import { CustomerShareCard } from "@/components/dashboard/CustomerShareCard";
import { KpiCardGrid } from "@/components/dashboard/KpiCardGrid";
import { RevenueChart } from "@/components/dashboard/RevenueChart";
import { SalesActivityCard } from "@/components/dashboard/SalesActivityCard";
import { SalesTable } from "@/components/dashboard/SalesTable";
import { useDateRange } from "@/contexts/DateRangeContext";
import { toApiDate } from "@/lib/dateUtils";

export function DashboardPage() {
  const { preset, range } = useDateRange();
  const startDate = toApiDate(range.from);
  const endDate = toApiDate(range.to);

  return (
    <div className="max-w-7xl mx-auto px-6 pt-4 pb-8 space-y-8">
      <KpiCardGrid
        startDate={startDate}
        endDate={endDate}
        preset={preset}
        range={range}
      />
      {/* v1.56-b: OrdersDistributionCard (€/week/rep tile) moved into
          SalesActivityCard as the 5th bar chart.
          v1.56-c: two CustomerShareCards — one per data source (Aufträge
          + Rechnungen) side by side. */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <CustomerShareCard
          startDate={startDate}
          endDate={endDate}
          source="auftraege"
        />
        <CustomerShareCard
          startDate={startDate}
          endDate={endDate}
          source="revenues"
        />
      </div>
      <RevenueChart
        startDate={startDate}
        endDate={endDate}
        preset={preset}
        range={range}
      />
      <SalesActivityCard startDate={startDate} endDate={endDate} />
      <SalesTable startDate={startDate} endDate={endDate} />
    </div>
  );
}
