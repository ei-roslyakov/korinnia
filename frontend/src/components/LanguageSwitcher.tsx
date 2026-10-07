import { useTranslation } from "react-i18next";

import { useMe, useUpdateMe } from "@/features/auth/api";
import { SUPPORTED_LANGUAGES } from "@/i18n";
import type { Language } from "@/lib/types";

import { HeaderSelect } from "./HeaderSelect";

export function LanguageSwitcher() {
  const { t, i18n } = useTranslation();
  const me = useMe();
  const updateMe = useUpdateMe();
  return (
    <label className="text-bark-700 flex items-center gap-1.5 text-sm">
      <span>{t("nav.language")}</span>
      <HeaderSelect
        aria-label={t("nav.language")}
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
      </HeaderSelect>
    </label>
  );
}
