/** Release version baked in at build time by the Publish workflow; "dev" for local builds. */
export const APP_VERSION: string = import.meta.env.VITE_APP_VERSION || "dev";

/** "v0.0.4", or "dev". */
export const versionLabel = (v: string = APP_VERSION) => (/^\d/.test(v) ? `v${v}` : v);
