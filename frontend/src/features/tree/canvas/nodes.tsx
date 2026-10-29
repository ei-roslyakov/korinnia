import { Handle, Position, useStore, type Node, type NodeProps } from "@xyflow/react";
import { memo, useContext, useState } from "react";
import { useTranslation } from "react-i18next";

import { Avatar } from "@/features/person/Avatar";
import { formatPartialDate, lifeYears } from "@/lib/dates";
import type { PersonSummary, RelativeRelation } from "@/lib/genealogy";

import { FullDetail, NAME_ONLY_ZOOM } from "./detail";
import { FAMILY_SIZE, PERSON_HEIGHT, PERSON_WIDTH } from "./familyGraph";
import { BRANCH, GROUND_HEIGHT, seeded, TRUNK_REACH, type TreeStyle } from "./treeStyle";

export interface PersonNodeData extends Record<string, unknown> {
  person: PersonSummary;
  highlighted: boolean;
  hiddenUp: boolean;
  hiddenDown: boolean;
  /** Builder mode: show "+" buttons to add relatives. */
  onAdd?: (personId: string, relation: RelativeRelation) => void;
}
export type PersonFlowNode = Node<PersonNodeData, "person">;

const hidden = "!h-1 !w-1 !min-h-0 !min-w-0 !border-0 !bg-transparent";

// A thin accent on the left of each card (pastel, readable in every theme).
const ACCENT: Record<string, string> = {
  male: "border-l-sky-400",
  female: "border-l-rose-400",
  other: "border-l-violet-400",
  unknown: "border-l-stone-400",
};

/** Name only when zoomed far out (re-renders only on a change). */
const farSelector = (s: { transform: [number, number, number] }) => s.transform[2] < NAME_ONLY_ZOOM;

export const PersonNode = memo(function PersonNode({ data, selected }: NodeProps<PersonFlowNode>) {
  const { t } = useTranslation();
  const { person, highlighted, hiddenUp, hiddenDown, onAdd } = data;
  const zoomedOut = useStore(farSelector);
  // Exports draw every card in full.
  const fullDetail = useContext(FullDetail);
  const far = zoomedOut && !fullDetail;
  // The hover preview is only built while the pointer is over the card.
  const [hover, setHover] = useState(false);
  const ring = highlighted || selected ? "ring-2 ring-leaf-600" : "";
  const died = Boolean(person.death) || !person.is_living;
  const frame = `border-bark-100 bg-surface relative flex cursor-pointer items-center rounded-lg border border-l-4 shadow-sm ${ACCENT[person.gender] ?? ACCENT.unknown} ${ring}`;
  if (far) {
    return (
      <div
        style={{ width: PERSON_WIDTH, height: PERSON_HEIGHT }}
        className={`${frame} px-3`}
        data-testid="person-card"
        title={person.display_name}
      >
        <Handle type="target" position={Position.Bottom} className={hidden} isConnectable={false} />
        <div className="line-clamp-2 text-sm leading-tight font-medium">{person.display_name}</div>
        <Handle type="source" position={Position.Top} className={hidden} isConnectable={false} />
      </div>
    );
  }
  return (
    <div
      style={{ width: PERSON_WIDTH, height: PERSON_HEIGHT }}
      className={`group ${frame} gap-2.5 pr-2 pl-2 transition-shadow hover:shadow-md`}
      data-testid="person-card"
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
    >
      {/* The tree grows upwards: the link from the parents arrives at the bottom of a card,
          links to the person's own family leave from the top. */}
      <Handle type="target" position={Position.Bottom} className={hidden} isConnectable={false} />
      <Avatar name={person.display_name} gender={person.gender} url={person.avatar_url} size="md" />
      <div className="min-w-0">
        <div className="line-clamp-2 text-sm leading-tight font-medium">{person.display_name}</div>
        <div className="text-bark-700 text-xs leading-snug">
          {lifeYears(person.birth, person.death, person.is_living)}
          {died && person.death && (
            <span className="ml-1" aria-hidden="true">
              †
            </span>
          )}
          {person.details_hidden && (
            <span
              className="ml-1"
              role="img"
              title={t("person.detailsHiddenShort")}
              aria-label={t("person.detailsHiddenShort")}
            >
              🔒
            </span>
          )}
        </div>
      </div>
      {hover && <Preview person={person} />}
      {onAdd && <AddButtons personId={person.id} onAdd={onAdd} />}
      {!onAdd && hiddenUp && (
        <span
          className="bg-bark-100 text-bark-700 absolute -bottom-2 left-1/2 -translate-x-1/2 rounded-full px-1.5 text-[10px] leading-4"
          title={t("canvas.moreAbove")}
        >
          ▼
        </span>
      )}
      {!onAdd && hiddenDown && (
        <span
          className="bg-bark-100 text-bark-700 absolute -top-2 left-1/2 -translate-x-1/2 rounded-full px-1.5 text-[10px] leading-4"
          title={t("canvas.moreBelow")}
        >
          ▲
        </span>
      )}
      <Handle type="source" position={Position.Top} className={hidden} isConnectable={false} />
    </div>
  );
});

