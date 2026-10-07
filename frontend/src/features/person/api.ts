import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { api, qs } from "@/lib/api";
import type { PersonDetail, PersonSummary, TreeGraph } from "@/lib/genealogy";
import type { Page } from "@/lib/types";

export const graphKey = (treeId: string) => ["tree", treeId, "graph"] as const;
export const personKey = (treeId: string, personId: string) =>
  ["tree", treeId, "person", personId] as const;

export function useGraph(treeId: string) {
  return useQuery({
    queryKey: graphKey(treeId),
    queryFn: () => api.get<TreeGraph>(`/api/v1/trees/${treeId}/graph`),
  });
}

export function usePerson(treeId: string, personId: string | null) {
  return useQuery({
    queryKey: personKey(treeId, personId ?? ""),
    queryFn: () => api.get<PersonDetail>(`/api/v1/trees/${treeId}/persons/${personId}`),
    enabled: Boolean(personId),
  });
}

export function usePersonSearch(treeId: string, q: string) {
  return useQuery({
    queryKey: ["tree", treeId, "search", q],
    queryFn: () =>
      api.get<Page<PersonSummary>>(`/api/v1/trees/${treeId}/persons${qs({ q, limit: 12 })}`),
    enabled: q.trim().length >= 2,
    placeholderData: keepPreviousData,
    staleTime: 30_000,
  });
}
