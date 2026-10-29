import { useLayoutEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router";

import { formatPartialDate } from "@/lib/dates";
import type { MediaItem } from "@/lib/genealogy";

/** What is shown above a photo: the title (bold), the description cut to a few lines with
 *  "more", then date · place. `fallback` stands in when there is no title or description. */
export function PhotoCaption({
  item,
  lines = 3,
  tone = "page",
  fallback,
  className = "",
}: {
  item: MediaItem;
  lines?: 2 | 3;
  tone?: "page" | "dark";
  fallback?: string;
  className?: string;
}) {
  const { t, i18n } = useTranslation();
  const [expanded, setExpanded] = useState(false);
  const [overflows, setOverflows] = useState(false);
  const ref = useRef<HTMLParagraphElement>(null);

  useLayoutEffect(() => {
    const el = ref.current;
    if (!el || expanded) return;
    const check = () => setOverflows(el.scrollHeight > el.clientHeight + 1);
    check();
    if (typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(check);
    observer.observe(el);
    return () => observer.disconnect();
  }, [item.description, expanded]);

  const { treeId } = useParams();
  const date = formatPartialDate(item.date, t, i18n.language);
  const muted = tone === "dark" ? "text-white/70" : "text-bark-700";
  const title = item.title ?? (item.description ? null : fallback);
  const clamp = lines === 2 ? "line-clamp-2" : "line-clamp-3";

  return (
    <div className={`text-sm ${className}`} data-testid="photo-caption">
      {title && <strong className="block font-semibold">{title}</strong>}
      {item.description && (
        <div className={expanded ? "max-h-40 overflow-y-auto" : ""}>
          <p ref={ref} className={`whitespace-pre-line ${expanded ? "" : clamp}`}>
            {item.description}
          </p>
          {(overflows || expanded) && (
            <button
              type="button"
              aria-expanded={expanded}
              className={`text-xs underline ${muted}`}
              onClick={() => setExpanded((v) => !v)}
            >
              {expanded ? t("album.less") : t("album.more")}
            </button>
          )}
        </div>
      )}
      {(date || item.place) && (
        <div className={`text-xs ${muted}`}>
          {date}
          {date && item.place && " · "}
          {item.place &&
            (treeId ? (
              <Link to={`/trees/${treeId}/places/${item.place.id}`} className="underline">
                {item.place.name}
              </Link>
            ) : (
              item.place.name
            ))}
        </div>
      )}
    </div>
  );
}
