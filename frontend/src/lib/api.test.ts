import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, apiFetch, getReadiness } from "./api";

afterEach(() => vi.unstubAllGlobals());

describe("apiFetch", () => {
  it("throws ApiError with parsed body on failure", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          new Response(JSON.stringify({ detail: "nope" }), {
            status: 404,
            headers: { "content-type": "application/json" },
          }),
        ),
      ),
    );
    await expect(apiFetch("/api/x")).rejects.toMatchObject({
      status: 404,
      body: { detail: "nope" },
    });
  });

  it("getReadiness rethrows non-503 errors", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(new Response("bad gateway", { status: 502 }))),
    );
    await expect(getReadiness()).rejects.toBeInstanceOf(ApiError);
  });
});
