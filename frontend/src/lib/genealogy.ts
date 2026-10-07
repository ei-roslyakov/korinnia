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
  avatar_url?: string | null;
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
  /** Manual card nudges relative to the automatic layout (builder mode). */
  layout_offsets?: Record<string, { dx: number; dy: number }>;
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
  primary_photo_crop: Region | null;
  avatar_url: string | null;
  /** The cropped portrait is still being rendered (avatar_url is a temporary fallback). */
  portrait_pending: boolean;
  media: MediaItem[];
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
  citations: Citation[];
  stories: StorySummary[];
  open_questions: OpenQuestion[];
}

export interface HistoricalName {
  name: string;
  from_year?: number | null;
  until_year?: number | null;
  note?: string | null;
}

export interface Place extends PlaceSummary {
  historical_names: HistoricalName[];
  notes: string | null;
}

/** Request shape of a partial date (backend PartialDateIn). */
export interface PartialDateInput {
  year?: number | null;
  month?: number | null;
  day?: number | null;
  precision?: DatePrecision | null;
  end_year?: number | null;
  end_month?: number | null;
  end_day?: number | null;
  phrase?: string | null;
}

export type RelativeRelation = "parent" | "child" | "partner" | "sibling";

export interface DeletePreview {
  person: PersonSummary;
  parent_links: number;
  child_links: number;
  partnerships: number;
  events: number;
  shared_events: number;
}

export interface TrashItem {
  entity_type: "person" | "place" | "event" | "parent_child" | "partnership";
  entity_id: string;
  label: string;
  deleted_at: string;
  deleted_by: string | null;
  batch_size: number;
}

export const EVENT_TYPES = [
  "birth",
  "baptism",
  "death",
  "burial",
  "marriage",
  "divorce",
  "education",
  "graduation",
  "military_service",
  "occupation",
  "residence",
  "emigration",
  "immigration",
  "award",
  "illness",
  "custom",
] as const;
export const PARTICIPANT_ROLES = [
  "principal",
  "spouse",
  "witness",
  "godparent",
  "officiant",
  "other",
] as const;
export const PARENT_CHILD_TYPES: ParentChildType[] = [
  "biological",
  "adoptive",
  "step",
  "foster",
  "unknown",
];
export const PARTNERSHIP_TYPES: PartnershipType[] = ["marriage", "civil_union", "partnership"];
export const END_REASONS = ["divorce", "death", "separation", "other"] as const;
export const GENDERS: Gender[] = ["female", "male", "other", "unknown"];
export const NAME_TYPES = ["birth", "married", "nickname", "alias", "religious", "other"] as const;
export const SCRIPTS = ["cyrillic", "latin", "other"] as const;

export type MediaKind = "photo" | "document_scan" | "audio" | "video" | "pdf" | "other";

