import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { api, qs } from "@/lib/api";
import type { ParentChildType, PartnershipType, PersonSummary } from "@/lib/genealogy";

export type Direction = "ancestors" | "descendants";

export interface LineageLink {
  parent_id: string;
  child_id: string;
  type: ParentChildType;
}

export interface LineagePartnership {
  id: string;
  person_a_id: string;
  person_b_id: string;
  type: PartnershipType;
  year: number | null;
}

/** One person's ancestors or descendants (D118). */
export interface Lineage {
  root_id: string;
  direction: Direction;
  depth: number;
  persons: PersonSummary[];
  parent_links: LineageLink[];
  partnerships: LineagePartnership[];
  /** Ancestors reached through more than one line (pedigree collapse). */
  repeated: string[];
  truncated: boolean;
}

export function useLineage(treeId: string, personId: string, direction: Direction, depth: number) {
  return useQuery({
    queryKey: ["tree", treeId, "lineage", personId, direction, depth],
    queryFn: () =>
      api.get<Lineage>(
        `/api/v1/trees/${treeId}/persons/${personId}/lineage${qs({ direction, depth })}`,
      ),
    placeholderData: keepPreviousData,
  });
}
