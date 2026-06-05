import { HrKpiCardGrid } from "@/components/dashboard/HrKpiCardGrid";
import { HrKpiCharts } from "@/components/dashboard/HrKpiCharts";
import { EmployeeTable } from "@/components/dashboard/EmployeeTable";
import { BirthdaysCard } from "@/components/dashboard/BirthdaysCard";
import { JoinersCard } from "@/components/dashboard/JoinersCard";

export function HRPage() {
  return (
    <div className="max-w-7xl mx-auto px-6 pt-4 pb-8 space-y-8">
      <BirthdaysCard />
      <JoinersCard />
      <HrKpiCardGrid />
      <HrKpiCharts />
      <EmployeeTable />
    </div>
  );
}
