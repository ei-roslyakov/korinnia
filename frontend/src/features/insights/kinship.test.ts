import { describe, expect, it } from "vitest";

import type { Gender, PersonSummary, Relationship } from "@/lib/genealogy";

import { kinshipTerm, ukGenitive } from "./kinship";

const person = (gender: Gender, name = "X"): PersonSummary => ({
  id: name,
  display_name: name,
  gender,
  is_living: false,
  birth: null,
  death: null,
  birth_place: null,
  primary_photo_id: null,
  avatar_url: null,
});

function rel(
  up: number | null,
  down: number | null,
  b: Gender,
  extra: Partial<Relationship> & { pathGenders?: Gender[] } = {},
): Relationship {
  const { pathGenders = [], ...rest } = extra;
  return {
    a: person("male", "A"),
    b: person(b, "B"),
    kind: "blood",
    up,
    down,
    half: false,
    non_biological: false,
    side: null,
    via: null,
    common_ancestors: [],
    path: pathGenders.map((g, i) => ({ person: person(g, `p${i}`), edge: i ? "parent" : null })),
    ...rest,
  };
}

const terms = (r: Relationship) => ["uk", "en", "pl"].map((l) => kinshipTerm(r, l));

describe("kinship terms: blood", () => {
  it.each([
    [1, 0, "male", ["батько", "father", "ojciec"]],
    [2, 0, "female", ["баба", "grandmother", "babcia"]],
    [3, 0, "male", ["прадід", "great-grandfather", "pradziadek"]],
    [5, 0, "male", ["прапрапрадід", "3× great-grandfather", "praprapradziadek"]],
    [0, 1, "female", ["донька", "daughter", "córka"]],
    [0, 2, "male", ["онук", "grandson", "wnuk"]],
    [0, 3, "female", ["правнучка", "great-granddaughter", "prawnuczka"]],
    [1, 1, "male", ["брат", "brother", "brat"]],
    [2, 1, "female", ["тітка", "aunt", "ciocia"]],
    [2, 2, "male", ["двоюрідний брат", "first cousin", "kuzyn"]],
    [2, 2, "female", ["двоюрідна сестра", "first cousin", "kuzynka"]],
    [3, 3, "female", ["троюрідна сестра", "second cousin", "kuzynka 2. stopnia"]],
    [
      3,
      2,
      "male",
      ["двоюрідний дядько", "first cousin once removed", "kuzyn, o 1 pokolenie starszy"],
    ],
    [
      2,
      3,
      "female",
      ["двоюрідна племінниця", "first cousin once removed", "kuzynka, o 1 pokolenie młodsza"],
    ],
    [5, 5, "male", ["п'ятиюрідний брат", "fourth cousin", "kuzyn 4. stopnia"]],
    [
      2,
      4,
      "male",
      ["троюрідний онук", "first cousin twice removed", "kuzyn, o 2 pokolenia młodszy"],
    ],
  ] as const)("(%i up, %i down, %s)", (up, down, g, expected) => {
    expect(terms(rel(up, down, g))).toEqual(expected);
  });

  it("names grand-uncles and grand-nephews", () => {
    // a → parent → grandparent → great-grandparent (common) → b
    const r = rel(3, 1, "male", { pathGenders: ["male", "male", "female", "male", "male"] });
    expect(terms(r)).toEqual(["двоюрідний дід", "great-uncle", "brat babci"]);
    const n = rel(1, 3, "female", { pathGenders: ["male", "male", "female", "male", "female"] });
    expect(terms(n)).toEqual(["двоюрідна онука", "great-niece", "wnuczka siostry"]);
    const nephew = rel(1, 2, "male", { pathGenders: ["male", "male", "male", "male"] });
    expect(kinshipTerm(nephew, "pl")).toBe("bratanek");
    expect(kinshipTerm(nephew, "uk")).toBe("племінник");
  });

  it("marks half relations", () => {
    const sharedFather = rel(1, 1, "female", {
      half: true,
      pathGenders: ["male", "male", "female"],
    });
    expect(terms(sharedFather)).toEqual([
      "єдинокровна сестра",
      "half-sister",
      "przyrodnia siostra",
    ]);
    const sharedMother = rel(1, 1, "male", { half: true, pathGenders: ["male", "female", "male"] });
    expect(kinshipTerm(sharedMother, "uk")).toBe("єдиноутробний брат");
    const cousin = rel(2, 2, "male", { half: true });
    expect(terms(cousin)).toEqual([
      "двоюрідний брат (по одному з батьків)",
      "half first cousin",
      "przyrodni kuzyn",
    ]);
  });

  it("joins both forms when the gender is unknown", () => {
    expect(terms(rel(1, 1, "unknown"))).toEqual([
      "брат / сестра",
      "brother / sister",
      "brat / siostra",
    ]);
    expect(terms(rel(2, 2, "other"))).toEqual([
      "двоюрідний брат / двоюрідна сестра",
      "first cousin",
      "kuzyn / kuzynka",
    ]);
  });
});

