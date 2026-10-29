import { forwardRef } from "react";
import { useTranslation } from "react-i18next";

import { lifeYears } from "@/lib/dates";
import type { PersonSummary } from "@/lib/genealogy";

import { LINE_FILL, LINE_TEXT } from "./colors";
import type { Slot } from "./lineage";

const CARD_W = 168;
const CARD_H = 44;
const GAP_X = 36;
const ROW = 52;
const MARGIN = 8;

const cut = (s: string, n: number) => (s.length > n ? `${s.slice(0, n - 1)}…` : s);

/** Ancestors left to right: the person, then parents, grandparents… as compact cards joined
 * by elbow lines (dashed for adoptive / step links), unknown ancestors faint. */
export const PedigreeChart = forwardRef<
  SVGSVGElement,
  { slots: Slot[]; generations: number; onOpen: (person: PersonSummary) => void }
>(function PedigreeChart({ slots, generations, onOpen }, ref) {
  const { t } = useTranslation();
  const leaves = 2 ** (generations - 1);
  const width = generations * (CARD_W + GAP_X) - GAP_X + 2 * MARGIN;
  const height = leaves * ROW + 2 * MARGIN;
  const pos = (s: Slot) => {
    const count = 2 ** s.generation;
    const i = s.n - count;
    return {
      x: MARGIN + s.generation * (CARD_W + GAP_X),
      y: MARGIN + (i + 0.5) * (leaves / count) * ROW - CARD_H / 2,
    };
  };
  const shown = slots.filter((s) => s.generation < generations);

  return (
    <svg
      ref={ref}
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      role="img"
      aria-label={t("charts.pedigree.title")}
      className="font-sans"
      data-testid="pedigree-chart"
    >
      {shown.map((s) => {
        if (s.n === 1) return null;
        const child = pos(slots[Math.floor(s.n / 2) - 1]!);
        const me = pos(s);
        const x0 = child.x + CARD_W;
        const y0 = child.y + CARD_H / 2;
        const x1 = me.x;
        const y1 = me.y + CARD_H / 2;
        const xm = (x0 + x1) / 2;
        return (
          <path
            key={`l${s.n}`}
            d={`M ${x0} ${y0} H ${xm} V ${y1} H ${x1}`}
            fill="none"
            style={{ stroke: "var(--k-branch)" }}
            strokeWidth={1.5}
            opacity={s.person ? 0.8 : 0.3}
            strokeDasharray={s.link && s.link !== "biological" ? "5 3" : undefined}
          />
        );
      })}
      {shown.map((s) => {
        const { x, y } = pos(s);
        const p = s.person;
        if (!p) {
          return (
            <g key={s.n} opacity={0.45}>
              <rect
                x={x}
                y={y}
                width={CARD_W}
                height={CARD_H}
                rx={6}
                style={{ fill: "var(--k-bark-50)", stroke: "var(--k-bark-100)" }}
                strokeDasharray="3 3"
              />
              <text
                x={x + 10}
                y={y + CARD_H / 2 + 4}
                style={{ fill: "var(--k-bark-700)", fontSize: 11 }}
              >
                {t("charts.unknown")}
              </text>
            </g>
          );
        }
        const years = lifeYears(p.birth, p.death, p.is_living);
        return (
          <g
            key={s.n}
            role="link"
            tabIndex={0}
            aria-label={`${p.display_name}${years ? `, ${years}` : ""}`}
            className="cursor-pointer"
            onClick={() => onOpen(p)}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                onOpen(p);
              }
            }}
            data-testid="pedigree-card"
          >
            <rect
              x={x}
              y={y}
              width={CARD_W}
              height={CARD_H}
              rx={6}
              style={{ fill: LINE_FILL[s.line], stroke: "var(--k-branch)" }}
              strokeWidth={s.n === 1 ? 2 : 1}
              strokeOpacity={0.5}
            />
            <text x={x + 10} y={y + 18} style={{ fill: LINE_TEXT[s.line], fontSize: 12 }}>
              <tspan fontWeight={600}>{cut(p.display_name, 22)}</tspan>
              {s.repeat && <tspan> ⟳</tspan>}
            </text>
            <text x={x + 10} y={y + 34} style={{ fill: "var(--k-bark-700)", fontSize: 11 }}>
              {years}
            </text>
          </g>
        );
      })}
    </svg>
  );
});
