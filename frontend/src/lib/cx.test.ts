import { describe, expect, it } from "vitest";

import { cx } from "./cx";

describe("cx", () => {
  it("lets caller classes replace base classes of the same group", () => {
    const base = "block w-full rounded-md px-3 py-2 text-sm";
    expect(cx(base, "w-auto py-1")).toBe("block rounded-md px-3 text-sm w-auto py-1");
    expect(cx(base, "p-0")).toBe("block w-full rounded-md text-sm p-0");
    expect(cx(base, "inline-block")).toBe("w-full rounded-md px-3 py-2 text-sm inline-block");
  });

  it("keeps everything else", () => {
    expect(cx("block w-full", "sm:w-auto text-red-700")).toBe(
      "block w-full sm:w-auto text-red-700",
    );
    expect(cx("block w-full")).toBe("block w-full");
  });
});
