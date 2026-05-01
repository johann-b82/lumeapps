import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Separator } from "@/components/ui/separator";
import { DropZone } from "@/components/DropZone";
import { ContactsDropZone } from "@/components/ContactsDropZone";
import { ErrorList } from "@/components/ErrorList";
import { UploadHistory } from "@/components/UploadHistory";
import type { ValidationErrorDetail } from "@/lib/api";
import { useRole } from "@/auth/useAuth";

export function UploadPage() {
  const { t } = useTranslation();
  const [errors, setErrors] = useState<ValidationErrorDetail[]>([]);
  const role = useRole();

  // Inline role check (D-04 "Inline allowed where JSX wrap is awkward") —
  // page-level permission message for Viewer. Admin sees full page body.
  if (role !== "admin") {
    return (
      <div className="max-w-7xl mx-auto px-6 pt-4 pb-8">
        <p className="text-muted-foreground text-sm text-center py-16">
          You don't have permission to access this page.
        </p>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-6 pt-4 pb-8 space-y-8">
      <h1 className="text-xl font-semibold">{t("page_title")}</h1>

      {errors.length > 0 && <ErrorList errors={errors} />}

      <Separator className="my-8" />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <div className="space-y-4">
          <h2 className="text-xl font-semibold">{t("upload.orders_title")}</h2>
          <DropZone
            onUploadSuccess={() => setErrors([])}
            onUploadError={(data) => setErrors(data.errors)}
          />
        </div>
        <div className="space-y-4">
          <h2 className="text-xl font-semibold">{t("upload.contacts_title")}</h2>
          <ContactsDropZone />
        </div>
      </div>

      <div className="space-y-4">
        <h2 className="text-xl font-semibold">{t("history_title")}</h2>
        <UploadHistory />
      </div>
    </div>
  );
}
