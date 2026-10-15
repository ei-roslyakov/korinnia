import { createContext } from "react";

/** Below this zoom the name and years on a card grow gradually as the tree shrinks, so they stay
 * readable without a jump in size (D107). */
export const TEXT_GROW_FROM = 0.7;
/** The most the card text grows (it still fits two lines of name and the years on a card). */
export const MAX_TEXT_SCALE = 1.35;

/** How much larger the card text is drawn at this zoom (1 = normal), rounded to 0.01. */
export function cardTextScale(zoom: number): number {
  const scale = Math.min(MAX_TEXT_SCALE, Math.max(1, TEXT_GROW_FROM / zoom));
  return Math.round(scale * 100) / 100;
}

/** Below this zoom cards show the name only: nothing else is readable that far out, and
 * hundreds of full cards make a large tree slow to draw and to pan (D97). Whole trees of a
 * few dozen people open well above it. */
export const NAME_ONLY_ZOOM = 0.15;

/** True while the tree is exported to PNG / PDF: every card is drawn in full. */
export const FullDetail = createContext(false);
