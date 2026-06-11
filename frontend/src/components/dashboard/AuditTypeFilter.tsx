/**
 * AuditTypeFilter — checkbox group for the four audit-type codes
 * (BH AUD / EX AUD / IN AUD / KU AUD). All four are pre-selected;
 * unchecking one removes its findings from the count.
 */
import { useTranslation } from "react-i18next";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { AUDIT_TYPE_CODES, type AuditTypeCode } from "@/lib/api";

interface AuditTypeFilterProps {
  selected: readonly AuditTypeCode[];
  onChange: (next: AuditTypeCode[]) => void;
}

export function AuditTypeFilter({ selected, onChange }: AuditTypeFilterProps) {
  const { t } = useTranslation();
  const set = new Set<AuditTypeCode>(selected);

  const toggle = (code: AuditTypeCode, checked: boolean) => {
    const next = new Set(set);
    if (checked) next.add(code);
    else next.delete(code);
    onChange(AUDIT_TYPE_CODES.filter((c) => next.has(c)));
  };

  return (
    <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
      <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {t("quality.filter.auditTypes")}
      </p>
      {AUDIT_TYPE_CODES.map((code) => {
        const id = `audit-type-${code.replace(/\s+/g, "-").toLowerCase()}`;
        return (
          <div key={code} className="flex items-center gap-2">
            <Checkbox
              id={id}
              checked={set.has(code)}
              onCheckedChange={(state) => toggle(code, state === true)}
            />
            <Label htmlFor={id} className="text-sm font-normal cursor-pointer">
              {t(`quality.auditType.${code.replace(/\s+/g, "_")}`)}
            </Label>
          </div>
        );
      })}
    </div>
  );
}
