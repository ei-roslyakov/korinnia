import { keepPreviousData, useInfiniteQuery, useQuery } from "@tanstack/react-query";

import { api, qs } from "@/lib/api";
import type { MapData, OnThisDay, Relationship, TimelinePage, TreeStats } from "@/lib/genealogy";

const base = (treeId: string) => `/api/v1/trees/${treeId}`;

export interface TimelineFilter {
  types?: string[];
  personId?: string | null;
  fromYear?: number | null;
  toYear?: number | null;
}

export const TIMELINE_PAGE = 100;

/** Pages of 100 facts; `fetchNextPage` loads more ("show more"). */
export function useTimeline(treeId: string, f: TimelineFilter) {
  const params = new URLSearchParams();
  for (const ty of f.types ?? []) params.append("type", ty);
  if (f.personId) params.set("person_id", f.personId);
  if (f.fromYear) params.set("from_year", String(f.fromYear));
  if (f.toYear) params.set("to_year", String(f.toYear));
  params.set("limit", String(TIMELINE_PAGE));
  return useInfiniteQuery({
    queryKey: ["tree", treeId, "timeline", params.toString()],
    queryFn: ({ pageParam }) =>
      api.get<TimelinePage>(`${base(treeId)}/timeline?${params.toString()}&offset=${pageParam}`),
    initialPageParam: 0,
    getNextPageParam: (last) =>
      last.offset + last.items.length < last.total ? last.offset + last.items.length : undefined,
    placeholderData: keepPreviousData,
  });
}

export function useOnThisDay(treeId: string, date: string, days: number) {
  return useQuery({
    queryKey: ["tree", treeId, "on-this-day", date, days],
    queryFn: () => api.get<OnThisDay>(`${base(treeId)}/on-this-day${qs({ date, days })}`),
  });
}

export function useMapData(treeId: string, personId: string | null) {
  return useQuery({
    queryKey: ["tree", treeId, "map", personId],
    queryFn: () => api.get<MapData>(`${base(treeId)}/map${qs({ person_id: personId })}`),
    placeholderData: keepPreviousData,
  });
}

export function useRelationship(treeId: string, a: string | null, b: string | null) {
  return useQuery({
    queryKey: ["tree", treeId, "relationship", a, b],
    queryFn: () => api.get<Relationship>(`${base(treeId)}/relationship${qs({ a, b })}`),
    enabled: Boolean(a && b),
  });
}

export function useTreeStats(treeId: string) {
  return useQuery({
    queryKey: ["tree", treeId, "stats"],
    queryFn: () => api.get<TreeStats>(`${base(treeId)}/stats`),
  });
}
