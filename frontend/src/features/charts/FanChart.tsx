import { forwardRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { lifeYears } from "@/lib/dates";
import type { PersonSummary } from "@/lib/genealogy";

import { LINE_FILL, LINE_TEXT } from "./colors";
import { lineToRoot, type Slot } from "./lineage";

const CENTER = 64;
const RING = 78;
const MARGIN = 12;
const LINE_HEIGHT = 12;

const rad = (deg: number) => (deg * Math.PI) / 180;
const point = (r: number, deg: number) => [r * Math.cos(rad(deg)), r * Math.sin(rad(deg))];

function sector(r0: number, r1: number, a0: number, a1: number): string {
  const large = a1 - a0 > 180 ? 1 : 0;
  const [x0, y0] = point(r1, a0);
  const [x1, y1] = point(r1, a1);
  const [x2, y2] = point(r0, a1);
  const [x3, y3] = point(r0, a0);
  return [
    `M ${x0} ${y0}`,
    `A ${r1} ${r1} 0 ${large} 1 ${x1} ${y1}`,
    `L ${x2} ${y2}`,
    r0 > 0 ? `A ${r0} ${r0} 0 ${large} 0 ${x3} ${y3}` : "",
    "Z",
  ].join(" ");
}

const cut = (s: string, n: number) => (s.length > n ? `${s.slice(0, Math.max(1, n - 1))}…` : s);

/** First name, surname (without a maiden name in brackets or a patronymic) and years. */
function label(p: PersonSummary, repeat: boolean): [string, string, string] {
  const parts = p.display_name
    .replace(/\s*\([^)]*\)/g, "")
    .trim()
    .split(/\s+/);
  const first = parts[0] ?? "";
  const last = parts.length > 1 ? parts[parts.length - 1]! : "";
  return [
    `${first}${repeat ? " ⟳" : ""}`,
    last,
    lifeYears(p.birth, p.death, p.is_living && !p.death),
  ];
}

/** Ancestors in rings: father's line on the left, mother's on the right, each sector with
 * the name and years; unknown ancestors faint, repeated ones (pedigree collapse) with ⟳. */
export const FanChart = forwardRef<
  SVGSVGElement,
  {
    slots: Slot[];
    generations: number;
    half: boolean;
    onOpen: (person: PersonSummary) => void;
  }
>(function FanChart({ slots, generations, half, onOpen }, ref) {
  const { t } = useTranslation();
  const [hover, setHover] = useState<number | null>(null);
  const highlighted = new Set(hover ? lineToRoot(hover) : []);
  const radius = CENTER + (generations - 1) * RING;
  const start = half ? 180 : 90; // degrees; y grows downwards in SVG
  const total = half ? 180 : 360;
  const width = 2 * (radius + MARGIN);
  const height = half ? radius + CENTER / 2 + 2 * MARGIN : width;
  const cx = width / 2;
  const cy = half ? radius + MARGIN : width / 2;

  return (
    <svg
      ref={ref}
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      role="img"
      aria-label={t("charts.fan.title")}
      className="font-sans"
      data-testid="fan-chart"
    >
      <g transform={`translate(${cx} ${cy})`}>
        {slots.map((s) => {
          if (s.generation >= generations) return null;
          const isRoot = s.n === 1;
          const count = 2 ** s.generation;
          const span = total / count;
          const a0 = start + (s.n - count) * span;
          const a1 = a0 + span;
          const r0 = isRoot ? 0 : CENTER + (s.generation - 1) * RING;
          const r1 = isRoot ? CENTER : r0 + RING;
          const path = isRoot
            ? half
              ? sector(0, CENTER, 180, 360)
              : `M ${-CENTER} 0 A ${CENTER} ${CENTER} 0 1 1 ${CENTER} 0 A ${CENTER} ${CENTER} 0 1 1 ${-CENTER} 0 Z`
            : sector(r0, r1, a0, a1);
          const dim = hover !== null && !highlighted.has(s.n);
          const p = s.person;
          if (!p) {
            return (
              <path
                key={s.n}
                d={path}
                style={{ fill: "var(--k-bark-50)", stroke: "var(--k-bark-100)" }}
                strokeDasharray="3 3"
                opacity={0.6}
              >
                <title>{t("charts.unknown")}</title>
              </path>
            );
          }
          const mid = (a0 + a1) / 2;
          const rMid = isRoot ? 0 : (r0 + r1) / 2;
          const arc = isRoot ? CENTER * 2 : rad(span) * rMid;
          const lines = label(p, s.repeat).slice(
            0,
            Math.max(1, Math.min(3, Math.floor(arc / LINE_HEIGHT))),
          );
          const fontSize = s.generation > 4 ? 9 : 11;
          const chars = Math.floor((isRoot ? CENTER * 1.6 : RING - 6) / (fontSize * 0.56));
          // Text runs along the radius, turned so it never reads upside down.
          const flip = mid % 360 > 90 && mid % 360 < 270;
          const [tx, ty] = point(rMid, mid);
          const rotate = isRoot ? 0 : flip ? mid + 180 : mid;
          const name = `${p.display_name}${p.birth || p.death ? `, ${lifeYears(p.birth, p.death, p.is_living)}` : ""}`;
          return (
            <g
              key={s.n}
              role="link"
              tabIndex={0}
              aria-label={name}
              className="cursor-pointer outline-none"
              opacity={dim ? 0.45 : 1}
              onMouseEnter={() => setHover(s.n)}
              onMouseLeave={() => setHover(null)}
              onFocus={() => setHover(s.n)}
              onBlur={() => setHover(null)}
              onClick={() => onOpen(p)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  onOpen(p);
                }
              }}
              data-testid="fan-sector"
              data-slot={s.n}
            >
              <title>{name}</title>
              <path
                d={path}
                style={{
                  fill: LINE_FILL[s.line],
                  stroke: highlighted.has(s.n) ? "var(--k-leaf-600)" : "var(--k-surface)",
                }}
                strokeWidth={highlighted.has(s.n) ? 2.5 : 1.5}
                strokeDasharray={s.link && s.link !== "biological" ? "5 3" : undefined}
              />
              <text
                transform={`translate(${tx} ${isRoot && half ? -CENTER / 2.4 : ty}) rotate(${rotate})`}
                textAnchor="middle"
                style={{ fill: LINE_TEXT[s.line], fontSize }}
              >
                {lines.map((line, i) => (
                  <tspan
                    key={i}
                    x={0}
                    dy={i === 0 ? `${(-(lines.length - 1) * LINE_HEIGHT) / 2 + 4}` : LINE_HEIGHT}
                    fontWeight={i === 0 ? 600 : 400}
                  >
                    {cut(line, chars)}
                  </tspan>
                ))}
              </text>
            </g>
          );
        })}
      </g>
    </svg>
  );
});
