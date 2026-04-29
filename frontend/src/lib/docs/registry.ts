import enUserIntro from "../../docs/en/user-guide/intro.md?raw";
import deUserIntro from "../../docs/de/user-guide/intro.md?raw";
import enAdminIntro from "../../docs/en/admin-guide/intro.md?raw";
import deAdminIntro from "../../docs/de/admin-guide/intro.md?raw";
import enSystemSetup from "../../docs/en/admin-guide/system-setup.md?raw";
import deSystemSetup from "../../docs/de/admin-guide/system-setup.md?raw";
import enArchitecture from "../../docs/en/admin-guide/architecture.md?raw";
import deArchitecture from "../../docs/de/admin-guide/architecture.md?raw";
import enDigitalSignage from "../../docs/en/admin-guide/digital-signage.md?raw";
import deDigitalSignage from "../../docs/de/admin-guide/digital-signage.md?raw";
import enPersonio from "../../docs/en/admin-guide/personio.md?raw";
import dePersonio from "../../docs/de/admin-guide/personio.md?raw";
import enSensorMonitor from "../../docs/en/admin-guide/sensor-monitor.md?raw";
import deSensorMonitor from "../../docs/de/admin-guide/sensor-monitor.md?raw";
import enUserManagement from "../../docs/en/admin-guide/user-management.md?raw";
import deUserManagement from "../../docs/de/admin-guide/user-management.md?raw";
import enUploadingData from "../../docs/en/user-guide/uploading-data.md?raw";
import deUploadingData from "../../docs/de/user-guide/uploading-data.md?raw";
import enSalesDashboard from "../../docs/en/user-guide/sales-dashboard.md?raw";
import deSalesDashboard from "../../docs/de/user-guide/sales-dashboard.md?raw";
import enHrDashboard from "../../docs/en/user-guide/hr-dashboard.md?raw";
import deHrDashboard from "../../docs/de/user-guide/hr-dashboard.md?raw";
import enFilters from "../../docs/en/user-guide/filters.md?raw";
import deFilters from "../../docs/de/user-guide/filters.md?raw";
import enLanguageAndTheme from "../../docs/en/user-guide/language-and-theme.md?raw";
import deLanguageAndTheme from "../../docs/de/user-guide/language-and-theme.md?raw";

export type ArticleEntry = { slug: string; titleKey: string };
export type SectionId = "user-guide" | "admin-guide";

/** Sidebar structure — ordered lists of articles per section */
export const sections: Record<SectionId, ArticleEntry[]> = {
  "user-guide": [
    { slug: "intro", titleKey: "docs.nav.userGuideIntro" },
    { slug: "uploading-data", titleKey: "docs.nav.uploadingData" },
    { slug: "sales-dashboard", titleKey: "docs.nav.salesDashboard" },
    { slug: "hr-dashboard", titleKey: "docs.nav.hrDashboard" },
    { slug: "filters", titleKey: "docs.nav.filters" },
    { slug: "language-and-theme", titleKey: "docs.nav.languageAndTheme" },
  ],
  "admin-guide": [
    { slug: "intro", titleKey: "docs.nav.adminGuideIntro" },
    { slug: "system-setup", titleKey: "docs.nav.adminSystemSetup" },
    { slug: "architecture", titleKey: "docs.nav.adminArchitecture" },
    { slug: "digital-signage", titleKey: "docs.nav.adminDigitalSignage" },
    { slug: "personio", titleKey: "docs.nav.adminPersonio" },
    { slug: "sensor-monitor", titleKey: "docs.nav.adminSensorMonitor" },
    { slug: "user-management", titleKey: "docs.nav.adminUserManagement" },
  ],
};

/** Content registry: registry[lang][section][slug] = raw Markdown string */
export const registry: Record<string, Record<string, Record<string, string>>> = {
  en: {
    "user-guide": {
      intro: enUserIntro,
      "uploading-data": enUploadingData,
      "sales-dashboard": enSalesDashboard,
      "hr-dashboard": enHrDashboard,
      filters: enFilters,
      "language-and-theme": enLanguageAndTheme,
    },
    "admin-guide": {
      intro: enAdminIntro,
      "system-setup": enSystemSetup,
      architecture: enArchitecture,
      "digital-signage": enDigitalSignage,
      personio: enPersonio,
      "sensor-monitor": enSensorMonitor,
      "user-management": enUserManagement,
    },
  },
  de: {
    "user-guide": {
      intro: deUserIntro,
      "uploading-data": deUploadingData,
      "sales-dashboard": deSalesDashboard,
      "hr-dashboard": deHrDashboard,
      filters: deFilters,
      "language-and-theme": deLanguageAndTheme,
    },
    "admin-guide": {
      intro: deAdminIntro,
      "system-setup": deSystemSetup,
      architecture: deArchitecture,
      "digital-signage": deDigitalSignage,
      personio: dePersonio,
      "sensor-monitor": deSensorMonitor,
      "user-management": deUserManagement,
    },
  },
};
