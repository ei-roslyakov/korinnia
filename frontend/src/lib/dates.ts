import type { TFunction } from "i18next";

import type { PartialDate } from "./genealogy";

function formatPoint(lang: string, year: number, month: number | null, day: number | null): string {
  if (month && day) {
    return new Intl.DateTimeFormat(lang, { dateStyle: "long", timeZone: "UTC" }).format(
      Date.UTC(year, month - 1, day),
    );
  }
  if (month) {
    return new Intl.DateTimeFormat(lang, {
      month: "long",
      year: "numeric",
      timeZone: "UTC",
    }).format(Date.UTC(year, month - 1, 1));
  }
  return String(year);
}

/** Human-readable, localised partial date: "14 лютого 1931 р.", "бл. 1850", "між 1914 і 1918". */
export function formatPartialDate(
  d: PartialDate | null | undefined,
  t: TFunction,
  lang: string,
): string {
  if (!d) return "";
  if (d.year === null) return d.phrase ?? "";
  const point = formatPoint(lang, d.year, d.month, d.day);
  switch (d.precision) {
    case "approx":
      return t("dates.approx", { date: point });
    case "before":
      return t("dates.before", { date: point });
    case "after":
      return t("dates.after", { date: point });
    case "between":
      return t("dates.between", {
        from: point,
        to: formatPoint(lang, d.end_year ?? d.year, d.end_month, d.end_day),
      });
    default:
      return point;
  }
}

/** Compact year with uncertainty marker, for cards: "1890", "~1850", "<1944", "1914–1918". */
export function shortYear(d: PartialDate | null | undefined): string {
  if (!d || d.year === null) return "";
  switch (d.precision) {
    case "approx":
      return `~${d.year}`;
    case "before":
      return `<${d.year}`;
    case "after":
      return `>${d.year}`;
    case "between":
      return `${d.year}–${d.end_year ?? ""}`;
    default:
      return String(d.year);
  }
}

/** Card subtitle: "1890 – 1944", "1931" (living), "1890 – ?" (dead, date unknown), "? – 1944". */
export function lifeYears(
  birth: PartialDate | null,
  death: PartialDate | null,
  isLiving: boolean,
): string {
  const b = shortYear(birth);
  const d = shortYear(death);
  if (isLiving && !d) return b;
  if (!b && !d) return "";
  return `${b || "?"} – ${d || "?"}`;
}

/** A calendar date in the viewer's time zone, as YYYY-MM-DD (today by default). */
export function localIsoDate(d = new Date()): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}
