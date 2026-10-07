/** Types mirroring the genealogy API (backend app/schemas/{dates,persons,events,...}.py). */

export type Gender = "male" | "female" | "other" | "unknown";
export type DatePrecision =
  "exact" | "month" | "year" | "approx" | "before" | "after" | "between" | "unknown";

export interface PartialDate {
  year: number | null;
  month: number | null;
  day: number | null;
  precision: DatePrecision | null;
  end_year: number | null;
  end_month: number | null;
  end_day: number | null;
  phrase: string | null;
  text: string;
  sort: string | null;
}

export interface PlaceSummary {
  id: string;
  name: string;
  country: string | null;
  region: string | null;
  latitude: string | null;
  longitude: string | null;
}

export interface PersonSummary {
  id: string;
  display_name: string;
  gender: Gender;
  is_living: boolean;
  birth: PartialDate | null;
  death: PartialDate | null;
  birth_place: string | null;
  primary_photo_id: string | null;
}

export type ParentChildType = "biological" | "adoptive" | "step" | "foster" | "unknown";
export type PartnershipType = "marriage" | "civil_union" | "partnership";

export interface GraphEdge {
  id: string;
  parent_id: string;
  child_id: string;
  type: ParentChildType;
}

export interface GraphPartnership {
  id: string;
  person_a_id: string;
  person_b_id: string;
  type: PartnershipType;
  start_date: PartialDate | null;
  end_date: PartialDate | null;
}

export interface TreeGraph {
  persons: PersonSummary[];
  parent_child: GraphEdge[];
  partnerships: GraphPartnership[];
}

export interface PersonName {
  id: string;
  type: "birth" | "married" | "nickname" | "alias" | "religious" | "other";
  first_name: string | null;
  middle_name: string | null;
  patronymic: string | null;
  last_name: string | null;
  maiden_name: string | null;
  script: "cyrillic" | "latin" | "other";
  is_primary: boolean;
  notes: string | null;
  display: string;
}

export interface Vital {
  event_id: string;
  date: PartialDate | null;
  place: PlaceSummary | null;
  description: string | null;
}

export interface LifeEvent {
  id: string;
  type: string;
  title: string | null;
  description: string | null;
  date: PartialDate | null;
  place: PlaceSummary | null;
  cemetery_name: string | null;
  burial_plot: string | null;
  latitude: string | null;
  longitude: string | null;
  participants: { person_id: string; role: string; display_name: string }[];
}

export interface RelativeRef {
  relationship_id: string;
  type: ParentChildType;
  person: PersonSummary;
}

export interface PartnerRef {
  partnership_id: string;
  type: PartnershipType;
  start_date: PartialDate | null;
  end_date: PartialDate | null;
  end_reason: "divorce" | "death" | "separation" | "other" | null;
  person: PersonSummary;
}

export interface DataWarning {
  code: string;
  params: Record<string, unknown>;
}

export interface PersonDetail {
  id: string;
  tree_id: string;
  display_name: string;
  gender: Gender;
  is_living: boolean;
  short_summary: string | null;
  biography: string | null;
  occupation: string | null;
  education: string | null;
  religion: string | null;
  nationality: string | null;
  notes_for_descendants: string | null;
  research_status: "complete" | "partial" | "unknown";
  primary_photo_id: string | null;
  names: PersonName[];
  birth: Vital | null;
  death: Vital | null;
  events: LifeEvent[];
  parents: RelativeRef[];
  children: RelativeRef[];
  partners: PartnerRef[];
  siblings: { half: boolean; person: PersonSummary }[];
  warnings: DataWarning[];
  created_at: string;
  updated_at: string;
}
