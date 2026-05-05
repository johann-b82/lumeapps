import { CustomerShareCard } from "@/components/dashboard/CustomerShareCard";
import { KpiCardGrid } from "@/components/dashboard/KpiCardGrid";
import { OrdersDistributionCard } from "@/components/dashboard/OrdersDistributionCard";
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
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 items-stretch">
        <OrdersDistributionCard
          startDate={startDate}
          endDate={endDate}
          preset={preset}
          range={range}
        />
        <CustomerShareCard
          startDate={startDate}
          endDate={endDate}
          className="lg:col-span-2"
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
