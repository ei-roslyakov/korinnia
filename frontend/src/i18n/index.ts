import i18n from "i18next";
import LanguageDetector from "i18next-browser-languagedetector";
import { initReactI18next } from "react-i18next";

import en from "./locales/en.json";
import pl from "./locales/pl.json";
import uk from "./locales/uk.json";

export const SUPPORTED_LANGUAGES = [
  { code: "uk", label: "Українська" },
  { code: "en", label: "English" },
  { code: "pl", label: "Polski" },
] as const;

export type LanguageCode = (typeof SUPPORTED_LANGUAGES)[number]["code"];

/** Before the server says otherwise (DEFAULT_LANGUAGE in /api/v1/meta). */
export const DEFAULT_LANGUAGE: LanguageCode = "en";

const LANGUAGE_KEY = "korinnia.lang";

/** Whether this browser had an explicit language choice before the app started. */
export const hadStoredLanguage = (() => {
  try {
    return localStorage.getItem(LANGUAGE_KEY) !== null;
  } catch {
    return false;
  }
})();

void i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: { uk: { translation: uk }, en: { translation: en }, pl: { translation: pl } },
    fallbackLng: DEFAULT_LANGUAGE,
    supportedLngs: SUPPORTED_LANGUAGES.map((l) => l.code),
    interpolation: { escapeValue: false },
    detection: {
      // Explicit choice (localStorage) wins; otherwise the installation default, not the
      // browser locale.
      order: ["localStorage"],
      lookupLocalStorage: LANGUAGE_KEY,
      caches: ["localStorage"],
    },
  });

i18n.on("languageChanged", (lng) => {
  document.documentElement.lang = lng;
});

export default i18n;
