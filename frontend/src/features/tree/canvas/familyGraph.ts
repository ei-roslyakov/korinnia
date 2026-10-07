/**
 * Pure functions turning the tree graph (people + parent/child links + partnerships) into
 * a layered layout graph for ELK, and computing "focus" subsets.
 *
 * A family tree is a graph, not a tree. We insert a small *family* node per couple (or per
 * set of co-parents): parent → family → child. ELK's layered algorithm then places each
 * generation on its own row with families in between.
 */
import type { ElkNode } from "elkjs/lib/elk-api";

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

export function toElkGraph(personIds: string[], families: Family[]): ElkNode {
  return {
    id: "root",
    layoutOptions: {
      "elk.algorithm": "layered",
      "elk.direction": "DOWN",
      "elk.spacing.nodeNode": "28",
      "elk.layered.spacing.nodeNodeBetweenLayers": "36",
      "elk.layered.nodePlacement.strategy": "NETWORK_SIMPLEX",
      "elk.layered.considerModelOrder.strategy": "NODES_AND_EDGES",
      "elk.layered.crossingMinimization.forceNodeModelOrder": "false",
      "elk.separateConnectedComponents": "true",
      "elk.spacing.componentComponent": "80",
    },
    children: [
      ...personIds.map((id) => ({ id, width: PERSON_WIDTH, height: PERSON_HEIGHT })),
      ...families.map((f) => ({ id: f.id, width: FAMILY_SIZE, height: FAMILY_SIZE })),
    ],
    edges: families.flatMap((f) => [
      ...f.parents.map((p) => ({ id: `${p}->${f.id}`, sources: [p], targets: [f.id] })),
      ...f.children.map((c) => ({ id: `${f.id}->${c.id}`, sources: [f.id], targets: [c.id] })),
    ]),
  };
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
