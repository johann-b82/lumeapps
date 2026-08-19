import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchOrgChart, type OrgChartNode } from "@/lib/api";

/** Personio-backed assignee picker (active workforce). Emits {id, name}. */
export function AssigneeSelect({
  value,
  onChange,
  placeholder,
}: {
  value: string | null;
  onChange: (v: { id: string; name: string } | null) => void;
  placeholder?: string;
}) {
  const { data } = useQuery({ queryKey: ["org-chart"], queryFn: fetchOrgChart });

  const people = useMemo(() => {
    const list = (data ?? []).map((n: OrgChartNode) => ({
      id: String(n.id),
      name: [n.last_name, n.first_name].filter(Boolean).join(", ") || `#${n.id}`,
    }));
    list.sort((a, b) => a.name.localeCompare(b.name, "de"));
    return list;
  }, [data]);

  return (
    <select
      value={value ?? ""}
      onChange={(e) => {
        const id = e.target.value;
        if (!id) return onChange(null);
        const p = people.find((x) => x.id === id);
        onChange(p ? { id: p.id, name: p.name } : null);
      }}
      className="h-8 w-full rounded-lg border border-border bg-background px-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      <option value="">{placeholder ?? "—"}</option>
      {people.map((p) => (
        <option key={p.id} value={p.id}>
          {p.name}
        </option>
      ))}
    </select>
  );
}
