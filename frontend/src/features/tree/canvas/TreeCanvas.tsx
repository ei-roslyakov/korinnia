import "@xyflow/react/dist/style.css";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
  type Edge,
  type Node,
  type NodeChange,
} from "@xyflow/react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { Spinner } from "@/components/ui";
import type { RelativeRelation, TreeGraph } from "@/lib/genealogy";

import {
  FAMILY_SIZE,
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
  included: Set<string>;
  focusMode: boolean;
  selectedId: string | null;
  center: CenterRequest | null;
  onSelectPerson: (personId: string) => void;
  /** Builder mode: draggable cards and "+" buttons. */
  builder?: boolean;
  onAddRelative?: (personId: string, relation: RelativeRelation) => void;
  onMoved?: (personId: string, dx: number, dy: number) => void;
}

type XY = { x: number; y: number };

function CanvasInner({
  treeId,
  graph,
  included,
  focusMode,
  selectedId,
  center,
  onSelectPerson,
  builder = false,
  onAddRelative,
  onMoved,
}: Props) {
  const { t } = useTranslation();
  const rf = useReactFlow();
  const rel = useMemo(() => indexRelations(graph), [graph]);
  const families = useMemo(() => buildFamilies(graph, included), [graph, included]);
  const personIds = useMemo(
    () => graph.persons.filter((p) => included.has(p.id)).map((p) => p.id),
    [graph, included],
  );
  // The layout depends only on structure (who is shown, how they are linked) — not on
  // names, dates or manual offsets — so edits and drags never trigger a re-layout.
  const layoutKey = useMemo(
    () =>
      hashKey(
        personIds.join(",") +
          "|" +
          families
            .map((f) => `${f.parents.join("+")}>${f.children.map((c) => c.id).join("+")}`)
            .join(";"),
      ),
    [personIds, families],
  );

  const layout = useQuery({
    queryKey: ["tree", treeId, "layout", layoutKey],
    queryFn: () => computeLayout(toElkGraph(personIds, families)),
    staleTime: Infinity,
    // While a changed structure is laid out, keep showing the previous layout instead of
    // unmounting the canvas (which would reset the view under the user's hands).
    placeholderData: keepPreviousData,
  });

  // Positions currently being dragged (not yet saved as offsets).
  const [dragging, setDragging] = useState<Record<string, XY>>({});
  const offsets = graph.layout_offsets;

  /** Final person positions: automatic layout + saved offsets + live drag. */
  const personPos = useMemo<Record<string, XY>>(() => {
    const pos = layout.data;
    if (!pos) return {};
    const out: Record<string, XY> = {};
    for (const id of personIds) {
      const base = pos[id] ?? { x: 0, y: 0 };
      const off = offsets?.[id];
      out[id] = dragging[id] ?? (off ? { x: base.x + off.dx, y: base.y + off.dy } : base);
    }
    return out;
  }, [layout.data, personIds, offsets, dragging]);

  const nodes = useMemo<Node[]>(() => {
    const pos = layout.data;
    if (!pos) return [];
    const byId = new Map(graph.persons.map((p) => [p.id, p]));
    const moved = (id: string) => Boolean(offsets?.[id] || dragging[id]);
    const personNodes: PersonFlowNode[] = personIds
      .filter((id) => pos[id])
      .map((id) => {
        const hiddenRel = focusMode
          ? hiddenRelatives(rel, id, included)
          : { up: false, down: false };
        return {
          id,
          type: "person",
          position: personPos[id] ?? { x: 0, y: 0 },
          selected: id === selectedId,
          draggable: builder,
          data: {
            person: byId.get(id)!,
            highlighted: id === center?.personId,
            hiddenUp: hiddenRel.up,
            hiddenDown: hiddenRel.down,
            onAdd: builder ? onAddRelative : undefined,
          },
        };
      });
    const familyNodes: Node[] = families
      .filter((f) => pos[f.id])
      .map((f) => {
        let position = pos[f.id] ?? { x: 0, y: 0 };
        // Keep a junction between its (moved) parents and children.
        if ([...f.parents, ...f.children.map((c) => c.id)].some(moved)) {
          const parents = f.parents.map((p) => personPos[p]).filter(Boolean) as XY[];
          const kids = f.children.map((c) => personPos[c.id]).filter(Boolean) as XY[];
          const anchor = parents.length ? parents : kids;
          const x =
            anchor.reduce((sum, p) => sum + p.x, 0) / anchor.length +
            PERSON_WIDTH / 2 -
            FAMILY_SIZE / 2;
          const parentBottom = parents.length
            ? Math.max(...parents.map((p) => p.y)) + PERSON_HEIGHT
            : null;
          const kidTop = kids.length ? Math.min(...kids.map((p) => p.y)) : null;
          const y =
            parentBottom !== null && kidTop !== null
              ? (parentBottom + kidTop) / 2
              : (parentBottom ?? (kidTop ?? 0) - 30) + (parentBottom !== null ? 20 : 0);
          position = { x, y };
        }
        return {
          id: f.id,
          type: "family",
          position,
          selectable: false,
          draggable: false,
          data: {},
        };
      });
    return [...personNodes, ...familyNodes];
  }, [
    layout.data,
    graph,
    personIds,
    personPos,
    families,
    rel,
    included,
    focusMode,
    selectedId,
    center,
    builder,
    onAddRelative,
    offsets,
    dragging,
  ]);

  const onNodesChange = (changes: NodeChange[]) => {
    const live: Record<string, XY> = {};
    for (const c of changes) {
      if (c.type === "position" && c.position && c.dragging) live[c.id] = c.position;
    }
    if (Object.keys(live).length) setDragging((d) => ({ ...d, ...live }));
  };

  const onNodeDragStop = (_: unknown, node: Node) => {
    const base = layout.data?.[node.id];
    if (node.type === "person" && base) {
      onMoved?.(
        node.id,
        Math.round(node.position.x - base.x),
        Math.round(node.position.y - base.y),
      );
    }
    setDragging((d) => {
      const rest = { ...d };
      delete rest[node.id];
      return rest;
    });
  };

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

  // Fit the whole tree once (first layout); afterwards only move the view on explicit
  // requests (search result, newly added person) — never on background refreshes.
  const fitted = useRef(false);
  const handledCenter = useRef<number | null>(null);
  useEffect(() => {
    if (!layout.data || layout.isPlaceholderData) return;
    const target = center ? personPos[center.personId] : undefined;
    const needCenter = Boolean(target) && handledCenter.current !== center?.nonce;
    if (!needCenter && fitted.current) return;
    const frame = requestAnimationFrame(() => {
      if (target && center) {
        handledCenter.current = center.nonce;
        void rf.setCenter(target.x + PERSON_WIDTH / 2, target.y + PERSON_HEIGHT / 2, {
          zoom: Math.max(rf.getZoom(), 0.9),
          duration: 500,
        });
      } else {
        void rf.fitView({ padding: 0.15, duration: 300, maxZoom: 1.2 });
      }
      fitted.current = true;
    });
    return () => cancelAnimationFrame(frame);
  }, [layout.data, layout.isPlaceholderData, center, personPos, rf]);

  // Leaving or entering focus mode is a new view: fit it again.
  useEffect(() => {
    fitted.current = false;
  }, [focusMode]);

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
      onNodesChange={onNodesChange}
      onNodeDragStop={onNodeDragStop}
      nodesDraggable={builder}
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
