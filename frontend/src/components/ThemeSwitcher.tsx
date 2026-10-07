import { useTranslation } from "react-i18next";

import { setTheme, THEME_CHOICES, useTheme, type ThemeChoice } from "@/lib/theme";

/** Light, dark or archive (sepia) look; remembered on this device. */
export function ThemeSwitcher() {
  const { t } = useTranslation();
  const { choice } = useTheme();
  return (
    <label className="text-bark-700 flex items-center gap-1.5 text-sm">
      <span>{t("theme.label")}</span>
      <select
        aria-label={t("theme.label")}
        className="border-bark-100 bg-surface text-bark-900 rounded-md border px-2 py-1 text-sm"
        value={choice}
        onChange={(e) => setTheme(e.target.value as ThemeChoice)}
      >
        {THEME_CHOICES.map((c) => (
          <option key={c} value={c}>
            {t(`theme.${c}`)}
          </option>
        ))}
      </select>
    </label>
  );
}
