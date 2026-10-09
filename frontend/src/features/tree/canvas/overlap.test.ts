import { describe, expect, it } from "vitest";

import { separate } from "./overlap";

const W = 200;
const H = 76;

describe("separate", () => {
  it("leaves cards that do not overlap where they are", () => {
    const pos = { a: { x: 0, y: 0 }, b: { x: 260, y: 0 }, c: { x: 0, y: 200 } };
    expect(separate(pos, W, H)).toEqual(pos);
  });

  it("pushes an overlapping card right, and the cards after it if needed", () => {
    const out = separate(
      { a: { x: 0, y: 0 }, b: { x: 50, y: 10 }, c: { x: 250, y: 0 }, far: { x: 900, y: 0 } },
      W,
      H,
    );
    expect(out.a).toEqual({ x: 0, y: 0 });
    expect(out.b).toEqual({ x: 216, y: 10 }); // cleared a, same height kept
    expect(out.c).toEqual({ x: 432, y: 0 }); // pushed on by b
    expect(out.far).toEqual({ x: 900, y: 0 }); // untouched
  });

  it("keeps cards in different rows apart only if they actually overlap", () => {
    const out = separate({ a: { x: 0, y: 0 }, b: { x: 0, y: 80 } }, W, H);
    expect(out.b).toEqual({ x: 0, y: 80 });
  });

  it("never leaves two cards overlapping", () => {
    const pos: Record<string, { x: number; y: number }> = {};
    for (let i = 0; i < 300; i++) pos[`p${i}`] = { x: (i * 37) % 1500, y: ((i * 53) % 5) * 90 };
    const out = Object.values(separate(pos, W, H));
    for (const [i, a] of out.entries())
      for (const b of out.slice(i + 1))
        expect(Math.abs(a.x - b.x) >= W || Math.abs(a.y - b.y) >= H).toBe(true);
  });
});
