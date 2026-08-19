import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Toggle } from "@/components/ui/toggle";
import { SegmentedControl } from "@/components/ui/segmented-control";
import { QualityKpiCardGrid } from "@/components/dashboard/QualityKpiCardGrid";
import { QualityKpiCharts } from "@/components/dashboard/QualityKpiCharts";
import { QualityFindingsTable } from "@/components/dashboard/QualityFindingsTable";
import { AuditTypeFilter } from "@/components/dashboard/AuditTypeFilter";
import { ComplaintRateCardGrid } from "@/components/dashboard/ComplaintRateCardGrid";
import { ComplaintRateChart } from "@/components/dashboard/ComplaintRateChart";
import { CustomerComplaintsTable } from "@/components/dashboard/CustomerComplaintsTable";
import { QualityInspectionCardGrid } from "@/components/dashboard/QualityInspectionCardGrid";
import { QualityInspectionCharts } from "@/components/dashboard/QualityInspectionCharts";
import { QualityInspectionList } from "@/components/dashboard/QualityInspectionList";
import { KpiBubbleOverlay } from "@/components/kpireview/KpiBubbleOverlay";
import {
  AUDIT_TYPE_CODES,
  type AuditTypeCode,
  type ComplaintType,
  type QtyMode,
} from "@/lib/api";

type QualityView = "audits" | "complaints" | "inspections";

export function QualityPage() {
  const { t } = useTranslation();

  // Top-level view toggle: Audits | Reklamationen | Qualitätsprüfung.
  // 3 segments → Toggle-component's 2-segment constraint doesn't fit,
  // so we use the SegmentedControl (same pattern as the complaint-type
  // 4-way switch below).
  const [view, setView] = useState<QualityView>("audits");

  // Audits state — unchanged from the v1.49 page.
  const [auditTypes, setAuditTypes] = useState<readonly AuditTypeCode[]>(
    AUDIT_TYPE_CODES,
  );

  // Reklamationen state: which art codes feed the numerator (Kunden- vs
  // interne Reklamation) and which Mengen-Spalte (K vs L) the sum uses.
  const [qtyMode, setQtyMode] = useState<QtyMode>("total");
  const [complaintType, setComplaintType] = useState<ComplaintType>("customer");

  return (
    <div className="max-w-7xl mx-auto px-6 pt-4 pb-8">
      <KpiBubbleOverlay kpiKey="quality">
        <div className="space-y-8">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <SegmentedControl<QualityView>
          segments={[
            { value: "audits", label: t("quality.view.audits") },
            { value: "complaints", label: t("quality.view.complaints") },
            { value: "inspections", label: t("quality.view.inspections") },
          ]}
          value={view}
          onChange={setView}
          aria-label={t("quality.view.toggleLabel")}
        />
        {view === "audits" && (
          <AuditTypeFilter selected={auditTypes} onChange={setAuditTypes} />
        )}
        {view === "complaints" && (
          <div className="flex flex-wrap items-center gap-3">
            <SegmentedControl<ComplaintType>
              segments={[
                { value: "customer", label: t("quality.complaintType.customer") },
                { value: "internal", label: t("quality.complaintType.internal") },
                { value: "supplier", label: t("quality.complaintType.supplier") },
                { value: "subcontractor", label: t("quality.complaintType.subcontractor") },
              ]}
              value={complaintType}
              onChange={setComplaintType}
              aria-label={t("quality.complaintType.toggleLabel")}
            />
            <Toggle<QtyMode>
              segments={[
                { value: "total", label: t("quality.qtyMode.total") },
                { value: "accepted", label: t("quality.qtyMode.accepted") },
              ] as const}
              value={qtyMode}
              onChange={setQtyMode}
              aria-label={t("quality.qtyMode.toggleLabel")}
              variant="muted"
            />
          </div>
        )}
      </div>

      {view === "audits" && (
        <>
          <QualityKpiCardGrid auditTypes={auditTypes} />
          <QualityKpiCharts auditTypes={auditTypes} />
          <QualityFindingsTable auditTypes={auditTypes} />
        </>
      )}
      {view === "complaints" && (
        <>
          <ComplaintRateCardGrid qtyMode={qtyMode} complaintType={complaintType} />
          <ComplaintRateChart qtyMode={qtyMode} complaintType={complaintType} />
          <CustomerComplaintsTable complaintType={complaintType} />
        </>
      )}
      {view === "inspections" && (
        <>
          <QualityInspectionCardGrid />
          <QualityInspectionCharts />
          <QualityInspectionList />
        </>
      )}
        </div>
      </KpiBubbleOverlay>
    </div>
  );
}
