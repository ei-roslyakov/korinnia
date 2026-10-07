import type { Edge, EdgeProps } from "@xyflow/react";
import { memo } from "react";

import { branchPath, pointOn } from "./branchPath";
import { BRANCH, seeded } from "./treeStyle";

export interface BranchEdgeData extends Record<string, unknown> {
  /** Width at the base (older, lower end) and at the tip. */
  w0: number;
  w1: number;
  /** Adoptive / step / foster link: drawn lighter. */
  faint?: boolean;
  opacity?: number;
  /** Varies the twigs from branch to branch. */
  seed?: number;
  /** Pixels of branch per leafy twig (smaller = leafier). */
  twigEvery?: number;
  /** Spring: some twigs end in a blossom. */
  blossoms?: boolean;
}

const LEAF = { fill: "var(--k-logo-leaf)" };
const LEAF_LIGHT = { fill: "var(--k-logo-leaf-light)" };
const TWIG_EVERY = 70; // px of branch length per twig (default)
const LEAF_FAN = [-1.2, -0.6, 0, 0.6, 1.2]; // leaf directions around a twig's tip
export type BranchFlowEdge = Edge<BranchEdgeData, "branch">;

/** A tapering branch (Oak style). The edge's source is always its lower, older end. */
export const BranchEdge = memo(function BranchEdge({
  sourceX,
  sourceY,
  targetX,
  targetY,
  data,
}: EdgeProps<BranchFlowEdge>) {
  const {
    w0 = 6,
    w1 = 4,
    faint = false,
    opacity = 1,
    seed = 1,
    twigEvery = TWIG_EVERY,
    blossoms = false,
  } = data ?? {};
  const base = { x: sourceX, y: sourceY };
  const tip = { x: targetX, y: targetY };
  const { outline, sheen } = branchPath(base, tip, w0, w1);
  // Short leafy twigs along the branch (at least one on any branch worth the name).
  const rnd = seeded(seed);
  const length = Math.hypot(targetX - sourceX, targetY - sourceY);
  const count = length < 45 ? 0 : Math.max(1, Math.floor(length / twigEvery));
  const twigs = Array.from({ length: count }, (_, i) => {
    const t = (i + 0.5 + (rnd() - 0.5) * 0.4) / count;
    const { p, d } = pointOn(base, tip, t);
    const len = Math.hypot(d.x, d.y) || 1;
    const side = rnd() > 0.5 ? 1 : -1;
    // Perpendicular to the branch, leaning upwards.
    const nx = (-d.y / len) * side;
    const ny = (d.x / len) * side;
    const reach = 24 + rnd() * 26;
    const end = { x: p.x + nx * reach, y: p.y + Math.min(ny * reach, 0) - reach * 0.6 };
    const width = Math.max(2, (w0 + (w1 - w0) * t) * 0.45);
    return {
      from: p,
      end,
      width,
      tilt: Math.atan2(end.y - p.y, end.x - p.x),
      light: rnd() > 0.5,
      size: 0.8 + rnd() * 0.45,
      blossom: blossoms && rnd() > 0.6,
    };
  });
  return (
    <g opacity={opacity} style={{ transition: "opacity 150ms" }}>
      <path d={outline} style={{ fill: BRANCH }} fillOpacity={faint ? 0.45 : 1} />
      {twigs.map((tw, i) => (
        <g key={i}>
          <path d={branchPath(tw.from, tw.end, tw.width, 1).outline} style={{ fill: BRANCH }} />
          {LEAF_FAN.map((a, k) => {
            const cx = tw.end.x + Math.cos(tw.tilt + a) * 8 * tw.size;
            const cy = tw.end.y + Math.sin(tw.tilt + a) * 8 * tw.size;
            return (
              <ellipse
                key={k}
                cx={cx}
                cy={cy}
                rx={9.5 * tw.size}
                ry={4.4 * tw.size}
                transform={`rotate(${((tw.tilt + a) * 180) / Math.PI} ${cx} ${cy})`}
                style={(k + (tw.light ? 1 : 0)) % 2 ? LEAF_LIGHT : LEAF}
              />
            );
          })}
          {/* A couple of leaves along the twig itself. */}
          {[0.45, 0.7].map((f, k) => {
            const cx = tw.from.x + (tw.end.x - tw.from.x) * f;
            const cy = tw.from.y + (tw.end.y - tw.from.y) * f;
            const a = tw.tilt + (k ? 0.9 : -0.9);
            return (
              <ellipse
                key={`s${k}`}
                cx={cx + Math.cos(a) * 5}
                cy={cy + Math.sin(a) * 5}
                rx={6.5 * tw.size}
                ry={3 * tw.size}
                transform={`rotate(${(a * 180) / Math.PI} ${cx + Math.cos(a) * 5} ${cy + Math.sin(a) * 5})`}
                style={k ? LEAF : LEAF_LIGHT}
              />
            );
          })}
          {tw.blossom && (
            <g transform={`translate(${tw.end.x} ${tw.end.y})`}>
              {[0, 72, 144, 216, 288].map((r) => (
                <ellipse
                  key={r}
                  cx="0"
                  cy="-4.5"
                  rx="3.4"
                  ry="4.6"
                  fill="#f4b6c8"
                  transform={`rotate(${r})`}
                />
              ))}
              <circle r="2.4" fill="#f2cf5b" />
            </g>
          )}
        </g>
      ))}
      <path
        d={sheen}
        fill="none"
        stroke="#fff"
        strokeOpacity={0.16}
        strokeWidth={Math.max(1, Math.min(w0, w1) * 0.22)}
        strokeLinecap="round"
      />
    </g>
  );
});
