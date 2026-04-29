import { HrKpiCardGrid } from "@/components/dashboard/HrKpiCardGrid";
import { HrKpiCharts } from "@/components/dashboard/HrKpiCharts";
import { EmployeeTable } from "@/components/dashboard/EmployeeTable";

export function HRPage() {
  return (
    <div className="max-w-7xl mx-auto px-6 pt-4 pb-8 space-y-8">
      <HrKpiCardGrid />
      <HrKpiCharts />
      <EmployeeTable />
    </div>
  );
}
