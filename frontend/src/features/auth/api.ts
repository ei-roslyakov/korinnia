import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, ApiError } from "@/lib/api";
import type { Language, LoginResponse, Me } from "@/lib/types";

export const ME_KEY = ["me"] as const;

/** Current user, or null when not logged in. */
export function useMe() {
  return useQuery({
    queryKey: ME_KEY,
    queryFn: async (): Promise<Me | null> => {
      try {
        return await api.get<Me>("/api/v1/auth/me");
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) return null;
        throw err;
      }
    },
    staleTime: 60_000,
  });
}

export function useLogin() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { email: string; password: string }) =>
      api.post<LoginResponse>("/api/v1/auth/login", body),
    onSuccess: (data) => {
      if (data.user) qc.setQueryData(ME_KEY, data.user);
    },
  });
}

export function useLoginMfa() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (code: string) => api.post<LoginResponse>("/api/v1/auth/login/mfa", { code }),
    onSuccess: (data) => {
      if (data.user) qc.setQueryData(ME_KEY, data.user);
    },
  });
}

export function useLogout() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<void>("/api/v1/auth/logout"),
    onSettled: () => {
      qc.clear();
      qc.setQueryData(ME_KEY, null);
    },
  });
}

export function useUpdateMe() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { display_name?: string; preferred_language?: Language }) =>
      api.patch<Me>("/api/v1/auth/me", body),
    onSuccess: (me) => qc.setQueryData(ME_KEY, me),
  });
}

export function useChangePassword() {
  return useMutation({
    mutationFn: (body: { current_password: string; new_password: string }) =>
      api.post<void>("/api/v1/auth/me/password", body),
  });
}

export interface TotpSetup {
  secret: string;
  otpauth_uri: string;
  qr_svg: string;
}

export function useTotpSetup() {
  return useMutation({ mutationFn: () => api.post<TotpSetup>("/api/v1/auth/2fa/setup") });
}

export function useTotpEnable() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (code: string) =>
      api.post<{ recovery_codes: string[] }>("/api/v1/auth/2fa/enable", { code }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ME_KEY }),
  });
}

export function useTotpDisable() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { password: string; code: string }) =>
      api.post<void>("/api/v1/auth/2fa/disable", body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ME_KEY }),
  });
}

export function useRegenerateRecoveryCodes() {
  return useMutation({
    mutationFn: (code: string) =>
      api.post<{ recovery_codes: string[] }>("/api/v1/auth/2fa/recovery-codes", { code }),
  });
}

export interface InvitationInfo {
  email: string;
  tree_name: string | null;
  role: string | null;
  is_superadmin: boolean;
  expires_at: string;
}

export function useInvitationInfo(token: string) {
  return useQuery({
    queryKey: ["invitation", token],
    queryFn: () => api.get<InvitationInfo>(`/api/v1/auth/invitations/${token}`),
    retry: false,
  });
}

export function useAcceptInvitation(token: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { display_name: string; password: string; preferred_language: Language }) =>
      api.post<LoginResponse>(`/api/v1/auth/invitations/${token}/accept`, body),
    onSuccess: (data) => qc.setQueryData(ME_KEY, data.user),
  });
}

export function usePasswordResetInfo(token: string) {
  return useQuery({
    queryKey: ["password-reset", token],
    queryFn: () =>
      api.get<{ email: string; expires_at: string }>(`/api/v1/auth/password-reset/${token}`),
    retry: false,
  });
}

export function usePasswordReset(token: string) {
  return useMutation({
    mutationFn: (password: string) =>
      api.post<void>(`/api/v1/auth/password-reset/${token}`, { password }),
  });
}
