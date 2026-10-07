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
import { useTheme } from "@/lib/theme";

import {
  FAMILY_SIZE,
  PERSON_HEIGHT,
  PERSON_WIDTH,
  buildFamilies,
  ROW_GAP,
  hiddenRelatives,
  indexRelations,
  junctionY,
  toElkGraph,
} from "./familyGraph";
import { computeLayout } from "./layout";
import { BRANCH, BRANCH_COLOR, GROUND_HEIGHT, TRUNK_REACH, branchWidth } from "./treeStyle";
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
  const { theme } = useTheme();
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

  /** Final person positions: automatic layout + saved offsets + live drag. Cards only move
   * sideways, so every generation stays on its row (a stored vertical offset is ignored). */
  const personPos = useMemo<Record<string, XY>>(() => {
    const pos = layout.data;
    if (!pos) return {};
    const out: Record<string, XY> = {};
    for (const id of personIds) {
      const base = pos[id] ?? { x: 0, y: 0 };
      const x = dragging[id]?.x ?? base.x + (offsets?.[id]?.dx ?? 0);
      out[id] = { x, y: base.y };
    }
    return out;
  }, [layout.data, personIds, offsets, dragging]);

  const nodes = useMemo<Node[]>(() => {
    const pos = layout.data;
    if (!pos) return [];
    const byId = new Map(graph.persons.map((p) => [p.id, p]));
    const moved = (id: string) => Boolean(offsets?.[id] || dragging[id]);
    // Soil under the oldest generation, with a trunk under each founding couple.
    const groundNodes = (): Node[] => {
      const placed = personIds.map((id) => personPos[id]).filter(Boolean) as XY[];
      if (!placed.length) return [];
      const rootRow = Math.max(...placed.map((p) => p.y));
      const left = Math.min(...placed.map((p) => p.x)) - 160;
      const right = Math.max(...placed.map((p) => p.x)) + PERSON_WIDTH + 160;
      const trunks = families
        .filter((f) => f.children.length && f.parents.every((p) => personPos[p]?.y === rootRow))
        .map((f) => {
          const xs = f.parents.map((p) => personPos[p]!.x + PERSON_WIDTH / 2);
          return (Math.min(...xs) + Math.max(...xs)) / 2 - left;
        });
      return [
        {
          id: "ground",
          type: "ground",
          position: { x: left, y: rootRow + PERSON_HEIGHT + TRUNK_REACH },
          initialWidth: right - left,
          initialHeight: GROUND_HEIGHT,
          selectable: false,
          draggable: false,
          focusable: false,
          zIndex: -1,
          style: { pointerEvents: "none" },
          data: { width: right - left, trunks },
        },
      ];
    };
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
          // Known sizes: React Flow hides nodes it has not measured yet, and a rebuilt
          // node array can drop measurements, leaving the canvas blank until a resize.
          initialWidth: PERSON_WIDTH,
          initialHeight: PERSON_HEIGHT,
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
          const parentTop = parents.length
            ? Math.min(...parents.map((p) => p.y))
            : Math.max(...kids.map((p) => p.y)) + PERSON_HEIGHT + ROW_GAP;
          position = {
            x,
            y: junctionY(
              parentTop,
              kids.map((k) => k.y),
            ),
          };
        }
        return {
          id: f.id,
          type: "family",
          position,
          initialWidth: FAMILY_SIZE,
          initialHeight: FAMILY_SIZE,
          selectable: false,
          draggable: false,
          data: {},
        };
      });
    return [...groundNodes(), ...personNodes, ...familyNodes];
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
      onMoved?.(node.id, Math.round(node.position.x - base.x), 0);
    }
    setDragging((d) => {
      const rest = { ...d };
      delete rest[node.id];
      return rest;
    });
  };

  // Generation rank of each row, counted from the bottom (0 = the oldest generation).
  const rankOf = useMemo(() => {
    const rows = [...new Set(Object.values(personPos).map((p) => p.y))].sort((a, b) => b - a);
    return (id: string) => Math.max(0, rows.indexOf(personPos[id]?.y ?? rows[0] ?? 0));
  }, [personPos]);

  const edges = useMemo<Edge[]>(
    () =>
      families.flatMap((f) => {
        const rank = Math.min(...f.parents.map(rankOf));
        const branch = { stroke: BRANCH, strokeLinecap: "round" as const };
        return [
          ...f.parents.map((p) => ({
            id: `${p}->${f.id}`,
            source: p,
            target: f.id,
            type: "default",
            style: { ...branch, strokeWidth: branchWidth(rank) },
          })),
          ...f.children.map((c) => ({
            id: `${f.id}->${c.id}`,
            source: f.id,
            target: c.id,
            type: "default",
            style: {
              ...branch,
              strokeWidth: branchWidth(rank + 0.5),
              strokeDasharray: c.type === "biological" ? undefined : "6 5",
            },
          })),
        ];
      }),
    [families, rankOf],
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
      // Sky above, meadow towards the ground (per theme).
      style={{ background: "var(--k-canvas)" }}
      colorMode={theme === "dark" ? "dark" : "light"}
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
      <Background gap={24} color="var(--k-canvas-dots)" bgColor="transparent" />
      <Controls showInteractive={false} fitViewOptions={{ padding: 0.15, duration: 300 }} />
      <MiniMap
        bgColor="var(--k-surface)"
        pannable
        zoomable
        ariaLabel={t("canvas.minimap")}
        nodeColor={(n) =>
          n.type === "person"
            ? (GENDER_COLORS[(n as PersonFlowNode).data.person.gender] ?? "#e7e5e4")
            : n.type === "ground"
              ? "transparent"
              : BRANCH_COLOR
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
