import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, apiFetch } from "@/lib/api";

export type ImportStatus =
  "analyzing" | "ready" | "importing" | "done" | "failed" | "undoing" | "undone" | "cancelled";

/** Statuses in which the worker is busy: the page polls until they change. */
export const BUSY: ImportStatus[] = ["analyzing", "importing", "undoing"];

export interface ImportCounts {
  persons: number;
  families: number;
  partnerships: number;
  parent_links: number;
  events: number;
  places: number;
  sources: number;
  citations: number;
  notes: number;
  media_links: number;
}

export interface Duplicate {
  xref: string;
  name: string;
  years: string;
  /** Both birth years known and agree (pre-selected as "same person"). */
  strong: boolean;
  existing: { id: string; name: string; years: string };
}

export interface ImportPreview {
  header: { source: string | null; version: string | null; date: string | null };
  encoding: string;
  counts: ImportCounts;
  warnings: { code: string; count: number }[];
  skipped_tags: { tag: string; count: number }[];
  people: { xref: string; name: string; gender: string; years: string }[];
  duplicates: Duplicate[];
}

export interface ImportWarning {
  code: string;
  reason?: string;
  name?: string;
  type?: string;
  parent?: string;
  child?: string;
  a?: string;
  b?: string;
}

export interface ImportResult {
  counts: Record<string, number>;
  warnings: ImportWarning[];
}

export interface GedcomImport {
  id: string;
  status: ImportStatus;
  filename: string;
  size: number;
  created_at: string;
  finished_at: string | null;
  created_by: string | null;
  preview: ImportPreview | null;
  result: ImportResult | null;
  error: string | null;
}

const base = (treeId: string) => `/api/v1/trees/${treeId}/imports`;
const listKey = (treeId: string) => ["tree", treeId, "imports"] as const;
const itemKey = (treeId: string, id: string) => ["tree", treeId, "imports", id] as const;

export function useImports(treeId: string) {
  return useQuery({
    queryKey: listKey(treeId),
    queryFn: () => api.get<GedcomImport[]>(base(treeId)),
  });
}

export function useImport(treeId: string, id: string | null) {
  return useQuery({
    queryKey: itemKey(treeId, id ?? ""),
    queryFn: () => api.get<GedcomImport>(`${base(treeId)}/${id}`),
    enabled: Boolean(id),
    refetchInterval: (q) => (q.state.data && BUSY.includes(q.state.data.status) ? 1500 : false),
  });
}

/** After an import changes, the tree itself (people, graph) may have changed too. */
function useRefresh(treeId: string) {
  const qc = useQueryClient();
  return (imp: GedcomImport) => {
    qc.setQueryData(itemKey(treeId, imp.id), imp);
    void qc.invalidateQueries({ queryKey: listKey(treeId), exact: true });
  };
}

export function useUploadGedcom(treeId: string) {
  const refresh = useRefresh(treeId);
  return useMutation({
    mutationFn: (file: File) => {
      const body = new FormData();
      body.append("file", file);
      return apiFetch<GedcomImport>(base(treeId), { method: "POST", body });
    },
    onSuccess: refresh,
  });
}

export function useImportAction(treeId: string) {
  const qc = useQueryClient();
  const refresh = useRefresh(treeId);
  return useMutation({
    mutationFn: ({
      id,
      action,
      merge,
    }: {
      id: string;
      action: "confirm" | "cancel" | "undo";
      merge?: Record<string, string>;
    }) =>
      api.post<GedcomImport>(
        `${base(treeId)}/${id}/${action}`,
        action === "confirm" ? { merge: merge ?? {} } : undefined,
      ),
    onSuccess: (imp) => {
      refresh(imp);
      void qc.invalidateQueries({ queryKey: ["tree", treeId] });
    },
  });
}
