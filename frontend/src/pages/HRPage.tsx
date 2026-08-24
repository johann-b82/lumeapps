import { HrKpiCardGrid } from "@/components/dashboard/HrKpiCardGrid";
import { HrKpiCharts } from "@/components/dashboard/HrKpiCharts";
import { EmployeeTable } from "@/components/dashboard/EmployeeTable";
import { BirthdaysCard } from "@/components/dashboard/BirthdaysCard";
import { JoinersCard } from "@/components/dashboard/JoinersCard";
import { KpiBubbleOverlay } from "@/components/kpireview/KpiBubbleOverlay";
import { WeeklyReportSection } from "@/components/dashboard/WeeklyReportSection";
import { AdminOnly } from "@/auth/AdminOnly";

export function HRPage() {
  return (
    <div className="max-w-7xl mx-auto px-6 pt-4 pb-8">
      <KpiBubbleOverlay kpiKey="hr">
        <div className="space-y-8">
          <BirthdaysCard />
          <JoinersCard />
          <HrKpiCardGrid />
          <HrKpiCharts />
          {/* Weekly Report: personenbezogene Leistungs-/Gesundheitsdaten → admin-only. */}
          <AdminOnly>
            <WeeklyReportSection />
          </AdminOnly>
          <EmployeeTable />
        </div>
      </KpiBubbleOverlay>
    </div>
  );
}
