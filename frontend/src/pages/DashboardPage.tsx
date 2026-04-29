import { KpiCardGrid } from "@/components/dashboard/KpiCardGrid";
import { RevenueChart } from "@/components/dashboard/RevenueChart";
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
      <RevenueChart
        startDate={startDate}
        endDate={endDate}
        preset={preset}
        range={range}
      />
      <SalesTable startDate={startDate} endDate={endDate} />
    </div>
  );
}
