import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams, useSearchParams } from "react-router";

import { EmptyState } from "@/components/EmptyState";
import { TextSkeleton } from "@/components/Skeleton";
import { Button, ErrorAlert, Input, PageHeader, Select } from "@/components/ui";
import { Lightbox } from "@/features/media/Lightbox";
import { photoAlt } from "@/features/media/photoAlt";
import { PhotoCaption } from "@/features/media/PhotoCaption";
import { usePerson } from "@/features/person/api";
import { PersonCombobox } from "@/features/person/PersonCombobox";
import { useTree } from "@/features/tree/api";

import { AlbumCarousel } from "./AlbumCarousel";
import { useAlbum } from "./api";

/** /trees/:treeId/album — every photo of the family: a large carousel or a grid, with
 *  filters by person and decade and two orders. The filters live in the URL. */
export function AlbumPage() {
  const { t } = useTranslation();
  const { treeId = "" } = useParams();
  const [params, setParams] = useSearchParams();
  const tree = useTree(treeId);
  const personIds = params.getAll("person");
  const decade = params.get("decade") ? Number(params.get("decade")) : null;
  const sort = params.get("sort") === "newest" ? "newest" : "date";
  const view = params.get("view") === "grid" ? "grid" : "carousel";
  const q = params.get("q") ?? "";
  const [search, setSearch] = useState(q);
  const album = useAlbum(treeId, { personIds, decade, sort, q });
  const [viewing, setViewing] = useState<number | null>(null);
  const { hasNextPage, isFetchingNextPage, fetchNextPage } = album;
  const more = useCallback(() => {
    if (hasNextPage && !isFetchingNextPage) void fetchNextPage();
  }, [hasNextPage, isFetchingNextPage, fetchNextPage]);
  const personLink = (id: string) => `/trees/${treeId}/people/${id}`;

  const update = useCallback(
    (changes: Record<string, string | string[] | null>) =>
      setParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          for (const [k, v] of Object.entries(changes)) {
            next.delete(k);
            for (const value of Array.isArray(v) ? v : v ? [v] : []) next.append(k, value);
          }
          return next;
        },
        { replace: true },
      ),
    [setParams],
  );

  // Search as the viewer types, without a request per keystroke.
  useEffect(() => {
    if (search.trim() === q) return;
    const id = window.setTimeout(() => update({ q: search.trim() || null }), 300);
    return () => window.clearTimeout(id);
  }, [search, q, update]);

  const filtered = personIds.length > 0 || decade !== null || q !== "";
  const toggleButton = (active: boolean) =>
    `px-3 py-1 whitespace-nowrap ${active ? "bg-leaf-700 text-on-leaf" : "bg-surface"}`;

  return (
    <div className="mx-auto max-w-5xl space-y-4">
      <Link to={`/trees/${treeId}`} className="text-leaf-700 text-sm underline">
        ← {t("person.backToTree")}
      </Link>
      <PageHeader
        title={tree.data ? `${t("album.title")} · ${tree.data.name}` : t("album.title")}
      />

      <div className="flex flex-wrap items-end gap-3">
        <div className="w-full max-w-xs space-y-2">
          <PersonCombobox
            treeId={treeId}
            label={t("album.person")}
            excludeIds={personIds}
            onSelect={(p) => update({ person: [...personIds, p.id] })}
          />
          {personIds.length > 0 && (
            <ul className="flex flex-wrap gap-1.5">
              {personIds.map((id) => (
                <PersonChip
                  key={id}
                  treeId={treeId}
                  personId={id}
                  onRemove={() => update({ person: personIds.filter((x) => x !== id) })}
                />
              ))}
            </ul>
          )}
        </div>
        <Select
          aria-label={t("album.decade")}
          className="w-auto"
          value={decade ?? ""}
          onChange={(e) => update({ decade: e.target.value || null })}
        >
          <option value="">{t("album.allDecades")}</option>
          {album.decades.map((d) => (
            <option key={d} value={d}>
              {t("album.decadeValue", { decade: d, end: d + 9 })}
            </option>
          ))}
        </Select>
        <Select
          aria-label={t("album.sort")}
          className="w-auto"
          value={sort}
          onChange={(e) => update({ sort: e.target.value === "newest" ? "newest" : null })}
        >
          <option value="date">{t("album.sortDate")}</option>
          <option value="newest">{t("album.sortNewest")}</option>
        </Select>
        <Input
          type="search"
          className="w-auto min-w-48"
          aria-label={t("album.search")}
          placeholder={t("album.search")}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <div
          role="group"
          aria-label={t("album.view")}
          className="border-bark-100 inline-flex overflow-hidden rounded-full border text-sm"
        >
          <button
            type="button"
            aria-pressed={view === "carousel"}
            className={toggleButton(view === "carousel")}
            onClick={() => update({ view: null })}
          >
            {t("album.viewCarousel")}
          </button>
          <button
            type="button"
            aria-pressed={view === "grid"}
            className={toggleButton(view === "grid")}
            onClick={() => update({ view: "grid" })}
          >
            {t("album.viewGrid")}
          </button>
        </div>
      </div>

      <ErrorAlert error={album.error} />
      {album.isPending && <TextSkeleton lines={4} label={t("common.loading")} />}
      {!album.isPending && album.total === 0 && (
        <EmptyState
          title={filtered ? t("album.noMatch") : t("album.emptyTitle")}
          hint={filtered ? undefined : t("album.emptyHint")}
        />
      )}

      {album.total > 0 && (
        <p className="text-bark-700 text-sm">{t("album.count", { count: album.total })}</p>
      )}
      {album.total > 0 && view === "carousel" && (
        <div className="border-bark-100 bg-surface rounded-3xl border p-3 shadow-sm sm:p-5">
          <AlbumCarousel
            key={`${personIds.join()}|${decade}|${sort}|${q}`}
            items={album.items}
            total={album.total}
            hasMore={Boolean(hasNextPage)}
            onNearEnd={more}
            onOpen={setViewing}
            personLink={personLink}
            label={t("album.title")}
            size="large"
            personActions={{
              onFilter: (p) => update({ person: [...new Set([...personIds, p.person_id])] }),
            }}
          />
        </div>
      )}
      {album.total > 0 && view === "grid" && (
        <>
          <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
            {album.items.map((item, i) => (
              <li
                key={item.id}
                className="border-bark-100 bg-surface rounded-2xl border p-2.5 shadow-sm"
              >
                <PhotoCaption item={item} lines={2} className="mb-2" />
                <button
                  type="button"
                  title={t("album.openPhoto")}
                  onClick={() => setViewing(i)}
                  className="bg-bark-100 hover:ring-leaf-600 block aspect-[4/3] w-full overflow-hidden rounded-xl hover:ring-2"
                >
                  <img
                    src={item.urls.thumb ?? item.urls.web}
                    alt={photoAlt(item, t)}
                    loading="lazy"
                    className="size-full object-cover"
                  />
                </button>
              </li>
            ))}
          </ul>
          {hasNextPage && (
            <div className="flex justify-center">
              <Button variant="secondary" busy={isFetchingNextPage} onClick={more}>
                {t("album.loadMore")}
              </Button>
            </div>
          )}
        </>
      )}

      {viewing !== null && (
        <Lightbox
          items={album.items}
          total={album.total}
          index={viewing}
          onIndex={(i) => {
            setViewing(i);
            if (i >= album.items.length - 3) more();
          }}
          onClose={() => setViewing(null)}
          personLink={personLink}
          comments={tree.data ? { treeId, role: tree.data.my_role } : undefined}
        />
      )}
    </div>
  );
}

function PersonChip({
  treeId,
  personId,
  onRemove,
}: {
  treeId: string;
  personId: string;
  onRemove: () => void;
}) {
  const { t } = useTranslation();
  const person = usePerson(treeId, personId);
  return (
    <li className="border-bark-100 bg-bark-50 inline-flex items-center gap-2 rounded-full border px-3 py-1 text-sm">
      {person.data?.display_name ?? "…"}
      <button
        type="button"
        aria-label={t("insights.clearPerson")}
        className="text-bark-700 hover:text-bark-900"
        onClick={onRemove}
      >
        ✕
      </button>
    </li>
  );
}
