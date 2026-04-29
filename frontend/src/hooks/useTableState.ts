import { useMemo, useState } from "react";

type SortDir = "asc" | "desc";

export interface ColumnFilter {
  key: string;
  value: string;
}

export function useTableState<T extends Record<string, unknown>>(
  data: T[] | undefined,
  defaultSort?: { key: keyof T & string; dir: SortDir }
) {
  const [sortKey, setSortKey] = useState<string>(defaultSort?.key ?? "");
  const [sortDir, setSortDir] = useState<SortDir>(defaultSort?.dir ?? "asc");
  const [filters, setFilters] = useState<Record<string, string>>({});

  const toggleSort = (key: string) => {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("asc");
    }
  };

  const setFilter = (key: string, value: string) => {
    setFilters((prev) => {
      if (!value) {
        const next = { ...prev };
        delete next[key];
        return next;
      }
      return { ...prev, [key]: value };
    });
  };

  const processed = useMemo(() => {
    if (!data) return [];
    let rows = [...data];

    // Apply column filters
    for (const [key, value] of Object.entries(filters)) {
      if (!value) continue;
      const lower = value.toLowerCase();
      rows = rows.filter((row) => {
        const cell = row[key];
        if (cell == null) return false;
        return String(cell).toLowerCase().includes(lower);
      });
    }

    // Apply sort
    if (sortKey) {
      rows.sort((a, b) => {
        const av = a[sortKey];
        const bv = b[sortKey];
        if (av == null && bv == null) return 0;
        if (av == null) return 1;
        if (bv == null) return -1;
        if (typeof av === "number" && typeof bv === "number") {
          return sortDir === "asc" ? av - bv : bv - av;
        }
        const cmp = String(av).localeCompare(String(bv), undefined, { numeric: true });
        return sortDir === "asc" ? cmp : -cmp;
      });
    }

    return rows;
  }, [data, filters, sortKey, sortDir]);

  return { processed, sortKey, sortDir, toggleSort, filters, setFilter };
}
