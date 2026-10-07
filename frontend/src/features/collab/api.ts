import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, qs } from "@/lib/api";
import type {
  Citation,
  CitationQuality,
  CitedEntity,
  CommentItem,
  DataQuality,
  OpenQuestion,
  PartialDateInput,
  Source,
  SourceType,
  Story,
  StoryStatus,
  StorySummary,
  Suggestion,
} from "@/lib/genealogy";
import type { Page } from "@/lib/types";

const base = (treeId: string) => `/api/v1/trees/${treeId}`;

function useInvalidate(treeId: string) {
  const qc = useQueryClient();
  return () => qc.invalidateQueries({ queryKey: ["tree", treeId] });
}

// --- Sources & citations --------------------------------------------------------------------

export function useSources(treeId: string, q: string) {
  return useQuery({
    queryKey: ["tree", treeId, "sources", q],
    queryFn: () => api.get<Page<Source>>(`${base(treeId)}/sources${qs({ q, limit: 100 })}`),
  });
}

export interface SourcePayload {
  title?: string;
  type?: SourceType;
  author?: string | null;
  archive_name?: string | null;
  reference_number?: string | null;
  url?: string | null;
  notes?: string | null;
  media_ids?: string[];
}

export function useSaveSource(treeId: string) {
  const invalidate = useInvalidate(treeId);
  return useMutation({
    mutationFn: ({ id, ...body }: SourcePayload & { id?: string }) =>
      id
        ? api.patch<Source>(`${base(treeId)}/sources/${id}`, body)
        : api.post<Source>(`${base(treeId)}/sources`, body),
    onSuccess: invalidate,
  });
}

export function useDeleteSource(treeId: string) {
  const invalidate = useInvalidate(treeId);
  return useMutation({
    mutationFn: (id: string) => api.delete(`${base(treeId)}/sources/${id}`),
    onSuccess: invalidate,
  });
}

export function useSourceCitations(treeId: string, sourceId: string | null) {
  return useQuery({
    queryKey: ["tree", treeId, "citations", "source", sourceId],
    queryFn: () => api.get<Citation[]>(`${base(treeId)}/citations${qs({ source_id: sourceId })}`),
    enabled: Boolean(sourceId),
  });
}

export interface CitationPayload {
  source_id?: string;
  entity_type?: CitedEntity;
  entity_id?: string;
  field?: string | null;
  page?: string | null;
  quality?: CitationQuality;
  notes?: string | null;
}

export function useSaveCitation(treeId: string) {
  const invalidate = useInvalidate(treeId);
  return useMutation({
    mutationFn: ({ id, ...body }: CitationPayload & { id?: string }) =>
      id
        ? api.patch<Citation>(`${base(treeId)}/citations/${id}`, body)
        : api.post<Citation>(`${base(treeId)}/citations`, body),
    onSuccess: invalidate,
  });
}

export function useDeleteCitation(treeId: string) {
  const invalidate = useInvalidate(treeId);
  return useMutation({
    mutationFn: (id: string) => api.delete(`${base(treeId)}/citations/${id}`),
    onSuccess: invalidate,
  });
}

// --- Stories ------------------------------------------------------------------------------

export function useStories(treeId: string, filter: { status?: StoryStatus; person_id?: string }) {
  return useQuery({
    queryKey: ["tree", treeId, "stories", filter],
    queryFn: () =>
      api.get<Page<StorySummary>>(`${base(treeId)}/stories${qs({ ...filter, limit: 200 })}`),
  });
}

export function useStory(treeId: string, storyId: string | undefined) {
  return useQuery({
    queryKey: ["tree", treeId, "story", storyId],
    queryFn: () => api.get<Story>(`${base(treeId)}/stories/${storyId}`),
    enabled: Boolean(storyId),
  });
}

export interface StoryPayload {
  title?: string;
  body?: string;
  narrator?: string | null;
  date?: PartialDateInput | null;
  person_ids?: string[];
  media_ids?: string[];
  status?: StoryStatus;
}

export function useSaveStory(treeId: string) {
  const invalidate = useInvalidate(treeId);
  return useMutation({
    mutationFn: ({ id, ...body }: StoryPayload & { id?: string }) =>
      id
        ? api.patch<Story>(`${base(treeId)}/stories/${id}`, body)
        : api.post<Story>(`${base(treeId)}/stories`, body),
    onSuccess: invalidate,
  });
}

