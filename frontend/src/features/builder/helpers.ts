/** Pure helpers for builder forms (kept out of component files for fast refresh). */
import type { PartialDate, PartialDateInput } from "@/lib/genealogy";

import type { NameInput } from "./api";

export function fromPartialDate(d: PartialDate | null | undefined): PartialDateInput | null {
  if (!d) return null;
  return {
    year: d.year,
    month: d.month,
    day: d.day,
    precision: d.precision,
    end_year: d.end_year,
    end_month: d.end_month,
    end_day: d.end_day,
    phrase: d.phrase,
  };
}

/** Normalise for the API: drop fields the chosen precision does not use; null if empty. */
export function toPayload(v: PartialDateInput | null): PartialDateInput | null {
  if (!v) return null;
  const p = v.precision ?? "unknown";
  const phrase = v.phrase?.trim() || null;
  if (p === "unknown") return phrase ? { precision: "unknown", phrase } : null;
  const out: PartialDateInput = { precision: p, year: v.year ?? null, phrase };
  if (p !== "year") {
    out.month = v.month ?? null;
    out.day = p === "month" ? null : (v.day ?? null);
  }
  if (p === "between") {
    out.end_year = v.end_year ?? null;
    out.end_month = v.end_month ?? null;
    out.end_day = v.end_day ?? null;
  }
  return out;
}

export const emptyName = (primary = false): NameInput => ({
  type: "birth",
  first_name: "",
  middle_name: "",
  patronymic: "",
  last_name: "",
  maiden_name: "",
  script: "cyrillic",
  is_primary: primary,
});

/** Payload cleanup: trim parts, drop empty names, ensure one primary. */
export function cleanNames(names: NameInput[]): NameInput[] {
  const trimmed = names
    .map((n) => ({
      ...n,
      first_name: n.first_name?.trim() || null,
      middle_name: n.middle_name?.trim() || null,
      patronymic: n.patronymic?.trim() || null,
      last_name: n.last_name?.trim() || null,
      maiden_name: n.maiden_name?.trim() || null,
    }))
    .filter((n) => n.first_name || n.middle_name || n.patronymic || n.last_name || n.maiden_name);
  if (trimmed.length && !trimmed.some((n) => n.is_primary))
    trimmed[0] = { ...trimmed[0]!, is_primary: true };
  return trimmed;
}

export interface Draft {
  text: string;
  savedAt: string;
}

export function readDraft(key: string): Draft | null {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as Draft) : null;
  } catch {
    return null;
  }
}

export function clearDraft(key: string) {
  try {
    localStorage.removeItem(key);
  } catch {
    /* storage unavailable */
  }
}
