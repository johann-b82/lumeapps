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
import enAtr from "../../docs/en/admin-guide/atr.md?raw";
import deAtr from "../../docs/de/admin-guide/atr.md?raw";
import enFair from "../../docs/en/admin-guide/fair.md?raw";
import deFair from "../../docs/de/admin-guide/fair.md?raw";
import enUserManagement from "../../docs/en/admin-guide/user-management.md?raw";
import deUserManagement from "../../docs/de/admin-guide/user-management.md?raw";
import enUploadingData from "../../docs/en/user-guide/uploading-data.md?raw";
import deUploadingData from "../../docs/de/user-guide/uploading-data.md?raw";
import enSalesDashboard from "../../docs/en/user-guide/sales-dashboard.md?raw";
import deSalesDashboard from "../../docs/de/user-guide/sales-dashboard.md?raw";
import enProcurementDashboard from "../../docs/en/user-guide/procurement-dashboard.md?raw";
import deProcurementDashboard from "../../docs/de/user-guide/procurement-dashboard.md?raw";
import enProductionDashboard from "../../docs/en/user-guide/production-dashboard.md?raw";
import deProductionDashboard from "../../docs/de/user-guide/production-dashboard.md?raw";
import enHrDashboard from "../../docs/en/user-guide/hr-dashboard.md?raw";
import deHrDashboard from "../../docs/de/user-guide/hr-dashboard.md?raw";
import enOrganigramm from "../../docs/en/user-guide/organigramm.md?raw";
import deOrganigramm from "../../docs/de/user-guide/organigramm.md?raw";
import enQualityDashboard from "../../docs/en/user-guide/quality-dashboard.md?raw";
import deQualityDashboard from "../../docs/de/user-guide/quality-dashboard.md?raw";
import enFinanceDashboard from "../../docs/en/user-guide/finance-dashboard.md?raw";
import deFinanceDashboard from "../../docs/de/user-guide/finance-dashboard.md?raw";
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
    { slug: "procurement-dashboard", titleKey: "docs.nav.procurementDashboard" },
    { slug: "production-dashboard", titleKey: "docs.nav.productionDashboard" },
    { slug: "hr-dashboard", titleKey: "docs.nav.hrDashboard" },
    { slug: "organigramm", titleKey: "docs.nav.organigramm" },
    { slug: "quality-dashboard", titleKey: "docs.nav.qualityDashboard" },
    { slug: "finance-dashboard", titleKey: "docs.nav.financeDashboard" },
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
    { slug: "atr", titleKey: "docs.nav.adminAtr" },
    { slug: "fair", titleKey: "docs.nav.adminFair" },
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
      "procurement-dashboard": enProcurementDashboard,
      "production-dashboard": enProductionDashboard,
      "hr-dashboard": enHrDashboard,
      organigramm: enOrganigramm,
      "quality-dashboard": enQualityDashboard,
      "finance-dashboard": enFinanceDashboard,
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
      atr: enAtr,
      fair: enFair,
      "user-management": enUserManagement,
    },
  },
  de: {
    "user-guide": {
      intro: deUserIntro,
      "uploading-data": deUploadingData,
      "sales-dashboard": deSalesDashboard,
      "procurement-dashboard": deProcurementDashboard,
      "production-dashboard": deProductionDashboard,
      "hr-dashboard": deHrDashboard,
      organigramm: deOrganigramm,
      "quality-dashboard": deQualityDashboard,
      "finance-dashboard": deFinanceDashboard,
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
      atr: deAtr,
      fair: deFair,
      "user-management": deUserManagement,
    },
  },
};