/** Hover preview with the full name, dates and birthplace. */
function Preview({ person }: { person: PersonSummary }) {
  const { t, i18n } = useTranslation();
  const dates = [
    person.birth && `${t("person.born")}: ${formatPartialDate(person.birth, t, i18n.language)}`,
    person.death && `${t("person.died")}: ${formatPartialDate(person.death, t, i18n.language)}`,
  ].filter(Boolean);
  return (
    <div
      role="tooltip"
      className="border-bark-100 bg-surface pointer-events-none absolute top-full left-1/2 z-50 mt-2 w-64 -translate-x-1/2 rounded-lg border p-3 text-left shadow-lg"
    >
      <div className="font-serif text-sm font-semibold">{person.display_name}</div>
      {dates.map((d) => (
        <div key={d as string} className="text-bark-700 text-xs">
          {d}
        </div>
      ))}
      {person.birth_place && <div className="text-bark-700 text-xs">📍 {person.birth_place}</div>}
    </div>
  );
}

const ADD_POSITIONS: Record<RelativeRelation, string> = {
  // Ancestors are below, descendants above.
  parent: "-bottom-3 left-1/2 -translate-x-1/2",
  child: "-top-3 left-1/2 -translate-x-1/2",
  partner: "top-1/2 -right-3 -translate-y-1/2",
  sibling: "top-1/2 -left-3 -translate-y-1/2",
};

function AddButtons({
  personId,
  onAdd,
}: {
  personId: string;
  onAdd: (personId: string, relation: RelativeRelation) => void;
}) {
  const { t } = useTranslation();
  return (
    <>
      {(Object.keys(ADD_POSITIONS) as RelativeRelation[]).map((relation) => (
        <button
          key={relation}
          type="button"
          // nodrag/nopan: React Flow must not treat clicks on the button as canvas drags.
          className={`nodrag nopan border-leaf-600 text-leaf-700 hover:bg-leaf-700 bg-surface hover:text-on-leaf absolute z-10 flex size-6 items-center justify-center rounded-full border text-sm leading-none shadow-sm ${ADD_POSITIONS[relation]}`}
          aria-label={t(`builder.family.new.${relation}`)}
          title={t(`builder.family.new.${relation}`)}
          onClick={(e) => {
            e.stopPropagation();
            onAdd(personId, relation);
          }}
        >
          +
        </button>
      ))}
    </>
  );
}

export interface FamilyNodeData extends Record<string, unknown> {
  decor?: TreeStyle;
  /** Blossoms at the youngest generations (spring). */
  blossom?: boolean;
  /** Varies the leaves from knot to knot. */
  seed?: number;
  /** Oak: diameter of the joint where branches meet. */
  knot?: number;
}
export type FamilyFlowNode = Node<FamilyNodeData, "family">;

const LEAF = { fill: "var(--k-logo-leaf)" };
const LEAF_LIGHT = { fill: "var(--k-logo-leaf-light)" };

/** Leaves (and a blossom) around a family knot, drawn in a 64×64 box centred on it. */
function KnotDecor({ blossom, seed }: { blossom: boolean; seed: number }) {
  const rnd = seeded(seed + 7);
  // A full fan of leaves around the upper side of the knot.
  const leaves = Array.from({ length: 9 }, (_, i) => {
    const angle = -175 + i * 21 + (rnd() - 0.5) * 14;
    return { angle, light: rnd() > 0.5, len: 12 + rnd() * 9 };
  });
  return (
    <svg
      viewBox="-32 -32 64 64"
      className="pointer-events-none absolute top-1/2 left-1/2 size-16 -translate-x-1/2 -translate-y-1/2 overflow-visible"
      aria-hidden="true"
    >
      {leaves.map((l, i) => (
        <g key={i} transform={`rotate(${l.angle})`}>
          <path
            d={`M7 0 Q${7 + l.len / 2} -6 ${7 + l.len} 0 Q${7 + l.len / 2} 6 7 0Z`}
            style={l.light ? LEAF_LIGHT : LEAF}
          />
        </g>
      ))}
      {blossom && (
        <g transform="translate(0 -14)">
          {[0, 72, 144, 216, 288].map((a) => (
            <ellipse
              key={a}
              cx="0"
              cy="-4.5"
              rx="3.4"
              ry="4.6"
              fill="#f4b6c8"
              transform={`rotate(${a})`}
            />
          ))}
          <circle r="2.4" fill="#f2cf5b" />
        </g>
      )}
    </svg>
  );
}

