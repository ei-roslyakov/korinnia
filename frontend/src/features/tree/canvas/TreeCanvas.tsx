import "@xyflow/react/dist/style.css";

import { useQuery } from "@tanstack/react-query";
import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
  type Edge,
  type Node,
} from "@xyflow/react";
import { useEffect, useMemo } from "react";
import { useTranslation } from "react-i18next";

import { Spinner } from "@/components/ui";
import type { TreeGraph } from "@/lib/genealogy";

import {
  PERSON_HEIGHT,
  PERSON_WIDTH,
  buildFamilies,
  hiddenRelatives,
  indexRelations,
  toElkGraph,
} from "./familyGraph";
import { computeLayout } from "./layout";
import type { PersonFlowNode } from "./nodes";
import { nodeTypes } from "./nodeTypes";

function hashKey(text: string): string {
  let h = 5381;
  for (let i = 0; i < text.length; i++) h = ((h << 5) + h + text.charCodeAt(i)) | 0;
  return (h >>> 0).toString(36);
}

const GENDER_COLORS: Record<string, string> = {
  male: "#bae6fd",
  female: "#fecdd3",
  other: "#ddd6fe",
  unknown: "#e7e5e4",
};

export interface CenterRequest {
  personId: string;
  nonce: number;
}

interface Props {
  treeId: string;
  graph: TreeGraph;
  graphVersion: number;
  included: Set<string>;
  focusMode: boolean;
  selectedId: string | null;
  center: CenterRequest | null;
  onSelectPerson: (personId: string) => void;
}

function CanvasInner({
  treeId,
  graph,
  graphVersion,
  included,
  focusMode,
  selectedId,
  center,
  onSelectPerson,
}: Props) {
  const { t } = useTranslation();
  const rf = useReactFlow();
  const rel = useMemo(() => indexRelations(graph), [graph]);
  const families = useMemo(() => buildFamilies(graph, included), [graph, included]);
  const personIds = useMemo(
    () => graph.persons.filter((p) => included.has(p.id)).map((p) => p.id),
    [graph, included],
  );
  const layoutKey = useMemo(() => hashKey(personIds.join(",")), [personIds]);

  const layout = useQuery({
    queryKey: ["tree", treeId, "layout", graphVersion, layoutKey],
    queryFn: () => computeLayout(toElkGraph(personIds, families)),
    staleTime: Infinity,
  });

  const nodes = useMemo<Node[]>(() => {
    const pos = layout.data;
    if (!pos) return [];
    const byId = new Map(graph.persons.map((p) => [p.id, p]));
    const personNodes: PersonFlowNode[] = personIds.map((id) => {
      const hiddenRel = focusMode ? hiddenRelatives(rel, id, included) : { up: false, down: false };
      return {
        id,
        type: "person",
        position: pos[id] ?? { x: 0, y: 0 },
        selected: id === selectedId,
        data: {
          person: byId.get(id)!,
          highlighted: id === center?.personId,
          hiddenUp: hiddenRel.up,
          hiddenDown: hiddenRel.down,
        },
      };
    });
    const familyNodes: Node[] = families.map((f) => ({
      id: f.id,
      type: "family",
      position: pos[f.id] ?? { x: 0, y: 0 },
      selectable: false,
      data: {},
    }));
    return [...personNodes, ...familyNodes];
  }, [layout.data, graph, personIds, families, rel, included, focusMode, selectedId, center]);

  const edges = useMemo<Edge[]>(
    () =>
      families.flatMap((f) => [
        ...f.parents.map((p) => ({
          id: `${p}->${f.id}`,
          source: p,
          target: f.id,
          type: "smoothstep",
          style: { stroke: "#a8a29e" },
        })),
        ...f.children.map((c) => ({
          id: `${f.id}->${c.id}`,
          source: f.id,
          target: c.id,
          type: "smoothstep",
          style: {
            stroke: "#78716c",
            strokeDasharray: c.type === "biological" ? undefined : "6 4",
          },
        })),
      ]),
    [families],
  );

  // After a (re)layout: center the requested person, or fit the whole view.
  useEffect(() => {
    if (!layout.data) return;
    const target = center ? layout.data[center.personId] : undefined;
    const frame = requestAnimationFrame(() => {
      if (target) {
        void rf.setCenter(target.x + PERSON_WIDTH / 2, target.y + PERSON_HEIGHT / 2, {
          zoom: Math.max(rf.getZoom(), 0.9),
          duration: 500,
        });
      } else {
        void rf.fitView({ padding: 0.15, duration: 300, maxZoom: 1.2 });
      }
    });
    return () => cancelAnimationFrame(frame);
  }, [layout.data, center, rf]);

  if (layout.isPending) {
    return (
      <div className="text-bark-700 flex h-full items-center justify-center gap-2">
        <Spinner /> {t("canvas.layouting")}
      </div>
    );
  }

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      onNodeClick={(_, node) => node.type === "person" && onSelectPerson(node.id)}
      nodesDraggable={false}
      nodesConnectable={false}
      edgesFocusable={false}
      onlyRenderVisibleElements
      ariaLabelConfig={{
        "controls.ariaLabel": t("canvas.controls"),
        "controls.zoomIn.ariaLabel": t("canvas.zoomIn"),
        "controls.zoomOut.ariaLabel": t("canvas.zoomOut"),
        "controls.fitView.ariaLabel": t("canvas.fit"),
        "minimap.ariaLabel": t("canvas.minimap"),
      }}
      minZoom={0.05}
      maxZoom={2}
      fitView
      fitViewOptions={{ padding: 0.15, maxZoom: 1.2 }}
    >
      <Background gap={24} color="#e7e5e4" />
      <Controls showInteractive={false} fitViewOptions={{ padding: 0.15, duration: 300 }} />
      <MiniMap
        pannable
        zoomable
        ariaLabel={t("canvas.minimap")}
        nodeColor={(n) =>
          n.type === "person"
            ? (GENDER_COLORS[(n as PersonFlowNode).data.person.gender] ?? "#e7e5e4")
            : "#78716c"
        }
        className="!hidden sm:!block"
      />
    </ReactFlow>
  );
}

/** Pan/zoom canvas of the family graph, laid out with ELK. */
export function TreeCanvas(props: Props) {
  return (
    <ReactFlowProvider>
      <CanvasInner {...props} />
    </ReactFlowProvider>
  );
}
