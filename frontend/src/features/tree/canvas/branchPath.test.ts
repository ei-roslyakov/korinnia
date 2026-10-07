import { describe, expect, it } from "vitest";

import { branchPath } from "./branchPath";

const points = (d: string) =>
  d
    .replace(/[MLZ]/g, " ")
    .trim()
    .split(/\s+/)
    .map(Number)
    .reduce<number[][]>(
      (acc, n, i) => (i % 2 ? (acc[acc.length - 1]!.push(n), acc) : [...acc, [n]]),
      [],
    );

describe("branchPath", () => {
  it("tapers from the base width to the tip width", () => {
    const { outline } = branchPath({ x: 0, y: 100 }, { x: 0, y: 0 }, 20, 4);
    const pts = points(outline);
    const half = pts.length / 2;
    const width = (i: number) =>
      Math.hypot(
        pts[i]![0]! - pts[pts.length - 1 - i]![0]!,
        pts[i]![1]! - pts[pts.length - 1 - i]![1]!,
      );
    expect(width(0)).toBeCloseTo(20, 0); // at the base
    expect(width(half - 1)).toBeCloseTo(4, 0); // at the tip
    expect(outline.endsWith("Z")).toBe(true);
  });

  it("starts at the base and ends at the tip", () => {
    const { sheen } = branchPath({ x: 10, y: 200 }, { x: 150, y: 50 }, 10, 4);
    const pts = points(sheen);
    expect(pts[0]![1]).toBeGreaterThan(190);
    expect(pts[pts.length - 1]![1]).toBeLessThan(60);
    expect(pts[pts.length - 1]![0]).toBeGreaterThan(140);
  });
});
