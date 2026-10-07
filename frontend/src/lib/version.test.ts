import { describe, expect, it } from "vitest";

import { APP_VERSION, versionLabel } from "./version";

describe("app version", () => {
  it("is 'dev' unless the build sets one", () => {
    expect(APP_VERSION).toBe("dev");
  });

  it("is shown with a v prefix for releases", () => {
    expect(versionLabel("0.0.4")).toBe("v0.0.4");
    expect(versionLabel("dev")).toBe("dev");
  });
});
