import "@xyflow/react/dist/style.css";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import {
  Background,
  Controls,
  MiniMap,
  Panel,
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
  type Edge,
  type Node,
  type NodeChange,
} from "@xyflow/react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { Button, Spinner } from "@/components/ui";
import type { RelativeRelation, TreeGraph } from "@/lib/genealogy";
import { useTheme } from "@/lib/theme";
import { useToast } from "@/lib/toast";

import {
  FAMILY_SIZE,
  PERSON_HEIGHT,
  PERSON_WIDTH,
  buildFamilies,
  ROW_GAP,
  branch,
  hiddenRelatives,
  indexRelations,
  junctionY,
  lineage,
  roman,
  toElkGraph,
  type Family,
} from "./familyGraph";
import { edgeTypes } from "./edgeTypes";
import { exportFileName, exportTree, type ExportFormat } from "./exportTree";
import { computeLayout } from "./layout";
import {
  BRANCH,
  BRANCH_COLOR,
  GROUND_HEIGHT,
  STYLE_WIDTH,
  TRUNK_REACH,
  branchWidth,
  type TreeStyle,
} from "./treeStyle";
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
  /** How the tree is drawn (simple, oak, spring). */
  treeStyle?: TreeStyle;
  graph: TreeGraph;
  included: Set<string>;
  focusMode: boolean;
  selectedId: string | null;
  center: CenterRequest | null;
  onSelectPerson: (personId: string) => void;
  /** Builder mode: draggable cards and "+" buttons. */
  builder?: boolean;
  onAddRelative?: (personId: string, relation: RelativeRelation) => void;
  /** New offsets (from the automatic layout) of the cards moved by one drag. */
  onMoved?: (offsets: Record<string, { dx: number; dy: number }>) => void;
  /** Tree name: offers "download as PNG / PDF" with this title. */
  exportTitle?: string;
}

type XY = { x: number; y: number };

/** A stable number from an id, to vary decorations deterministically. */
const hashOf = (s: string) => Math.abs([...s].reduce((h, c) => (h * 31 + c.charCodeAt(0)) | 0, 7));

