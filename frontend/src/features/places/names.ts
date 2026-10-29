import type { TFunction } from "i18next";

import type { HistoricalName } from "@/lib/genealogy";

/** "Stanislaviv (1772–1962)", "Kiev (until 1991)", "Lemberg (from 1772)" or just the name. */
export function historicalLabel(t: TFunction, h: HistoricalName): string {
  const { from_year: from, until_year: until } = h;
  if (from && until) return t("places.period.both", { name: h.name, from, until });
  if (until) return t("places.period.until", { name: h.name, until });
  if (from) return t("places.period.from", { name: h.name, from });
  return h.name;
}
