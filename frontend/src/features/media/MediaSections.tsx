import { useState } from "react";
import { useTranslation } from "react-i18next";

import { formatPartialDate } from "@/lib/dates";
import { formatSize } from "@/lib/format";
import { isVisual, type MediaItem } from "@/lib/genealogy";
import type { Role } from "@/lib/types";

import { Lightbox } from "./Lightbox";

function Pending() {
  const { t } = useTranslation();
  return <span className="text-bark-700 text-xs">{t("media.processing")}</span>;
}

/** Person media: photo gallery (lightbox), documents, recordings, videos. */
export function MediaSections({
  media,
  personLink,
  Section,
  comments,
}: {
  media: MediaItem[];
  personLink: (id: string) => string;
  comments?: { treeId: string; role: Role };
  Section: (props: { title: string; children: React.ReactNode }) => React.ReactNode;
}) {
  const { t, i18n } = useTranslation();
  const [open, setOpen] = useState<number | null>(null);
  const photos = media.filter((m) => m.kind === "photo");
  const viewable = media.filter((m) => isVisual(m) || m.kind === "video");
  const documents = media.filter(
    (m) => m.kind === "document_scan" || m.kind === "pdf" || m.kind === "other",
  );
  const audio = media.filter((m) => m.kind === "audio");
  const videos = media.filter((m) => m.kind === "video");
  const openItem = (m: MediaItem) => setOpen(viewable.findIndex((v) => v.id === m.id));
  const caption = (m: MediaItem) =>
    [m.title ?? m.original_filename, formatPartialDate(m.date, t, i18n.language)]
      .filter(Boolean)
      .join(" · ");

  if (media.length === 0) return null;
  return (
    <>
      {photos.length > 0 && (
        <Section title={t("media.photos")}>
          <ul className="grid grid-cols-3 gap-2 sm:grid-cols-4">
            {photos.map((m) => (
              <li key={m.id}>
                <button
                  type="button"
                  className="bg-bark-100 block aspect-square w-full overflow-hidden rounded-md"
                  onClick={() => openItem(m)}
                  aria-label={caption(m)}
                  title={caption(m)}
                >
                  {m.urls.thumb ? (
                    <img
                      src={m.urls.thumb}
                      alt=""
                      loading="lazy"
                      className="size-full object-cover"
                    />
                  ) : (
                    <Pending />
                  )}
                </button>
              </li>
            ))}
          </ul>
        </Section>
      )}
      {documents.length > 0 && (
        <Section title={t("media.documents")}>
          <ul className="space-y-2">
            {documents.map((m) => (
              <li key={m.id} className="flex items-center gap-3 text-sm">
                <div className="border-bark-100 bg-bark-50 flex size-14 shrink-0 items-center justify-center overflow-hidden rounded border">
                  {m.urls.thumb ? (
                    <img
                      src={m.urls.thumb}
                      alt=""
                      loading="lazy"
                      className="size-full object-cover"
                    />
                  ) : (
                    "📄"
                  )}
                </div>
                <div className="min-w-0">
                  {m.kind === "document_scan" ? (
                    <button
                      type="button"
                      className="text-leaf-700 text-left hover:underline"
                      onClick={() => openItem(m)}
                    >
                      {caption(m)}
                    </button>
                  ) : (
                    <a
                      href={m.urls.original}
                      target="_blank"
                      rel="noopener"
                      className="text-leaf-700 hover:underline"
                    >
                      {caption(m)}
                    </a>
                  )}
                  <div className="text-bark-700 text-xs">
                    {t(`media.kinds.${m.kind}`)} · {formatSize(m.size)}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </Section>
      )}
      {audio.length > 0 && (
        <Section title={t("media.recordings")}>
          <ul className="space-y-3">
            {audio.map((m) => (
              <li key={m.id} className="space-y-1 text-sm">
                <div>{caption(m)}</div>
                <audio controls preload="none" src={m.urls.web} className="w-full" />
                {m.description && <p className="text-bark-700 text-xs">{m.description}</p>}
              </li>
            ))}
          </ul>
        </Section>
      )}
      {videos.length > 0 && (
        <Section title={t("media.videos")}>
          <ul className="grid gap-3 sm:grid-cols-2">
            {videos.map((m) => (
              <li key={m.id} className="space-y-1 text-sm">
                {m.processing_status === "pending" ? (
                  <Pending />
                ) : (
                  <video
                    controls
                    preload="none"
                    poster={m.urls.thumb ?? undefined}
                    src={m.urls.web}
                    className="w-full rounded-md"
                  />
                )}
                <div>{caption(m)}</div>
              </li>
            ))}
          </ul>
        </Section>
      )}
      {open !== null && (
        <Lightbox
          items={viewable}
          index={open}
          onIndex={setOpen}
          onClose={() => setOpen(null)}
          personLink={personLink}
          comments={comments}
        />
      )}
    </>
  );
}
