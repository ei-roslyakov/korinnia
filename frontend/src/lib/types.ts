/** Types mirroring the backend API schemas (app/schemas/*). */

export type Role = "viewer" | "contributor" | "editor" | "admin";
export const ROLES: Role[] = ["viewer", "contributor", "editor", "admin"];
export type Language = "uk" | "en" | "pl";

export interface MeTree {
  id: string;
  name: string;
  role: Role;
}

export interface Me {
  id: string;
  email: string;
  display_name: string;
  preferred_language: Language;
  is_superadmin: boolean;
  totp_enabled: boolean;
  trees: MeTree[];
  /** Onboarding: welcome guide dismissed for good; newest "What's new" entry seen. */
  welcome_dismissed: boolean;
  changelog_seen: string | null;
  show_changelog: boolean;
}

export interface LoginResponse {
  status: "ok" | "mfa_required";
  user: Me | null;
}

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface User {
  id: string;
  email: string;
  display_name: string;
  preferred_language: Language;
  is_superadmin: boolean;
  is_active: boolean;
  totp_enabled: boolean;
  created_at: string;
  last_login_at: string | null;
}

export interface Invitation {
  id: string;
  email: string;
  tree_id: string | null;
  tree_name: string | null;
  role: Role | null;
  is_superadmin: boolean;
  created_at: string;
  expires_at: string;
  accepted_at: string | null;
  revoked_at: string | null;
  created_by_name: string | null;
}

export interface Tree {
  id: string;
  name: string;
  description: string | null;
  owner_id: string | null;
  created_at: string;
  updated_at: string;
  my_role: Role;
  /** The user's own copy of the fictional demo family. */
  is_demo?: boolean;
  person_count?: number;
  first_year?: number | null;
  last_year?: number | null;
  cover?: string[];
}

export interface Member {
  user_id: string;
  email: string;
  display_name: string;
  role: Role;
  is_active: boolean;
  created_at: string;
}

export interface AuditEntry {
  id: string;
  created_at: string;
  user_id: string | null;
  user_label: string | null;
  action: string;
  entity_type: string;
  entity_id: string | null;
  tree_id: string | null;
  before: Record<string, unknown> | null;
  after: Record<string, unknown> | null;
  ip_address: string | null;
}

export interface LinkResponse {
  url: string;
  expires_at: string;
}

const RANK: Record<Role, number> = { viewer: 1, contributor: 2, editor: 3, admin: 4 };
export const atLeast = (role: Role, min: Role) => RANK[role] >= RANK[min];
