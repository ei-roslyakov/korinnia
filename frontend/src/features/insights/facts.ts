import type { TFunction } from "i18next";

import type { FactCategory } from "@/lib/genealogy";

export const CATEGORY_STYLE: Record<FactCategory, { badge: string; color: string }> = {
  birth: { badge: "bg-green-100 text-green-800", color: "#15803d" },
  family: { badge: "bg-rose-100 text-rose-800", color: "#be123c" },
  life: { badge: "bg-sky-100 text-sky-800", color: "#0369a1" },
  migration: { badge: "bg-violet-100 text-violet-800", color: "#6d28d9" },
  death: { badge: "bg-stone-200 text-stone-800", color: "#44403c" },
};

/** Event types, plus the partnership facts (civil union, separation…) that are not events. */
export function factTypeLabel(t: TFunction, type: string): string {
  return t(`eventTypes.${type}`, {
    defaultValue: t(`insights.factTypes.${type}`, { defaultValue: type }),
  });
}

/** Categories from a comma-separated URL parameter. */
export function parseCategories(raw: string | null): FactCategory[] {
  const all = Object.keys(CATEGORY_STYLE);
  return (raw ?? "").split(",").filter((c): c is FactCategory => all.includes(c));
}
