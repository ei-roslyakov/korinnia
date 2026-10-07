/**
 * Pure functions turning the tree graph (people + parent/child links + partnerships) into
 * a layered layout graph for ELK, and computing "focus" subsets.
 *
 * A family tree is a graph, not a tree. We insert a small *family* node per couple (or per
 * set of co-parents): parent → family → child, drawn as branches growing upwards.
 */
import type { ElkExtendedEdge, ElkNode } from "elkjs/lib/elk-api";

import type { GraphEdge, ParentChildType, TreeGraph } from "@/lib/genealogy";

export const PERSON_WIDTH = 200;
export const PERSON_HEIGHT = 76;
export const FAMILY_SIZE = 10;

export interface Family {
  id: string;
  parents: string[];
  children: { id: string; type: ParentChildType }[];
  partnershipId: string | null;
}

export interface Relations {
  parents: Map<string, GraphEdge[]>;
  children: Map<string, GraphEdge[]>;
  partners: Map<string, string[]>;
}

export function indexRelations(graph: TreeGraph): Relations {
  const parents = new Map<string, GraphEdge[]>();
  const children = new Map<string, GraphEdge[]>();
  const partners = new Map<string, string[]>();
  const push = <T>(m: Map<string, T[]>, k: string, v: T) => {
    const list = m.get(k);
    if (list) list.push(v);
    else m.set(k, [v]);
  };
  for (const e of graph.parent_child) {
    push(parents, e.child_id, e);
    push(children, e.parent_id, e);
  }
  for (const p of graph.partnerships) {
    push(partners, p.person_a_id, p.person_b_id);
    push(partners, p.person_b_id, p.person_a_id);
  }
  return { parents, children, partners };
}

/** Group children by their (included) set of parents; couples without children still
 * get a family node so partners are drawn next to each other. */
export function buildFamilies(graph: TreeGraph, included: Set<string>): Family[] {
  const families = new Map<string, Family>();
  const keyOf = (ids: string[]) => [...ids].sort().join("+");

  for (const p of graph.partnerships) {
    if (!included.has(p.person_a_id) || !included.has(p.person_b_id)) continue;
    const parents = [p.person_a_id, p.person_b_id];
    const key = keyOf(parents);
    if (!families.has(key)) {
      families.set(key, { id: `family:${key}`, parents, children: [], partnershipId: p.id });
    }
  }

  const byChild = new Map<string, GraphEdge[]>();
  for (const e of graph.parent_child) {
    if (!included.has(e.parent_id) || !included.has(e.child_id)) continue;
    const list = byChild.get(e.child_id) ?? [];
    list.push(e);
    byChild.set(e.child_id, list);
  }
  for (const [childId, edges] of byChild) {
    const parents = edges.map((e) => e.parent_id);
    const key = keyOf(parents);
    let family = families.get(key);
    if (!family) {
      family = { id: `family:${key}`, parents, children: [], partnershipId: null };
      families.set(key, family);
    }
    // A child counts as non-biological if any of its links in this family is.
    const nonBio = edges.find((e) => e.type !== "biological");
    family.children.push({ id: childId, type: nonBio ? nonBio.type : "biological" });
  }
  return [...families.values()];
}

/** People shown in focus mode: N generations of ancestors and descendants of `rootId`,
 * plus partners of the root and its descendants, and the root's siblings. */
export function focusSet(
  rel: Relations,
  rootId: string,
  generationsUp: number,
  generationsDown: number,
): Set<string> {
  const result = new Set<string>([rootId]);

  let frontier = [rootId];
  for (let g = 0; g < generationsUp && frontier.length; g++) {
    const next: string[] = [];
    for (const id of frontier) {
      for (const e of rel.parents.get(id) ?? []) {
        if (!result.has(e.parent_id)) {
          result.add(e.parent_id);
          next.push(e.parent_id);
        }
      }
    }
    frontier = next;
  }

  // Siblings: other children of the root's parents.
  if (generationsUp > 0) {
    for (const e of rel.parents.get(rootId) ?? []) {
      for (const c of rel.children.get(e.parent_id) ?? []) result.add(c.child_id);
    }
  }

  const addPartners = (id: string) => {
    for (const p of rel.partners.get(id) ?? []) result.add(p);
  };
  addPartners(rootId);
  const visitedDown = new Set<string>([rootId]);
  frontier = [rootId];
  for (let g = 0; g < generationsDown && frontier.length; g++) {
    const next: string[] = [];
    for (const id of frontier) {
      for (const e of rel.children.get(id) ?? []) {
        result.add(e.child_id);
        if (!visitedDown.has(e.child_id)) {
          visitedDown.add(e.child_id);
          next.push(e.child_id);
        }
      }
    }
    next.forEach(addPartners);
    frontier = next;
  }
  return result;
}

