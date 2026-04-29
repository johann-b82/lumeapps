import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import de from "./locales/de.json";
import en from "./locales/en.json";

// No `lng` — bootstrap.ts is the single initial-language writer (D-02).
// i18next uses `fallbackLng` until bootstrap calls `changeLanguage()`.
export const i18nInitPromise = i18n.use(initReactI18next).init({
  resources: {
    de: { translation: de },
    en: { translation: en },
  },
  fallbackLng: "en",
  keySeparator: false,
  interpolation: { escapeValue: false },
});

export default i18n;
