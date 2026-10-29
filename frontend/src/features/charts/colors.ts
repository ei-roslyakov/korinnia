import type { Line } from "./lineage";

/** Theme colours of the father's and the mother's line (every theme redefines them). */
export const LINE_FILL: Record<Line, string> = {
  root: "var(--k-green-100)",
  paternal: "var(--k-sky-100)",
  maternal: "var(--k-rose-100)",
};
export const LINE_TEXT: Record<Line, string> = {
  root: "var(--k-green-800)",
  paternal: "var(--k-sky-800)",
  maternal: "var(--k-rose-800)",
};
