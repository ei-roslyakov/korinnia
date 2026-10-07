import type { ELK as ElkApi, ElkNode } from "elkjs/lib/elk-api";

import { resolveElkConstructor } from "./elk";

export type Positions = Record<string, { x: number; y: number }>;

let elkPromise: Promise<ElkApi> | null = null;

/**
 * In browsers ELK runs in its official Web Worker (elk-worker.min.js, served as a
 * same-origin asset), so laying out 2,000+ people never blocks the UI. Without Worker
 * support (tests) the bundled in-process build is used.
 */
function getElk(): Promise<ElkApi> {
  elkPromise ??= (async () => {
    if (typeof Worker !== "undefined") {
      const [api, worker] = await Promise.all([
        import("elkjs/lib/elk-api.js"),
        import("elkjs/lib/elk-worker.min.js?url"),
      ]);
      const Ctor = resolveElkConstructor(api);
      return new Ctor({ workerFactory: () => new Worker(worker.default) });
    }
    const bundled = await import("elkjs/lib/elk.bundled.js");
    return new (resolveElkConstructor(bundled))();
  })();
  return elkPromise;
}

/** Compute node positions (top-left corners) with ELK's layered algorithm. */
export async function computeLayout(graph: ElkNode): Promise<Positions> {
  const elk = await getElk();
  const result = await elk.layout(graph);
  return Object.fromEntries(
    (result.children ?? []).map((c) => [c.id, { x: c.x ?? 0, y: c.y ?? 0 }]),
  );
}
