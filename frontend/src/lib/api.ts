/** Minimal fetch wrapper for the Korinnia REST API (same-origin, cookies included). */

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly body: unknown,
  ) {
    super(`API request failed with status ${status}`);
    this.name = "ApiError";
  }
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const resp = await fetch(path, {
    credentials: "same-origin",
    ...init,
    headers: { Accept: "application/json", ...init.headers },
  });
  const isJson = resp.headers.get("content-type")?.includes("application/json");
  const body: unknown = isJson ? await resp.json() : await resp.text();
  if (!resp.ok) throw new ApiError(resp.status, body);
  return body as T;
}

export interface MetaInfo {
  name: string;
  version: string;
  environment: string;
}

export type CheckStatus = "ok" | "error";

export interface ReadinessStatus {
  status: CheckStatus;
  checks: Record<string, CheckStatus>;
}

export const getMeta = () => apiFetch<MetaInfo>("/api/v1/meta");

/** Readiness returns 503 with a JSON body when a dependency is down — still a valid answer. */
export async function getReadiness(): Promise<ReadinessStatus> {
  try {
    return await apiFetch<ReadinessStatus>("/api/readyz");
  } catch (err) {
    if (err instanceof ApiError && err.status === 503 && typeof err.body === "object") {
      return err.body as ReadinessStatus;
    }
    throw err;
  }
}