export function useStoryAction(treeId: string) {
  const invalidate = useInvalidate(treeId);
  return useMutation({
    mutationFn: ({
      id,
      action,
      comment,
    }: {
      id: string;
      action: "submit" | "publish" | "return";
      comment?: string;
    }) =>
      api.post<Story>(`${base(treeId)}/stories/${id}/${action}`, comment ? { comment } : undefined),
    onSuccess: invalidate,
  });
}

export function useDeleteStory(treeId: string) {
  const invalidate = useInvalidate(treeId);
  return useMutation({
    mutationFn: (id: string) => api.delete(`${base(treeId)}/stories/${id}`),
    onSuccess: invalidate,
  });
}

// --- Suggestions & moderation ---------------------------------------------------------------

export function useSuggestions(treeId: string, status?: Suggestion["status"]) {
  return useQuery({
    queryKey: ["tree", treeId, "suggestions", status],
    queryFn: () => api.get<Suggestion[]>(`${base(treeId)}/suggestions${qs({ status })}`),
  });
}

export function useCreateSuggestion(treeId: string) {
  const invalidate = useInvalidate(treeId);
  return useMutation({
    mutationFn: (body: {
      entity_type: "person" | "event";
      entity_id: string;
      patch: Record<string, unknown>;
      comment?: string;
    }) => api.post<Suggestion>(`${base(treeId)}/suggestions`, body),
    onSuccess: invalidate,
  });
}

export function useReviewSuggestion(treeId: string) {
  const invalidate = useInvalidate(treeId);
  return useMutation({
    mutationFn: ({
      id,
      decision,
      comment,
    }: {
      id: string;
      decision: "approve" | "reject";
      comment?: string;
    }) =>
      api.post<Suggestion>(
        `${base(treeId)}/suggestions/${id}/${decision}`,
        comment ? { comment } : undefined,
      ),
    onSuccess: invalidate,
  });
}

export function useModerationCounts(treeId: string, enabled: boolean) {
  return useQuery({
    queryKey: ["tree", treeId, "moderation"],
    queryFn: () => api.get<{ suggestions: number; stories: number }>(`${base(treeId)}/moderation`),
    enabled,
    refetchInterval: 60_000,
  });
}

// --- Comments & questions -----------------------------------------------------------------

export function useComments(
  treeId: string,
  entityType: CommentItem["entity_type"],
  entityId: string,
) {
  return useQuery({
    queryKey: ["tree", treeId, "comments", entityType, entityId],
    queryFn: () =>
      api.get<CommentItem[]>(
        `${base(treeId)}/comments${qs({ entity_type: entityType, entity_id: entityId })}`,
      ),
  });
}

export function useSaveComment(treeId: string) {
  const invalidate = useInvalidate(treeId);
  return useMutation({
    mutationFn: ({
      id,
      ...body
    }: {
      id?: string;
      entity_type?: string;
      entity_id?: string;
      body: string;
    }) =>
      id
        ? api.patch<CommentItem>(`${base(treeId)}/comments/${id}`, { body: body.body })
        : api.post<CommentItem>(`${base(treeId)}/comments`, body),
    onSuccess: invalidate,
  });
}

export function useDeleteComment(treeId: string) {
  const invalidate = useInvalidate(treeId);
  return useMutation({
    mutationFn: (id: string) => api.delete(`${base(treeId)}/comments/${id}`),
    onSuccess: invalidate,
  });
}

export function useSaveQuestion(treeId: string) {
  const invalidate = useInvalidate(treeId);
  return useMutation({
    mutationFn: ({
      id,
      ...body
    }: {
      id?: string;
      person_id?: string;
      question?: string;
      status?: string;
      resolution?: string | null;
    }) =>
      id
        ? api.patch<OpenQuestion>(`${base(treeId)}/questions/${id}`, body)
        : api.post<OpenQuestion>(`${base(treeId)}/questions`, body),
    onSuccess: invalidate,
  });
}

export function useDeleteQuestion(treeId: string) {
  const invalidate = useInvalidate(treeId);
  return useMutation({
    mutationFn: (id: string) => api.delete(`${base(treeId)}/questions/${id}`),
    onSuccess: invalidate,
  });
}

export function useDataQuality(treeId: string) {
  return useQuery({
    queryKey: ["tree", treeId, "data-quality"],
    queryFn: () => api.get<DataQuality>(`${base(treeId)}/data-quality`),
  });
}
