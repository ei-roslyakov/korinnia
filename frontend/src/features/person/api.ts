import { keepPreviousData, useQuery, useQueryClient } from "@tanstack/react-query";

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
  const qc = useQueryClient();
  return useQuery({
    queryKey: personKey(treeId, personId ?? ""),
    queryFn: async () => {
      const person = await api.get<PersonDetail>(`/api/v1/trees/${treeId}/persons/${personId}`);
      const previous = qc.getQueryData<PersonDetail>(personKey(treeId, personId ?? ""));
      // A preview or portrait just finished: refresh the canvas cards too.
      if (
        previous &&
        (pendingCount(previous) > pendingCount(person) || previous.avatar_url !== person.avatar_url)
      ) {
        void qc.invalidateQueries({ queryKey: graphKey(treeId) });
      }
      return person;
    },
    enabled: Boolean(personId),
    // Poll while the worker is preparing previews or the portrait (capped at ~3 minutes).
    refetchInterval: (q) =>
      q.state.data &&
      (pendingCount(q.state.data) > 0 || q.state.data.portrait_pending) &&
      q.state.dataUpdateCount < 60
        ? 3000
        : false,
  });
}

const pendingCount = (p: PersonDetail) =>
  p.media.filter((m) => m.processing_status === "pending").length;

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
