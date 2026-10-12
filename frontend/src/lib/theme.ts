import { useEffect, useSyncExternalStore } from "react";

/** "system" follows the device's light / dark setting. */
export const THEME_CHOICES = ["system", "light", "dark", "sepia", "night"] as const;
export type ThemeChoice = (typeof THEME_CHOICES)[number];
export type Theme = Exclude<ThemeChoice, "system">;

const KEY = "korinnia.theme";
const listeners = new Set<() => void>();
const darkQuery = () =>
  typeof window !== "undefined" && window.matchMedia
    ? window.matchMedia("(prefers-color-scheme: dark)")
    : null;

/** The stored choice; storage may be unavailable (private mode), then "system". */
export function readTheme(): ThemeChoice {
  try {
    const v = localStorage.getItem(KEY);
    return (THEME_CHOICES as readonly string[]).includes(v ?? "") ? (v as ThemeChoice) : "system";
  } catch {
    return "system";
  }
}

/** Themes with light text on a dark background (the tree canvas and map adapt to them). */
export function isDarkTheme(theme: Theme): boolean {
  return theme === "dark" || theme === "night";
}

export function resolveTheme(choice: ThemeChoice): Theme {
  if (choice !== "system") return choice;
  return darkQuery()?.matches ? "dark" : "light";
}

/** Set `data-theme` on <html>; the CSS variables of that theme then apply everywhere. */
export function applyTheme(choice: ThemeChoice = readTheme()): void {
  document.documentElement.dataset.theme = resolveTheme(choice);
}

export function setTheme(choice: ThemeChoice): void {
  try {
    if (choice === "system") localStorage.removeItem(KEY);
    else localStorage.setItem(KEY, choice);
  } catch {
    /* not remembered, still applied */
  }
  applyTheme(choice);
  listeners.forEach((l) => l());
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  const query = darkQuery();
  const onSystem = () => {
    applyTheme();
    listener();
  };
  query?.addEventListener?.("change", onSystem);
  return () => {
    listeners.delete(listener);
    query?.removeEventListener?.("change", onSystem);
  };
}

/** The chosen and the effective theme; re-renders when either changes. */
export function useTheme(): { choice: ThemeChoice; theme: Theme } {
  const choice = useSyncExternalStore(subscribe, readTheme, () => "system" as ThemeChoice);
  const theme = useSyncExternalStore(
    subscribe,
    () => resolveTheme(readTheme()),
    () => "light" as Theme,
  );
  useEffect(() => applyTheme(choice), [choice]);
  return { choice, theme };
}
