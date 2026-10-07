import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { useTranslation } from "react-i18next";

import { Button, Dialog, ErrorAlert, Input, Spinner } from "@/components/ui";
import type { MediaItem } from "@/lib/genealogy";

import { uploadMedia, useTreeMedia } from "./api";

function Thumb({ m }: { m: MediaItem }) {
  return m.urls.thumb ? (
    <img src={m.urls.thumb} alt="" className="size-full object-cover" loading="lazy" />
  ) : (
    <span className="text-bark-700 flex size-full items-center justify-center p-1 text-center text-[10px] break-all">
      {m.original_filename}
    </span>
  );
}

/** Choose files from the tree's media library, or upload new ones (editors). */
export function MediaPicker({
  treeId,
  initial,
  canUpload,
  onDone,
  onClose,
}: {
  treeId: string;
  initial: MediaItem[];
  canUpload: boolean;
  onDone: (items: MediaItem[]) => void;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const [text, setText] = useState("");
  const [q, setQ] = useState("");
  const [chosen, setChosen] = useState<MediaItem[]>(initial);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const library = useTreeMedia(treeId, q);

  useEffect(() => {
    const id = setTimeout(() => setQ(text.trim()), 250);
    return () => clearTimeout(id);
  }, [text]);

  const toggle = (m: MediaItem) =>
    setChosen((c) => (c.some((x) => x.id === m.id) ? c.filter((x) => x.id !== m.id) : [...c, m]));

  const upload = async (files: FileList | null) => {
    if (!files?.length) return;
    setUploading(true);
    setError(null);
    try {
      for (const file of Array.from(files)) {
        const item = await uploadMedia(treeId, file, { allowDuplicate: false }).catch(
          (e: unknown) => {
            setError(e);
            return null;
          },
        );
        if (item) setChosen((c) => [...c, item]);
      }
      await library.refetch();
    } finally {
      setUploading(false);
    }
  };

  const items = library.data?.items ?? [];
  return (
    <Dialog open title={t("media.picker.title")} onClose={onClose}>
      <div className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <Input
            type="search"
            className="flex-1"
            aria-label={t("media.picker.search")}
            placeholder={t("media.picker.search")}
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
          {canUpload && (
            <label className="border-bark-100 hover:bg-bark-50 cursor-pointer rounded-md border px-3 py-1.5 text-sm">
              {uploading ? <Spinner /> : t("media.picker.upload")}
              <input
                type="file"
                multiple
                className="sr-only"
                onChange={(e) => void upload(e.target.files)}
              />
            </label>
          )}
        </div>
        <ErrorAlert error={error ?? library.error} />
        {library.isPending && <Spinner />}
        {library.data && items.length === 0 && (
          <p className="text-bark-700 text-sm">{t("media.picker.empty")}</p>
        )}
        <ul className="grid max-h-[50vh] grid-cols-3 gap-2 overflow-y-auto sm:grid-cols-4">
          {items.map((m) => {
            const on = chosen.some((x) => x.id === m.id);
            return (
              <li key={m.id}>
                <button
                  type="button"
                  aria-pressed={on}
                  title={m.title ?? m.original_filename}
                  onClick={() => toggle(m)}
                  className={`bg-bark-50 relative block aspect-square w-full overflow-hidden rounded-md border-2 ${on ? "border-leaf-600" : "border-transparent"}`}
                >
                  <Thumb m={m} />
                  <span className="sr-only">{m.title ?? m.original_filename}</span>
                  {on && (
                    <span className="bg-leaf-700 text-on-leaf absolute top-1 right-1 rounded-full px-1.5 text-xs">
                      ✓
                    </span>
                  )}
                </button>
              </li>
            );
          })}
        </ul>
        <div className="flex items-center justify-between gap-2">
          <span className="text-bark-700 text-sm">
            {t("media.picker.selected", { count: chosen.length })}
          </span>
          <div className="flex gap-2">
            <Button variant="secondary" onClick={onClose}>
              {t("common.cancel")}
            </Button>
            <Button onClick={() => onDone(chosen)}>{t("media.picker.done")}</Button>
          </div>
        </div>
      </div>
    </Dialog>
  );
}

/** Attached media as removable thumbnails plus a button opening the picker. */
export function MediaAttach({
  treeId,
  label,
  value,
  onChange,
  canUpload,
}: {
  treeId: string;
  label: string;
  value: MediaItem[];
  onChange: (items: MediaItem[]) => void;
  canUpload: boolean;
}) {
  const { t } = useTranslation();
  const [picking, setPicking] = useState(false);
  return (
    <div className="space-y-2">
      <span className="block text-sm font-medium">{label}</span>
      {value.length > 0 && (
        <ul className="flex flex-wrap gap-2">
          {value.map((m) => (
            <li
              key={m.id}
              className="border-bark-100 relative size-16 overflow-hidden rounded-md border"
              title={m.title ?? m.original_filename}
            >
              <Thumb m={m} />
              <button
                type="button"
                aria-label={`${t("common.remove")}: ${m.title ?? m.original_filename}`}
                className="absolute top-0 right-0 rounded-bl bg-black/60 px-1 text-xs text-white"
                onClick={() => onChange(value.filter((x) => x.id !== m.id))}
              >
                ✕
              </button>
            </li>
          ))}
        </ul>
      )}
      <Button variant="secondary" onClick={() => setPicking(true)}>
        + {t("media.picker.add")}
      </Button>
      {/* Portalled: a modal dialog is never nested inside another one in the DOM (D67). */}
      {picking &&
        createPortal(
          <MediaPicker
            treeId={treeId}
            initial={value}
            canUpload={canUpload}
            onClose={() => setPicking(false)}
            onDone={(items) => {
              onChange(items);
              setPicking(false);
            }}
          />,
          document.body,
        )}
    </div>
  );
}
