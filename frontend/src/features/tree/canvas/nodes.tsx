import { Handle, Position, type Node, type NodeProps } from "@xyflow/react";
import { memo } from "react";
import { useTranslation } from "react-i18next";

import { Avatar } from "@/features/person/Avatar";
import { lifeYears } from "@/lib/dates";
import type { PersonSummary } from "@/lib/genealogy";

import { FAMILY_SIZE, PERSON_HEIGHT, PERSON_WIDTH } from "./familyGraph";

export interface PersonNodeData extends Record<string, unknown> {
  person: PersonSummary;
  highlighted: boolean;
  hiddenUp: boolean;
  hiddenDown: boolean;
}
export type PersonFlowNode = Node<PersonNodeData, "person">;
export type FamilyFlowNode = Node<Record<string, never>, "family">;

const hidden = "!h-1 !w-1 !min-h-0 !min-w-0 !border-0 !bg-transparent";

export const PersonNode = memo(function PersonNode({ data, selected }: NodeProps<PersonFlowNode>) {
  const { t } = useTranslation();
  const { person, highlighted, hiddenUp, hiddenDown } = data;
  const ring = highlighted || selected ? "ring-2 ring-leaf-600" : "";
  return (
    <div
      style={{ width: PERSON_WIDTH, height: PERSON_HEIGHT }}
      className={`border-bark-100 relative flex cursor-pointer items-center gap-3 rounded-lg border bg-white px-3 shadow-sm transition-shadow hover:shadow-md ${ring}`}
      data-testid="person-card"
      title={person.display_name}
    >
      <Handle type="target" position={Position.Top} className={hidden} isConnectable={false} />
      <Avatar name={person.display_name} gender={person.gender} size="sm" />
      <div className="min-w-0">
        <div className="line-clamp-2 text-sm leading-tight font-medium">{person.display_name}</div>
        <div className="text-bark-700 text-xs">
          {lifeYears(person.birth, person.death, person.is_living)}
        </div>
      </div>
      {hiddenUp && (
        <span
          className="bg-bark-100 text-bark-700 absolute -top-2 left-1/2 -translate-x-1/2 rounded-full px-1.5 text-[10px] leading-4"
          title={t("canvas.moreAbove")}
        >
          ▲
        </span>
      )}
      {hiddenDown && (
        <span
          className="bg-bark-100 text-bark-700 absolute -bottom-2 left-1/2 -translate-x-1/2 rounded-full px-1.5 text-[10px] leading-4"
          title={t("canvas.moreBelow")}
        >
          ▼
        </span>
      )}
      <Handle type="source" position={Position.Bottom} className={hidden} isConnectable={false} />
    </div>
  );
});

export const FamilyNode = memo(function FamilyNode() {
  return (
    <div style={{ width: FAMILY_SIZE, height: FAMILY_SIZE }} className="bg-bark-700 rounded-full">
      <Handle type="target" position={Position.Top} className={hidden} isConnectable={false} />
      <Handle type="source" position={Position.Bottom} className={hidden} isConnectable={false} />
    </div>
  );
});
