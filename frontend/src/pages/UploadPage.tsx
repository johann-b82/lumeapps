import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Card } from "@/components/ui/card";
import { DropZone } from "@/components/DropZone";
import { ContactsDropZone } from "@/components/ContactsDropZone";
import { QualityDropZone } from "@/components/QualityDropZone";
import { InteressentenDropZone } from "@/components/InteressentenDropZone";
import { AngeboteDropZone } from "@/components/AngeboteDropZone";
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
      {errors.length > 0 && <ErrorList errors={errors} />}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
        <Card className="p-6 space-y-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            {t("upload.orders_title")}
          </p>
          <DropZone
            onUploadSuccess={() => setErrors([])}
            onUploadError={(data) => setErrors(data.errors)}
          />
        </Card>
        <Card className="p-6 space-y-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            {t("upload.contacts_title")}
          </p>
          <ContactsDropZone />
        </Card>
        <Card className="p-6 space-y-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            {t("upload.quality_title")}
          </p>
          <QualityDropZone
            onUploadSuccess={() => setErrors([])}
            onUploadError={(errs) => setErrors(errs)}
          />
        </Card>
        <Card className="p-6 space-y-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            {t("upload.interessenten_title")}
          </p>
          <InteressentenDropZone
            onUploadSuccess={() => setErrors([])}
            onUploadError={(errs) => setErrors(errs)}
          />
        </Card>
        <Card className="p-6 space-y-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            {t("upload.angebote_title")}
          </p>
          <AngeboteDropZone
            onUploadSuccess={() => setErrors([])}
            onUploadError={(errs) => setErrors(errs)}
          />
        </Card>
      </div>

      <Card className="p-6 space-y-4">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          {t("history_title")}
        </p>
        <UploadHistory />
      </Card>
    </div>
  );
}
