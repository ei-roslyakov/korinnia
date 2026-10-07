import type { ELK as ElkApi } from "elkjs/lib/elk-api";

import { resolveElkConstructor } from "./elk";
import { expandLayout, type LayoutGraph, type Positions } from "./familyGraph";

export type { Positions };

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

/** Person and family positions (top-left corners), one row per generation. */
export async function computeLayout(graph: LayoutGraph): Promise<Positions> {
  const elk = await getElk();
  return expandLayout(await elk.layout(graph.elk), graph);
}
