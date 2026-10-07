import { useMutation, useQueryClient } from "@tanstack/react-query";

import { api, ApiError, csrfToken } from "@/lib/api";
import type { MediaItem, PartialDateInput, Region } from "@/lib/genealogy";

const base = (treeId: string) => `/api/v1/trees/${treeId}`;

function useInvalidateTree(treeId: string) {
  const qc = useQueryClient();
  return () => qc.invalidateQueries({ queryKey: ["tree", treeId] });
}

export interface UploadOptions {
  personId?: string;
  title?: string;
  kind?: "photo" | "document_scan";
  allowDuplicate?: boolean;
  onProgress?: (fraction: number) => void;
}

/** Upload one file with progress (XHR: fetch has no upload progress events). */
export async function uploadMedia(
  treeId: string,
  file: File,
  opts: UploadOptions = {},
): Promise<MediaItem> {
  const form = new FormData();
  form.append("file", file);
  if (opts.personId) form.append("person_id", opts.personId);
  if (opts.title) form.append("title", opts.title);
  if (opts.kind) form.append("kind", opts.kind);
  if (opts.allowDuplicate) form.append("allow_duplicate", "true");
  const token = await csrfToken();
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${base(treeId)}/media`);
    xhr.withCredentials = true;
    xhr.setRequestHeader("X-CSRF-Token", token);
    xhr.setRequestHeader("Accept", "application/json");
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) opts.onProgress?.(e.loaded / e.total);
    };
    xhr.onload = () => {
      let body: unknown = xhr.responseText;
      try {
        body = JSON.parse(xhr.responseText);
      } catch {
        /* non-JSON error page (e.g. nginx 413) */
      }
      if (xhr.status >= 200 && xhr.status < 300) resolve(body as MediaItem);
      else
        reject(
          new ApiError(
            xhr.status,
            xhr.status === 413 && typeof body === "string" ? { code: "file_too_large" } : body,
          ),
        );
    };
    xhr.onerror = () => reject(new TypeError("network error"));
    xhr.send(form);
  });
}

export interface MediaPatch {
  kind?: string;
  title?: string | null;
  description?: string | null;
  date?: PartialDateInput | null;
  place_id?: string | null;
}

export function useUpdateMedia(treeId: string) {
  const invalidate = useInvalidateTree(treeId);
  return useMutation({
    mutationFn: ({ id, ...body }: MediaPatch & { id: string }) =>
      api.patch<MediaItem>(`${base(treeId)}/media/${id}`, body),
    onSuccess: invalidate,
  });
}

export function useDeleteMedia(treeId: string) {
  const invalidate = useInvalidateTree(treeId);
  return useMutation({
    mutationFn: (id: string) => api.delete(`${base(treeId)}/media/${id}`),
    onSuccess: invalidate,
  });
}

export function useReprocessMedia(treeId: string) {
  const invalidate = useInvalidateTree(treeId);
  return useMutation({
    mutationFn: (id: string) => api.post<MediaItem>(`${base(treeId)}/media/${id}/reprocess`),
    onSuccess: invalidate,
  });
}

export function useTagPerson(treeId: string) {
  const invalidate = useInvalidateTree(treeId);
  return useMutation({
    mutationFn: ({
      mediaId,
      personId,
      region,
    }: {
      mediaId: string;
      personId: string;
      region: Region | null;
    }) =>
      api.post<MediaItem>(`${base(treeId)}/media/${mediaId}/people`, {
        person_id: personId,
        region,
      }),
    onSuccess: invalidate,
  });
}

export function useUntagPerson(treeId: string) {
  const invalidate = useInvalidateTree(treeId);
  return useMutation({
    mutationFn: ({ mediaId, personId }: { mediaId: string; personId: string }) =>
      api.delete<MediaItem>(`${base(treeId)}/media/${mediaId}/people/${personId}`),
    onSuccess: invalidate,
  });
}

export function useReorderMedia(treeId: string, personId: string) {
  const invalidate = useInvalidateTree(treeId);
  return useMutation({
    mutationFn: (mediaIds: string[]) =>
      api.put(`${base(treeId)}/persons/${personId}/media-order`, { media_ids: mediaIds }),
    onSuccess: invalidate,
  });
}
