import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, ApiError } from "@/lib/api";

export interface ShareSession {
  tree_id: string;
  tree_name: string;
  expires_at: string | null;
}

export interface ShareLink {
  id: string;
  label: string | null;
  created_at: string;
  created_by: string | null;
  expires_at: string | null;
  revoked_at: string | null;
  last_used_at: string | null;
  use_count: number;
  active: boolean;
}

const SESSION_KEY = ["share-session"] as const;
const linksKey = (treeId: string) => ["tree", treeId, "share-links"] as const;

/** The tree this browser may view through a share link, or null (D98). */
export function useShareSession(enabled = true) {
  return useQuery({
    queryKey: SESSION_KEY,
    queryFn: async (): Promise<ShareSession | null> => {
      try {
        return await api.get<ShareSession>("/api/v1/share/session");
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) return null;
        throw err;
      }
    },
    enabled,
    staleTime: 60_000,
    retry: false,
  });
}

export function useOpenShareLink() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (token: string) =>
      api.post<ShareSession>(`/api/v1/share/${encodeURIComponent(token)}/open`),
    onSuccess: (session) => qc.setQueryData(SESSION_KEY, session),
  });
}

export function useLeaveShare() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<void>("/api/v1/share/leave"),
    onSuccess: () => qc.setQueryData(SESSION_KEY, null),
  });
}

export function useShareLinks(treeId: string) {
  return useQuery({
    queryKey: linksKey(treeId),
    queryFn: () => api.get<ShareLink[]>(`/api/v1/trees/${treeId}/share-links`),
  });
}

export function useCreateShareLink(treeId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { label: string | null; expires_in_days: number | null }) =>
      api.post<{ link: ShareLink; url: string }>(`/api/v1/trees/${treeId}/share-links`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: linksKey(treeId) }),
  });
}

export function useRevokeShareLink(treeId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.delete(`/api/v1/trees/${treeId}/share-links/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: linksKey(treeId) }),
  });
}
