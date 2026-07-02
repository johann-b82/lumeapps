/**
 * FAIR module page (Erstmusterprüfung / drawing ballooning). Without an :id it
 * shows the project list + upload; with an :id it shows the editor canvas and
 * the running value table.
 */
import { useCallback, useRef } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useLocation, useParams } from "wouter";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { ArrowLeft, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { fairApi } from "@/lib/fairApi";
import type { FairBalloon } from "@/lib/fairApi";
import { fairKeys } from "@/lib/queryKeys";
import { FairProjectList } from "@/components/fair/FairProjectList";
import { FairEditorCanvas } from "@/components/fair/FairEditorCanvas";
import { FairBalloonTable } from "@/components/fair/FairBalloonTable";

export function FairPage() {
  const { t } = useTranslation();
  const params = useParams<{ id?: string }>();
  const id = params.id;

  if (!id) {
    return (
      <div className="mx-auto max-w-5xl px-6 pt-4 pb-8">
        <h2 className="mb-4 text-lg font-semibold">{t("fair.title")}</h2>
        <FairProjectList />
      </div>
    );
  }
  return <FairEditorView projectId={id} />;
}

function FairEditorView({ projectId }: { projectId: string }) {
  const { t } = useTranslation();
  const [, navigate] = useLocation();
  const queryClient = useQueryClient();

  // The editor (which owns the drawing + OCR worker) registers a per-balloon
  // re-OCR function here so the results table can trigger it per row.
  const reOcrRef = useRef<((b: FairBalloon) => Promise<string | null>) | null>(
    null,
  );
  const registerReocr = useCallback(
    (fn: (b: FairBalloon) => Promise<string | null>) => {
      reOcrRef.current = fn;
    },
    [],
  );

  const { data: project, isLoading, isError } = useQuery({
    queryKey: fairKeys.project(projectId),
    queryFn: () => fairApi.getProject(projectId),
  });

  const saveField = async (
    field: "part_number" | "customer" | "article_number",
    value: string,
  ) => {
    const v = value.trim() || null;
    if (v === (project?.[field] ?? null)) return;
    try {
      await fairApi.patchProject(projectId, { [field]: v });
      await queryClient.invalidateQueries({ queryKey: fairKeys.project(projectId) });
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  if (isLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }
  if (isError || !project) {
    return (
      <div className="mx-auto max-w-5xl px-6 pt-8 text-center">
        <p className="text-sm text-muted-foreground">{t("fair.loadError")}</p>
        <Button className="mt-4" variant="outline" onClick={() => navigate("/fair")}>
          {t("fair.back")}
        </Button>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-[1920px] space-y-4 px-6 pt-4 pb-8">
      <div className="flex flex-wrap items-center gap-3">
        <Button variant="ghost" size="sm" onClick={() => navigate("/fair")}>
          <ArrowLeft className="h-4 w-4" />
          <span className="ml-1">{t("fair.back")}</span>
        </Button>
        <h2 className="truncate text-lg font-semibold">{project.name}</h2>
        <div className="ml-auto flex flex-wrap items-center gap-x-4 gap-y-2">
          <LabeledField
            id="fair-customer"
            label={t("fair.customer")}
            value={project.customer}
            placeholder={t("fair.customerPlaceholder")}
            onSave={(v) => void saveField("customer", v)}
          />
          <LabeledField
            id="fair-article"
            label={t("fair.articleNumber")}
            value={project.article_number}
            placeholder={t("fair.articleNumberPlaceholder")}
            onSave={(v) => void saveField("article_number", v)}
          />
          <LabeledField
            id="fair-pn"
            label={t("fair.partNumber")}
            value={project.part_number}
            placeholder={t("fair.partNumberPlaceholder")}
            onSave={(v) => void saveField("part_number", v)}
          />
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-4">
        <div className="lg:col-span-3">
          <FairEditorCanvas project={project} registerReocr={registerReocr} />
        </div>
        <div className="lg:col-span-1">
          <FairBalloonTable
            projectId={project.id}
            projectName={project.name}
            balloons={project.balloons}
            showPage={project.page_count > 1}
            onReocr={(b) =>
              reOcrRef.current ? reOcrRef.current(b) : Promise.resolve(null)
            }
          />
        </div>
      </div>
    </div>
  );
}

/** Labeled, uncontrolled text field that commits on blur / Enter. */
function LabeledField({
  id,
  label,
  value,
  placeholder,
  onSave,
}: {
  id: string;
  label: string;
  value: string | null;
  placeholder: string;
  onSave: (v: string) => void;
}) {
  return (
    <div className="flex items-center gap-2">
      <label htmlFor={id} className="text-sm font-medium text-muted-foreground">
        {label}
      </label>
      <Input
        id={id}
        key={value ?? ""}
        defaultValue={value ?? ""}
        placeholder={placeholder}
        className="h-8 w-40"
        onBlur={(e) => onSave(e.currentTarget.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") e.currentTarget.blur();
        }}
      />
    </div>
  );
}
