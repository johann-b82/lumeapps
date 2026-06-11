import { useState } from "react";
import { QualityKpiCardGrid } from "@/components/dashboard/QualityKpiCardGrid";
import { QualityKpiCharts } from "@/components/dashboard/QualityKpiCharts";
import { QualityFindingsTable } from "@/components/dashboard/QualityFindingsTable";
import { AuditTypeFilter } from "@/components/dashboard/AuditTypeFilter";
import { AUDIT_TYPE_CODES, type AuditTypeCode } from "@/lib/api";

export function QualityPage() {
  // All four audit types pre-selected — the typical view is the full
  // audit picture; unchecking is the rare drill-down.
  const [auditTypes, setAuditTypes] = useState<readonly AuditTypeCode[]>(
    AUDIT_TYPE_CODES,
  );

  return (
    <div className="max-w-7xl mx-auto px-6 pt-4 pb-8 space-y-8">
      <AuditTypeFilter selected={auditTypes} onChange={setAuditTypes} />
      <QualityKpiCardGrid auditTypes={auditTypes} />
      <QualityKpiCharts auditTypes={auditTypes} />
      <QualityFindingsTable auditTypes={auditTypes} />
    </div>
  );
}
