import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { signageApi } from "@/signage/lib/signageApi";
import { signageKeys } from "@/lib/queryKeys";
import type { SignageMedia } from "@/signage/lib/signageTypes";

/**
 * MediaRegisterUrlForm — inline (non-modal) form for registering a URL or
 * HTML snippet as a `signage_media` row. Lives directly on /signage/media
 * as the right half of the entry-points grid (next to the upload drop
 * zone) since v1.36; previously this same form was wrapped in a Dialog
 * (MediaRegisterUrlDialog) and triggered by a button.
 *
 * Per ADR-0001 the create surface lives in Directus, not FastAPI:
 *   - kind=url  → { kind: "url",  title, uri: <content> }
 *   - kind=html → { kind: "html", title, html_content: <content> }
 * The user-supplied content maps to `uri` for url kind and `html_content`
 * for html kind; the form never POSTs to a FastAPI route.
 */

const formSchema = z.object({
  kind: z.enum(["url", "html"]),
  title: z.string().min(1),
  content: z.string().min(1),
});
type FormValues = z.infer<typeof formSchema>;

export function MediaRegisterUrlForm() {
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

  const kindValue = watch("kind");

  const createMutation = useMutation<SignageMedia, Error, FormValues>({
    mutationFn: async (values) => {
      // v1.23 C-4: createMedia routes non-PPTX kinds to Directus.
      //   url  → uri = values.content
      //   html → html_content = values.content
      if (values.kind === "url") {
        return await signageApi.createMedia({
          kind: "url",
          title: values.title,
          uri: values.content,
        });
      }
      return await signageApi.createMedia({
        kind: "html",
        title: values.title,
        html_content: values.content,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: signageKeys.media() });
      toast.success(t("signage.admin.media.register_url_title"));
      // Inline form: reset to empty so the next entry can be typed without
      // an extra click. Previous Dialog version closed the modal here.
      reset({ kind: "url", title: "", content: "" });
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
    // v1.40: drop the dashed border + bg-muted chrome — the form sits
    // inside the page-level Card now and matches the visual weight of a
    // settings-form section.
    <form
      onSubmit={handleSubmit(onSubmit)}
      className="flex flex-col gap-3"
      aria-labelledby="register-url-heading"
    >
      <h2
        id="register-url-heading"
        className="text-sm font-semibold text-foreground"
      >
        {t("signage.admin.media.register_url_title")}
      </h2>
      <fieldset className="flex flex-col gap-2">
        <legend className="sr-only">
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
          className="bg-background"
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
          className="bg-background"
          {...register("content")}
          aria-invalid={errors.content ? "true" : "false"}
          placeholder={
            kindValue === "url" ? "https://example.com" : "<div>...</div>"
          }
        />
      </div>

      <div className="flex justify-end pt-1">
        <Button type="submit" disabled={isSubmitting}>
          {t("signage.admin.media.register_url_cta")}
        </Button>
      </div>
    </form>
  );
}
