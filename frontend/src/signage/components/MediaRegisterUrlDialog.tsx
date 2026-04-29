import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { apiClient } from "@/lib/apiClient";
import { signageKeys } from "@/lib/queryKeys";
import type { SignageMedia } from "@/signage/lib/signageTypes";

/**
 * MediaRegisterUrlDialog — small URL/HTML registration form (D-03).
 *
 * Posts a SignageMedia create payload to /api/signage/media. Two kinds:
 *   - kind=url  → body { kind: "url", title, url: <content>, tags: [] }
 *   - kind=html → body { kind: "html", title, metadata: { html: <content> },
 *                        tags: [] }
 *
 * The backend's SignageMediaCreate has Pydantic v2 default extra="ignore" so
 * unknown fields like `tags` and `metadata` are dropped server-side; that's
 * fine — they are documented per UI-SPEC for forward compatibility.
 */

const formSchema = z.object({
  kind: z.enum(["url", "html"]),
  title: z.string().min(1),
  content: z.string().min(1),
});
type FormValues = z.infer<typeof formSchema>;

export interface MediaRegisterUrlDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function MediaRegisterUrlDialog({
  open,
  onOpenChange,
}: MediaRegisterUrlDialogProps) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();

  const {
    register,
    handleSubmit,
    reset,
    watch,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: { kind: "url", title: "", content: "" },
  });

  // Reset form when the dialog closes so re-opening is clean.
  useEffect(() => {
    if (!open) reset({ kind: "url", title: "", content: "" });
  }, [open, reset]);

  const kindValue = watch("kind");

  const createMutation = useMutation<SignageMedia, Error, FormValues>({
    mutationFn: async (values) => {
      const body =
        values.kind === "url"
          ? {
              kind: "url" as const,
              title: values.title,
              url: values.content,
              tags: [] as number[],
            }
          : {
              kind: "html" as const,
              title: values.title,
              metadata: { html: values.content },
              tags: [] as number[],
            };
      return await apiClient<SignageMedia>("/api/signage/media", {
        method: "POST",
        body: JSON.stringify(body),
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: signageKeys.media() });
      toast.success(t("signage.admin.media.register_url_title"));
      onOpenChange(false);
    },
    onError: (err) => {
      toast.error(
        t("signage.admin.error.generic", { detail: err.message }),
      );
    },
  });

  const onSubmit = (values: FormValues) => {
    createMutation.mutate(values);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            {t("signage.admin.media.register_url_title")}
          </DialogTitle>
          <DialogDescription>
            {t("signage.admin.media.register_url_label")}
          </DialogDescription>
        </DialogHeader>
        <form
          onSubmit={handleSubmit(onSubmit)}
          className="flex flex-col gap-4"
        >
          <fieldset className="flex flex-col gap-2">
            <legend className="text-sm font-medium text-foreground">
              {t("signage.admin.media.register_url_label")}
            </legend>
            <div className="flex gap-3 text-sm">
              <label className="flex items-center gap-2">
                <Input
                  type="radio"
                  value="url"
                  checked={kindValue === "url"}
                  onChange={() => setValue("kind", "url")}
                  className="h-auto w-auto min-w-0 rounded-none border-0 bg-transparent px-0 py-0"
                />
                URL
              </label>
              <label className="flex items-center gap-2">
                <Input
                  type="radio"
                  value="html"
                  checked={kindValue === "html"}
                  onChange={() => setValue("kind", "html")}
                  className="h-auto w-auto min-w-0 rounded-none border-0 bg-transparent px-0 py-0"
                />
                HTML
              </label>
            </div>
          </fieldset>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="register-title">
              {t("signage.admin.media.register_url_title")}
            </Label>
            <Input
              id="register-title"
              type="text"
              {...register("title")}
              aria-invalid={errors.title ? "true" : "false"}
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="register-content">
              {t("signage.admin.media.register_url_label")}
            </Label>
            <Input
              id="register-content"
              type="text"
              {...register("content")}
              aria-invalid={errors.content ? "true" : "false"}
              placeholder={
                kindValue === "url" ? "https://example.com" : "<div>...</div>"
              }
            />
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              {t("signage.admin.media.delete_cancel")}
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {t("signage.admin.media.register_url_cta")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