/** Root ancestor with the most descendants — a sensible default focus for large trees. */
export function defaultFocus(graph: TreeGraph, rel: Relations): string | null {
  let best: string | null = null;
  let bestCount = -1;
  for (const p of graph.persons) {
    if (rel.parents.has(p.id)) continue;
    const seen = new Set<string>();
    const stack = [p.id];
    while (stack.length) {
      const id = stack.pop() as string;
      for (const e of rel.children.get(id) ?? []) {
        if (!seen.has(e.child_id)) {
          seen.add(e.child_id);
          stack.push(e.child_id);
        }
      }
    }
    if (seen.size > bestCount) {
      bestCount = seen.size;
      best = p.id;
    }
  }
  return best ?? graph.persons[0]?.id ?? null;
}

// --- Layout --------------------------------------------------------------------------------
//
// Every person gets a generation number, and each generation is one row (ELK's interactive
// layering with the row as a hint). Partners are merged into one *unit* — a block ELK cannot
// split — so couples always stand side by side. Each unit has fixed connection points
// (ports): one on top of every member, and one at the bottom for each family it heads (between
// the partners for a couple). ELK orders the units to minimise crossings and centres children
// under their parents; family junctions are then placed halfway between the rows.

export const PARTNER_GAP = 24;
export const UNIT_GAP = 40;
export const ROW_GAP = 80;

/**
 * Generation (row) of every person: children one below their parents, partners on the same
 * row. Propagated breadth-first from each connected group, so in-laws without recorded parents
 * land next to their partner; afterwards every child is pushed below all of its parents.
 */
export function generations(personIds: string[], families: Family[]): Map<string, number> {
  const neighbours = new Map<string, [string, number][]>(personIds.map((id) => [id, []]));
  const link = (a: string, b: string, d: number) => neighbours.get(a)?.push([b, d]);
  for (const f of families) {
    for (const a of f.parents) {
      for (const b of f.parents) if (a !== b) link(a, b, 0);
      for (const c of f.children) {
        link(a, c.id, 1);
        link(c.id, a, -1);
      }
    }
  }
  const gen = new Map<string, number>();
  for (const start of personIds) {
    if (gen.has(start)) continue;
    gen.set(start, 0);
    const group = [start];
    for (let i = 0; i < group.length; i++) {
      const id = group[i]!;
      for (const [other, d] of neighbours.get(id) ?? []) {
        if (!gen.has(other)) {
          gen.set(other, gen.get(id)! + d);
          group.push(other);
        }
      }
    }
    const top = Math.min(...group.map((id) => gen.get(id)!));
    for (const id of group) gen.set(id, gen.get(id)! - top);
  }
  // Unusual data (e.g. marrying into an older generation) can leave a child level with or
  // above a parent; push such children down so every link points downwards.
  for (let changed = true, rounds = 0; changed && rounds < personIds.length; rounds++) {
    changed = false;
    for (const f of families) {
      const below = Math.max(...f.parents.map((p) => gen.get(p) ?? 0)) + 1;
      for (const c of f.children) {
        if ((gen.get(c.id) ?? 0) < below) {
          gen.set(c.id, below);
          changed = true;
        }
      }
    }
  }
  return gen;
}

export interface LayoutUnit {
  id: string;
  members: string[]; // left to right
}

/** Partners on the same row form one unit; a person with several partners stands between
 * them where possible (members are ordered along the chain of partnerships). */
export function buildUnits(
  personIds: string[],
  families: Family[],
  gen: Map<string, number>,
): LayoutUnit[] {
  const partners = new Map<string, string[]>(personIds.map((id) => [id, []]));
  for (const f of families) {
    if (f.parents.length !== 2) continue;
    const [a, b] = f.parents as [string, string];
    if (gen.get(a) !== gen.get(b) || partners.get(a)?.includes(b)) continue;
    partners.get(a)?.push(b);
    partners.get(b)?.push(a);
  }
  const seen = new Set<string>();
  const units: LayoutUnit[] = [];
  for (const id of personIds) {
    if (seen.has(id)) continue;
    // Collect the group, then walk it from an end (someone with a single partner).
    const group: string[] = [];
    const stack = [id];
    const inGroup = new Set([id]);
    while (stack.length) {
      const cur = stack.pop()!;
      group.push(cur);
      for (const p of partners.get(cur) ?? []) {
        if (!inGroup.has(p)) {
          inGroup.add(p);
          stack.push(p);
        }
      }
    }
    const startAt = group.find((m) => (partners.get(m)?.length ?? 0) <= 1) ?? id;
    const members: string[] = [];
    const walk = (m: string) => {
      if (seen.has(m)) return;
      seen.add(m);
      members.push(m);
      for (const p of partners.get(m) ?? []) walk(p);
    };
    walk(startAt);
    units.push({ id: `unit:${members[0]}`, members });
  }
  return units;
}