/** Where a couple's branch splits towards their children: a knot on the branch. */
export const FamilyNode = memo(function FamilyNode({ data }: NodeProps<FamilyFlowNode>) {
  const decor = data?.decor ?? "simple";
  return (
    <div
      style={{
        width: FAMILY_SIZE,
        height: FAMILY_SIZE,
        background: decor === "oak" ? "transparent" : BRANCH,
      }}
      className="relative rounded-full"
    >
      {decor === "oak" && (
        <span
          aria-hidden="true"
          className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 rounded-full"
          style={{ width: data?.knot ?? 12, height: data?.knot ?? 12, background: BRANCH }}
        />
      )}
      {decor !== "simple" && (
        <KnotDecor blossom={decor === "spring" && Boolean(data?.blossom)} seed={data?.seed ?? 1} />
      )}
      <Handle type="target" position={Position.Bottom} className={hidden} isConnectable={false} />
      <Handle type="source" position={Position.Top} className={hidden} isConnectable={false} />
    </div>
  );
});

export interface CrownNodeData extends Record<string, unknown> {
  width: number;
  height: number;
  /** Leafy crown (ellipse inside the node's box) behind the upper generations. */
  crown: { cx: number; cy: number; rx: number; ry: number } | null;
  /** Trunks from the ground up to each founding couple's knot. */
  trunks: { x: number; width: number; bottom: number; top: number }[];
}
export type CrownFlowNode = Node<CrownNodeData, "crown">;

/** The oak: a broad trunk and a soft leafy crown behind the family. Purely visual. */
export const CrownNode = memo(function CrownNode({ data }: NodeProps<CrownFlowNode>) {
  const { width, height, crown, trunks } = data;
  const blobs: { x: number; y: number; r: number; light: boolean; o: number }[] = [];
  if (crown) {
    const rnd = seeded(Math.round(crown.rx * 7 + crown.ry * 13));
    const base = Math.min(crown.rx, crown.ry);
    // Clumps around the rim, then a fill inside: an irregular, cloud-like crown.
    for (let i = 0; i < 26; i++) {
      const a = (i / 26) * Math.PI * 2;
      const f = 0.82 + rnd() * 0.16;
      blobs.push({
        x: crown.cx + Math.cos(a) * crown.rx * f,
        y: crown.cy + Math.sin(a) * crown.ry * f,
        r: base * (0.22 + rnd() * 0.14),
        light: rnd() > 0.55,
        o: 0.16 + rnd() * 0.1,
      });
    }
    for (let i = 0; i < 40; i++) {
      const a = rnd() * Math.PI * 2;
      const d = Math.sqrt(rnd()) * 0.75;
      blobs.push({
        x: crown.cx + Math.cos(a) * crown.rx * d,
        y: crown.cy + Math.sin(a) * crown.ry * d,
        r: base * (0.2 + rnd() * 0.18),
        light: rnd() > 0.5,
        o: 0.12 + rnd() * 0.08,
      });
    }
  }
  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      aria-hidden="true"
      style={{ pointerEvents: "none", overflow: "visible" }}
    >
      <defs>
        <filter id="crown-soft" x="-10%" y="-10%" width="120%" height="120%">
          <feGaussianBlur stdDeviation="6" />
        </filter>
        <linearGradient id="bark" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" style={{ stopColor: "var(--k-branch)" }} stopOpacity="0.75" />
          <stop offset="0.45" style={{ stopColor: "var(--k-branch)" }} />
          <stop offset="1" style={{ stopColor: "var(--k-branch)" }} stopOpacity="0.8" />
        </linearGradient>
      </defs>
      {crown && (
        <g filter="url(#crown-soft)">
          {blobs.map((b, i) => (
            <circle
              key={i}
              cx={b.x}
              cy={b.y}
              r={b.r}
              style={b.light ? LEAF_LIGHT : LEAF}
              opacity={b.o}
            />
          ))}
        </g>
      )}
      {trunks.map((t, i) => {
        const h = t.bottom - t.top;
        const w1 = t.width / 2 + 1; // meets the founders' branches at their knot
        const w0 = Math.max(28, t.width * 2.2);
        return (
          <path
            key={i}
            d={`M ${t.x - w0} ${t.bottom}
                C ${t.x - w0 * 0.7} ${t.bottom - h * 0.35}, ${t.x - w1 * 1.4} ${t.top + h * 0.35}, ${t.x - w1} ${t.top}
                L ${t.x + w1} ${t.top}
                C ${t.x + w1 * 1.4} ${t.top + h * 0.35}, ${t.x + w0 * 0.7} ${t.bottom - h * 0.35}, ${t.x + w0} ${t.bottom} Z`}
            fill="url(#bark)"
          />
        );
      })}
    </svg>
  );
});

