import { describe, expect, it } from "vitest";

import en from "./locales/en.json";
import pl from "./locales/pl.json";
import uk from "./locales/uk.json";

/** All keys, with plural suffixes folded (languages need different plural forms). */
function keys(obj: object, prefix = ""): Set<string> {
  const out = new Set<string>();
  for (const [k, v] of Object.entries(obj)) {
    const key = prefix + k.replace(/_(zero|one|two|few|many|other)$/, "");
    if (v && typeof v === "object") for (const sub of keys(v, `${key}.`)) out.add(sub);
    else out.add(key);
  }
  return out;
}

describe("locales", () => {
  it("have the same keys in every language", () => {
    const base = [...keys(uk)].sort();
    expect([...keys(en)].sort()).toEqual(base);
    expect([...keys(pl)].sort()).toEqual(base);
  });

  it("define every plural form each language needs", () => {
    const forms: Record<string, string[]> = {
      uk: ["one", "few", "many", "other"],
      pl: ["one", "few", "many", "other"],
      en: ["one", "other"],
    };
    for (const [lang, data] of Object.entries({ uk, en, pl })) {
      const flat = JSON.stringify(data);
      for (const m of flat.matchAll(/"(\w+)_one"/g)) {
        for (const form of forms[lang]!)
          expect(flat, `${lang}: ${m[1]}_${form}`).toContain(`"${m[1]}_${form}"`);
      }
    }
  });
});
