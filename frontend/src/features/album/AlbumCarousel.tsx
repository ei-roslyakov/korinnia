import useEmblaCarousel from "embla-carousel-react";
import { useCallback, useEffect, useRef, useState, type KeyboardEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import { photoAlt } from "@/features/media/photoAlt";
import { PhotoCaption } from "@/features/media/PhotoCaption";
import type { MediaItem } from "@/lib/genealogy";

import { useDocumentHidden, usePrefersReducedMotion } from "./hooks";

export const AUTOPLAY_MS = 6000;
/** Load the next page when this close to the last loaded photo. */
const NEAR_END = 3;

/** The caption has a fixed height, so the photo — and the arrows on it — never jump. */
const SIZES = {
  popup: "[--cap:6rem] [--photo:36dvh] sm:[--photo:48dvh]",
  large: "[--cap:7rem] [--photo:45vh] sm:[--photo:56vh]",
};

type Tagged = MediaItem["people"][number];

/** What a person chip offers besides opening the person's page. */
export interface PersonActions {
  /** Show only the photos of this person. */
  onFilter?: (person: Tagged) => void;
  /** Close the album and centre the tree on this person. */
  onShowOnTree?: (personId: string) => void;
}

/**
 * Photos one at a time with the description above each: swipe (Embla), arrows on the photo,
 * ←/→ keys, thumbnails and an optional slideshow. Only the shown photo and its neighbours load.
 */
export function AlbumCarousel({
  items,
  total,
  hasMore,
  onNearEnd,
  onOpen,
  personLink,
  personActions,
  label,
  size = "popup",
  thumbnails = true,
}: {
  items: MediaItem[];
  total: number;
  hasMore: boolean;
  onNearEnd: () => void;
  onOpen: (index: number) => void;
  personLink: (id: string) => string;
  personActions?: PersonActions;
  label: string;
  size?: keyof typeof SIZES;
  thumbnails?: boolean;
}) {
  const { t } = useTranslation();
  const reduced = usePrefersReducedMotion();
  const hidden = useDocumentHidden();
  const [viewportRef, embla] = useEmblaCarousel({ align: "start", containScroll: false });
  const [selected, setSelected] = useState(0);
  const [canPrev, setCanPrev] = useState(false);
  const [canNext, setCanNext] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [hovered, setHovered] = useState(false);
  const [focused, setFocused] = useState(false);
  const thumbsRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!embla) return;
    const sync = () => {
      setSelected(embla.selectedScrollSnap());
      setCanPrev(embla.canScrollPrev());
      setCanNext(embla.canScrollNext());
    };
    sync();
    embla.on("select", sync).on("reInit", sync);
    return () => {
      embla.off("select", sync).off("reInit", sync);
    };
  }, [embla]);

  // Fetch more before the viewer reaches the end of what is loaded.
  useEffect(() => {
    if (hasMore && selected >= items.length - NEAR_END) onNearEnd();
  }, [hasMore, selected, items.length, onNearEnd]);

  // Keep the current thumbnail in view (scrolling only the strip, never the page).
  useEffect(() => {
    const strip = thumbsRef.current;
    const thumb = strip?.children[selected] as HTMLElement | undefined;
    if (!strip || !thumb) return;
    strip.scrollTo?.({
      left: thumb.offsetLeft - strip.clientWidth / 2 + thumb.clientWidth / 2,
      behavior: reduced ? "auto" : "smooth",
    });
  }, [selected, reduced]);

  const go = useCallback((i: number) => embla?.scrollTo(i, reduced), [embla, reduced]);
  const prev = () => go(selected - 1);
  const next = () => go(selected + 1);

  const paused = !playing || reduced || hovered || focused || hidden;
  useEffect(() => {
    if (paused || !embla) return;
    const id = window.setInterval(() => {
      if (embla.canScrollNext()) embla.scrollTo(embla.selectedScrollSnap() + 1);
      else if (!hasMore) embla.scrollTo(0);
    }, AUTOPLAY_MS);
    return () => window.clearInterval(id);
  }, [paused, embla, hasMore]);

  const onKeyDown = (e: KeyboardEvent) => {
    if (e.target instanceof HTMLElement && e.target.closest("input, textarea, select")) return;
    if (e.key === "ArrowRight" && canNext) {
      e.preventDefault();
      next();
    } else if (e.key === "ArrowLeft" && canPrev) {
      e.preventDefault();
      prev();
    }
  };

  // Hovering over or focusing the photos pauses the slideshow; the controls do not.
  const pauseHandlers = {
    onMouseEnter: () => setHovered(true),
    onMouseLeave: () => setHovered(false),
    onFocus: () => setFocused(true),
    onBlur: (e: React.FocusEvent) => {
      if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setFocused(false);
    },
  };
  const count = Math.max(total, items.length);
  const arrow =
    "absolute top-[calc(var(--cap)+0.5rem+var(--photo)/2)] z-[1] flex size-10 -translate-y-1/2 items-center justify-center rounded-full bg-black/45 text-2xl leading-none text-white shadow-lg backdrop-blur-sm transition hover:bg-black/65 focus-visible:ring-2 focus-visible:ring-white disabled:hidden";

  return (
    <section
      aria-roledescription={t("album.carousel")}
      aria-label={label}
      onKeyDown={onKeyDown}
      className={SIZES[size]}
    >
      <div className="relative" {...pauseHandlers}>
        <div ref={viewportRef} className="overflow-hidden">
          <div className="flex touch-pan-y">
            {items.map((item, i) => {
              const near = Math.abs(i - selected) <= 1;
              return (
                <div
                  key={item.id}
                  role="group"
                  aria-roledescription={t("album.slide")}
                  aria-label={t("album.slideOf", { n: i + 1, total: count })}
                  inert={i !== selected}
                  className="min-w-0 flex-[0_0_100%] px-1"
                >
                  <div className="mb-2 h-[var(--cap)] overflow-y-auto">
                    <PhotoCaption item={item} lines={size === "large" ? 3 : 2} />
                  </div>
                  <button
                    type="button"
                    title={t("album.openPhoto")}
                    onClick={() => onOpen(i)}
                    className="bg-bark-100 focus-visible:ring-leaf-600 block h-[var(--photo)] w-full overflow-hidden rounded-2xl shadow-inner focus-visible:ring-2"
                  >
                    {near && (
                      <img
                        src={item.urls.web}
                        srcSet={
                          item.urls.thumb
                            ? `${item.urls.thumb} 480w, ${item.urls.web} 2048w`
                            : undefined
                        }
                        sizes={size === "large" ? "(min-width: 1024px) 60rem, 100vw" : "100vw"}
                        alt={photoAlt(item, t)}
                        draggable={false}
                        className="size-full object-contain"
                      />
                    )}
                  </button>
                  {item.people.length > 0 && (
                    <ul aria-label={t("media.inPhoto")} className="mt-3 flex flex-wrap gap-1.5">
                      {item.people.map((p) => (
                        <PersonChip
                          key={p.person_id}
                          person={p}
                          href={personLink(p.person_id)}
                          actions={personActions}
                        />
                      ))}
                    </ul>
                  )}
                </div>
              );
            })}
          </div>
        </div>
        <button
          type="button"
          className={`${arrow} left-3`}
          aria-label={t("media.previous")}
          disabled={!canPrev}
          onClick={prev}
        >
          ‹
        </button>
        <button
          type="button"
          className={`${arrow} right-3`}
          aria-label={t("media.next")}
          disabled={!canNext}
          onClick={next}
        >
          ›
        </button>
      </div>

      {thumbnails && items.length > 1 && (
        <div
          ref={thumbsRef}
          role="group"
          aria-label={t("album.thumbnails")}
          className="relative mt-3 flex gap-2 overflow-x-auto px-1 py-1"
          {...pauseHandlers}
        >
          {items.map((item, i) => (
            <button
              key={item.id}
              type="button"
              aria-label={t("album.goTo", { n: i + 1 })}
              aria-current={i === selected ? "true" : undefined}
              onClick={() => go(i)}
              className={`bg-bark-100 size-14 shrink-0 overflow-hidden rounded-xl transition ${i === selected ? "ring-leaf-600 ring-2 ring-offset-2 ring-offset-[var(--k-surface-solid)]" : "opacity-60 hover:opacity-100"}`}
            >
              {item.urls.thumb && (
                <img
                  src={item.urls.thumb}
                  alt=""
                  loading="lazy"
                  className="size-full object-cover"
                />
              )}
            </button>
          ))}
        </div>
      )}

      <div className="mt-2 flex items-center justify-between gap-2 text-sm">
        <span
          aria-live={paused ? "polite" : "off"}
          className="bg-bark-50 border-bark-100 text-bark-700 rounded-full border px-3 py-0.5 tabular-nums"
        >
          {t("album.slideOf", { n: selected + 1, total: count })}
        </span>
        {!reduced && items.length > 1 && (
          <button
            type="button"
            className="border-bark-100 bg-surface text-leaf-700 hover:border-leaf-600 rounded-full border px-3 py-0.5"
            aria-pressed={playing}
            onClick={() => setPlaying((v) => !v)}
          >
            {playing ? `❚❚ ${t("album.pause")}` : `▶ ${t("album.play")}`}
          </button>
        )}
      </div>
    </section>
  );
}

