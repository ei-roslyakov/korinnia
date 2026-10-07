/** Look of the tree: brown branches that thin out towards the youngest generations. */

/** Branch colour of the current theme (CSS variable, usable in SVG `style`). */
export const BRANCH = "var(--k-branch)";
/** Minimap colour for junctions (the minimap needs a literal colour). */
export const BRANCH_COLOR = "#7a5638";
export const GROUND_HEIGHT = 110;
/** The trunk starts this far above the ground node, i.e. right under the founders' cards. */
export const TRUNK_REACH = 18;

/** Branch thickness for links starting at generation `rank` (0 = the oldest, at the root). */
export function branchWidth(rank: number): number {
  return Math.max(1.5, 7 - rank * 1.2);
}

/** How the tree is drawn: today's clean look, a big oak, or spring branches in bloom. */
export const TREE_STYLES = ["simple", "oak", "spring"] as const;
export type TreeStyle = (typeof TREE_STYLES)[number];

/** Branch thickness relative to the simple style. */
export const STYLE_WIDTH: Record<TreeStyle, number> = { simple: 1, oak: 1.9, spring: 0.85 };

const STYLE_KEY = "korinnia.treeStyle";

export function readTreeStyle(): TreeStyle {
  try {
    const v = localStorage.getItem(STYLE_KEY);
    return (TREE_STYLES as readonly string[]).includes(v ?? "") ? (v as TreeStyle) : "simple";
  } catch {
    return "simple";
  }
}

export function saveTreeStyle(style: TreeStyle): void {
  try {
    localStorage.setItem(STYLE_KEY, style);
  } catch {
    /* not remembered, still applied */
  }
}

/** A small deterministic pseudo-random sequence (the same tree always looks the same). */
export function seeded(seed: number): () => number {
  let s = seed % 2147483647 || 1;
  return () => {
    s = (s * 16807) % 2147483647;
    return (s - 1) / 2147483646;
  };
}
