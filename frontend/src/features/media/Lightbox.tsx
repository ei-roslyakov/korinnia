import { useEffect, useRef, useState, type PointerEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import { CommentsThread } from "@/features/collab/CommentsThread";
import type { MediaItem } from "@/lib/genealogy";
import { atLeast, type Role } from "@/lib/types";

import { photoAlt } from "./photoAlt";
import { PhotoCaption } from "./PhotoCaption";

/** A horizontal move of at least this many pixels (and more sideways than up) is a swipe. */
const SWIPE_PX = 50;

/** Full-screen viewer for photos, scans and videos with prev/next, swipe and face tags. */
export function Lightbox({
  items,
  index,
  onIndex,
  onClose,
  personLink,
  comments,
  total,
}: {
  items: MediaItem[];
  index: number;
  onIndex: (i: number) => void;
  onClose: () => void;
  personLink: (id: string) => string;
  /** Tree members can read and (contributor+) write comments on the item. */
  comments?: { treeId: string; role: Role };
  /** All items, when `items` is only what is loaded so far (the family album). */
  total?: number;
}) {
  const { t } = useTranslation();
  const [showTags, setShowTags] = useState(true);
  const [showComments, setShowComments] = useState(false);
  const swipeStart = useRef<{ x: number; y: number } | null>(null);
  const item = items[index];

  // One item is shown at a time, so a swipe only needs its direction (no drag-follow).
  const onPointerDown = (e: PointerEvent) => {
    swipeStart.current = { x: e.clientX, y: e.clientY };
  };
  const onPointerUp = (e: PointerEvent) => {
    const start = swipeStart.current;
    swipeStart.current = null;
    if (!start) return;
    const dx = e.clientX - start.x;
    if (Math.abs(dx) < SWIPE_PX || Math.abs(dx) < Math.abs(e.clientY - start.y)) return;
    if (dx < 0 && index < items.length - 1) onIndex(index + 1);
    if (dx > 0 && index > 0) onIndex(index - 1);
  };

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      // Arrow keys move the cursor while writing a comment.
      if (e.target instanceof HTMLElement && e.target.closest("input, textarea, select")) return;
      if (e.key === "ArrowRight" && index < items.length - 1) onIndex(index + 1);
      if (e.key === "ArrowLeft" && index > 0) onIndex(index - 1);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [index, items.length, onClose, onIndex]);

  if (!item) return null;
  const tagged = item.people.filter((p) => p.region);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={item.title ?? item.original_filename}
      className="fixed inset-0 z-50 flex flex-col bg-black/90 text-white"
    >
      <div className="flex items-center justify-between gap-2 px-4 py-2 text-sm">
        <span>
          {index + 1} / {Math.max(total ?? 0, items.length)}
        </span>
        <div className="flex items-center gap-3">
          {tagged.length > 0 && (
            <label className="flex items-center gap-1">
              <input
                type="checkbox"
                checked={showTags}
                onChange={(e) => setShowTags(e.target.checked)}
              />
              {t("media.showTags")}
            </label>
          )}
          {comments && (
            <button
              type="button"
              aria-pressed={showComments}
              className="underline"
              onClick={() => setShowComments((v) => !v)}
            >
              {t("media.comments")}
            </button>
          )}
          <a href={item.urls.original} download={item.original_filename} className="underline">
            {t("media.downloadOriginal")}
          </a>
          <button
            type="button"
            onClick={onClose}
            aria-label={t("canvas.close")}
            className="text-xl"
          >
            ✕
          </button>
        </div>
      </div>
      <div className="flex min-h-0 flex-1">
        <div className="flex min-w-0 flex-1 flex-col">
          <PhotoCaption
            key={item.id}
            item={item}
            tone="dark"
            fallback={item.original_filename}
            className="mx-auto w-full max-w-3xl px-4 pb-2"
          />
          <div
            className="relative flex min-h-0 flex-1 touch-pan-y items-center justify-center px-12"
            onPointerDown={onPointerDown}
            onPointerUp={onPointerUp}
            onPointerCancel={() => (swipeStart.current = null)}
            data-testid="lightbox-stage"
          >
            {index > 0 && (
              <button
                type="button"
                className="absolute left-2 rounded-full bg-white/10 px-3 py-2 text-2xl hover:bg-white/20"
                aria-label={t("media.previous")}
                onClick={() => onIndex(index - 1)}
              >
                ‹
              </button>
            )}
            {item.kind === "video" ? (
              <video src={item.urls.web} controls autoPlay className="max-h-full max-w-full" />
            ) : (
              <div className="relative inline-block max-h-full">
                <img
                  src={item.urls.web}
                  alt={
                    item.kind === "photo"
                      ? photoAlt(item, t)
                      : (item.title ?? item.original_filename)
                  }
                  draggable={false}
                  className="block max-h-[calc(100dvh-12rem)] max-w-full object-contain"
                />
                {showTags &&
                  tagged.map((p) => (
                    <Link
                      key={p.person_id}
                      to={personLink(p.person_id)}
                      onClick={onClose}
                      className="group hover:border-leaf-600 absolute border-2 border-white/80 shadow-[0_0_0_1px_rgba(0,0,0,0.5)]"
                      style={{
                        left: `${p.region!.x * 100}%`,
                        top: `${p.region!.y * 100}%`,
                        width: `${p.region!.w * 100}%`,
                        height: `${p.region!.h * 100}%`,
                      }}
                    >
                      <span className="absolute top-full left-0 mt-1 rounded bg-black/70 px-1.5 py-0.5 text-xs whitespace-nowrap">
                        {p.display_name}
                      </span>
                    </Link>
                  ))}
              </div>
            )}
            {index < items.length - 1 && (
              <button
                type="button"
                className="absolute right-2 rounded-full bg-white/10 px-3 py-2 text-2xl hover:bg-white/20"
                aria-label={t("media.next")}
                onClick={() => onIndex(index + 1)}
              >
                ›
              </button>
            )}
          </div>
          {item.people.length > 0 && (
            <div className="px-4 py-3 text-sm">
              <div className="flex flex-wrap gap-x-2 text-white/80">
                {t("media.inPhoto")}:{" "}
                {item.people.map((p) => (
                  <Link
                    key={p.person_id}
                    to={personLink(p.person_id)}
                    onClick={onClose}
                    className="underline"
                  >
                    {p.display_name}
                  </Link>
                ))}
              </div>
            </div>
          )}
        </div>
        {comments && showComments && (
          <aside
            aria-label={t("media.comments")}
            className="text-bark-900 bg-surface w-full max-w-sm shrink-0 overflow-y-auto p-4 max-sm:absolute max-sm:inset-x-0 max-sm:bottom-0 max-sm:max-h-[60%] max-sm:max-w-none"
          >
            <CommentsThread
              treeId={comments.treeId}
              entityType="media"
              entityId={item.id}
              canWrite={atLeast(comments.role, "contributor")}
              canModerate={atLeast(comments.role, "editor")}
            />
          </aside>
        )}
      </div>
    </div>
  );
}
