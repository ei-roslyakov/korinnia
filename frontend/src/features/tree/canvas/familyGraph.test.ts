import { describe, expect, it } from "vitest";

import type { TreeGraph } from "@/lib/genealogy";

import {
  FAMILY_SIZE,
  PARTNER_GAP,
  PERSON_HEIGHT,
  PERSON_WIDTH,
  ROW_GAP,
  buildFamilies,
  buildUnits,
  defaultFocus,
  focusSet,
  generations,
  hiddenRelatives,
  indexRelations,
  junctionY,
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

  it("assigns generations: partners share a row, children sit below every parent", () => {
    const families = buildFamilies(graph, all);
    const gen = generations([...all], families);
    expect(["gp1", "gp2", "gp3"].map((id) => gen.get(id))).toEqual([0, 0, 0]);
    expect(["dad", "mom", "other"].map((id) => gen.get(id))).toEqual([1, 1, 1]);
    expect(["kid1", "kid2", "half"].map((id) => gen.get(id))).toEqual([2, 2, 2]);
    expect(gen.get("grandkid")).toBe(3);
  });

  it("places junctions above the parents, just above a childless couple", () => {
    const childRow = 500 - ROW_GAP - PERSON_HEIGHT;
    expect(junctionY(500, [childRow])).toBe(500 - ROW_GAP / 2 - FAMILY_SIZE / 2);
    // Never further than half a row from the parents, even if the children are far above.
    expect(junctionY(500, [childRow - 400])).toBe(500 - ROW_GAP / 2 - FAMILY_SIZE / 2);
    expect(junctionY(500, [])).toBe(500 - 24 - FAMILY_SIZE / 2);
  });

  it("puts partners in one unit, a person with two partners between them", () => {
    const families = buildFamilies(graph, all);
    const units = buildUnits([...all], families, generations([...all], families));
    const unitOf = (id: string) => units.find((u) => u.members.includes(id))!.members;
    expect(unitOf("gp1")).toEqual(expect.arrayContaining(["gp1", "gp2"]));
    expect(unitOf("dad")).toHaveLength(3);
    expect(unitOf("dad")[1]).toBe("dad"); // mom and `other` on either side
    // kid2 ⚭ gp3 spans generations, so they are not merged.
    expect(unitOf("kid2")).toEqual(["kid2"]);
    expect(units.flatMap((u) => u.members).sort()).toEqual([...all].sort());
  });

  it("grows upwards: one row per generation, partners side by side", async () => {
    const families = buildFamilies(graph, all);
    const pos = await computeLayout(toElkGraph([...all], families));
    const y = (id: string) => pos[id]!.y;
    const x = (id: string) => pos[id]!.x;
    expect(new Set(["gp1", "gp2", "gp3"].map(y)).size).toBe(1);
    expect(new Set(["dad", "mom", "other"].map(y)).size).toBe(1);
    expect(y("kid1")).toBe(y("half"));
    // The oldest generation is at the bottom.
    expect(y("gp1")).toBeGreaterThan(y("dad"));
    expect(y("dad")).toBeGreaterThan(y("kid1"));
    expect(y("kid1")).toBeGreaterThan(y("grandkid"));
    // Partners are adjacent: exactly one card width plus the partner gap apart.
    expect(Math.abs(x("gp1") - x("gp2"))).toBe(PERSON_WIDTH + PARTNER_GAP);
    expect(Math.abs(x("dad") - x("mom"))).toBe(PERSON_WIDTH + PARTNER_GAP);
    // The dad+mom junction sits above them, halfway up to their children.
    const fam = families.find((f) => f.parents.includes("dad") && f.parents.includes("mom"))!;
    const j = pos[fam.id]!;
    expect(j.x + FAMILY_SIZE / 2).toBe((x("dad") + x("mom")) / 2 + PERSON_WIDTH / 2);
    expect(j.y + FAMILY_SIZE).toBeLessThan(y("dad"));
    expect(j.y).toBeGreaterThan(y("kid1") + PERSON_HEIGHT);
  });
});
