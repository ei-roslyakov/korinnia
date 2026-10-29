import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, qs } from "@/lib/api";
import type { Place, PlaceIndexItem, PlacePage } from "@/lib/genealogy";
import type { PlacePayload } from "@/features/builder/api";

const base = (treeId: string) => `/api/v1/trees/${treeId}/places`;

/** Every place with how much happened there, most first; `q` matches any name variant. */
export function usePlaceIndex(treeId: string, q: string) {
  return useQuery({
    queryKey: ["tree", treeId, "place-index", q],
    queryFn: () => api.get<PlaceIndexItem[]>(`${base(treeId)}/index${qs({ q: q || undefined })}`),
    placeholderData: keepPreviousData,
  });
}

export function usePlacePage(treeId: string, placeId: string) {
  return useQuery({
    queryKey: ["tree", treeId, "place", placeId],
    queryFn: () => api.get<PlacePage>(`${base(treeId)}/${placeId}/summary`),
  });
}

export function useUpdatePlace(treeId: string, placeId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Partial<PlacePayload>) =>
      api.patch<Place>(`${base(treeId)}/${placeId}`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tree", treeId] }),
  });
}

/** Merge `placeId` into `targetId`; returns the target. */
export function useMergePlace(treeId: string, placeId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (targetId: string) =>
      api.post<Place>(`${base(treeId)}/${placeId}/merge`, { target_id: targetId }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tree", treeId] }),
  });
}
