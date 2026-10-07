/** Look of the tree: brown branches that thin out towards the youngest generations. */

export const BRANCH_COLOR = "#7a5638";
export const GROUND_HEIGHT = 110;
/** The trunk starts this far above the ground node, i.e. right under the founders' cards. */
export const TRUNK_REACH = 18;

/** Branch thickness for links starting at generation `rank` (0 = the oldest, at the root). */
export function branchWidth(rank: number): number {
  return Math.max(1.5, 7 - rank * 1.2);
}
