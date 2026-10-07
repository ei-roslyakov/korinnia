import { beforeEach, describe, expect, it } from "vitest";

import { readTreeStyle, saveTreeStyle, seeded, STYLE_WIDTH, TREE_STYLES } from "./treeStyle";

beforeEach(() => localStorage.clear());

describe("tree style", () => {
  it("is remembered in the browser, simple by default", () => {
    expect(readTreeStyle()).toBe("simple");
    saveTreeStyle("oak");
    expect(readTreeStyle()).toBe("oak");
    localStorage.setItem("korinnia.treeStyle", "palm");
    expect(readTreeStyle()).toBe("simple");
  });

  it("has a branch width for every style, thickest for the oak", () => {
    expect(TREE_STYLES.every((s) => STYLE_WIDTH[s] > 0)).toBe(true);
    expect(STYLE_WIDTH.oak).toBeGreaterThan(STYLE_WIDTH.simple);
  });

  it("draws the same decorations every time (seeded randomness)", () => {
    const a = seeded(42);
    const b = seeded(42);
    const first = [a(), a(), a()];
    expect([b(), b(), b()]).toEqual(first);
    expect(first.every((x) => x >= 0 && x < 1)).toBe(true);
    expect(seeded(43)()).not.toBe(first[0]);
  });
});
