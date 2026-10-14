import { useSyncExternalStore } from "react";

/**
 * "Your session has expired": set when the server says the sign-in session ended (refresh
 * answered `session_expired`) or when its end time passes in the browser. The popup asks the
 * user to sign in again without leaving the page.
 */
let expired = false;
const listeners = new Set<() => void>();

export function setSessionExpired(value: boolean): void {
  if (expired === value) return;
  expired = value;
  listeners.forEach((l) => l());
}

export function useSessionExpired(): boolean {
  return useSyncExternalStore(
    (l) => {
      listeners.add(l);
      return () => listeners.delete(l);
    },
    () => expired,
    () => false,
  );
}
