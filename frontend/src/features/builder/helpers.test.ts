import { describe, expect, it } from "vitest";

import { cleanNames, emptyName, fromPartialDate, toPayload } from "./helpers";

describe("builder helpers", () => {
  it("normalises partial dates for the API", () => {
    expect(toPayload(null)).toBeNull();
    expect(toPayload({ precision: "unknown" })).toBeNull();
    expect(toPayload({ precision: "unknown", phrase: " Easter " })).toEqual({
      precision: "unknown",
      phrase: "Easter",
    });
    expect(toPayload({ precision: "year", year: 1890, month: 3, day: 2 })).toEqual({
      precision: "year",
      year: 1890,
      phrase: null,
    });
    expect(toPayload({ precision: "month", year: 1902, month: 3, day: 9 })).toEqual({
      precision: "month",
      year: 1902,
      month: 3,
      day: null,
      phrase: null,
    });
    expect(
      toPayload({ precision: "between", year: 1914, end_year: 1918, end_month: 11 }),
    ).toMatchObject({
      year: 1914,
      end_year: 1918,
      end_month: 11,
    });
    expect(
      fromPartialDate({
        year: 1931,
        month: 2,
        day: 14,
        precision: "exact",
        end_year: null,
        end_month: null,
        end_day: null,
        phrase: null,
        text: "",
        sort: null,
      }),
    ).toMatchObject({ year: 1931, month: 2, day: 14, precision: "exact" });
    expect(fromPartialDate(null)).toBeNull();
  });

  it("cleans names and guarantees a primary name", () => {
    const names = [
      { ...emptyName(), first_name: "  " },
      { ...emptyName(), first_name: " Іван ", last_name: "Коваленко" },
      { ...emptyName(), last_name: "Kovalenko", script: "latin" },
    ];
    const cleaned = cleanNames(names);
    expect(cleaned).toHaveLength(2);
    expect(cleaned[0]).toMatchObject({ first_name: "Іван", is_primary: true, patronymic: null });
    expect(cleaned[1]?.is_primary).toBe(false);
  });
});
