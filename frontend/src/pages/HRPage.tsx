import { HrKpiCardGrid } from "@/components/dashboard/HrKpiCardGrid";
import { HrKpiCharts } from "@/components/dashboard/HrKpiCharts";
import { EmployeeTable } from "@/components/dashboard/EmployeeTable";
import { BirthdaysCard } from "@/components/dashboard/BirthdaysCard";

export function HRPage() {
  return (
    <div className="max-w-7xl mx-auto px-6 pt-4 pb-8 space-y-8">
      <BirthdaysCard />
      <HrKpiCardGrid />
      <HrKpiCharts />
      <EmployeeTable />
    </div>
  );
}
