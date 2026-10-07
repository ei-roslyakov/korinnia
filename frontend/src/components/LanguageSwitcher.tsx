import { useTranslation } from "react-i18next";

import { SUPPORTED_LANGUAGES } from "@/i18n";

export function LanguageSwitcher() {
  const { t, i18n } = useTranslation();
  return (
    <label className="flex items-center gap-2 text-sm">
      <span className="sr-only">{t("nav.language")}</span>
      <select
        aria-label={t("nav.language")}
        className="border-bark-100 rounded-md border bg-white px-2 py-1"
        value={i18n.resolvedLanguage}
        onChange={(e) => void i18n.changeLanguage(e.target.value)}
      >
        {SUPPORTED_LANGUAGES.map((lang) => (
          <option key={lang.code} value={lang.code}>
            {lang.label}
          </option>
        ))}
      </select>
    </label>
  );
}
