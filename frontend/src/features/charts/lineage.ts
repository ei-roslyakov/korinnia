import type { ParentChildType, PersonSummary } from "@/lib/genealogy";

import type { Lineage } from "./api";

export type Line = "root" | "paternal" | "maternal";

/** One position of a pedigree (Ahnentafel numbering: the root is 1, the father of n is 2n,
 * the mother 2n + 1). */
export interface Slot {
  n: number;
  generation: number;
  person: PersonSummary | null;
  /** How this person is the parent of the slot below (adoptive / step links are dashed). */
  link: ParentChildType | null;
  line: Line;
  /** This person already appears in a lower-numbered slot (pedigree collapse, ⟳). */
  repeat: boolean;
}

const BIOLOGICAL_FIRST: Record<ParentChildType, number> = {
  biological: 0,
  adoptive: 1,
  foster: 2,
  step: 3,
  unknown: 4,
};

/** The two parents shown for a child: father and mother, biological ones first; a parent of
 * unknown gender takes whichever place is free. */
export function parentsOf(
  lineage: Lineage,
  byId: Map<string, PersonSummary>,
  childId: string,
): [{ id: string; type: ParentChildType } | null, { id: string; type: ParentChildType } | null] {
  const links = lineage.parent_links
    .filter((l) => l.child_id === childId && byId.has(l.parent_id))
    .sort((a, b) => BIOLOGICAL_FIRST[a.type] - BIOLOGICAL_FIRST[b.type]);
  let father: { id: string; type: ParentChildType } | null = null;
  let mother: { id: string; type: ParentChildType } | null = null;
  const rest: typeof links = [];
  for (const l of links) {
    const gender = byId.get(l.parent_id)!.gender;
    if (gender === "male" && !father) father = { id: l.parent_id, type: l.type };
    else if (gender === "female" && !mother) mother = { id: l.parent_id, type: l.type };
    else rest.push(l);
  }
  for (const l of rest) {
    if (!father && l.parent_id !== mother?.id) father = { id: l.parent_id, type: l.type };
    else if (!mother && l.parent_id !== father?.id) mother = { id: l.parent_id, type: l.type };
  }
  return [father, mother];
}

/** Every slot of a pedigree of `generations` generations (the root is generation 0), empty
 * ones included, so charts can draw unknown ancestors faintly. */
export function pedigreeSlots(lineage: Lineage, generations: number): Slot[] {
  const byId = new Map(lineage.persons.map((p) => [p.id, p]));
  const slots: Slot[] = [];
  const shown = new Set<string>();
  const root = byId.get(lineage.root_id) ?? null;
  slots[1] = { n: 1, generation: 0, person: root, link: null, line: "root", repeat: false };
  if (root) shown.add(root.id);
  for (let n = 1; n < 2 ** (generations - 1); n++) {
    const child = slots[n]!;
    const generation = child.generation + 1;
    const [father, mother] =
      child.person && !child.repeat ? parentsOf(lineage, byId, child.person.id) : [null, null];
    for (const [i, parent] of [father, mother].entries()) {
      const k = 2 * n + i;
      const person = parent ? (byId.get(parent.id) ?? null) : null;
      const line: Line = n === 1 ? (i === 0 ? "paternal" : "maternal") : child.line;
      const repeat = person ? shown.has(person.id) : false;
      if (person) shown.add(person.id);
      slots[k] = { n: k, generation, person, link: parent?.type ?? null, line, repeat };
    }
  }
  return slots.slice(1);
}

/** Slots from `n` down to the root (for highlighting a line). */
export function lineToRoot(n: number): number[] {
  const out: number[] = [];
  for (let k = n; k >= 1; k = Math.floor(k / 2)) out.push(k);
  return out;
}

export interface DescendantNode {
  /** d'Aboville number: 1, 1.1, 1.2, 1.2.1 … */
  number: string;
  person: PersonSummary;
  partners: { person: PersonSummary; year: number | null }[];
  children: DescendantNode[];
}

const sortKey = (p: PersonSummary) => p.birth?.sort ?? "9999";

/** The descendants of the root as an outline numbered in the d'Aboville system: children
 * by birth date, each child under the first of its parents met on the way down. */
export function descendancy(lineage: Lineage): DescendantNode | null {
  const byId = new Map(lineage.persons.map((p) => [p.id, p]));
  const root = byId.get(lineage.root_id);
  if (!root) return null;
  const placed = new Set<string>();
  const build = (person: PersonSummary, number: string): DescendantNode => {
    placed.add(person.id);
    const partners = lineage.partnerships
      .filter((x) => x.person_a_id === person.id || x.person_b_id === person.id)
      .map((x) => ({
        person: byId.get(x.person_a_id === person.id ? x.person_b_id : x.person_a_id)!,
        year: x.year,
      }))
      .filter((x) => x.person)
      .sort((a, b) => (a.year ?? 9999) - (b.year ?? 9999));
    const children = lineage.parent_links
      .filter((l) => l.parent_id === person.id && !placed.has(l.child_id))
      .map((l) => byId.get(l.child_id))
      .filter((c): c is PersonSummary => Boolean(c))
      .sort((a, b) => sortKey(a).localeCompare(sortKey(b)));
    const unique = [...new Map(children.map((c) => [c.id, c])).values()];
    for (const c of unique) placed.add(c.id);
    return {
      number,
      person,
      partners,
      children: unique.map((c, i) => build(c, `${number}.${i + 1}`)),
    };
  };
  return build(root, "1");
}