describe("kinship terms: partners and in-laws", () => {
  const inLaw = (
    side: "partner_relative" | "relative_partner",
    up: number,
    down: number,
    a: Gender,
    b: Gender,
    via: Gender,
  ) =>
    rel(up, down, b, {
      kind: "in_law",
      side,
      a: person(a, "A"),
      via: person(via, "V"),
      pathGenders: [a, via, b, b, b],
    });

  it("partner, same person, distant and none", () => {
    expect(terms(rel(null, null, "female", { kind: "partner" }))).toEqual([
      "дружина",
      "wife",
      "żona",
    ]);
    expect(kinshipTerm(rel(0, 0, "male", { kind: "same" }), "en")).toBe("the same person");
    expect(kinshipTerm(rel(null, null, "male", { kind: "distant" }), "uk")).toBe("далекий родич");
    expect(kinshipTerm(rel(null, null, "male", { kind: "none" }), "pl")).toBe(
      "nie znaleziono pokrewieństwa",
    );
  });

  it("relatives of the partner", () => {
    expect(terms(inLaw("partner_relative", 1, 0, "male", "female", "female"))).toEqual([
      "теща",
      "mother-in-law",
      "teściowa",
    ]);
    expect(terms(inLaw("partner_relative", 1, 0, "female", "male", "male"))).toEqual([
      "свекор",
      "father-in-law",
      "teść",
    ]);
    expect(terms(inLaw("partner_relative", 1, 1, "male", "male", "female"))).toEqual([
      "шурин",
      "brother-in-law",
      "szwagier",
    ]);
    expect(kinshipTerm(inLaw("partner_relative", 1, 1, "female", "female", "male"), "uk")).toBe(
      "зовиця",
    );
    expect(terms(inLaw("partner_relative", 0, 1, "male", "female", "female"))).toEqual([
      "падчерка",
      "stepdaughter",
      "pasierbica",
    ]);
    expect(terms(inLaw("partner_relative", 2, 2, "male", "male", "female"))).toEqual([
      "двоюрідний брат дружини",
      "wife's first cousin",
      "kuzyn żony",
    ]);
  });

  it("partners of relatives", () => {
    expect(terms(inLaw("relative_partner", 0, 1, "male", "female", "male"))).toEqual([
      "невістка",
      "daughter-in-law",
      "synowa",
    ]);
    expect(terms(inLaw("relative_partner", 1, 1, "male", "female", "male"))).toEqual([
      "невістка",
      "sister-in-law",
      "bratowa",
    ]);
    expect(terms(inLaw("relative_partner", 1, 0, "male", "male", "female"))).toEqual([
      "вітчим",
      "stepfather",
      "ojczym",
    ]);
    expect(terms(inLaw("relative_partner", 2, 1, "male", "female", "male"))).toEqual([
      "тітка",
      "aunt",
      "ciocia",
    ]);
    expect(terms(inLaw("relative_partner", 0, 2, "male", "female", "male"))).toEqual([
      "дружина онука",
      "grandson's wife",
      "żona wnuka",
    ]);
    expect(kinshipTerm(inLaw("relative_partner", 2, 2, "male", "female", "male"), "uk")).toBe(
      "дружина двоюрідного брата",
    );
  });
});

describe("ukGenitive", () => {
  it.each([
    ["двоюрідна сестра", "двоюрідної сестри"],
    ["прадід", "прадіда"],
    ["онука", "онуки"],
    ["правнучка", "правнучки"],
    ["троюрідний племінник", "троюрідного племінника"],
    ["брат / сестра", null],
    ["шурин", null],
  ])("%s → %s", (nom, gen) => {
    expect(ukGenitive(nom)).toBe(gen);
  });

  it("falls back to English for other languages", () => {
    expect(kinshipTerm(rel(1, 0, "male"), "de")).toBe("father");
  });
});
