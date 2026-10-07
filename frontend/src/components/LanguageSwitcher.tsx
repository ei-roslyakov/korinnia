import { useTranslation } from "react-i18next";

import { useMe, useUpdateMe } from "@/features/auth/api";
import { SUPPORTED_LANGUAGES } from "@/i18n";
import type { Language } from "@/lib/types";

export function LanguageSwitcher() {
  const { t, i18n } = useTranslation();
  const me = useMe();
  const updateMe = useUpdateMe();
  return (
    <select
      aria-label={t("nav.language")}
      className="border-bark-100 rounded-md border bg-white px-2 py-1 text-sm"
      value={i18n.resolvedLanguage}
      onChange={(e) => {
        const lang = e.target.value as Language;
        void i18n.changeLanguage(lang);
        // Logged-in users: remember the choice in the profile (follows them across devices).
        if (me.data && me.data.preferred_language !== lang) {
          updateMe.mutate({ preferred_language: lang });
        }
      }}
    >
      {SUPPORTED_LANGUAGES.map((lang) => (
        <option key={lang.code} value={lang.code}>
          {lang.label}
        </option>
      ))}
    </select>
  );
}
