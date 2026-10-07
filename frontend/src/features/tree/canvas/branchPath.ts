/**
 * Geometry of a drawn branch: a filled outline around a curve from its base (the older,
 * lower end) to its tip, tapering from `w0` to `w1`. The curve first rises from the base,
 * sweeps sideways, and bends up into the tip, like a branch growing towards the light.
 */
export interface Pt {
  x: number;
  y: number;
}

const STEPS = 24;

function curve(base: Pt, tip: Pt): [Pt, Pt, Pt, Pt] {
  const rise = base.y - tip.y; // positive: the tip is above
  return [
    base,
    { x: base.x + (tip.x - base.x) * 0.18, y: base.y - rise * 0.6 },
    { x: tip.x - (tip.x - base.x) * 0.12, y: tip.y + rise * 0.5 },
    tip,
  ];
}

function at([p0, p1, p2, p3]: [Pt, Pt, Pt, Pt], t: number): { p: Pt; d: Pt } {
  const u = 1 - t;
  const p = {
    x: u * u * u * p0.x + 3 * u * u * t * p1.x + 3 * u * t * t * p2.x + t * t * t * p3.x,
    y: u * u * u * p0.y + 3 * u * u * t * p1.y + 3 * u * t * t * p2.y + t * t * t * p3.y,
  };
  const d = {
    x: 3 * u * u * (p1.x - p0.x) + 6 * u * t * (p2.x - p1.x) + 3 * t * t * (p3.x - p2.x),
    y: 3 * u * u * (p1.y - p0.y) + 6 * u * t * (p2.y - p1.y) + 3 * t * t * (p3.y - p2.y),
  };
  return { p, d };
}

const fmt = (n: number) => Math.round(n * 10) / 10;

/** SVG path data of the branch outline, and of a thin highlight along it. */
export function branchPath(
  base: Pt,
  tip: Pt,
  w0: number,
  w1: number,
): { outline: string; sheen: string } {
  const bez = curve(base, tip);
  const left: Pt[] = [];
  const right: Pt[] = [];
  const sheen: Pt[] = [];
  for (let i = 0; i <= STEPS; i++) {
    const t = i / STEPS;
    const { p, d } = at(bez, t);
    const len = Math.hypot(d.x, d.y) || 1;
    const n = { x: -d.y / len, y: d.x / len };
    const half = (w0 + (w1 - w0) * t) / 2;
    left.push({ x: p.x + n.x * half, y: p.y + n.y * half });
    right.push({ x: p.x - n.x * half, y: p.y - n.y * half });
    sheen.push({ x: p.x + n.x * half * 0.35, y: p.y + n.y * half * 0.35 });
  }
  const pts = (list: Pt[]) => list.map((q) => `${fmt(q.x)} ${fmt(q.y)}`).join(" L ");
  return {
    outline: `M ${pts(left)} L ${pts(right.reverse())} Z`,
    sheen: `M ${pts(sheen)}`,
  };
}

/** A point on the branch's centre line (t = 0 at the base, 1 at the tip) and its direction. */
export function pointOn(base: Pt, tip: Pt, t: number): { p: Pt; d: Pt } {
  return at(curve(base, tip), t);
}