/** Rectangle as fractions (0..1) of the image size. */
export interface Region {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface MediaItem {
  id: string;
  kind: MediaKind;
  title: string | null;
  description: string | null;
  date: PartialDate | null;
  place: PlaceSummary | null;
  original_filename: string;
  mime_type: string;
  size: number;
  sha256: string;
  width: number | null;
  height: number | null;
  duration_seconds: number | null;
  processing_status: "pending" | "ready" | "failed";
  processing_error: string | null;
  urls: { original: string; web: string; thumb: string | null };
  people: { person_id: string; display_name: string; region: Region | null }[];
  created_at: string;
}

export const isVisual = (m: MediaItem) => m.kind === "photo" || m.kind === "document_scan";

// --- Sources, stories, collaboration --------------------------------------------------------

export const SOURCE_TYPES = [
  "civil_record",
  "church_record",
  "archive_document",
  "census",
  "newspaper",
  "letter",
  "oral_history",
  "book",
  "website",
  "other",
] as const;
export type SourceType = (typeof SOURCE_TYPES)[number];
export const CITATION_QUALITIES = [
  "primary",
  "secondary",
  "family_tradition",
  "unverified",
] as const;
export type CitationQuality = (typeof CITATION_QUALITIES)[number];
export type CitedEntity =
  "person" | "person_name" | "event" | "parent_child" | "partnership" | "media";

export interface SourceSummary {
  id: string;
  title: string;
  type: SourceType;
}

export interface Source extends SourceSummary {
  author: string | null;
  archive_name: string | null;
  reference_number: string | null;
  url: string | null;
  notes: string | null;
  media: MediaItem[];
  citation_count: number;
  created_at: string;
  updated_at: string;
}

export interface Citation {
  id: string;
  source: SourceSummary;
  target: {
    entity_type: CitedEntity;
    entity_id: string;
    event_type: string | null;
    date: string | null;
    label: string | null;
  };
  field: string | null;
  page: string | null;
  quality: CitationQuality;
  notes: string | null;
  created_at: string;
}

export type StoryStatus = "draft" | "pending_review" | "published";
export interface UserRef {
  id: string;
  display_name: string;
}

export interface StorySummary {
  id: string;
  title: string;
  excerpt: string;
  narrator: string | null;
  date: PartialDate | null;
  status: StoryStatus;
  author: UserRef | null;
  person_ids: string[];
  updated_at: string;
}

export interface Story extends StorySummary {
  body: string;
  persons: PersonSummary[];
  media: MediaItem[];
  review_comment: string | null;
  can_edit: boolean;
  created_at: string;
}

export interface Suggestion {
  id: string;
  entity_type: "person" | "event";
  entity_id: string;
  entity_label: string;
  patch: Record<string, unknown>;
  current: Record<string, unknown>;
  comment: string | null;
  status: "pending" | "approved" | "rejected";
  author: UserRef | null;
  reviewer: UserRef | null;
  review_comment: string | null;
  reviewed_at: string | null;
  created_at: string;
}

export interface CommentItem {
  id: string;
  entity_type: "person" | "story" | "media";
  entity_id: string;
  body: string;
  author: UserRef | null;
  created_at: string;
  updated_at: string;
}

export interface OpenQuestion {
  id: string;
  person_id: string;
  person_name: string;
  question: string;
  notes: string | null;
  status: "open" | "resolved";
  resolution: string | null;
  resolved_at: string | null;
  created_by: UserRef | null;
  created_at: string;
}

export interface DataQuality {
  counts: Record<string, number>;
  missing_birth: PersonSummary[];
  missing_photo: PersonSummary[];
  without_sources: PersonSummary[];
  date_problems: { person: PersonSummary; warnings: DataWarning[] }[];
  open_questions: OpenQuestion[];
}

// --- Phase 8: timeline, map, on this day, kinship, statistics --------------------------------

export type FactKind = "event" | "partnership_start" | "partnership_end";

export interface FactPerson {
  id: string;
  display_name: string;
  role: string;
}

/** An event, or the start / end of a partnership (type: marriage, civil_union, divorce…). */
export interface Fact {
  kind: FactKind;
  id: string;
  type: string;
  title: string | null;
  date: PartialDate | null;
  place: PlaceSummary | null;
  latitude: string | null;
  longitude: string | null;
  cemetery_name: string | null;
  persons: FactPerson[];
}

export interface TimelinePage {
  items: Fact[];
  total: number;
  limit: number;
  offset: number;
  undated: number;
}

export interface Anniversary {
  on: string;
  years: number;
  fact: Fact;
}

export interface OnThisDay {
  start: string;
  days: number;
  items: Anniversary[];
}

export interface MapPoint {
  latitude: string;
  longitude: string;
  label: string;
  place_id: string | null;
  facts: Fact[];
}

export interface MapData {
  points: MapPoint[];
  unplaced: number;
  places_without_coordinates: PlaceSummary[];
}

export type KinshipEdge = "parent" | "child" | "partner";
export type KinshipKind = "same" | "blood" | "partner" | "in_law" | "distant" | "none";

export interface PathStep {
  person: PersonSummary;
  edge: KinshipEdge | null;
}

export interface Relationship {
  a: PersonSummary;
  b: PersonSummary;
  kind: KinshipKind;
  up: number | null;
  down: number | null;
  half: boolean;
  non_biological: boolean;
  side: "partner_relative" | "relative_partner" | null;
  via: PersonSummary | null;
  common_ancestors: PersonSummary[];
  path: PathStep[];
}

export interface NameCount {
  name: string;
  count: number;
  variants: string[];
}

export interface TreeStats {
  persons: number;
  male: number;
  female: number;
  other_gender: number;
  living: number;
  deceased: number;
  generations: number;
  partnerships: number;
  places: number;
  events: number;
  media: number;
  sources: number;
  stories: number;
  earliest_year: number | null;
  latest_year: number | null;
  oldest_ancestor: { person: PersonSummary; years: number | null } | null;
  longest_lived: { person: PersonSummary; years: number | null } | null;
  average_lifespan: number | null;
  lifespan_sample: number;
  surnames: NameCount[];
  first_names: NameCount[];
  by_decade: { decade: number; births: number; deaths: number }[];
}

/** Fact types grouped for filters (timeline and map). */
export const FACT_CATEGORIES = {
  birth: ["birth", "baptism"],
  family: ["marriage", "civil_union", "partnership", "divorce", "separation", "partnership_end"],
  life: [
    "education",
    "graduation",
    "military_service",
    "occupation",
    "residence",
    "award",
    "illness",
    "custom",
  ],
  migration: ["emigration", "immigration"],
  death: ["death", "burial"],
} as const;
export type FactCategory = keyof typeof FACT_CATEGORIES;
export const factCategory = (type: string): FactCategory =>
  (Object.keys(FACT_CATEGORIES) as FactCategory[]).find((c) =>
    (FACT_CATEGORIES[c] as readonly string[]).includes(type),
  ) ?? "life";
