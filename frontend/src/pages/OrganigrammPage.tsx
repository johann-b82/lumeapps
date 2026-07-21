import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { ChevronDown, ChevronUp, Loader2, Network, User } from "lucide-react";
import { fetchOrgChart, type OrgChartNode } from "@/lib/api";
import { hrKpiKeys } from "@/lib/queryKeys";

// Default location filter — the two main German offices, pre-selected.
const DEFAULT_OFFICES = ["Hamburg", "Memmingen"];

interface TreeNode extends OrgChartNode {
  children: TreeNode[];
}

function fullName(n: OrgChartNode): string {
  return [n.first_name, n.last_name].filter(Boolean).join(" ").trim() || `#${n.id}`;
}

/**
 * Build a forest from flat nodes. A node is a root when it has no supervisor,
 * or when its supervisor is not part of the active set (defensive — the backend
 * currently returns no such orphans). Guards against self- and cyclic parents.
 */
function buildForest(nodes: OrgChartNode[]): TreeNode[] {
  const byId = new Map<number, TreeNode>();
  nodes.forEach((n) => byId.set(n.id, { ...n, children: [] }));

  const roots: TreeNode[] = [];
  byId.forEach((node) => {
    const parent =
      node.supervisor_id != null ? byId.get(node.supervisor_id) : undefined;
    if (parent && parent.id !== node.id) parent.children.push(node);
    else roots.push(node);
  });

  const sortRec = (arr: TreeNode[]) => {
    arr.sort((a, b) => fullName(a).localeCompare(fullName(b)));
    arr.forEach((c) => sortRec(c.children));
  };
  sortRec(roots);
  return roots;
}

/** Compact row card used inside a stacked leaf column. */
function LeafCard({ node }: { node: TreeNode }) {
  return (
    <div className="flex w-[148px] items-center gap-2 text-left">
      <div
        className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full
                   bg-gradient-to-br from-sky-500 to-indigo-600 shadow-sm"
      >
        <User className="h-4 w-4 text-white" aria-hidden="true" />
      </div>
      <div className="min-w-0">
        <div className="truncate text-xs leading-tight font-medium">{fullName(node)}</div>
        {node.position && (
          <div className="truncate text-[11px] leading-tight text-muted-foreground">
            {node.position}
          </div>
        )}
      </div>
    </div>
  );
}

function OrgNode({ node, depth = 0 }: { node: TreeNode; depth?: number }) {
  // Levels 3+ start collapsed so the chart fits without sideways scrolling.
  const [open, setOpen] = useState(depth < 2);
  const hasChildren = node.children.length > 0;
  // When every report is itself a leaf, stack them in one narrow column
  // instead of spreading them across the full width.
  const leafOnly =
    hasChildren && node.children.every((c) => c.children.length === 0);

  return (
    <li>
      {/* Node card: avatar on top, details centred below — the connector lines
          around it come from the .org-tree rules in index.css. */}
      <div className="flex w-[160px] flex-col items-center px-1 text-center">
        <div
          className="flex h-14 w-14 items-center justify-center rounded-full
                     bg-gradient-to-br from-sky-500 to-indigo-600 shadow-sm"
        >
          <User className="h-7 w-7 text-white drop-shadow" aria-hidden="true" />
        </div>

        <div className="mt-2 text-sm leading-tight font-medium">{fullName(node)}</div>
        {node.position && (
          <div className="text-xs leading-tight text-muted-foreground">
            {node.position}
          </div>
        )}
        {node.department && (
          <div className="mt-0.5 text-[11px] leading-tight text-muted-foreground/80">
            {node.department}
          </div>
        )}

        {hasChildren && (
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            aria-expanded={open}
            aria-label={fullName(node)}
            className="mt-1 flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px]
                       text-muted-foreground hover:text-foreground
                       focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            {open ? (
              <ChevronUp className="h-3 w-3" aria-hidden="true" />
            ) : (
              <ChevronDown className="h-3 w-3" aria-hidden="true" />
            )}
            {node.children.length}
          </button>
        )}
      </div>

      {hasChildren &&
        open &&
        (leafOnly ? (
          <ul className="org-leaves">
            {node.children.map((child) => (
              <li key={child.id}>
                <LeafCard node={child} />
              </li>
            ))}
          </ul>
        ) : (
          <ul>
            {node.children.map((child) => (
              <OrgNode key={child.id} node={child} depth={depth + 1} />
            ))}
          </ul>
        ))}
    </li>
  );
}

export function OrganigrammPage() {
  const { t } = useTranslation();
  const [selected, setSelected] = useState<Set<string>>(
    () => new Set(DEFAULT_OFFICES),
  );
  const { data, isLoading, isError } = useQuery({
    queryKey: hrKpiKeys.orgChart(),
    queryFn: fetchOrgChart,
  });

  // Distinct offices present in the data, sorted — drives the filter chips.
  const offices = useMemo(() => {
    const set = new Set<string>();
    data?.forEach((n) => n.office && set.add(n.office));
    return Array.from(set).sort((a, b) => a.localeCompare(b));
  }, [data]);

  // Multi-select: show employees whose office is selected. Empty selection =
  // no location filter (show everyone).
  const filtered = useMemo(() => {
    if (!data) return [];
    if (selected.size === 0) return data;
    return data.filter((n) => n.office != null && selected.has(n.office));
  }, [data, selected]);

  const forest = useMemo(() => buildForest(filtered), [filtered]);

  const toggleOffice = (office: string) =>
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(office)) next.delete(office);
      else next.add(office);
      return next;
    });

  return (
    <div className="max-w-7xl mx-auto px-6 pt-4 pb-8">
      <div className="flex flex-wrap items-start justify-between gap-4 mb-6">
        <div>
          <h1 className="text-lg font-semibold mb-1 flex items-center gap-2">
            <Network className="w-5 h-5" aria-hidden="true" />
            {t("hr.organigramm.title")}
          </h1>
          {data && filtered.length > 0 && (
            <p className="text-sm text-muted-foreground">
              {t("hr.organigramm.subtitle", { count: filtered.length })}
            </p>
          )}
        </div>

        {data && offices.length > 0 && (
          <div className="flex flex-col gap-1.5">
            <span className="text-xs text-muted-foreground">
              {t("hr.organigramm.office")}
            </span>
            <div
              className="flex flex-wrap gap-2"
              role="group"
              aria-label={t("hr.organigramm.office")}
            >
              {offices.map((o) => {
                const on = selected.has(o);
                return (
                  <button
                    key={o}
                    type="button"
                    onClick={() => toggleOffice(o)}
                    aria-pressed={on}
                    className={`rounded-full border px-3 py-1 text-sm transition-colors
                                focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring
                                ${
                                  on
                                    ? "bg-primary text-primary-foreground border-primary"
                                    : "bg-transparent text-muted-foreground border-border hover:bg-muted"
                                }`}
                  >
                    {o}
                  </button>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {isLoading && (
        <div className="flex h-64 items-center justify-center">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" aria-label={t("hr.organigramm.title")} />
        </div>
      )}

      {isError && (
        <p className="text-sm text-destructive">{t("hr.organigramm.error")}</p>
      )}

      {data && filtered.length === 0 && (
        <p className="text-sm text-muted-foreground">{t("hr.organigramm.empty")}</p>
      )}

      {forest.length > 0 && (
        <div className="org-tree mt-2 overflow-x-auto pb-4">
          <ul>
            {forest.map((root) => (
              <OrgNode key={root.id} node={root} />
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
