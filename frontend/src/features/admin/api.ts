import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ME_KEY } from "@/features/auth/api";
import { treesKey } from "@/features/tree/api";
import { api, qs } from "@/lib/api";
import type { AuditEntry, Invitation, Language, LinkResponse, Page, Role, User } from "@/lib/types";

const usersKey = ["admin", "users"] as const;
const invitationsKey = ["admin", "invitations"] as const;
const adminTreesKey = ["admin", "trees"] as const;

export function useUsers(params: { q?: string; is_active?: boolean; offset?: number }) {
  return useQuery({
    queryKey: [...usersKey, params],
    queryFn: () => api.get<Page<User>>(`/api/v1/admin/users${qs({ ...params, limit: 50 })}`),
    placeholderData: keepPreviousData,
  });
}

export function useCreateUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: {
      email: string;
      display_name: string;
      password: string;
      preferred_language: Language;
      is_superadmin: boolean;
    }) => api.post<User>("/api/v1/admin/users", body),
    onSuccess: () => qc.invalidateQueries({ queryKey: usersKey }),
  });
}

export function useUpdateUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: { id: string; is_active?: boolean; is_superadmin?: boolean }) =>
      api.patch<User>(`/api/v1/admin/users/${id}`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: usersKey }),
  });
}

export function useDeleteUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.delete(`/api/v1/admin/users/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: usersKey }),
  });
}

export function useResetLink() {
  return useMutation({
    mutationFn: (id: string) => api.post<LinkResponse>(`/api/v1/admin/users/${id}/password-reset`),
  });
}

export function useAdminDisable2fa() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.post<User>(`/api/v1/admin/users/${id}/disable-2fa`),
    onSuccess: () => qc.invalidateQueries({ queryKey: usersKey }),
  });
}

export function useInvitations() {
  return useQuery({
    queryKey: invitationsKey,
    queryFn: () => api.get<Invitation[]>("/api/v1/admin/invitations"),
  });
}

export function useCreateInvitation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: {
      email: string;
      tree_id: string | null;
      role: Role | null;
      is_superadmin: boolean;
    }) => api.post<{ invitation: Invitation; url: string }>("/api/v1/admin/invitations", body),
    onSuccess: () => qc.invalidateQueries({ queryKey: invitationsKey }),
  });
}

export function useRevokeInvitation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.delete(`/api/v1/admin/invitations/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: invitationsKey }),
  });
}

export interface AuditFilters {
  action?: string;
  entity_type?: string;
  user_id?: string;
  date_from?: string;
  date_to?: string;
  offset?: number;
}

/** Audit log, global (superadmin) or scoped to one tree (tree admin). */
export function useAuditLog(treeId: string | undefined, filters: AuditFilters) {
  const base = treeId ? `/api/v1/trees/${treeId}/audit-log` : "/api/v1/admin/audit-log";
  return useQuery({
    queryKey: ["audit", treeId ?? "all", filters],
    queryFn: () => api.get<Page<AuditEntry>>(`${base}${qs({ ...filters, limit: 50 })}`),
    placeholderData: keepPreviousData,
  });
}

export function useAuditActions(enabled: boolean) {
  return useQuery({
    queryKey: ["audit", "actions"],
    queryFn: () => api.get<string[]>("/api/v1/admin/audit-log/actions"),
    enabled,
  });
}

export interface AdminTree {
  id: string;
  name: string;
  is_demo: boolean;
  owner_id: string | null;
  owner_name: string | null;
  owner_email: string | null;
  member_count: number;
  person_count: number;
  created_at: string;
  deleted_at: string | null;
}

export function useAdminTrees(params: { q?: string; deleted?: boolean; offset?: number }) {
  return useQuery({
    queryKey: [...adminTreesKey, params],
    queryFn: () => api.get<Page<AdminTree>>(`/api/v1/admin/trees${qs({ ...params, limit: 50 })}`),
    placeholderData: keepPreviousData,
  });
}

/** Deleting or restoring changes everyone's tree list, the admin list and the user's menu. */
function useTreeListChange() {
  const qc = useQueryClient();
  return () => {
    void qc.invalidateQueries({ queryKey: adminTreesKey });
    void qc.invalidateQueries({ queryKey: treesKey });
    void qc.invalidateQueries({ queryKey: ME_KEY });
  };
}

export function useAdminDeleteTree() {
  const onSuccess = useTreeListChange();
  return useMutation({
    mutationFn: (id: string) => api.delete(`/api/v1/trees/${id}`),
    onSuccess,
  });
}

export function useRestoreTree() {
  const onSuccess = useTreeListChange();
  return useMutation({
    mutationFn: (id: string) => api.post(`/api/v1/admin/trees/${id}/restore`),
    onSuccess,
  });
}
