import { describe, expect, it } from "vitest";

import type { TreeGraph } from "@/lib/genealogy";

import {
  buildFamilies,
  defaultFocus,
  focusSet,
  hiddenRelatives,
  indexRelations,
  toElkGraph,
} from "./familyGraph";
import { computeLayout } from "./layout";

const person = (id: string) => ({
  id,
  display_name: id,
  gender: "unknown" as const,
  is_living: false,
  birth: null,
  death: null,
  birth_place: null,
  primary_photo_id: null,
});

/*
 *   gp1 ⚭ gp2        gp3
 *      |              |
 *     dad    ⚭       mom      dad also has `half` with `other`
 *        |                    |
 *      kid1, kid2           (half)
 *        |
 *      grandkid
 */
const graph: TreeGraph = {
  persons: ["gp1", "gp2", "gp3", "dad", "mom", "other", "kid1", "kid2", "half", "grandkid"].map(
    person,
  ),
  parent_child: [
    ["gp1", "dad"],
    ["gp2", "dad"],
    ["gp3", "mom"],
    ["dad", "kid1"],
    ["mom", "kid1"],
    ["dad", "kid2"],
    ["mom", "kid2"],
    ["dad", "half"],
    ["other", "half"],
    ["kid1", "grandkid"],
  ].map(([parent_id, child_id], i) => ({
    id: `e${i}`,
    parent_id: parent_id as string,
    child_id: child_id as string,
    type:
      child_id === "kid2" && parent_id === "dad" ? ("adoptive" as const) : ("biological" as const),
  })),
  partnerships: [
    {
      id: "p1",
      person_a_id: "gp1",
      person_b_id: "gp2",
      type: "marriage",
      start_date: null,
      end_date: null,
    },
    {
      id: "p2",
      person_a_id: "dad",
      person_b_id: "mom",
      type: "marriage",
      start_date: null,
      end_date: null,
    },
    {
      id: "p3",
      person_a_id: "kid2",
      person_b_id: "gp3",
      type: "marriage",
      start_date: null,
      end_date: null,
    },
  ],
};

describe("family graph", () => {
  const rel = indexRelations(graph);
  const all = new Set(graph.persons.map((p) => p.id));

  it("groups children by parent set and keeps childless couples", () => {
    const families = buildFamilies(graph, all);
    const byParents = Object.fromEntries(families.map((f) => [[...f.parents].sort().join("+"), f]));
    expect(byParents["dad+mom"]?.children.map((c) => c.id)).toEqual(["kid1", "kid2"]);
    expect(byParents["dad+mom"]?.partnershipId).toBe("p2");
    expect(byParents["dad+mom"]?.children.find((c) => c.id === "kid2")?.type).toBe("adoptive");
    expect(byParents["dad+other"]?.partnershipId).toBeNull();
    expect(byParents["gp3"]?.children.map((c) => c.id)).toEqual(["mom"]);
    expect(byParents["gp3+kid2"]?.children).toEqual([]);
    expect(families).toHaveLength(6);
  });

  it("computes focus sets", () => {
    const f = focusSet(rel, "kid1", 1, 1);
    expect([...f].sort()).toEqual(["dad", "grandkid", "half", "kid1", "kid2", "mom"].sort());
    expect([...focusSet(rel, "kid1", 0, 0)]).toEqual(["kid1"]);
    const deep = focusSet(rel, "dad", 1, 2);
    expect(deep.has("grandkid")).toBe(true);
    expect(deep.has("gp3")).toBe(true); // partner of descendant kid2
    expect(deep.has("gp1")).toBe(true);
  });

  it("flags hidden relatives", () => {
    const f = focusSet(rel, "kid1", 1, 0);
    expect(hiddenRelatives(rel, "dad", f)).toEqual({ up: true, down: false });
    expect(hiddenRelatives(rel, "kid1", f)).toEqual({ up: false, down: true });
  });

  it("picks the root ancestor with most descendants as default focus", () => {
    expect(["gp1", "gp2"]).toContain(defaultFocus(graph, rel));
    expect(
      defaultFocus(
        { persons: [], parent_child: [], partnerships: [] },
        indexRelations({ persons: [], parent_child: [], partnerships: [] }),
      ),
    ).toBeNull();
  });

  it("lays out generations top to bottom", async () => {
    const families = buildFamilies(graph, all);
    const elk = toElkGraph([...all], families);
    expect(elk.edges).toHaveLength(
      families.reduce((n, f) => n + f.parents.length + f.children.length, 0),
    );
    const pos = await computeLayout(elk);
    const y = (id: string) => pos[id]?.y ?? NaN;
    expect(y("gp1")).toBeLessThan(y("dad"));
    expect(y("dad")).toBeLessThan(y("kid1"));
    expect(y("kid1")).toBeLessThan(y("grandkid"));
  });
});
