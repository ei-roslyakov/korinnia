import { describe, expect, it } from "vitest";

import { cardTextScale, MAX_TEXT_SCALE } from "./detail";

describe("cardTextScale", () => {
  it("keeps the normal size when zoomed in and grows gradually when zoomed out", () => {
    expect(cardTextScale(1)).toBe(1);
    expect(cardTextScale(0.7)).toBe(1);
    expect(cardTextScale(0.6)).toBe(1.17);
    expect(cardTextScale(0.3)).toBe(MAX_TEXT_SCALE);
  });
});
