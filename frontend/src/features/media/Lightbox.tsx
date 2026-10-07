import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import { formatPartialDate } from "@/lib/dates";
import type { MediaItem } from "@/lib/genealogy";

/** Full-screen viewer for photos, scans and videos with prev/next and face tags. */
export function Lightbox({
  items,
  index,
  onIndex,
  onClose,
  personLink,
}: {
  items: MediaItem[];
  index: number;
  onIndex: (i: number) => void;
  onClose: () => void;
  personLink: (id: string) => string;
}) {
  const { t, i18n } = useTranslation();
  const [showTags, setShowTags] = useState(true);
  const item = items[index];

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
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
          {index + 1} / {items.length}
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
      <div className="relative flex min-h-0 flex-1 items-center justify-center px-12">
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
              alt={item.title ?? item.original_filename}
              className="block max-h-[calc(100dvh-10rem)] max-w-full object-contain"
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
      <div className="space-y-1 px-4 py-3 text-sm">
        <div className="font-medium">{item.title ?? item.original_filename}</div>
        <div className="text-white/70">
          {[formatPartialDate(item.date, t, i18n.language), item.place?.name]
            .filter(Boolean)
            .join(" · ")}
        </div>
        {item.description && (
          <p className="whitespace-pre-line text-white/80">{item.description}</p>
        )}
        {item.people.length > 0 && (
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
        )}
      </div>
    </div>
  );
}
