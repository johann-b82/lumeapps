import { useTranslation } from "react-i18next";
import { useLocation } from "wouter";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  useSettingsDraftStatus,
  type SettingsSection,
} from "@/contexts/SettingsDraftContext";
import { useSettingsSection } from "@/hooks/useSettingsSection";

const SECTIONS: SettingsSection[] = ["general", "hr", "sensors"];

export function SettingsSectionPicker() {
  const { t } = useTranslation();
  const { section } = useSettingsSection();
  const status = useSettingsDraftStatus();
  const [, navigate] = useLocation();

  const labelFor = (s: SettingsSection) => t(`settings.section.${s}`);

  const handleChange = (next: SettingsSection) => {
    if (!status) {
      navigate(`/settings/${next}`);
      return;
    }
    status.requestSectionChange(next, (dest) => navigate(dest));
  };

  return (
    <Select<SettingsSection> value={section} onValueChange={handleChange}>
      <SelectTrigger
        data-testid="settings-section-picker-trigger"
        className="w-40"
        aria-label={t("settings.section_picker.aria")}
      >
        <SelectValue>{labelFor}</SelectValue>
      </SelectTrigger>
      <SelectContent>
        {SECTIONS.map((s) => (
          <SelectItem key={s} value={s}>
            {labelFor(s)}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