/** A person in the photo: a link to their page, or a small menu when there is more to do. */
function PersonChip({
  person,
  href,
  actions,
}: {
  person: Tagged;
  href: string;
  actions?: PersonActions;
}) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLLIElement>(null);
  const chip =
    "border-bark-100 bg-bark-50 text-leaf-700 hover:border-leaf-600 inline-flex items-center gap-1 rounded-full border px-3 py-1 text-xs";

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  if (!actions?.onFilter && !actions?.onShowOnTree) {
    return (
      <li>
        <Link to={href} className={chip}>
          {person.display_name}
        </Link>
      </li>
    );
  }
  const item =
    "hover:bg-bark-50 block w-full rounded-lg px-3 py-1.5 text-left whitespace-nowrap text-bark-900";
  return (
    <li
      ref={ref}
      className="relative"
      onKeyDown={(e) => {
        if (e.key === "Escape" && open) {
          e.stopPropagation();
          setOpen(false);
        }
      }}
    >
      <button type="button" aria-expanded={open} className={chip} onClick={() => setOpen(!open)}>
        {person.display_name}
        <span aria-hidden="true" className="text-[0.6rem]">
          ▾
        </span>
      </button>
      {open && (
        <div className="border-bark-100 absolute bottom-full left-0 z-10 mb-1 min-w-44 rounded-xl border bg-[var(--k-surface-solid)] p-1 text-sm shadow-xl">
          {actions.onFilter && (
            <button
              type="button"
              className={item}
              onClick={() => {
                setOpen(false);
                actions.onFilter!(person);
              }}
            >
              {t("album.onlyTheirPhotos")}
            </button>
          )}
          {actions.onShowOnTree && (
            <button
              type="button"
              className={item}
              onClick={() => actions.onShowOnTree!(person.person_id)}
            >
              {t("album.showOnTree")}
            </button>
          )}
          <Link to={href} className={item}>
            {t("album.openPersonPage")}
          </Link>
        </div>
      )}
    </li>
  );
}