export interface GroundNodeData extends Record<string, unknown> {
  width: number;
  /** Trunk positions (x within the node) under the founding couples. */
  trunks: number[];
}
export type GroundFlowNode = Node<GroundNodeData, "ground">;

/** Decorative soil under the oldest generation, with a trunk and roots under each founding
 * couple. Purely visual: not focusable, ignores the pointer. */
export const GroundNode = memo(function GroundNode({ data }: NodeProps<GroundFlowNode>) {
  const { width, trunks } = data;
  const soil = 34; // y of the grass line
  return (
    <svg
      width={width}
      height={GROUND_HEIGHT + TRUNK_REACH}
      viewBox={`0 ${-TRUNK_REACH} ${width} ${GROUND_HEIGHT + TRUNK_REACH}`}
      aria-hidden="true"
      style={{ marginTop: -TRUNK_REACH, overflow: "visible", pointerEvents: "none" }}
    >
      <defs>
        <linearGradient id="soil" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" style={{ stopColor: "var(--k-grass)" }} stopOpacity="0.55" />
          <stop offset="0.25" style={{ stopColor: "var(--k-soil)" }} stopOpacity="0.35" />
          <stop offset="1" style={{ stopColor: "var(--k-soil)" }} stopOpacity="0" />
        </linearGradient>
        {/* Fade the soil out at both ends instead of cutting it off. */}
        <linearGradient id="soil-fade" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stopColor="#fff" stopOpacity="0" />
          <stop offset="0.12" stopColor="#fff" stopOpacity="1" />
          <stop offset="0.88" stopColor="#fff" stopOpacity="1" />
          <stop offset="1" stopColor="#fff" stopOpacity="0" />
        </linearGradient>
        <mask id="soil-mask">
          <rect
            x="0"
            y={-TRUNK_REACH}
            width={width}
            height={GROUND_HEIGHT + TRUNK_REACH}
            fill="url(#soil-fade)"
          />
        </mask>
      </defs>
      <path
        mask="url(#soil-mask)"
        d={`M0 ${soil} Q ${width / 4} ${soil - 8} ${width / 2} ${soil} T ${width} ${soil} V ${GROUND_HEIGHT} H 0 Z`}
        fill="url(#soil)"
      />
      {trunks.map((x) => (
        <g key={x} style={{ fill: BRANCH, stroke: BRANCH }} strokeLinecap="round">
          {/* A trunk widening towards the ground… */}
          <path
            d={`M ${x - 5} ${-TRUNK_REACH} C ${x - 6} ${soil - 20}, ${x - 12} ${soil - 6}, ${x - 22} ${soil + 2}
                L ${x + 22} ${soil + 2} C ${x + 12} ${soil - 6}, ${x + 6} ${soil - 20}, ${x + 5} ${-TRUNK_REACH} Z`}
            stroke="none"
          />
          {/* …and roots spreading into the soil. */}
          <path
            d={`M ${x} ${soil} C ${x - 20} ${soil + 18}, ${x - 46} ${soil + 22}, ${x - 70} ${soil + 40}`}
            fill="none"
            strokeWidth="4"
            opacity="0.8"
          />
          <path
            d={`M ${x} ${soil} C ${x + 18} ${soil + 20}, ${x + 40} ${soil + 26}, ${x + 64} ${soil + 46}`}
            fill="none"
            strokeWidth="4"
            opacity="0.8"
          />
          <path
            d={`M ${x} ${soil} C ${x - 4} ${soil + 22}, ${x + 6} ${soil + 40}, ${x - 2} ${soil + 60}`}
            fill="none"
            strokeWidth="3"
            opacity="0.6"
          />
          <path
            d={`M ${x - 30} ${soil + 14} C ${x - 40} ${soil + 30}, ${x - 34} ${soil + 44}, ${x - 44} ${soil + 58}`}
            fill="none"
            strokeWidth="2"
            opacity="0.5"
          />
          <path
            d={`M ${x + 28} ${soil + 16} C ${x + 40} ${soil + 26}, ${x + 52} ${soil + 30}, ${x + 60} ${soil + 22}`}
            fill="none"
            strokeWidth="2"
            opacity="0.5"
          />
        </g>
      ))}
    </svg>
  );
});