function CanvasInner({
  treeId,
  treeStyle = "simple",
  graph,
  included,
  focusMode,
  selectedId,
  center,
  onSelectPerson,
  builder = false,
  onAddRelative,
  onMoved,
  exportTitle,
}: Props) {
  const { t, i18n } = useTranslation();
  const { theme } = useTheme();
  const rf = useReactFlow();
  const rel = useMemo(() => indexRelations(graph), [graph]);
  // The person whose line is highlighted: the one under the pointer, else the selected one.
  const [hovered, setHovered] = useState<string | null>(null);
  // While exporting, every card is rendered and nothing is highlighted.
  const [exporting, setExporting] = useState<ExportFormat | null>(null);
  const focusPerson = exporting ? null : (hovered ?? selectedId ?? null);
  const lit = useMemo(() => (focusPerson ? lineage(rel, focusPerson) : null), [rel, focusPerson]);
  /** A family junction on the highlighted line (or nothing highlighted). */
  const familyLit = useCallback(
    (f: Family) =>
      !lit ||
      (f.parents.some((p) => lit.has(p)) &&
        (f.children.some((c) => lit.has(c.id)) || f.parents.includes(focusPerson ?? ""))),
    [lit, focusPerson],
  );
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
      out[id] = dragging[id] ?? { x: base.x + (off?.dx ?? 0), y: base.y + (off?.dy ?? 0) };
    }
    return out;
  }, [layout.data, personIds, offsets, dragging]);

  const nodes = useMemo<Node[]>(() => {
    const pos = layout.data;
    if (!pos) return [];
    const byId = new Map(graph.persons.map((p) => [p.id, p]));
    const moved = (id: string) => Boolean(offsets?.[id] || dragging[id]);
    // "III покоління · 1910-ті" beside each row (rows counted from the oldest, at the bottom).
    const rowLabels = (): Node[] => {
      // Rows of the automatic layout: hand-moved cards keep their generation.
      const placed = personIds.filter((id) => personPos[id] && pos[id]);
      if (!placed.length) return [];
      const left = Math.min(...placed.map((id) => personPos[id]!.x)) - 230;
      const rows = [...new Set(placed.map((id) => pos[id]!.y))].sort((a, b) => b - a);
      return rows.map((y, i) => {
        const years = placed
          .filter((id) => pos[id]!.y === y)
          .map((id) => byId.get(id)?.birth?.year)
          .filter((v): v is number => typeof v === "number")
          .sort((a, b) => a - b);
        const median = years[Math.floor(years.length / 2)];
        return {
          id: `row:${i}`,
          type: "rowLabel",
          position: { x: left, y: y + PERSON_HEIGHT / 2 - 18 },
          selectable: false,
          draggable: false,
          focusable: false,
          data: {
            generation: t("canvas.generationRow", { n: roman(i + 1) }),
            period:
              median !== undefined
                ? t("insights.timeline.decade", { decade: Math.floor(median / 10) * 10 })
                : null,
          },
        };
      });
    };
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
    // Oak: a broad trunk under each founding couple and a leafy crown behind the family.
    const crownNodes = (): Node[] => {
      if (treeStyle !== "oak") return [];
      const placed = personIds.filter((id) => personPos[id]).map((id) => personPos[id]!);
      if (!placed.length) return [];
      const rootRow = Math.max(...placed.map((p) => p.y));
      const upper = placed.filter((p) => p.y < rootRow);
      const left = Math.min(...placed.map((p) => p.x)) - 220;
      const right = Math.max(...placed.map((p) => p.x)) + PERSON_WIDTH + 220;
      const top = Math.min(...placed.map((p) => p.y)) - 220;
      const ground = rootRow + PERSON_HEIGHT + TRUNK_REACH + 34;
      const crown = upper.length
        ? (() => {
            const x0 = Math.min(...upper.map((p) => p.x)) - 70;
            const x1 = Math.max(...upper.map((p) => p.x)) + PERSON_WIDTH + 70;
            const y0 = Math.min(...upper.map((p) => p.y)) - 90;
            const y1 = Math.max(...upper.map((p) => p.y)) + PERSON_HEIGHT + 30;
            return {
              cx: (x0 + x1) / 2 - left,
              cy: (y0 + y1) / 2 - top,
              rx: (x1 - x0) / 2,
              ry: (y1 - y0) / 2,
            };
          })()
        : null;
      const trunks = families
        .filter((f) => f.children.length && f.parents.every((p) => personPos[p]?.y === rootRow))
        .map((f) => {
          const xs = f.parents.map((p) => personPos[p]!.x + PERSON_WIDTH / 2);
          const knot = pos[f.id];
          return {
            x: (Math.min(...xs) + Math.max(...xs)) / 2 - left,
            width: branchWidth(0.5) * STYLE_WIDTH.oak,
            bottom: ground - top,
            top: (knot ? knot.y : rootRow - 40) + FAMILY_SIZE / 2 - top,
          };
        });
      return [
        {
          id: "crown",
          type: "crown",
          position: { x: left, y: top },
          initialWidth: right - left,
          initialHeight: ground - top,
          selectable: false,
          draggable: false,
          focusable: false,
          zIndex: -2,
          style: { pointerEvents: "none" },
          data: { width: right - left, height: ground - top, crown, trunks },
        },
      ];
    };
    // Rows counted from the oldest (0); the youngest rows blossom in spring.
    const rowsY = [...new Set(personIds.filter((id) => pos[id]).map((id) => pos[id]!.y))].sort(
      (a, b) => b - a,
    );
    const rowOf = (id: string) => rowsY.indexOf(pos[id]?.y ?? NaN);
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
          selected: !exporting && id === selectedId,
          draggable: builder,
          style: { opacity: lit && !lit.has(id) ? 0.3 : 1, transition: "opacity 150ms" },
          data: {
            person: byId.get(id)!,
            highlighted: !exporting && id === center?.personId,
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
          style: { opacity: familyLit(f) ? 1 : 0.3, transition: "opacity 150ms" },
          initialWidth: FAMILY_SIZE,
          initialHeight: FAMILY_SIZE,
          selectable: false,
          draggable: false,
          data: {
            decor: treeStyle,
            // Oak: the knot is as thick as the branches meeting there.
            knot:
              branchWidth(Math.min(...f.parents.map(rowOf).filter((r) => r >= 0), 0) + 0.5) *
              STYLE_WIDTH[treeStyle],
            blossom: Math.max(...f.parents.map(rowOf)) >= rowsY.length - 2 && rowsY.length > 2,
            seed: hashOf(f.id),
          },
        };
      });
    return [...crownNodes(), ...groundNodes(), ...rowLabels(), ...personNodes, ...familyNodes];
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
    exporting,
    builder,
    onAddRelative,
    offsets,
    dragging,
    lit,
    familyLit,
    t,
    treeStyle,
  ]);

  // Dragging a card moves its whole branch (partners and descendants); with Alt held,
  // only the card itself. Start positions are kept so every card moves by the same delta.
  const dragGroup = useRef<{ id: string; start: Record<string, XY> } | null>(null);

  const onNodeDragStart = (event: MouseEvent | TouchEvent, node: Node) => {
    if (node.type !== "person") return;
    const members = "altKey" in event && event.altKey ? new Set([node.id]) : branch(rel, node.id);
    const start: Record<string, XY> = {};
    for (const m of members) if (personPos[m]) start[m] = personPos[m]!;
    dragGroup.current = { id: node.id, start };
  };

  const onNodesChange = (changes: NodeChange[]) => {
    const group = dragGroup.current;
    for (const c of changes) {
      if (c.type !== "position" || !c.position || !c.dragging) continue;
      if (!group || c.id !== group.id) {
        setDragging((d) => ({ ...d, [c.id]: c.position! }));
        continue;
      }
      const origin = group.start[group.id]!;
      const dx = c.position.x - origin.x;
      const dy = c.position.y - origin.y;
      const live: Record<string, XY> = {};
      for (const [m, p] of Object.entries(group.start)) live[m] = { x: p.x + dx, y: p.y + dy };
      setDragging((d) => ({ ...d, ...live }));
    }
  };

  const onNodeDragStop = (_: unknown, node: Node) => {
    const group = dragGroup.current;
    dragGroup.current = null;
    if (node.type === "person" && layout.data && group) {
      const origin = group.start[group.id]!;
      const dx = node.position.x - origin.x;
      const dy = node.position.y - origin.y;
      const moved: Record<string, { dx: number; dy: number }> = {};
      for (const [m, p] of Object.entries(group.start)) {
        const base = layout.data[m];
        if (!base) continue;
        moved[m] = { dx: Math.round(p.x + dx - base.x), dy: Math.round(p.y + dy - base.y) };
      }
      if (dx !== 0 || dy !== 0) onMoved?.(moved);
    }
    setDragging({});
  };

  // Generation rank of each row, counted from the bottom (0 = the oldest generation).
  // From the automatic layout, so moving cards by hand never changes anyone's generation.
  const rankOf = useMemo(() => {
    const base = layout.data ?? {};
    const ys = personIds.map((id) => base[id]?.y).filter((y): y is number => y !== undefined);
    const rows = [...new Set(ys)].sort((a, b) => b - a);
    return (id: string) => Math.max(0, rows.indexOf(base[id]?.y ?? NaN));
  }, [layout.data, personIds]);

  const maxRank = useMemo(
    () => personIds.reduce((m, id) => Math.max(m, rankOf(id)), 0),
    [personIds, rankOf],
  );

  const edges = useMemo<Edge[]>(
    () =>
      families.flatMap((f): Edge[] => {
        const rank = Math.min(...f.parents.map(rankOf));
        const scale = STYLE_WIDTH[treeStyle];
        const width = (r: number) => branchWidth(r) * scale;
        const on = familyLit(f);
        const opacity = (id: string) => (on && (!lit || lit.has(id)) ? 1 : 0.18);
        if (treeStyle !== "simple") {
          const spring = treeStyle === "spring";
          // Young branches blossom in spring.
          const young = rank >= maxRank - 2;
          // Oak and spring: tapering branches whose thickness carries on through each knot: parent → knot
          // goes from width(rank) to width(rank + ½), knot → child on to width(rank + 1).
          return [
            ...f.parents.map((p) => ({
              id: `${p}->${f.id}`,
              source: p,
              target: f.id,
              type: "branch",
              data: {
                w0: width(rank),
                w1: width(rank + 0.5),
                opacity: opacity(p),
                seed: hashOf(`${p}${f.id}`),
                twigEvery: spring ? 80 : 70,
                blossoms: spring && young,
              },
            })),
            ...f.children.map((c) => ({
              id: `${f.id}->${c.id}`,
              source: f.id,
              target: c.id,
              type: "branch",
              data: {
                w0: width(rank + 0.5),
                w1: width(rank + 1),
                faint: c.type !== "biological",
                opacity: opacity(c.id),
                seed: hashOf(`${f.id}${c.id}`),
                twigEvery: spring ? 80 : 70,
                blossoms: spring && young,
              },
            })),
          ];
        }
        const branch = { stroke: BRANCH, strokeLinecap: "round" as const };
        return [
          ...f.parents.map((p) => ({
            id: `${p}->${f.id}`,
            source: p,
            target: f.id,
            type: "default",
            style: { ...branch, strokeWidth: width(rank), strokeOpacity: opacity(p) },
          })),
          ...f.children.map((c) => ({
            id: `${f.id}->${c.id}`,
            source: f.id,
            target: c.id,
            type: "default",
            style: {
              ...branch,
              strokeWidth: width(rank + 0.5),
              strokeDasharray: c.type === "biological" ? undefined : "6 5",
              strokeOpacity: opacity(c.id),
            },
          })),
        ];
      }),
    [families, rankOf, familyLit, lit, treeStyle, maxRank],
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

  // Export runs once the canvas has re-rendered without culling and highlights (and the
  // 150 ms opacity transition of dimmed cards has finished).
  const rootRef = useRef<HTMLDivElement>(null);
  const toast = useToast();
  useEffect(() => {
    if (!exporting || !exportTitle) return;
    let cancelled = false;
    const timer = setTimeout(() => {
      const root = rootRef.current;
      const run = root
        ? exportTree({
            root,
            bounds: rf.getNodesBounds(rf.getNodes()),
            format: exporting,
            title: exportTitle,
            subtitle: [
              t("canvas.persons", { count: graph.persons.length }),
              new Intl.DateTimeFormat(i18n.language, { dateStyle: "long" }).format(new Date()),
            ].join(" · "),
            fileName: exportFileName(exportTitle),
          })
        : Promise.reject(new Error("no canvas"));
      run
        .catch(() => !cancelled && toast(t("canvas.export.failed"), "error"))
        .finally(() => !cancelled && setExporting(null));
    }, 300);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [exporting, exportTitle, rf, t, i18n.language, graph.persons.length, toast]);

  if (layout.isPending) {
    return (
      <div className="text-bark-700 flex h-full items-center justify-center gap-2">
        <Spinner /> {t("canvas.layouting")}
      </div>
    );
  }

  return (
    <ReactFlow
      ref={rootRef}
      // Sky above, meadow towards the ground (per theme).
      style={{ background: "var(--k-canvas)" }}
      colorMode={theme === "dark" ? "dark" : "light"}
      nodes={nodes}
      edges={edges}
      edgeTypes={edgeTypes}
      nodeTypes={nodeTypes}
      onNodeClick={(_, node) => node.type === "person" && onSelectPerson(node.id)}
      onNodeMouseEnter={(_, node) => node.type === "person" && setHovered(node.id)}
      onNodeMouseLeave={() => setHovered(null)}
      onNodesChange={onNodesChange}
      onNodeDragStart={onNodeDragStart}
      onNodeDragStop={onNodeDragStop}
      nodesDraggable={builder}
      nodesConnectable={false}
      edgesFocusable={false}
      onlyRenderVisibleElements={!exporting}
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
      {exportTitle && (
        <Panel position="top-left">
          <div
            role="group"
            aria-label={t("canvas.export.label")}
            className="border-bark-100 bg-surface flex items-center gap-1 rounded-md border px-2 py-1 text-xs shadow-sm"
          >
            <span className="text-bark-700">{t("canvas.export.label")}:</span>
            {(["png", "pdf"] as const).map((f) => (
              <Button
                key={f}
                variant="ghost"
                className="px-2 py-0.5 text-xs"
                busy={exporting === f}
                disabled={Boolean(exporting)}
                title={t(`canvas.export.${f}Hint`)}
                onClick={() => setExporting(f)}
              >
                {f.toUpperCase()}
              </Button>
            ))}
          </div>
        </Panel>
      )}
      <Controls showInteractive={false} fitViewOptions={{ padding: 0.15, duration: 300 }} />
      <MiniMap
        bgColor="var(--k-surface)"
        pannable
        zoomable
        ariaLabel={t("canvas.minimap")}
        nodeColor={
          (n) =>
            n.type === "person"
              ? (GENDER_COLORS[(n as PersonFlowNode).data.person.gender] ?? "#e7e5e4")
              : n.type === "family"
                ? BRANCH_COLOR
                : "transparent" // decorations (ground, crown, row labels)
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