const memberX = (index: number) => index * (PERSON_WIDTH + PARTNER_GAP);
const unitWidth = (u: LayoutUnit) => memberX(u.members.length) - PARTNER_GAP;

export interface LayoutGraph {
  elk: ElkNode;
  units: LayoutUnit[];
  /** Per family: the unit and x offset (within it) its junction hangs from. */
  anchors: Map<string, { unitId: string; x: number }>;
  families: Family[];
}

export function toElkGraph(personIds: string[], families: Family[]): LayoutGraph {
  const gen = generations(personIds, families);
  const units = buildUnits(personIds, families, gen);
  const unitOf = new Map<string, { unit: LayoutUnit; index: number }>();
  for (const unit of units) unit.members.forEach((m, index) => unitOf.set(m, { unit, index }));
  const centre = (id: string) => memberX(unitOf.get(id)!.index) + PERSON_WIDTH / 2;

  const ports = new Map<string, { id: string; x: number; y: number; side: string }[]>(
    units.map((u) => [
      u.id,
      u.members.map((m, i) => ({
        id: `${u.id}:in:${m}`,
        x: memberX(i) + PERSON_WIDTH / 2,
        y: 0,
        side: "NORTH",
      })),
    ]),
  );
  const anchors = new Map<string, { unitId: string; x: number }>();
  const edges: ElkExtendedEdge[] = [];
  for (const f of families) {
    // Parents grouped by unit; a couple in one unit shares one port between them.
    const byUnit = new Map<string, string[]>();
    for (const p of f.parents) {
      const u = unitOf.get(p)!.unit.id;
      byUnit.set(u, [...(byUnit.get(u) ?? []), p]);
    }
    const outPorts: string[] = [];
    let lowest: { unitId: string; x: number; gen: number } | null = null;
    for (const [unitId, members] of byUnit) {
      const xs = members.map(centre);
      const x = (Math.min(...xs) + Math.max(...xs)) / 2;
      const portId = `${unitId}:out:${f.id}`;
      ports.get(unitId)!.push({ id: portId, x, y: PERSON_HEIGHT, side: "SOUTH" });
      outPorts.push(portId);
      const g = gen.get(members[0]!) ?? 0;
      if (!lowest || g > lowest.gen || (g === lowest.gen && members.length > 1))
        lowest = { unitId, x, gen: g };
    }
    if (lowest) anchors.set(f.id, { unitId: lowest.unitId, x: lowest.x });
    for (const c of f.children) {
      const target = `${unitOf.get(c.id)!.unit.id}:in:${c.id}`;
      for (const source of outPorts)
        edges.push({ id: `${source}->${c.id}`, sources: [source], targets: [target] });
    }
  }

  const elk: ElkNode = {
    id: "root",
    layoutOptions: {
      "elk.algorithm": "layered",
      "elk.direction": "DOWN",
      // Rows come from the generations (input y), not from ELK's own layering.
      "elk.layered.layering.strategy": "INTERACTIVE",
      "elk.spacing.nodeNode": String(UNIT_GAP),
      "elk.layered.spacing.nodeNodeBetweenLayers": String(ROW_GAP),
      "elk.layered.nodePlacement.strategy": "NETWORK_SIMPLEX",
      "elk.layered.considerModelOrder.strategy": "NODES_AND_EDGES",
      "elk.edgeRouting": "POLYLINE",
      "elk.separateConnectedComponents": "true",
      "elk.spacing.componentComponent": "80",
    },
    children: units.map((u) => ({
      id: u.id,
      x: 0,
      y: (gen.get(u.members[0]!) ?? 0) * (PERSON_HEIGHT + ROW_GAP),
      width: unitWidth(u),
      height: PERSON_HEIGHT,
      layoutOptions: { "elk.portConstraints": "FIXED_POS" },
      ports: ports.get(u.id)!.map((p) => ({
        id: p.id,
        x: p.x,
        y: p.y,
        width: 0,
        height: 0,
        layoutOptions: { "elk.port.side": p.side },
      })),
    })),
    edges,
  };
  return { elk, units, anchors, families };
}

export type Positions = Record<string, { x: number; y: number }>;

