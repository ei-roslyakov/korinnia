import { createContext } from "react";

/** Below this zoom cards show the name only: nothing else is readable that far out, and
 * hundreds of full cards make a large tree slow to draw and to pan (D97). Whole trees of a
 * few dozen people open well above it. */
export const NAME_ONLY_ZOOM = 0.15;

/** True while the tree is exported to PNG / PDF: every card is drawn in full. */
export const FullDetail = createContext(false);
