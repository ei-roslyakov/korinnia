import { describe, expect, it } from "vitest";

import { exportFileName, exportRatio, gradientStops } from "./exportTree";

describe("tree export", () => {
  it("names the file after the tree and the date", () => {
    const day = new Date("2026-10-08T12:00:00Z");
    expect(exportFileName("Родина Коваленків (демо)", day)).toBe(
      "Родина-Коваленків-(демо)-2026-10-08",
    );
    expect(exportFileName('a/b: "c"?', day)).toBe("ab-c-2026-10-08");
    expect(exportFileName("   ", day)).toBe("tree-2026-10-08");
  });

  it("exports small trees sharp and keeps big ones within canvas limits", () => {
    expect(exportRatio(1500, 800)).toBe(3);
    const r = exportRatio(60000, 4000);
    expect(60000 * r).toBeLessThanOrEqual(14000);
    expect(60000 * r * 4000 * r).toBeLessThanOrEqual(100_000_000);
  });

  it("reads the theme's canvas gradient", () => {
    expect(
      gradientStops("linear-gradient(to bottom, #f1f6fa 0%, rgb(246, 248, 240) 70%, #eef3e2 100%)"),
    ).toEqual([
      ["#f1f6fa", 0],
      ["rgb(246, 248, 240)", 0.7],
      ["#eef3e2", 1],
    ]);
    expect(gradientStops("")).toEqual([]);
  });
});
