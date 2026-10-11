import { vi } from "vitest";

export type Handler = (init: RequestInit & { url: string }) => Response | Promise<Response>;

export function json(body: unknown, status = 200): Response {
  return new Response(status === 204 ? null : JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

/**
 * Stub global fetch with handlers keyed by "METHOD /path" (query string ignored).
 * Unknown routes return 404. Returns the mock to inspect calls.
 */
export function mockApi(routes: Record<string, Handler>) {
  const fn = vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
    const url = typeof input === "string" ? input : input.toString();
    const path = url.split("?")[0];
    const method = (init.method ?? "GET").toUpperCase();
    const handler = routes[`${method} ${path}`];
    if (!handler) return json({ detail: "not mocked", code: "not_found" }, 404);
    return handler({ ...init, url });
  });
  vi.stubGlobal("fetch", fn);
  return fn;
}

export const ME = {
  id: "u1",
  email: "halyna@example.com",
  display_name: "Галина",
  preferred_language: "uk",
  is_superadmin: false,
  totp_enabled: false,
  trees: [{ id: "t1", name: "Родина", role: "viewer" }],
  // Has seen the welcome guide and all news (onboarding has its own tests).
  welcome_dismissed: true,
  changelog_seen: "9999-12-31",
  show_changelog: true,
};
