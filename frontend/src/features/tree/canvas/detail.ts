import { createContext } from "react";

/** Below this zoom cards are drawn simply (name only): details would not be readable, and
 * hundreds of full cards make a large tree slow to draw and to pan (D97). */
export const DETAIL_ZOOM = 0.45;

/** True while the tree is exported to PNG / PDF: every card is drawn in full. */
export const FullDetail = createContext(false);
