import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, qs } from "@/lib/api";
import type {
  DeletePreview,
  Gender,
  HistoricalName,
  LifeEvent,
  ParentChildType,
  PartialDateInput,
  PartnershipType,
  PersonDetail,
  Place,
  RelativeRelation,
  TrashItem,
  TreeGraph,
} from "@/lib/genealogy";
import type { AuditEntry, Page } from "@/lib/types";

/** Everything genealogical about a tree lives under ["tree", id]; refresh it after edits. */
function useInvalidateTree(treeId: string) {
  const qc = useQueryClient();
  return () => qc.invalidateQueries({ queryKey: ["tree", treeId] });
}

const base = (treeId: string) => `/api/v1/trees/${treeId}`;

export interface NameInput {
  type: string;
  first_name: string | null;
  middle_name: string | null;
  patronymic: string | null;
  last_name: string | null;
  maiden_name: string | null;
  script: string;
  is_primary: boolean;
  notes?: string | null;
}

export interface VitalInput {
  date: PartialDateInput | null;
  place_id: string | null;
  description?: string | null;
}

export interface PersonPayload {
  gender?: Gender;
  is_living?: boolean | null;
  short_summary?: string | null;
  biography?: string | null;
  occupation?: string | null;
  education?: string | null;
  religion?: string | null;
  nationality?: string | null;
  notes_for_descendants?: string | null;
  research_status?: string;
  names?: NameInput[];
  birth?: VitalInput | null;
  death?: VitalInput | null;
  relative?: {
    person_id: string;
    relation: RelativeRelation;
    parent_child_type?: ParentChildType;
    partnership_type?: PartnershipType;
    other_parent_id?: string | null;
  };
}

export function useCreatePerson(treeId: string) {
  const invalidate = useInvalidateTree(treeId);
  return useMutation({
    mutationFn: (body: PersonPayload) => api.post<PersonDetail>(`${base(treeId)}/persons`, body),
    onSuccess: invalidate,
  });
}

export function useUpdatePerson(treeId: string, personId: string) {
  const invalidate = useInvalidateTree(treeId);
  return useMutation({
    mutationFn: (body: PersonPayload) =>
      api.patch<PersonDetail>(`${base(treeId)}/persons/${personId}`, body),
    onSuccess: invalidate,
  });
}

export function useDeletePreview(treeId: string, personId: string, enabled: boolean) {
  return useQuery({
    queryKey: ["tree", treeId, "delete-preview", personId],
    queryFn: () => api.get<DeletePreview>(`${base(treeId)}/persons/${personId}/delete-preview`),
    enabled,
  });
}

export function useDeletePerson(treeId: string) {
  const qc = useQueryClient();
  const invalidate = useInvalidateTree(treeId);
  return useMutation({
    mutationFn: (personId: string) => api.delete(`${base(treeId)}/persons/${personId}`),
    onSuccess: (_, personId) => {
      // Don't refetch the deleted person (404) while the editor is still on screen.
      qc.removeQueries({ queryKey: ["tree", treeId, "person", personId] });
      return invalidate();
    },
  });
}

// --- Events -------------------------------------------------------------------------------

export interface EventPayload {
  type?: string;
  title?: string | null;
  description?: string | null;
  date?: PartialDateInput | null;
  place_id?: string | null;
  cemetery_name?: string | null;
  burial_plot?: string | null;
  latitude?: string | null;
  longitude?: string | null;
  participants?: { person_id: string; role: string }[];
}

export function useSaveEvent(treeId: string) {
  const invalidate = useInvalidateTree(treeId);
  return useMutation({
    mutationFn: ({ id, ...body }: EventPayload & { id?: string }) =>
      id
        ? api.patch<LifeEvent>(`${base(treeId)}/events/${id}`, body)
        : api.post<LifeEvent>(`${base(treeId)}/events`, body),
    onSuccess: invalidate,
  });
}

export function useDeleteEvent(treeId: string) {
  const invalidate = useInvalidateTree(treeId);
  return useMutation({
    mutationFn: (id: string) => api.delete(`${base(treeId)}/events/${id}`),
    onSuccess: invalidate,
  });
}

// --- Relationships -----------------------------------------------------------------------

