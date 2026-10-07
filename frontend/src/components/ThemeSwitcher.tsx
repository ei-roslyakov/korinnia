import { useTranslation } from "react-i18next";

import { setTheme, THEME_CHOICES, useTheme, type ThemeChoice } from "@/lib/theme";

import { HeaderSelect } from "./HeaderSelect";

/** Light, dark or archive (sepia) look; remembered on this device. */
export function ThemeSwitcher() {
  const { t } = useTranslation();
  const { choice } = useTheme();
  return (
    <label className="text-bark-700 flex items-center gap-1.5 text-sm">
      <span>{t("theme.label")}</span>
      <HeaderSelect
        aria-label={t("theme.label")}
        value={choice}
        onChange={(e) => setTheme(e.target.value as ThemeChoice)}
      >
        {THEME_CHOICES.map((c) => (
          <option key={c} value={c}>
            {t(`theme.${c}`)}
          </option>
        ))}
      </HeaderSelect>
    </label>
  );
}
