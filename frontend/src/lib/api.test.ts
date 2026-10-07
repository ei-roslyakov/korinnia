import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { json, mockApi } from "@/test/mockApi";

import { ApiError, api, getReadiness, qs } from "./api";

beforeEach(() => {
  document.cookie = "korinnia_csrf=csrf-123; path=/";
});
afterEach(() => vi.unstubAllGlobals());

describe("api client", () => {
  it("sends the CSRF token on state-changing requests only", async () => {
    const fetch = mockApi({
      "GET /api/x": () => json({ ok: true }),
      "POST /api/x": () => json({ ok: true }),
    });
    await api.get("/api/x");
    await api.post("/api/x", { a: 1 });
    const getInit = fetch.mock.calls[0]?.[1] as RequestInit;
    const postInit = fetch.mock.calls[1]?.[1] as RequestInit;
    expect((getInit.headers as Record<string, string>)["X-CSRF-Token"]).toBeUndefined();
    expect((postInit.headers as Record<string, string>)["X-CSRF-Token"]).toBe("csrf-123");
    expect(postInit.body).toBe('{"a":1}');
  });

  it("refreshes the session once on 401 and retries", async () => {
    let calls = 0;
    const fetch = mockApi({
      "GET /api/v1/trees": () => (++calls === 1 ? json({ code: "token_expired" }, 401) : json([])),
      "POST /api/v1/auth/refresh": () => json(null, 204),
    });
    await expect(api.get("/api/v1/trees")).resolves.toEqual([]);
    expect(fetch.mock.calls.map((c) => c[0])).toEqual([
      "/api/v1/trees",
      "/api/v1/auth/refresh",
      "/api/v1/trees",
    ]);
  });

  it("shares one refresh between concurrent requests", async () => {
    const seen = new Set<string>();
    const fetch = mockApi({
      "GET /api/a": () => (seen.has("a") ? json(1) : (seen.add("a"), json({}, 401))),
      "GET /api/b": () => (seen.has("b") ? json(2) : (seen.add("b"), json({}, 401))),
      "POST /api/v1/auth/refresh": () => json(null, 204),
    });
    await expect(Promise.all([api.get("/api/a"), api.get("/api/b")])).resolves.toEqual([1, 2]);
    expect(fetch.mock.calls.filter((c) => c[0] === "/api/v1/auth/refresh")).toHaveLength(1);
  });

  it("does not refresh on login failures and exposes the error code", async () => {
    const fetch = mockApi({
      "POST /api/v1/auth/login": () => json({ code: "invalid_credentials" }, 401),
    });
    const err = await api.post("/api/v1/auth/login", {}).catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).code).toBe("invalid_credentials");
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("maps 422 without code to validation_error", async () => {
    mockApi({ "POST /api/x": () => json({ detail: [] }, 422) });
    const err = (await api.post("/api/x").catch((e: unknown) => e)) as ApiError;
    expect(err.code).toBe("validation_error");
  });

  it("getReadiness returns the 503 body and rethrows other errors", async () => {
    mockApi({
      "GET /api/readyz": () => json({ status: "error", checks: { database: "error" } }, 503),
    });
    await expect(getReadiness()).resolves.toMatchObject({ status: "error" });
    mockApi({ "GET /api/readyz": () => new Response("bad gateway", { status: 502 }) });
    await expect(getReadiness()).rejects.toBeInstanceOf(ApiError);
  });

  it("qs skips empty values", () => {
    expect(qs({ a: 1, b: "", c: undefined, d: false })).toBe("?a=1&d=false");
    expect(qs({})).toBe("");
  });
});
