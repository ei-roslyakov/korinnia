import { Handle, Position, type Node, type NodeProps } from "@xyflow/react";
import { memo } from "react";
import { useTranslation } from "react-i18next";

import { Avatar } from "@/features/person/Avatar";
import { formatPartialDate, lifeYears } from "@/lib/dates";
import type { PersonSummary, RelativeRelation } from "@/lib/genealogy";

import { FAMILY_SIZE, PERSON_HEIGHT, PERSON_WIDTH } from "./familyGraph";
import { BRANCH, GROUND_HEIGHT, TRUNK_REACH } from "./treeStyle";

export interface PersonNodeData extends Record<string, unknown> {
  person: PersonSummary;
  highlighted: boolean;
  hiddenUp: boolean;
  hiddenDown: boolean;
  /** Builder mode: show "+" buttons to add relatives. */
  onAdd?: (personId: string, relation: RelativeRelation) => void;
}
export type PersonFlowNode = Node<PersonNodeData, "person">;
export type FamilyFlowNode = Node<Record<string, never>, "family">;

const hidden = "!h-1 !w-1 !min-h-0 !min-w-0 !border-0 !bg-transparent";

// A thin accent on the left of each card (pastel, readable in every theme).
const ACCENT: Record<string, string> = {
  male: "border-l-sky-400",
  female: "border-l-rose-400",
  other: "border-l-violet-400",
  unknown: "border-l-stone-400",
};

export const PersonNode = memo(function PersonNode({ data, selected }: NodeProps<PersonFlowNode>) {
  const { t, i18n } = useTranslation();
  const { person, highlighted, hiddenUp, hiddenDown, onAdd } = data;
  const ring = highlighted || selected ? "ring-2 ring-leaf-600" : "";
  const died = Boolean(person.death) || !person.is_living;
  const dates = [
    person.birth && `${t("person.born")}: ${formatPartialDate(person.birth, t, i18n.language)}`,
    person.death && `${t("person.died")}: ${formatPartialDate(person.death, t, i18n.language)}`,
  ].filter(Boolean);
  return (
    <div
      style={{ width: PERSON_WIDTH, height: PERSON_HEIGHT }}
      className={`group border-bark-100 bg-surface relative flex cursor-pointer items-center gap-2.5 rounded-lg border border-l-4 pr-2 pl-2 shadow-sm transition-shadow hover:shadow-md ${ACCENT[person.gender] ?? ACCENT.unknown} ${ring}`}
      data-testid="person-card"
    >
      {/* The tree grows upwards: the link from the parents arrives at the bottom of a card,
          links to the person's own family leave from the top. */}
      <Handle type="target" position={Position.Bottom} className={hidden} isConnectable={false} />
      <Avatar name={person.display_name} gender={person.gender} url={person.avatar_url} size="md" />
      <div className="min-w-0">
        <div className="line-clamp-2 text-sm leading-tight font-medium">{person.display_name}</div>
        <div className="text-bark-700 text-xs">
          {lifeYears(person.birth, person.death, person.is_living)}
          {died && person.death && (
            <span className="ml-1" aria-hidden="true">
              †
            </span>
          )}
        </div>
      </div>
      {/* Hover preview with the full name, dates and birthplace. */}
      <div
        role="tooltip"
        className="border-bark-100 bg-surface pointer-events-none invisible absolute top-full left-1/2 z-50 mt-2 w-64 -translate-x-1/2 rounded-lg border p-3 text-left opacity-0 shadow-lg transition-opacity group-hover:visible group-hover:opacity-100"
      >
        <div className="font-serif text-sm font-semibold">{person.display_name}</div>
        {dates.map((d) => (
          <div key={d as string} className="text-bark-700 text-xs">
            {d}
          </div>
        ))}
        {person.birth_place && <div className="text-bark-700 text-xs">📍 {person.birth_place}</div>}
      </div>
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

/** Where a couple's branch splits towards their children: a knot on the branch. */
export const FamilyNode = memo(function FamilyNode() {
  return (
    <div
      style={{ width: FAMILY_SIZE, height: FAMILY_SIZE, background: BRANCH }}
      className="rounded-full"
    >
      <Handle type="target" position={Position.Bottom} className={hidden} isConnectable={false} />
      <Handle type="source" position={Position.Top} className={hidden} isConnectable={false} />
    </div>
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
