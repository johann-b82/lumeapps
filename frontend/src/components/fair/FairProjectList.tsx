/**
 * Landing view for /fair: upload a drawing, search across name / P/N / customer
 * / article number (live), and open/delete existing projects grouped by
 * customer. Customer groups are collapsible and collapsed by default; a search
 * expands the matching groups automatically.
 */
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useLocation } from "wouter";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import {
  ChevronDown,
  ChevronRight,
  FileImage,
  FileText,
  Loader2,
  Search,
  Trash2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { fairApi } from "@/lib/fairApi";
import type { FairProject } from "@/lib/fairApi";
import { fairKeys } from "@/lib/queryKeys";
import { FairUpload } from "./FairUpload";

export function FairProjectList() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [, navigate] = useLocation();
  const [query, setQuery] = useState("");
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const { data: projects, isLoading } = useQuery({
    queryKey: fairKeys.projects(),
    queryFn: fairApi.listProjects,
  });

  const handleDelete = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await fairApi.deleteProject(id);
      await queryClient.invalidateQueries({ queryKey: fairKeys.projects() });
    } catch (err) {
      toast.error((err as Error).message);
    }
  };

  const q = query.trim().toLowerCase();
  const isSearching = q.length > 0;
  const filtered = (projects ?? []).filter((p) =>
    !q
      ? true
      : [p.name, p.part_number, p.customer, p.article_number].some((f) =>
          (f ?? "").toLowerCase().includes(q),
        ),
  );

  // Group by customer ("" = no customer, sorted last).
  const groups = new Map<string, FairProject[]>();
  for (const p of filtered) {
    const key = (p.customer ?? "").trim();
    const arr = groups.get(key) ?? [];
    arr.push(p);
    groups.set(key, arr);
  }
  for (const arr of groups.values()) {
    arr.sort((a, b) => b.created_at.localeCompare(a.created_at));
  }
  const groupKeys = [...groups.keys()].sort((a, b) => {
    if (a === "") return 1;
    if (b === "") return -1;
    return a.localeCompare(b);
  });

  const toggle = (key: string) =>
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });

  return (
    <div className="space-y-6">
      <FairUpload />

      <div className="space-y-3">
        <div className="flex items-center justify-between gap-3">
          <h3 className="text-sm font-semibold">{t("fair.projects.title")}</h3>
          <div className="relative w-full max-w-xs">
            <Search className="pointer-events-none absolute left-2 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={t("fair.search.placeholder")}
              className="h-8 pl-8"
            />
          </div>
        </div>

        {isLoading ? (
          <div className="flex justify-center py-10">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : !projects || projects.length === 0 ? (
          <p className="py-8 text-center text-sm text-muted-foreground">
            {t("fair.projects.empty")}
          </p>
        ) : filtered.length === 0 ? (
          <p className="py-8 text-center text-sm text-muted-foreground">
            {t("fair.projects.noResults")}
          </p>
        ) : (
          <div className="space-y-2">
            {groupKeys.map((key) => {
              const items = groups.get(key) ?? [];
              const open = isSearching || expanded.has(key);
              return (
                <div key={key || "__none__"} className="rounded-md border">
                  <button
                    type="button"
                    onClick={() => toggle(key)}
                    className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-left hover:bg-muted/50"
                  >
                    {open ? (
                      <ChevronDown className="h-4 w-4 shrink-0" />
                    ) : (
                      <ChevronRight className="h-4 w-4 shrink-0" />
                    )}
                    <span className="font-medium">
                      {key || t("fair.projects.noCustomer")}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      ({items.length})
                    </span>
                  </button>
                  {open && (
                    <div className="grid gap-3 p-3 pt-0 sm:grid-cols-2 lg:grid-cols-3">
                      {items.map((p) => (
                        <ProjectCard
                          key={p.id}
                          project={p}
                          deleteLabel={t("fair.projects.delete")}
                          onOpen={() => navigate(`/fair/${p.id}`)}
                          onDelete={(e) => void handleDelete(p.id, e)}
                        />
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

function ProjectCard({
  project,
  deleteLabel,
  onOpen,
  onDelete,
}: {
  project: FairProject;
  deleteLabel: string;
  onOpen: () => void;
  onDelete: (e: React.MouseEvent) => void;
}) {
  const meta = [project.part_number, project.article_number]
    .filter(Boolean)
    .join(" · ");
  return (
    <Card
      role="button"
      tabIndex={0}
      onClick={onOpen}
      onKeyDown={(e) => {
        if (e.key === "Enter") onOpen();
      }}
      className="cursor-pointer transition-shadow hover:shadow-md"
    >
      <CardContent className="flex items-center gap-3 p-4">
        {project.file_kind === "pdf" ? (
          <FileText className="h-8 w-8 shrink-0 text-muted-foreground" />
        ) : (
          <FileImage className="h-8 w-8 shrink-0 text-muted-foreground" />
        )}
        <div className="min-w-0 flex-1">
          <p className="truncate font-medium">{project.name}</p>
          {meta && <p className="truncate text-xs text-muted-foreground">{meta}</p>}
          <p className="text-xs text-muted-foreground">
            {new Date(project.created_at).toLocaleDateString()}
          </p>
        </div>
        <Button
          type="button"
          size="icon-sm"
          variant="ghost"
          onClick={onDelete}
          title={deleteLabel}
        >
          <Trash2 className="h-4 w-4 text-destructive" />
        </Button>
      </CardContent>
    </Card>
  );
}
