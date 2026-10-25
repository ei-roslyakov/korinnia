import { keepPreviousData, useInfiniteQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { MediaItem } from "@/lib/genealogy";
import type { Page } from "@/lib/types";

export interface AlbumPage extends Page<MediaItem> {
  /** Decades (1950 = the 1950s) that have dated photos. */
  decades: number[];
}

export interface AlbumFilter {
  personIds?: string[];
  decade?: number | null;
  q?: string;
  sort?: "date" | "newest";
}

export const ALBUM_PAGE = 24;

/** The tree's photos, page by page (`fetchNextPage` as the viewer nears the end). */
export function useAlbum(treeId: string, f: AlbumFilter = {}) {
  const params = new URLSearchParams();
  for (const id of f.personIds ?? []) params.append("person_id", id);
  if (f.decade != null) {
    params.set("year_from", String(f.decade));
    params.set("year_to", String(f.decade + 9));
  }
  if (f.q?.trim()) params.set("q", f.q.trim());
  if (f.sort === "newest") params.set("sort", "newest");
  params.set("limit", String(ALBUM_PAGE));
  const query = useInfiniteQuery({
    queryKey: ["tree", treeId, "album", params.toString()],
    queryFn: ({ pageParam }) =>
      api.get<AlbumPage>(`/api/v1/trees/${treeId}/album?${params.toString()}&offset=${pageParam}`),
    initialPageParam: 0,
    getNextPageParam: (last) =>
      last.offset + last.items.length < last.total ? last.offset + last.items.length : undefined,
    placeholderData: keepPreviousData,
  });
  const pages = query.data?.pages ?? [];
  return {
    ...query,
    items: pages.flatMap((p) => p.items),
    total: pages[0]?.total ?? 0,
    decades: pages[0]?.decades ?? [],
  };
}
