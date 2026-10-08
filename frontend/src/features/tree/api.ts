import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ME_KEY } from "@/features/auth/api";
import { api } from "@/lib/api";
import type { Invitation, Member, Role, Tree } from "@/lib/types";

export const treesKey = ["trees"] as const;
export const treeKey = (id: string) => ["tree", id] as const;
export const membersKey = (id: string) => ["tree", id, "members"] as const;

export function useTrees() {
  return useQuery({ queryKey: treesKey, queryFn: () => api.get<Tree[]>("/api/v1/trees") });
}

export function useTree(id: string) {
  return useQuery({ queryKey: treeKey(id), queryFn: () => api.get<Tree>(`/api/v1/trees/${id}`) });
}

export function useCreateTree() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { name: string; description?: string | null; owner_id?: string | null }) =>
      api.post<Tree>("/api/v1/trees", body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: treesKey });
      void qc.invalidateQueries({ queryKey: ME_KEY });
    },
  });
}

export function useUpdateTree(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { name?: string; description?: string | null }) =>
      api.patch<Tree>(`/api/v1/trees/${id}`, body),
    onSuccess: (tree) => {
      qc.setQueryData(treeKey(id), tree);
      void qc.invalidateQueries({ queryKey: treesKey });
      void qc.invalidateQueries({ queryKey: ME_KEY });
    },
  });
}

/** Delete any tree by id (e.g. an empty tree made for a refused import). */
export function useDeleteTreeById() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.delete(`/api/v1/trees/${id}`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: treesKey });
      void qc.invalidateQueries({ queryKey: ME_KEY });
    },
  });
}

export function useDeleteTree(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.delete(`/api/v1/trees/${id}`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: treesKey });
      void qc.invalidateQueries({ queryKey: ME_KEY });
    },
  });
}

export interface MembersResponse {
  members: Member[];
  invitations: Invitation[];
}

export function useMembers(treeId: string) {
  return useQuery({
    queryKey: membersKey(treeId),
    queryFn: () => api.get<MembersResponse>(`/api/v1/trees/${treeId}/members`),
  });
}

export interface AddMemberResponse {
  kind: "member" | "invitation";
  member: Member | null;
  invitation: Invitation | null;
  url: string | null;
}

export function useAddMember(treeId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { email: string; role: Role }) =>
      api.post<AddMemberResponse>(`/api/v1/trees/${treeId}/members`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: membersKey(treeId) }),
  });
}

export function useUpdateMember(treeId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ userId, role }: { userId: string; role: Role }) =>
      api.patch<Member>(`/api/v1/trees/${treeId}/members/${userId}`, { role }),
    onSuccess: () => qc.invalidateQueries({ queryKey: membersKey(treeId) }),
  });
}

export function useRemoveMember(treeId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (userId: string) => api.delete(`/api/v1/trees/${treeId}/members/${userId}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: membersKey(treeId) }),
  });
}

export function useRevokeTreeInvitation(treeId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (invitationId: string) =>
      api.delete(`/api/v1/trees/${treeId}/invitations/${invitationId}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: membersKey(treeId) }),
  });
}
