/**
 * Fetch wrapper for the Korinnia REST API.
 *
 * - Same-origin cookies carry the session (httpOnly access/refresh JWTs).
 * - State-changing requests echo the CSRF cookie in the X-CSRF-Token header.
 * - On 401 the client refreshes the session once (shared by concurrent requests) and retries.
 */

import { setSessionExpired } from "./session";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly body: unknown,
  ) {
    super(`API request failed with status ${status}`);
    this.name = "ApiError";
  }

  /** Stable machine-readable error code from the backend (translated in the UI). */
  get code(): string {
    if (this.body && typeof this.body === "object" && "code" in this.body) {
      return String((this.body as { code: unknown }).code);
    }
    if (this.status === 422) return "validation_error";
    return "generic";
  }
}

const CSRF_COOKIE = "korinnia_csrf";
const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);
const NO_REFRESH_PATHS = [
  "/api/v1/auth/login",
  "/api/v1/auth/refresh",
  "/api/v1/auth/logout",
  "/api/v1/auth/invitations/",
  "/api/v1/auth/password-reset/",
];

export function readCookie(name: string): string | undefined {
  return document.cookie
    .split("; ")
    .find((c) => c.startsWith(`${name}=`))
    ?.slice(name.length + 1);
}

let csrfFetch: Promise<string> | null = null;

/**
 * The CSRF token to send. Always the *current cookie value* when there is one: concurrent
 * first requests without a cookie each get a different token minted by the server, and
 * only the last Set-Cookie survives, so a token taken from a response body may no longer
 * match the cookie. Cookie-less clients share a single /auth/csrf request.
 */
export async function csrfToken(): Promise<string> {
  const existing = readCookie(CSRF_COOKIE);
  if (existing) return existing;
  csrfFetch ??= fetch("/api/v1/auth/csrf", { credentials: "same-origin" })
    .then((resp) => resp.json() as Promise<{ csrf_token: string }>)
    .then((body) => body.csrf_token)
    .finally(() => {
      csrfFetch = null;
    });
  const fromBody = await csrfFetch;
  return readCookie(CSRF_COOKIE) ?? fromBody;
}

let refreshing: Promise<boolean> | null = null;

/** Refresh the session; concurrent callers share one request. */
export function refreshSession(): Promise<boolean> {
  refreshing ??= (async () => {
    try {
      const resp = await fetch("/api/v1/auth/refresh", {
        method: "POST",
        credentials: "same-origin",
        headers: { "X-CSRF-Token": await csrfToken() },
      });
      if (!resp.ok && resp.status === 401) {
        const body = (await resp.json().catch(() => null)) as { code?: string } | null;
        if (body?.code === "session_expired") setSessionExpired(true);
      }
      return resp.ok;
    } catch {
      return false;
    } finally {
      // Callers already awaiting hold this promise; later 401s start a fresh refresh.
      refreshing = null;
    }
  })();
  return refreshing;
}

export interface RequestOptions extends Omit<RequestInit, "body"> {
  json?: unknown;
  body?: BodyInit;
}

async function send(path: string, opts: RequestOptions): Promise<Response> {
  const { json, headers, ...init } = opts;
  const method = (init.method ?? "GET").toUpperCase();
  const finalHeaders: Record<string, string> = {
    Accept: "application/json",
    ...(headers as Record<string, string> | undefined),
  };
  if (json !== undefined) finalHeaders["Content-Type"] = "application/json";
  // Every request waits for the CSRF cookie when it is missing (one shared fetch), so
  // the server never mints competing tokens for parallel cookie-less requests.
  const token = await csrfToken();
  if (!SAFE_METHODS.has(method)) finalHeaders["X-CSRF-Token"] = token;
  return fetch(path, {
    credentials: "same-origin",
    ...init,
    method,
    headers: finalHeaders,
    body: json !== undefined ? JSON.stringify(json) : init.body,
  });
}

export async function apiFetch<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  let resp = await send(path, opts);
  if (resp.status === 401 && !NO_REFRESH_PATHS.some((p) => path.startsWith(p))) {
    if (await refreshSession()) resp = await send(path, opts);
  }
  if (resp.status === 204) return undefined as T;
  const isJson = resp.headers.get("content-type")?.includes("application/json");
  const body: unknown = isJson ? await resp.json() : await resp.text();
  if (!resp.ok) throw new ApiError(resp.status, body);
  return body as T;
}

export const api = {
  get: <T>(path: string) => apiFetch<T>(path),
  post: <T>(path: string, json?: unknown) => apiFetch<T>(path, { method: "POST", json }),
  patch: <T>(path: string, json?: unknown) => apiFetch<T>(path, { method: "PATCH", json }),
  put: <T>(path: string, json?: unknown) => apiFetch<T>(path, { method: "PUT", json }),
  delete: <T = void>(path: string) => apiFetch<T>(path, { method: "DELETE" }),
};

/** Build a query string, skipping empty values. */
export function qs(params: Record<string, string | number | boolean | null | undefined>): string {
  const search = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== "") search.set(k, String(v));
  }
  const s = search.toString();
  return s ? `?${s}` : "";
}

// --- System -------------------------------------------------------------------------------

export interface MetaInfo {
  default_language?: "uk" | "en" | "pl";
  name: string;
  version: string;
  environment: string;
  /** Public demo credentials, when the installation offers "Try the demo". */
  demo_login?: { email: string; password: string } | null;
}

export type CheckStatus = "ok" | "error";

export interface ReadinessStatus {
  status: CheckStatus;
  checks: Record<string, CheckStatus>;
}

export const getMeta = () => api.get<MetaInfo>("/api/v1/meta");

/** Readiness returns 503 with a JSON body when a dependency is down — still a valid answer. */
export async function getReadiness(): Promise<ReadinessStatus> {
  try {
    return await api.get<ReadinessStatus>("/api/readyz");
  } catch (err) {
    if (err instanceof ApiError && err.status === 503 && typeof err.body === "object") {
      return err.body as ReadinessStatus;
    }
    throw err;
  }
}
