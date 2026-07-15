import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { ChevronDown, ChevronRight, Loader2, Network } from "lucide-react";
import { fetchOrgChart, type OrgChartNode } from "@/lib/api";
import { hrKpiKeys } from "@/lib/queryKeys";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const ALL_OFFICES = "__all__";

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

function OrgNode({ node }: { node: TreeNode }) {
  const [open, setOpen] = useState(true);
  const hasChildren = node.children.length > 0;

  return (
    <li>
      <div className="flex items-start gap-1.5 py-1">
        {hasChildren ? (
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            aria-expanded={open}
            aria-label={fullName(node)}
            className="mt-1.5 text-muted-foreground hover:text-foreground
                       focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded"
          >
            {open ? (
              <ChevronDown className="w-4 h-4" aria-hidden="true" />
            ) : (
              <ChevronRight className="w-4 h-4" aria-hidden="true" />
            )}
          </button>
        ) : (
          <span className="w-4" aria-hidden="true" />
        )}

        <div className="rounded-lg border bg-card text-card-foreground px-3 py-2 shadow-sm min-w-[200px]">
          <div className="text-sm font-medium">{fullName(node)}</div>
          {node.position && (
            <div className="text-xs text-muted-foreground">{node.position}</div>
          )}
          {node.department && (
            <div className="text-[11px] text-muted-foreground/80 mt-0.5">
              {node.department}
            </div>
          )}
        </div>
      </div>

      {hasChildren && open && (
        <ul className="ml-[9px] border-l border-border pl-4">
          {node.children.map((child) => (
            <OrgNode key={child.id} node={child} />
          ))}
        </ul>
      )}
    </li>
  );
}

export function OrganigrammPage() {
  const { t } = useTranslation();
  const [office, setOffice] = useState<string>(ALL_OFFICES);
  const { data, isLoading, isError } = useQuery({
    queryKey: hrKpiKeys.orgChart(),
    queryFn: fetchOrgChart,
  });

  // Distinct offices present in the data, sorted — drives the filter dropdown.
  const offices = useMemo(() => {
    const set = new Set<string>();
    data?.forEach((n) => n.office && set.add(n.office));
    return Array.from(set).sort((a, b) => a.localeCompare(b));
  }, [data]);

  const filtered = useMemo(() => {
    if (!data) return [];
    return office === ALL_OFFICES ? data : data.filter((n) => n.office === office);
  }, [data, office]);

  const forest = useMemo(() => buildForest(filtered), [filtered]);

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
          <div className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground">
              {t("hr.organigramm.office")}
            </span>
            <Select value={office} onValueChange={setOffice}>
              <SelectTrigger className="w-48" aria-label={t("hr.organigramm.office")}>
                <SelectValue>
                  {office === ALL_OFFICES ? t("hr.organigramm.allOffices") : office}
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL_OFFICES}>
                  {t("hr.organigramm.allOffices")}
                </SelectItem>
                {offices.map((o) => (
                  <SelectItem key={o} value={o}>
                    {o}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
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
        <ul className="mt-2">
          {forest.map((root) => (
            <OrgNode key={root.id} node={root} />
          ))}
        </ul>
      )}
    </div>
  );
}
