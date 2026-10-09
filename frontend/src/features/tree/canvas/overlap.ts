/** Card positions without overlaps (D92). */

type XY = { x: number; y: number };

/** Horizontal space kept between two cards that had to be pushed apart. */
export const OVERLAP_GAP = 16;

/**
 * Push cards apart so that none overlaps another. Cards are taken from left to right; a card
 * that would overlap one already placed (in the same or a neighbouring row) moves right just
 * far enough to clear it, which can in turn push the cards after it. Left-to-right order is
 * kept, so partners stay side by side; nothing moves vertically. Cards that do not overlap
 * keep their exact position.
 */
export function separate(
  pos: Record<string, XY>,
  width: number,
  height: number,
  gap = OVERLAP_GAP,
): Record<string, XY> {
  const ids = Object.keys(pos).sort(
    (a, b) => pos[a]!.x - pos[b]!.x || pos[a]!.y - pos[b]!.y || (a < b ? -1 : 1),
  );
  // Placed cards by row band, so each card is only compared with its neighbours.
  const bands = new Map<number, XY[]>();
  const out: Record<string, XY> = {};
  for (const id of ids) {
    let { x } = pos[id]!;
    const { y } = pos[id]!;
    const band = Math.floor(y / height);
    const near = [band - 1, band, band + 1].flatMap((b) => bands.get(b) ?? []);
    for (let moved = true; moved;) {
      moved = false;
      for (const p of near) {
        if (Math.abs(p.y - y) < height && x < p.x + width + gap && p.x < x + width + gap) {
          x = p.x + width + gap;
          moved = true;
        }
      }
    }
    const placed = { x, y };
    out[id] = placed;
    if (!bands.has(band)) bands.set(band, []);
    bands.get(band)!.push(placed);
  }
  return out;
}
