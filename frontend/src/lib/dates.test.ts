import { describe, expect, it } from "vitest";

import i18n from "@/i18n";

import { formatPartialDate, lifeYears, shortYear } from "./dates";
import type { PartialDate } from "./genealogy";

const d = (p: Partial<PartialDate>): PartialDate => ({
  year: null,
  month: null,
  day: null,
  precision: "year",
  end_year: null,
  end_month: null,
  end_day: null,
  phrase: null,
  text: "",
  sort: null,
  ...p,
});

describe("dates", () => {
  it("formats partial dates per language", async () => {
    await i18n.changeLanguage("en");
    const t = i18n.t.bind(i18n);
    expect(
      formatPartialDate(d({ year: 1931, month: 2, day: 14, precision: "exact" }), t, "en"),
    ).toBe("February 14, 1931");
    expect(formatPartialDate(d({ year: 1902, month: 3, precision: "month" }), t, "en")).toBe(
      "March 1902",
    );
    expect(formatPartialDate(d({ year: 1850, precision: "approx" }), t, "en")).toBe("about 1850");
    expect(formatPartialDate(d({ year: 1901, precision: "before" }), t, "en")).toBe("before 1901");
    expect(formatPartialDate(d({ year: 1945, precision: "after" }), t, "en")).toBe("after 1945");
    expect(
      formatPartialDate(d({ year: 1914, end_year: 1918, precision: "between" }), t, "en"),
    ).toBe("between 1914 and 1918");
    expect(formatPartialDate(d({ phrase: "Easter", precision: "unknown" }), t, "en")).toBe(
      "Easter",
    );
    expect(formatPartialDate(null, t, "en")).toBe("");
    await i18n.changeLanguage("uk");
    expect(formatPartialDate(d({ year: 1850, precision: "approx" }), i18n.t.bind(i18n), "uk")).toBe(
      "бл. 1850",
    );
    expect(
      formatPartialDate(d({ year: 1902, month: 3, precision: "month" }), i18n.t.bind(i18n), "uk"),
    ).toMatch(/1902/);
  });

  it("builds compact life years", () => {
    expect(shortYear(d({ year: 1850, precision: "approx" }))).toBe("~1850");
    expect(shortYear(d({ year: 1944, precision: "before" }))).toBe("<1944");
    expect(shortYear(d({ year: 1944, precision: "after" }))).toBe(">1944");
    expect(shortYear(d({ year: 1914, end_year: 1918, precision: "between" }))).toBe("1914–1918");
    expect(lifeYears(d({ year: 1890 }), d({ year: 1944 }), false)).toBe("1890 – 1944");
    expect(lifeYears(d({ year: 1975 }), null, true)).toBe("1975");
    expect(lifeYears(d({ year: 1890 }), null, false)).toBe("1890 – ?");
    expect(lifeYears(null, d({ year: 1944 }), false)).toBe("? – 1944");
    expect(lifeYears(null, null, false)).toBe("");
  });
});