export function useSaveParentChild(treeId: string) {
  const invalidate = useInvalidateTree(treeId);
  return useMutation({
    mutationFn: ({
      id,
      ...body
    }: {
      id?: string;
      parent_id?: string;
      child_id?: string;
      type?: ParentChildType;
    }) =>
      id
        ? api.patch(`${base(treeId)}/parent-child/${id}`, body)
        : api.post(`${base(treeId)}/parent-child`, body),
    onSuccess: invalidate,
  });
}

export function useDeleteParentChild(treeId: string) {
  const invalidate = useInvalidateTree(treeId);
  return useMutation({
    mutationFn: (id: string) => api.delete(`${base(treeId)}/parent-child/${id}`),
    onSuccess: invalidate,
  });
}

export interface PartnershipPayload {
  person_a_id?: string;
  person_b_id?: string;
  type?: PartnershipType;
  start_date?: PartialDateInput | null;
  end_date?: PartialDateInput | null;
  end_reason?: string | null;
  place_id?: string | null;
  notes?: string | null;
}

export function useSavePartnership(treeId: string) {
  const invalidate = useInvalidateTree(treeId);
  return useMutation({
    mutationFn: ({ id, ...body }: PartnershipPayload & { id?: string }) =>
      id
        ? api.patch(`${base(treeId)}/partnerships/${id}`, body)
        : api.post(`${base(treeId)}/partnerships`, body),
    onSuccess: invalidate,
  });
}

export function useDeletePartnership(treeId: string) {
  const invalidate = useInvalidateTree(treeId);
  return useMutation({
    mutationFn: (id: string) => api.delete(`${base(treeId)}/partnerships/${id}`),
    onSuccess: invalidate,
  });
}

// --- Places -------------------------------------------------------------------------------

export function usePlaceSearch(treeId: string, q: string) {
  return useQuery({
    queryKey: ["tree", treeId, "places", q],
    queryFn: () => api.get<Page<Place>>(`${base(treeId)}/places${qs({ q, limit: 10 })}`),
    staleTime: 30_000,
  });
}

export interface PlacePayload {
  name: string;
  country?: string | null;
  region?: string | null;
  latitude?: string | null;
  longitude?: string | null;
  historical_names?: HistoricalName[];
  notes?: string | null;
}

export function useCreatePlace(treeId: string) {
  const invalidate = useInvalidateTree(treeId);
  return useMutation({
    mutationFn: (body: PlacePayload) => api.post<Place>(`${base(treeId)}/places`, body),
    onSuccess: invalidate,
  });
}

// --- History, trash, layout ------------------------------------------------------------------

export function usePersonHistory(treeId: string, personId: string) {
  return useQuery({
    queryKey: ["tree", treeId, "history", "person", personId],
    queryFn: () =>
      api.get<Page<AuditEntry>>(
        `${base(treeId)}/history${qs({ entity_type: "person", entity_id: personId, limit: 100 })}`,
      ),
  });
}

export function useRestoreRevision(treeId: string) {
  const invalidate = useInvalidateTree(treeId);
  return useMutation({
    mutationFn: (entryId: string) => api.post(`${base(treeId)}/history/${entryId}/restore`),
    onSuccess: invalidate,
  });
}

export function useTrash(treeId: string) {
  return useQuery({
    queryKey: ["tree", treeId, "trash"],
    queryFn: () => api.get<TrashItem[]>(`${base(treeId)}/trash`),
  });
}

export function useRestoreFromTrash(treeId: string) {
  const invalidate = useInvalidateTree(treeId);
  return useMutation({
    mutationFn: (item: TrashItem) =>
      api.post(`${base(treeId)}/trash/${item.entity_type}/${item.entity_id}/restore`),
    onSuccess: invalidate,
  });
}

export function useSaveLayoutOffset(treeId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ personId, dx, dy }: { personId: string; dx: number; dy: number }) =>
      api.put<void>(`${base(treeId)}/layout-offsets/${personId}`, { dx, dy }),
    // Optimistic: the canvas moves immediately; the server copy only needs to persist it.
    onMutate: ({ personId, dx, dy }) => {
      qc.setQueryData<TreeGraph>(["tree", treeId, "graph"], (old) =>
        old
          ? {
              ...old,
              layout_offsets: { ...(old.layout_offsets ?? {}), [personId]: { dx, dy } },
            }
          : old,
      );
    },
  });
}

export function useResetLayout(treeId: string) {
  const invalidate = useInvalidateTree(treeId);
  return useMutation({
    mutationFn: () => api.delete(`${base(treeId)}/layout-offsets`),
    onSuccess: invalidate,
  });
}