export interface RowLabelData extends Record<string, unknown> {
  generation: string;
  period: string | null;
}
export type RowLabelFlowNode = Node<RowLabelData, "rowLabel">;

/** "III покоління · 1910-ті" at the left of each generation row. Decorative. */
export const RowLabelNode = memo(function RowLabelNode({ data }: NodeProps<RowLabelFlowNode>) {
  return (
    <div className="text-bark-700 pointer-events-none w-48 text-right leading-tight select-none">
      <div className="font-serif text-sm font-semibold">{data.generation}</div>
      {data.period && <div className="text-xs opacity-80">{data.period}</div>}
    </div>
  );
});

export interface CoupleNodeData extends Record<string, unknown> {
  /** Gap between the two cards, which the link spans. */
  width: number;
  married: boolean;
  /** Divorced or separated: the rings are struck through. */
  broken: boolean;
  /** "1946", "~1888" or null. */
  year: string | null;
  /** "Marriage · 22 June 1946 · Lviv". */
  label: string;
  dim: boolean;
}
export type CoupleFlowNode = Node<CoupleNodeData, "couple">;

export const COUPLE_HEIGHT = 40;

/** The link between partners' cards: solid with rings for a marriage, dashed with a heart
 * otherwise, rings struck through after a divorce or separation; the wedding year below. */
export const CoupleNode = memo(function CoupleNode({ data }: NodeProps<CoupleFlowNode>) {
  const { width, married, broken, year, label, dim } = data;
  const mid = width / 2;
  const y = 14; // the line runs at the cards' mid-height
  return (
    <div
      className="pointer-events-none relative select-none"
      style={{ width, height: COUPLE_HEIGHT, opacity: dim ? 0.3 : 1, transition: "opacity 150ms" }}
    >
      <svg width={width} height={COUPLE_HEIGHT} aria-hidden="true" className="absolute inset-0">
        <g stroke={BRANCH} fill="none" strokeLinecap="round">
          <line
            x1={0}
            y1={y}
            x2={mid - 10}
            y2={y}
            strokeWidth={2}
            strokeDasharray={married ? undefined : "3 3"}
          />
          <line
            x1={mid + 10}
            y1={y}
            x2={width}
            y2={y}
            strokeWidth={2}
            strokeDasharray={married ? undefined : "3 3"}
          />
          {married ? (
            <>
              <circle cx={mid - 3} cy={y} r={5} strokeWidth={1.8} />
              <circle cx={mid + 3} cy={y} r={5} strokeWidth={1.8} />
            </>
          ) : (
            <path
              d={`M ${mid} ${y + 5} C ${mid - 9} ${y - 1}, ${mid - 4} ${y - 8}, ${mid} ${y - 3}
                  C ${mid + 4} ${y - 8}, ${mid + 9} ${y - 1}, ${mid} ${y + 5} Z`}
              fill={BRANCH}
              stroke="none"
            />
          )}
          {broken && <line x1={mid - 8} y1={y + 8} x2={mid + 8} y2={y - 8} strokeWidth={2} />}
        </g>
      </svg>
      {/* Hover target for the details (the rest of the link lets the canvas pan). */}
      <span
        className="pointer-events-auto absolute rounded-full"
        style={{ left: mid - 11, top: y - 11, width: 22, height: 22 }}
        title={label}
        aria-label={label}
        role="img"
      />
      {year && (
        <span
          className="text-bark-700 absolute w-full text-center text-[10px] leading-none tabular-nums"
          style={{ top: y + 10 }}
        >
          {year}
        </span>
      )}
    </div>
  );
});
