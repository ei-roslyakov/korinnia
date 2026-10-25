import { useCallback, useEffect, useId, useRef, useState, type KeyboardEvent } from "react";
import { createPortal } from "react-dom";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import { Spinner } from "@/components/ui";
import { slug } from "@/features/help/slug";
import { Lightbox } from "@/features/media/Lightbox";
import type { MediaItem } from "@/lib/genealogy";
import type { Role } from "@/lib/types";

import { AlbumCarousel } from "./AlbumCarousel";
import { useAlbum } from "./api";

type Tagged = MediaItem["people"][number];

/** "Family album" button for the tree header; the album opens in a popup over the tree. */
export function AlbumButton({
  treeId,
  role,
  canEdit,
  onShowOnTree,
}: {
  treeId: string;
  role: Role;
  canEdit: boolean;
  onShowOnTree: (personId: string) => void;
}) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const button = useRef<HTMLButtonElement>(null);
  const album = useAlbum(treeId);

  const close = useCallback(() => {
    setOpen(false);
    button.current?.focus();
  }, []);

  return (
    <>
      <button
        ref={button}
        type="button"
        aria-haspopup="dialog"
        onClick={() => setOpen(true)}
        className="border-bark-100 bg-surface hover:border-leaf-600 inline-flex shrink-0 items-center gap-1.5 rounded-full border px-3 py-1 text-sm whitespace-nowrap"
      >
        <span aria-hidden="true">🖼</span>
        {t("album.title")}
        {album.total > 0 && (
          <span className="bg-leaf-700 text-on-leaf rounded-full px-1.5 text-xs tabular-nums">
            {album.total}
          </span>
        )}
      </button>
      {open &&
        createPortal(
          <AlbumPopup
            treeId={treeId}
            role={role}
            canEdit={canEdit}
            onClose={close}
            onShowOnTree={(id) => {
              setOpen(false);
              onShowOnTree(id);
            }}
          />,
          document.body,
        )}
    </>
  );
}

function AlbumPopup({
  treeId,
  role,
  canEdit,
  onClose,
  onShowOnTree,
}: {
  treeId: string;
  role: Role;
  canEdit: boolean;
  onClose: () => void;
  onShowOnTree: (personId: string) => void;
}) {
  const { t, i18n } = useTranslation();
  const [person, setPerson] = useState<Tagged | null>(null);
  const [viewing, setViewing] = useState<number | null>(null);
  const album = useAlbum(treeId, { personIds: person ? [person.person_id] : [] });
  const panel = useRef<HTMLDivElement>(null);
  const titleId = useId();
  const { hasNextPage, isFetchingNextPage, fetchNextPage } = album;
  const more = useCallback(() => {
    if (hasNextPage && !isFetchingNextPage) void fetchNextPage();
  }, [hasNextPage, isFetchingNextPage, fetchNextPage]);
  const personLink = (id: string) => `/trees/${treeId}/people/${id}`;
  // The guide is in Ukrainian and English; other languages read the English one.
  const guideLang = i18n.resolvedLanguage === "uk" ? "uk" : "en";
  const guideHash = slug(i18n.getFixedT(guideLang)("album.title"));

  useEffect(() => panel.current?.focus(), []);

  const onKeyDown = (e: KeyboardEvent) => {
    // Esc closes the full-screen photo first (it listens itself), then the album.
    if (e.key === "Escape" && viewing === null) {
      e.stopPropagation();
      onClose();
    }
    // Keep Tab inside the popup.
    if (e.key === "Tab" && panel.current) {
      const focusable = [
        ...panel.current.querySelectorAll<HTMLElement>(
          'a[href], button:not([disabled]), input, select, textarea, [tabindex="0"]',
        ),
      ].filter((el) => !el.closest("[inert]"));
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (!first || !last) return;
      if (
        e.shiftKey &&
        (document.activeElement === first || document.activeElement === panel.current)
      ) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    }
  };

  return (
    <div
      className="fixed inset-0 z-40 flex items-end justify-center bg-black/50 p-0 backdrop-blur-[2px] motion-safe:animate-[album-fade_150ms_ease-out] sm:items-center sm:p-4"
      onMouseDown={(e) => e.target === e.currentTarget && onClose()}
    >
      <div
        ref={panel}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        onKeyDown={onKeyDown}
        className="border-bark-100 text-bark-900 flex max-h-[94dvh] w-full max-w-4xl flex-col overflow-hidden rounded-t-3xl border bg-[var(--k-surface-solid)] shadow-2xl outline-none motion-safe:animate-[album-in_200ms_ease-out] sm:rounded-3xl"
      >
        <div className="flex items-center gap-3 px-5 pt-4 pb-2">
          <h2 id={titleId} className="font-serif text-lg font-semibold">
            {t("album.title")}
          </h2>
          {album.total > 0 && (
            <span className="text-bark-700 text-sm">
              {t("album.count", { count: album.total })}
            </span>
          )}
          <div className="ml-auto flex items-center gap-1">
            <Link
              to={`/trees/${treeId}/album`}
              className="text-leaf-700 hover:bg-bark-50 rounded-full px-3 py-1 text-sm"
            >
              {t("album.showAll")} ⤢
            </Link>
            <button
              type="button"
              onClick={onClose}
              aria-label={t("canvas.close")}
              className="text-bark-700 hover:bg-bark-50 hover:text-bark-900 flex size-9 items-center justify-center rounded-full text-lg"
            >
              ✕
            </button>
          </div>
        </div>
        {person && (
          <div className="px-5 pb-2">
            <span className="bg-leaf-700 text-on-leaf inline-flex items-center gap-2 rounded-full py-1 pr-1 pl-3 text-sm">
              {t("album.filteredBy", { name: person.display_name })}
              <button
                type="button"
                aria-label={t("album.clearFilter")}
                onClick={() => setPerson(null)}
                className="flex size-6 items-center justify-center rounded-full hover:bg-black/20"
              >
                ✕
              </button>
            </span>
          </div>
        )}
        <div className="min-h-0 flex-1 overflow-y-auto px-4 pb-5 sm:px-5">
          {album.isPending ? (
            <div className="flex justify-center py-16">
              <Spinner />
            </div>
          ) : album.total === 0 ? (
            <div className="bg-bark-50 border-bark-100 rounded-2xl border border-dashed px-6 py-10 text-center text-sm">
              <p className="font-serif text-base font-semibold">{t("album.emptyTitle")}</p>
              <p className="text-bark-700 mt-1">{t("album.emptyHint")}</p>
              {canEdit && (
                <Link
                  to={`/help#${guideHash}`}
                  className="text-leaf-700 mt-3 inline-block underline"
                >
                  {t("album.emptyHowTo")}
                </Link>
              )}
            </div>
          ) : (
            <AlbumCarousel
              key={person?.person_id ?? "all"}
              items={album.items}
              total={album.total}
              hasMore={Boolean(hasNextPage)}
              onNearEnd={more}
              onOpen={setViewing}
              personLink={personLink}
              personActions={{ onFilter: setPerson, onShowOnTree }}
              label={t("album.title")}
            />
          )}
        </div>
      </div>
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
          comments={{ treeId, role }}
        />
      )}
    </div>
  );
}
