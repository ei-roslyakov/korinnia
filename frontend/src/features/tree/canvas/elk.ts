import type { ELK as ElkApi, ELKConstructorArguments } from "elkjs/lib/elk-api";

type ElkConstructor = new (args?: ELKConstructorArguments) => ElkApi;

/**
 * elkjs ships CommonJS/UMD. Depending on the bundler (Vite dev, Rolldown production build,
 * Vitest) the constructor arrives as the namespace's `default`, `default.default`, or the
 * namespace itself.
 */
export function resolveElkConstructor(module: unknown): ElkConstructor {
  const m = module as { default?: { default?: unknown } };
  const Ctor = [m.default?.default, m.default, module].find(
    (c): c is ElkConstructor => typeof c === "function",
  );
  if (!Ctor) throw new Error("elkjs: constructor not found");
  return Ctor;
}