/**
 * Person and family-junction positions (top-left corners) from the laid-out units.
 *
 * The tree grows upwards like a real one: ELK lays it out top-down, then rows are mirrored so
 * the oldest generation stands at the bottom and descendants branch out above it.
 */
export function expandLayout(result: ElkNode, graph: LayoutGraph): Positions {
  const placed = new Map((result.children ?? []).map((c) => [c.id, c]));
  const bottom = Math.max(0, ...[...placed.values()].map((c) => c.y ?? 0));
  const flip = (y: number) => bottom - y;
  const out: Positions = {};
  for (const unit of graph.units) {
    const box = placed.get(unit.id);
    if (!box) continue;
    unit.members.forEach((m, i) => {
      out[m] = { x: (box.x ?? 0) + memberX(i), y: flip(box.y ?? 0) };
    });
  }
  for (const f of graph.families) {
    const anchor = graph.anchors.get(f.id);
    const box = anchor && placed.get(anchor.unitId);
    if (!anchor || !box) continue;
    out[f.id] = {
      x: (box.x ?? 0) + anchor.x - FAMILY_SIZE / 2,
      y: junctionY(
        flip(box.y ?? 0),
        f.children.map((c) => out[c.id]?.y).filter((y): y is number => y !== undefined),
      ),
    };
  }
  return out;
}

/**
 * Where a family junction sits: above its parents' row (the tree grows upwards), halfway to
 * the nearest row of children; just above a childless couple.
 */
export function junctionY(parentTop: number, childTops: number[]): number {
  const nearest = childTops.length ? Math.max(...childTops) + PERSON_HEIGHT : null;
  const mid = nearest !== null ? (parentTop + nearest) / 2 : parentTop - 24;
  return Math.max(mid, parentTop - ROW_GAP / 2) - FAMILY_SIZE / 2;
}

/** For focus mode: does this person have relatives that are not currently shown? */
export function hiddenRelatives(
  rel: Relations,
  id: string,
  included: Set<string>,
): { up: boolean; down: boolean } {
  return {
    up: (rel.parents.get(id) ?? []).some((e) => !included.has(e.parent_id)),
    down: (rel.children.get(id) ?? []).some((e) => !included.has(e.child_id)),
  };
}

/** A person's own line: all ancestors, all descendants, and the partners of the person and
 * of the descendants. Siblings, cousins and in-laws' families stay out. */
export function lineage(rel: Relations, id: string): Set<string> {
  const out = new Set<string>([id]);
  for (const p of rel.partners.get(id) ?? []) out.add(p);
  const walk = (start: string, next: (x: string) => string[]) => {
    const queue = [start];
    while (queue.length) {
      for (const n of next(queue.shift()!)) {
        if (!out.has(n)) {
          out.add(n);
          queue.push(n);
        }
      }
    }
  };
  walk(id, (x) => (rel.parents.get(x) ?? []).map((e) => e.parent_id));
  // Descendants: not through the ancestors already added, so siblings stay unlit.
  const down = new Set<string>([id]);
  const queue = [id];
  while (queue.length) {
    for (const e of rel.children.get(queue.shift()!) ?? []) {
      if (!down.has(e.child_id)) {
        down.add(e.child_id);
        out.add(e.child_id);
        // Their partners too, so each couple's branch stays lit.
        for (const p of rel.partners.get(e.child_id) ?? []) out.add(p);
        queue.push(e.child_id);
      }
    }
  }
  return out;
}

const ROMAN: [number, string][] = [
  [10, "X"],
  [9, "IX"],
  [5, "V"],
  [4, "IV"],
  [1, "I"],
];

export function roman(n: number): string {
  let out = "";
  for (const [v, s] of ROMAN) {
    while (n >= v) {
      out += s;
      n -= v;
    }
  }
  return out;
}

/** What moves together when a card is dragged: the person, their partners, and all their
 * descendants with the descendants' partners and co-parents (the branch growing from them). */
export function branch(rel: Relations, id: string): Set<string> {
  const out = new Set<string>([id]);
  const visited = new Set<string>([id]); // people whose children have been followed
  const queue = [id];
  while (queue.length) {
    const cur = queue.shift()!;
    for (const p of rel.partners.get(cur) ?? []) out.add(p);
    for (const e of rel.children.get(cur) ?? []) {
      // The child's other parent belongs to this couple's family too, even without a
      // recorded partnership.
      for (const co of rel.parents.get(e.child_id) ?? []) out.add(co.parent_id);
      out.add(e.child_id);
      if (!visited.has(e.child_id)) {
        visited.add(e.child_id);
        queue.push(e.child_id);
      }
    }
  }
  return out;
}
