import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useLocation } from "wouter";
import { useForm, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { signageKeys } from "@/lib/queryKeys";
import { signageApi } from "@/signage/lib/signageApi";
import { TagPicker } from "@/signage/components/TagPicker";

// XXX-XXX where each X is [A-Z0-9].
const codePattern = /^[A-Z0-9]{3}-[A-Z0-9]{3}$/;

const schema = z.object({
  code: z.string().regex(codePattern, "format: XXX-XXX"),
  device_name: z.string().min(1).max(128),
  tags: z.array(z.string()),
});
type FormValues = z.infer<typeof schema>;

/**
 * /signage/pair — admin claim form for the 6-character device pairing code
 * (SGN-ADM-07). Code input auto-formats to XXX-XXX (hyphen auto-inserted
 * after position 3, uppercased, alphanumeric-only). Tag chips are
 * resolved name → id (creating unknown ones via signageApi.createTag) before
 * POST /api/signage/pair/claim. Backend collapses invalid/expired/claimed
 * into a single 404 ("pairing code invalid, expired, or already claimed");
 * we substring-match the detail to surface specific inline messages.
 */
export function PairPage() {
  const { t } = useTranslation();
  const [, setLocation] = useLocation();
  const queryClient = useQueryClient();
  const [rawCode, setRawCode] = useState("");

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { code: "", device_name: "", tags: [] },
  });

  function handleCodeChange(event: React.ChangeEvent<HTMLInputElement>) {
    const cleaned = event.target.value
      .replace(/[^A-Za-z0-9]/g, "")
      .toUpperCase()
      .slice(0, 6);
    const formatted =
      cleaned.length > 3 ? `${cleaned.slice(0, 3)}-${cleaned.slice(3)}` : cleaned;
    setRawCode(formatted);
    form.setValue("code", formatted, {
      shouldValidate: true,
      shouldDirty: true,
    });
  }

  const claimMutation = useMutation({
    mutationFn: async (values: FormValues) => {
      // Resolve tag names → ids (create-on-submit). Same dance as 46-05 task 3.
      const existing = await signageApi.listTags();
      const nameToId = new Map(existing.map((tag) => [tag.name, tag.id]));
      const tagIds: number[] = [];
      for (const name of values.tags) {
        let id = nameToId.get(name);
        if (id === undefined) {
          const created = await signageApi.createTag(name);
          id = created.id;
        }
        tagIds.push(id);
      }
      return signageApi.claimPairingCode({
        code: values.code,
        device_name: values.device_name,
        tag_ids: tagIds.length > 0 ? tagIds : null,
      });
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: signageKeys.devices() });
      queryClient.invalidateQueries({ queryKey: signageKeys.tags() });
      toast.success(
        t("signage.admin.pair.success", { name: variables.device_name }),
      );
      setLocation("/signage/devices");
    },
    onError: (err: unknown) => {
      const detail = err instanceof Error ? err.message : String(err);
      // Backend collapses invalid/expired/claimed into one 404 detail string;
      // best-effort substring match for actionable inline UX.
      if (/invalid|expired/i.test(detail) && !/claimed/i.test(detail)) {
        form.setError("code", {
          message: t("signage.admin.pair.error_not_found"),
        });
      } else if (/claimed/i.test(detail)) {
        form.setError("code", {
          message: t("signage.admin.pair.error_claimed"),
        });
      } else {
        toast.error(t("signage.admin.pair.error_generic", { detail }));
      }
    },
  });

  const onSubmit = form.handleSubmit((values) => claimMutation.mutate(values));

  return (
    <div className="max-w-xl mx-auto px-6 pt-8 pb-16">
      <div className="rounded-xl border border-border bg-card p-6 space-y-6 shadow-sm">
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold">
            {t("signage.admin.pair.title")}
          </h1>
          <p className="text-sm text-muted-foreground">
            {t("signage.admin.pair.subtitle")}
          </p>
        </div>

        <form onSubmit={onSubmit} className="space-y-5">
          <div className="space-y-2">
            <Label htmlFor="pair-code">
              {t("signage.admin.pair.code_label")}
            </Label>
            <Input
              id="pair-code"
              value={rawCode}
              onChange={handleCodeChange}
              placeholder={t("signage.admin.pair.code_placeholder")}
              maxLength={7}
              className="text-4xl font-mono font-semibold tracking-widest text-center w-full uppercase"
              aria-label={t("signage.admin.pair.code_label")}
              autoComplete="off"
              autoFocus
            />
            {form.formState.errors.code && (
              <p className="text-sm text-destructive">
                {form.formState.errors.code.message}
              </p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="pair-device-name">
              {t("signage.admin.pair.name_label")}
            </Label>
            <Input
              id="pair-device-name"
              {...form.register("device_name")}
              placeholder={t("signage.admin.pair.name_placeholder")}
              autoComplete="off"
            />
            {form.formState.errors.device_name && (
              <p className="text-sm text-destructive">
                {form.formState.errors.device_name.message}
              </p>
            )}
          </div>

          <div className="space-y-2">
            <Label>{t("signage.admin.pair.tags_label")}</Label>
            <Controller
              name="tags"
              control={form.control}
              render={({ field }) => (
                <TagPicker
                  value={field.value}
                  onChange={field.onChange}
                  placeholder={t("signage.admin.pair.tags_placeholder")}
                  ariaLabel={t("signage.admin.pair.tags_label")}
                />
              )}
            />
          </div>

          <div className="flex justify-between pt-2">
            <Button
              type="button"
              variant="ghost"
              onClick={() => setLocation("/signage/devices")}
              disabled={claimMutation.isPending}
            >
              {t("signage.admin.pair.cancel")}
            </Button>
            <Button type="submit" disabled={claimMutation.isPending}>
              {t("signage.admin.pair.submit")}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
