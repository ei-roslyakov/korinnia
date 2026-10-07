import type { PartialDate, PersonDetail, PersonSummary, TreeGraph } from "@/lib/genealogy";

export const year = (y: number, precision: PartialDate["precision"] = "year"): PartialDate => ({
  year: y,
  month: null,
  day: null,
  precision,
  end_year: null,
  end_month: null,
  end_day: null,
  phrase: null,
  text: String(y),
  sort: `${y}-01-01`,
});

export const summary = (
  id: string,
  name: string,
  extra: Partial<PersonSummary> = {},
): PersonSummary => ({
  id,
  display_name: name,
  gender: "female",
  is_living: false,
  birth: null,
  death: null,
  birth_place: null,
  primary_photo_id: null,
  ...extra,
});

export const smallGraph: TreeGraph = {
  persons: [
    summary("p1", "Йосип Шевчук", { gender: "male", birth: year(1885), death: year(1950) }),
    summary("p2", "Галина Коваленко", { birth: year(1923), death: year(2010) }),
  ],
  parent_child: [{ id: "e1", parent_id: "p1", child_id: "p2", type: "biological" }],
  partnerships: [],
};

export function bigGraph(n: number): TreeGraph {
  const persons = Array.from({ length: n }, (_, i) => summary(`b${i}`, `Person ${i}`));
  const parent_child = persons.slice(1).map((p, i) => ({
    id: `l${i}`,
    parent_id: `b${Math.floor(i / 2)}`,
    child_id: p.id,
    type: "biological" as const,
  }));
  return { persons, parent_child, partnerships: [] };
}

export const halyna: PersonDetail = {
  id: "p2",
  tree_id: "t1",
  display_name: "Галина Йосипівна Коваленко (Шевчук)",
  gender: "female",
  is_living: false,
  short_summary: "Вчителька, берегиня родинних історій.",
  biography: "## Війна\n\nУ 1944 році родина переїхала до **Львова**.",
  occupation: "Вчителька",
  education: null,
  religion: null,
  nationality: null,
  notes_for_descendants: "Зберігайте листи.",
  research_status: "complete",
  primary_photo_id: null,
  names: [
    {
      id: "n1",
      type: "married",
      first_name: "Галина",
      middle_name: null,
      patronymic: "Йосипівна",
      last_name: "Коваленко",
      maiden_name: "Шевчук",
      script: "cyrillic",
      is_primary: true,
      notes: null,
      display: "Галина Йосипівна Коваленко (Шевчук)",
    },
    {
      id: "n2",
      type: "married",
      first_name: "Halyna",
      middle_name: null,
      patronymic: null,
      last_name: "Kovalenko",
      maiden_name: null,
      script: "latin",
      is_primary: false,
      notes: null,
      display: "Halyna Kovalenko",
    },
  ],
  birth: {
    event_id: "ev1",
    date: { ...year(1923), month: 2, day: 14, precision: "exact" },
    place: {
      id: "pl1",
      name: "Івано-Франківськ",
      country: "Україна",
      region: null,
      latitude: null,
      longitude: null,
    },
    description: null,
  },
  death: { event_id: "ev2", date: year(2010), place: null, description: null },
  events: [
    {
      id: "ev3",
      type: "burial",
      title: null,
      description: null,
      date: year(2010),
      place: null,
      cemetery_name: "Байкове кладовище",
      burial_plot: "Ділянка 7",
      latitude: "50.41",
      longitude: "30.51",
      participants: [{ person_id: "p2", role: "principal", display_name: "Галина" }],
    },
    {
      id: "ev4",
      type: "residence",
      title: "Переїзд до Львова",
      description: "Після війни.",
      date: year(1944),
      place: null,
      cemetery_name: null,
      burial_plot: null,
      latitude: null,
      longitude: null,
      participants: [
        { person_id: "p2", role: "principal", display_name: "Галина" },
        { person_id: "p1", role: "other", display_name: "Йосип Шевчук" },
      ],
    },
  ],
  parents: [{ relationship_id: "e1", type: "biological", person: smallGraph.persons[0]! }],
  children: [],
  partners: [
    {
      partnership_id: "m1",
      type: "marriage",
      start_date: year(1946),
      end_date: null,
      end_reason: "death",
      person: summary("p3", "Олександр Коваленко", { gender: "male" }),
    },
  ],
  siblings: [{ half: false, person: summary("p4", "Ольга Ткачук") }],
  warnings: [{ code: "parent_too_young", params: { age: 9 } }],
  created_at: "2024-01-01T00:00:00Z",
  updated_at: "2024-01-01T00:00:00Z",
};
