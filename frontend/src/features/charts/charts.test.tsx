import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";

import i18n from "@/i18n";
import type { PersonSummary } from "@/lib/genealogy";
import { renderWithProviders } from "@/test/render";

import type { Lineage } from "./api";
import { DescendancyList } from "./DescendancyList";
import { descendancy, lineToRoot, pedigreeSlots } from "./lineage";

beforeEach(async () => {
  await i18n.changeLanguage("uk");
});

const person = (
  id: string,
  gender: PersonSummary["gender"],
  year: number | null,
  living = false,
): PersonSummary => ({
  id,
  display_name: id,
  gender,
  is_living: living,
  birth: year
    ? {
        year,
        month: null,
        day: null,
        precision: "year",
        end_year: null,
        end_month: null,
        end_day: null,
        phrase: null,
        text: String(year),
        sort: `${year}-01-01`,
      }
    : null,
  death: null,
  birth_place: null,
  primary_photo_id: null,
});

/** Stepan ⚭ Paraska → Ivan (1905), Maria (1903); Ivan ⚭ Halyna → Petro (1935), Olena (1931);
 * Maria → Taras (1930). */
const FAMILY: Lineage = {
  root_id: "Stepan",
  direction: "descendants",
  depth: 8,
  persons: [
    person("Stepan", "male", 1880),
    person("Paraska", "female", 1882),
    person("Ivan", "male", 1905),
    person("Maria", "female", 1903),
    person("Halyna", "female", 1908),
    person("Petro", "male", 1935),
    person("Olena", "female", 1931),
    person("Taras", "male", 1930, true),
  ],
  parent_links: [
    ["Stepan", "Ivan"],
    ["Paraska", "Ivan"],
    ["Stepan", "Maria"],
    ["Paraska", "Maria"],
    ["Ivan", "Petro"],
    ["Halyna", "Petro"],
    ["Ivan", "Olena"],
    ["Halyna", "Olena"],
    ["Maria", "Taras"],
  ].map(([parent_id, child_id]) => ({
    parent_id: parent_id!,
    child_id: child_id!,
    type: "biological",
  })),
  partnerships: [
    { id: "p1", person_a_id: "Stepan", person_b_id: "Paraska", type: "marriage", year: 1902 },
    { id: "p2", person_a_id: "Ivan", person_b_id: "Halyna", type: "marriage", year: 1929 },
  ],
  repeated: [],
  truncated: false,
};

describe("descendancy (d'Aboville numbering)", () => {
  it("numbers three generations by birth order", () => {
    const root = descendancy(FAMILY)!;
    renderWithProviders(
      <DescendancyList root={root} personLink={(id) => `/p/${id}`} namesOnly={false} />,
    );
    const numbered = screen
      .getAllByTestId("descendant")
      .map((li) => `${li.dataset.number} ${li.querySelector("a")!.textContent}`);
    expect(numbered).toEqual([
      "1 Stepan",
      "1.1 Maria",
      "1.1.1 Taras",
      "1.2 Ivan",
      "1.2.1 Olena",
      "1.2.2 Petro",
    ]);
    // Partners inline with the year of marriage.
    expect(screen.getAllByTestId("descendant")[0]).toHaveTextContent("⚭ 1902 Paraska");
  });

  it("folds a generation and can show living people as names only", async () => {
    const root = descendancy(FAMILY)!;
    const { unmount } = renderWithProviders(
      <DescendancyList root={root} personLink={(id) => `/p/${id}`} namesOnly={false} />,
    );
    expect(screen.getByText("(1930)")).toBeInTheDocument();
    unmount();
    renderWithProviders(<DescendancyList root={root} personLink={(id) => `/p/${id}`} namesOnly />);
    expect(screen.queryByText("(1930)")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Згорнути: Ivan" }));
    expect(screen.queryByText("Petro")).not.toBeInTheDocument();
  });
});

describe("pedigree slots", () => {
  it("places fathers on even and mothers on odd slots and marks repeated ancestors", () => {
    const lineage: Lineage = {
      ...FAMILY,
      root_id: "Kid",
      direction: "ancestors",
      persons: [
        person("Kid", "female", 1972),
        person("Petro", "male", 1935),
        person("Hanna", "female", 1938),
        person("Ivan", "male", 1905),
        person("Maria", "female", 1908),
        person("Stepan", "male", 1880),
        person("Paraska", "female", 1882),
      ],
      parent_links: [
        { parent_id: "Hanna", child_id: "Kid", type: "biological" },
        { parent_id: "Petro", child_id: "Kid", type: "adoptive" },
        { parent_id: "Ivan", child_id: "Petro", type: "biological" },
        { parent_id: "Maria", child_id: "Hanna", type: "biological" },
        { parent_id: "Stepan", child_id: "Ivan", type: "biological" },
        { parent_id: "Paraska", child_id: "Ivan", type: "biological" },
        { parent_id: "Stepan", child_id: "Maria", type: "biological" },
        { parent_id: "Paraska", child_id: "Maria", type: "biological" },
      ],
      partnerships: [],
    };
    const slots = pedigreeSlots(lineage, 4);
    const at = (n: number) => slots[n - 1]!;
    expect(slots).toHaveLength(15);
    expect([at(2).person?.id, at(2).link, at(2).line]).toEqual(["Petro", "adoptive", "paternal"]);
    expect([at(3).person?.id, at(3).line]).toEqual(["Hanna", "maternal"]);
    expect(at(5).person).toBeNull(); // Petro's mother is unknown
    expect([at(8).person?.id, at(8).repeat]).toEqual(["Stepan", false]);
    // Maria (slot 7) is the daughter of the same couple: drawn again, marked.
    expect([at(14).person?.id, at(14).repeat, at(15).repeat]).toEqual(["Stepan", true, true]);
    expect(lineToRoot(14)).toEqual([14, 7, 3, 1]);
  });
});
