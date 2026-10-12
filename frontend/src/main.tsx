// Self-hosted variable fonts (Latin, Cyrillic and more; the browser loads only the subsets a
// page needs). Imported before our CSS so the font families exist when it references them.
import "@fontsource-variable/inter";
import "@fontsource-variable/lora";
import "./index.css";
import "./i18n";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router";

import { App } from "./App";
import { applyTheme } from "./lib/theme";

// Before the first render, so the page never flashes in the wrong colours.
applyTheme();

// Pages load as separate files. After a new version is deployed, a tab opened earlier may ask
// for files that no longer exist: reload once to get the new version instead of failing.
window.addEventListener("vite:preloadError", (event) => {
  const key = "korinnia.reloaded-for-update";
  try {
    if (sessionStorage.getItem(key) === location.pathname) return;
    sessionStorage.setItem(key, location.pathname);
  } catch {
    return;
  }
  event.preventDefault();
  location.reload();
});

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, retry: 1 } },
});

const root = document.getElementById("root");
if (!root) throw new Error("#root element missing");

createRoot(root).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
