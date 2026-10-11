// Browser timings on a large tree (run by scripts/perf.sh in the Playwright image).
// Prints one JSON object with the measurements.
import { chromium } from "playwright";

const base = process.env.BASE_URL ?? "http://nginx";
const treeId = process.env.TREE_ID;
const email = process.env.ADMIN_EMAIL ?? "admin@example.com";
const password = process.env.ADMIN_PASSWORD ?? "change-me-now-please";

const browser = await chromium.launch();
const page = await (await browser.newContext({ viewport: { width: 1440, height: 900 } })).newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));

await page.goto(`${base}/login`);
const me = await page.evaluate(
  async ([email, password]) => {
    await fetch("/api/v1/auth/csrf");
    const csrf = document.cookie.match(/korinnia_csrf=([^;]+)/)?.[1] ?? "";
    const r = await fetch("/api/v1/auth/login", {
      method: "POST",
      headers: { "content-type": "application/json", "X-CSRF-Token": csrf },
      body: JSON.stringify({ email, password }),
    });
    return (await r.json()).user;
  },
  [email, password],
);
// The sign-in popups are not part of what is measured.
await page.addInitScript((id) => sessionStorage.setItem("korinnia.onboarding.shown", id), me.id);

// Long tasks (> 50 ms on the main thread) while the tree loads.
await page.addInitScript(() => {
  window.__long = [];
  new PerformanceObserver((list) => {
    for (const e of list.getEntries()) window.__long.push(e.duration);
  }).observe({ type: "longtask", buffered: true });
});

const cards = page.getByTestId("person-card");
const settle = async () => {
  // The layout runs in a worker; the canvas is ready when the card count stops changing.
  let last = -1;
  for (let i = 0; i < 100; i++) {
    const n = await cards.count();
    if (n > 0 && n === last) return n;
    last = n;
    await page.waitForTimeout(200);
  }
  return last;
};
const ms = (t0) => Math.round(performance.now() - t0);

const result = { errors };

// API: the median of three requests per endpoint (from the browser, through nginx).
result.api_ms = await page.evaluate(async (treeId) => {
  const base = `/api/v1/trees/${treeId}`;
  const graph = await (await fetch(`${base}/graph`)).json();
  const a = graph.persons[0].id;
  const b = graph.persons[graph.persons.length - 1].id;
  const endpoints = {
    graph: "/graph",
    person: `/persons/${a}`,
    search: "/persons?q=kovalenko&limit=20",
    stats: "/stats",
    timeline: "/timeline?limit=100",
    map: "/map",
    relationship: `/relationship?a=${a}&b=${b}`,
    gedcom_export: "/export/gedcom",
  };
  const out = { people: graph.persons.length };
  for (const [name, path] of Object.entries(endpoints)) {
    const runs = [];
    for (let i = 0; i < 3; i++) {
      const t = performance.now();
      const r = await fetch(base + path);
      await r.arrayBuffer();
      runs.push(performance.now() - t);
    }
    out[name] = Math.round(runs.sort((x, y) => x - y)[1]);
  }
  return out;
}, treeId);

let t0 = performance.now();
await page.goto(`${base}/trees/${treeId}`);
await cards.first().waitFor({ timeout: 60_000 });
result.open_first_card_ms = ms(t0);
result.open_cards = await settle();
result.open_settled_ms = ms(t0);
result.opened_in = (await page.getByRole("button", { name: /Focus|Фокус/ }).getAttribute("aria-pressed")) === "true" ? "focus" : "whole";

t0 = performance.now();
await page.getByRole("button", { name: /Whole tree|Усе дерево/ }).click();
const people = result.api_ms.people;
await page.waitForFunction(
  (n) => document.querySelectorAll(".react-flow__minimap-node").length >= n,
  people,
  { timeout: 120_000, polling: 100 },
);
result.whole_layout_ms = ms(t0);
result.whole_cards = await settle();
result.whole_settled_ms = ms(t0);

// Frames per second while panning the whole tree for ~1 s.
const pane = await page.locator(".react-flow__pane").boundingBox();
const fps = page.evaluate(
  () =>
    new Promise((resolve) => {
      let frames = 0;
      const start = performance.now();
      const tick = () => {
        frames++;
        if (performance.now() - start < 1000) requestAnimationFrame(tick);
        else resolve(frames);
      };
      requestAnimationFrame(tick);
    }),
);
await page.mouse.move(pane.x + pane.width / 2, pane.y + 40);
await page.mouse.down();
await page.mouse.move(pane.x + pane.width / 2 - 300, pane.y + 140, { steps: 30 });
await page.mouse.up();
result.pan_fps = await fps;

// Zoom in on the middle (fewer, bigger cards).
await page.mouse.move(pane.x + pane.width / 2, pane.y + pane.height / 2);
for (let i = 0; i < 6; i++) await page.mouse.wheel(0, -400);
result.zoomed_cards = await settle();

result.long_tasks = await page.evaluate(() => ({
  count: window.__long.length,
  total_ms: Math.round(window.__long.reduce((a, b) => a + b, 0)),
  max_ms: Math.round(Math.max(0, ...window.__long)),
}));
result.js_heap_mb = await page.evaluate(() =>
  performance.memory ? Math.round(performance.memory.usedJSHeapSize / 1048576) : null,
);
console.log(JSON.stringify(result, null, 2));
await browser.close();
