import { useState, type DragEvent, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import {
  Alert,
  Badge,
  Button,
  Card,
  Dialog,
  ErrorAlert,
  Field,
  Input,
  Select,
  TextArea,
} from "@/components/ui";
import { useUpdatePerson } from "@/features/builder/api";
import { fromPartialDate, toPayload } from "@/features/builder/helpers";
import { PartialDateInput } from "@/features/builder/PartialDateInput";
import { PlaceInput } from "@/features/builder/PlaceInput";
import { PersonCombobox } from "@/features/person/PersonCombobox";
import { ApiError } from "@/lib/api";
import { formatSize } from "@/lib/format";
import {
  isVisual,
  type MediaItem,
  type PartialDateInput as DateValue,
  type PersonDetail,
  type PlaceSummary,
  type Region,
} from "@/lib/genealogy";
import { useErrorMessage } from "@/lib/hooks";

import {
  uploadMedia,
  useDeleteMedia,
  useReorderMedia,
  useReprocessMedia,
  useTagPerson,
  useUntagPerson,
  useUpdateMedia,
} from "./api";
import { RegionSelector } from "./RegionSelector";

interface UploadState {
  key: string;
  name: string;
  progress: number;
  error?: unknown;
  duplicateOf?: string;
  file: File;
}

/** Media of one person in the editor: upload, order, metadata, tags, portrait crop. */
export function MediaTab({
  treeId,
  person,
  onChanged,
}: {
  treeId: string;
  person: PersonDetail;
  onChanged: () => void;
}) {
  const { t } = useTranslation();
  const errorMessage = useErrorMessage();
  const [uploads, setUploads] = useState<UploadState[]>([]);
  const [asDocument, setAsDocument] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [editing, setEditing] = useState<MediaItem | null>(null);
  const [tagging, setTagging] = useState<MediaItem | null>(null);
  const [cropping, setCropping] = useState<MediaItem | null>(null);
  const reorder = useReorderMedia(treeId, person.id);
  const untag = useUntagPerson(treeId);
  const tag = useTagPerson(treeId);
  const del = useDeleteMedia(treeId);
  const reprocess = useReprocessMedia(treeId);
  const media = person.media;

  const setUpload = (key: string, patch: Partial<UploadState>) =>
    setUploads((list) => list.map((u) => (u.key === key ? { ...u, ...patch } : u)));

  const send = async (file: File, key: string, allowDuplicate = false) => {
    try {
      await uploadMedia(treeId, file, {
        personId: person.id,
        kind: asDocument ? "document_scan" : undefined,
        allowDuplicate,
        onProgress: (progress) => setUpload(key, { progress }),
      });
      setUploads((list) => list.filter((u) => u.key !== key));
      onChanged();
    } catch (err) {
      const dup =
        err instanceof ApiError && err.code === "duplicate_media"
          ? String((err.body as { media_id: string }).media_id)
          : undefined;
      setUpload(key, { error: err, duplicateOf: dup });
    }
  };

  const addFiles = (files: FileList | File[]) => {
    for (const file of Array.from(files)) {
      const key = `${file.name}-${file.size}-${Math.random()}`;
      setUploads((list) => [...list, { key, name: file.name, progress: 0, file }]);
      void send(file, key);
    }
  };

  const move = (i: number, delta: number) => {
    const ids = media.map((m) => m.id);
    const j = i + delta;
    if (j < 0 || j >= ids.length) return;
    [ids[i], ids[j]] = [ids[j]!, ids[i]!];
    reorder.mutate(ids);
  };

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragging(false);
    if (e.dataTransfer.files.length) addFiles(e.dataTransfer.files);
  };

  return (
    <div className="space-y-4">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={`rounded-lg border-2 border-dashed p-6 text-center ${dragging ? "border-leaf-600 bg-leaf-600/5" : "border-bark-100 bg-surface"}`}
      >
        <p className="text-bark-700 mb-3 text-sm">{t("media.dropHint")}</p>
        <label className="bg-leaf-700 hover:bg-leaf-600 text-on-leaf inline-flex cursor-pointer items-center rounded-md px-3 py-1.5 text-sm font-medium">
          {t("media.chooseFiles")}
          <input
            type="file"
            multiple
            className="sr-only"
            aria-label={t("media.chooseFiles")}
            accept="image/*,video/*,audio/*,application/pdf,.txt,.md,.doc,.docx,.odt,.rtf,.heic,.heif"
            onChange={(e) => {
              if (e.target.files) addFiles(e.target.files);
              e.target.value = "";
            }}
          />
        </label>
        <label className="mt-3 flex items-center justify-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={asDocument}
            onChange={(e) => setAsDocument(e.target.checked)}
          />
          {t("media.asDocument")}
        </label>
        <p className="text-bark-700 mt-2 text-xs">{t("media.originalsKept")}</p>
      </div>

      {uploads.length > 0 && (
        <ul className="space-y-2" aria-label={t("media.uploading")}>
          {uploads.map((u) => (
            <li key={u.key} className="border-bark-100 bg-surface rounded-md border p-2 text-sm">
              <div className="flex justify-between gap-2">
                <span className="truncate">{u.name}</span>
                {!u.error && <span>{Math.round(u.progress * 100)}%</span>}
              </div>
              {!u.error && (
                <div className="bg-bark-100 mt-1 h-1.5 rounded">
                  <div
                    className="bg-leaf-600 h-full rounded"
                    style={{ width: `${u.progress * 100}%` }}
                  />
                </div>
              )}
              {u.error !== undefined && (
                <div className="mt-1 flex flex-wrap items-center gap-2 text-red-700">
                  {errorMessage(u.error)}
                  {u.duplicateOf && (
                    <>
                      <Button
                        variant="secondary"
                        onClick={() => {
                          tag.mutate(
                            { mediaId: u.duplicateOf!, personId: person.id, region: null },
                            { onSuccess: onChanged },
                          );
                          setUploads((list) => list.filter((x) => x.key !== u.key));
                        }}
                      >
                        {t("media.linkExisting")}
                      </Button>
                      <Button
                        variant="ghost"
                        onClick={() => {
                          setUpload(u.key, {
                            error: undefined,
                            duplicateOf: undefined,
                            progress: 0,
                          });
                          void send(u.file, u.key, true);
                        }}
                      >
                        {t("media.uploadAnyway")}
                      </Button>
                    </>
                  )}
                  <Button
                    variant="ghost"
                    onClick={() => setUploads((list) => list.filter((x) => x.key !== u.key))}
                  >
                    {t("canvas.close")}
                  </Button>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}

      <ErrorAlert error={reorder.error ?? untag.error ?? del.error ?? reprocess.error} />
      {media.length === 0 && uploads.length === 0 && (
        <p className="text-bark-700 text-sm">{t("media.none")}</p>
      )}
      <ul className="space-y-2">
        {media.map((m, i) => (
          <li key={m.id}>
            <Card className="flex flex-wrap items-center gap-3">
              <div className="bg-bark-100 flex size-16 shrink-0 items-center justify-center overflow-hidden rounded">
                {m.urls.thumb ? (
                  <img src={m.urls.thumb} alt="" className="size-full object-cover" />
                ) : (
                  <span className="text-xs">{t(`media.kinds.${m.kind}`)}</span>
                )}
              </div>
              <div className="min-w-0 flex-1 text-sm">
                <div className="truncate font-medium">{m.title ?? m.original_filename}</div>
                <div className="text-bark-700 text-xs">
                  {t(`media.kinds.${m.kind}`)} · {formatSize(m.size)}
                  {m.people.length > 1 &&
                    ` · ${t("media.peopleCount", { count: m.people.length })}`}
                </div>
                <div className="mt-1 flex flex-wrap gap-1">
                  {person.primary_photo_id === m.id && (
                    <Badge tone="green">{t("media.portrait")}</Badge>
                  )}
                  {m.processing_status === "pending" && <Badge>{t("media.processing")}</Badge>}
                  {m.processing_status === "failed" && (
                    <Badge tone="red">{t("media.failed")}</Badge>
                  )}
                </div>
              </div>
              <div className="flex flex-wrap gap-1">
                <Button
                  variant="ghost"
                  aria-label={t("media.moveUp")}
                  disabled={i === 0}
                  onClick={() => move(i, -1)}
                >
                  ↑
                </Button>
                <Button
                  variant="ghost"
                  aria-label={t("media.moveDown")}
                  disabled={i === media.length - 1}
                  onClick={() => move(i, 1)}
                >
                  ↓
                </Button>
                <Button variant="secondary" onClick={() => setEditing(m)}>
                  {t("builder.edit")}
                </Button>
                {isVisual(m) && m.processing_status === "ready" && (
                  <>
                    <Button variant="secondary" onClick={() => setTagging(m)}>
                      {t("media.tagPeople")}
                    </Button>
                    <Button variant="secondary" onClick={() => setCropping(m)}>
                      {t("media.setPortrait")}
                    </Button>
                  </>
                )}
                {m.processing_status === "failed" && (
                  <Button variant="secondary" onClick={() => reprocess.mutate(m.id)}>
                    {t("media.retry")}
                  </Button>
                )}
                <Button
                  variant="ghost"
                  onClick={() => untag.mutate({ mediaId: m.id, personId: person.id })}
                >
                  {t("builder.family.unlink")}
                </Button>
                <Button
                  variant="ghost"
                  className="text-red-700"
                  onClick={() => window.confirm(t("media.confirmDelete")) && del.mutate(m.id)}
                >
                  {t("common.delete")}
                </Button>
              </div>
            </Card>
          </li>
        ))}
      </ul>
      {editing && (
        <MediaMetaDialog treeId={treeId} media={editing} onClose={() => setEditing(null)} />
      )}
      {tagging && (
        <TagDialog
          treeId={treeId}
          media={media.find((m) => m.id === tagging.id) ?? tagging}
          onClose={() => setTagging(null)}
        />
      )}
      {cropping && (
        <PortraitDialog
          treeId={treeId}
          person={person}
          media={cropping}
          onClose={() => setCropping(null)}
        />
      )}
    </div>
  );
}

function MediaMetaDialog({
  treeId,
  media,
  onClose,
}: {
  treeId: string;
  media: MediaItem;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const update = useUpdateMedia(treeId);
  const [title, setTitle] = useState(media.title ?? "");
  const [description, setDescription] = useState(media.description ?? "");
  const [date, setDate] = useState<DateValue | null>(fromPartialDate(media.date));
  const [place, setPlace] = useState<PlaceSummary | null>(media.place);
  const [kind, setKind] = useState(media.kind);

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    update.mutate(
      {
        id: media.id,
        title: title.trim() || null,
        description: description.trim() || null,
        date: toPayload(date),
        place_id: place?.id ?? null,
        kind,
      },
      { onSuccess: onClose },
    );
  };
  return (
    <Dialog open title={media.original_filename} onClose={onClose}>
      <form onSubmit={onSubmit} className="max-h-[75vh] space-y-3 overflow-y-auto pr-1">
        <Field label={t("builder.events.title")}>
          {(id) => (
            <Input
              id={id}
              maxLength={300}
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
          )}
        </Field>
        {isVisual(media) && (
          <Field label={t("media.kind")}>
            {(id) => (
              <Select
                id={id}
                value={kind}
                onChange={(e) => setKind(e.target.value as MediaItem["kind"])}
              >
                <option value="photo">{t("media.kinds.photo")}</option>
                <option value="document_scan">{t("media.kinds.document_scan")}</option>
              </Select>
            )}
          </Field>
        )}
        <PartialDateInput label={t("builder.events.date")} value={date} onChange={setDate} />
        <PlaceInput
          treeId={treeId}
          label={t("builder.events.place")}
          value={place}
          onChange={setPlace}
        />
        <Field label={t("builder.events.description")}>
          {(id) => (
            <TextArea
              id={id}
              rows={4}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          )}
        </Field>
        <p className="text-bark-700 text-xs">
          SHA-256: <code className="break-all">{media.sha256}</code>
        </p>
        <ErrorAlert error={update.error} />
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>
            {t("common.cancel")}
          </Button>
          <Button type="submit" busy={update.isPending}>
            {t("common.save")}
          </Button>
        </div>
      </form>
    </Dialog>
  );
}

function TagDialog({
  treeId,
  media,
  onClose,
}: {
  treeId: string;
  media: MediaItem;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const tag = useTagPerson(treeId);
  const untag = useUntagPerson(treeId);
  const [region, setRegion] = useState<Region | null>(null);
  return (
    <Dialog open title={t("media.tagPeople")} onClose={onClose}>
      <div className="max-h-[80vh] space-y-3 overflow-y-auto">
        <p className="text-bark-700 text-sm">{t("media.tagHint")}</p>
        <RegionSelector
          src={media.urls.web}
          value={region}
          onChange={setRegion}
          label={t("media.tagPeople")}
          others={media.people
            .filter((p) => p.region)
            .map((p) => ({ region: p.region!, label: p.display_name }))}
        />
        <PersonCombobox
          treeId={treeId}
          label={region ? t("media.whoIsThis") : t("media.addPerson")}
          onSelect={(p) =>
            tag.mutate(
              { mediaId: media.id, personId: p.id, region },
              { onSuccess: () => setRegion(null) },
            )
          }
        />
        <ErrorAlert error={tag.error ?? untag.error} />
        <ul className="divide-bark-100 divide-y text-sm">
          {media.people.map((p) => (
            <li key={p.person_id} className="flex items-center justify-between py-1">
              <span>
                {p.display_name} {p.region ? "▣" : ""}
              </span>
              <Button
                variant="ghost"
                onClick={() => untag.mutate({ mediaId: media.id, personId: p.person_id })}
              >
                {t("common.remove")}
              </Button>
            </li>
          ))}
        </ul>
        <div className="flex justify-end">
          <Button onClick={onClose}>{t("media.done")}</Button>
        </div>
      </div>
    </Dialog>
  );
}

function PortraitDialog({
  treeId,
  person,
  media,
  onClose,
}: {
  treeId: string;
  person: PersonDetail;
  media: MediaItem;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const update = useUpdatePerson(treeId, person.id);
  const own = media.people.find((p) => p.person_id === person.id)?.region ?? null;
  const [crop, setCrop] = useState<Region | null>(
    // Saved crop of this portrait, otherwise the person's tagged face in the photo.
    (person.primary_photo_id === media.id ? person.primary_photo_crop : null) ?? own,
  );
  return (
    <Dialog open title={t("media.setPortrait")} onClose={onClose}>
      <div className="max-h-[80vh] space-y-3 overflow-y-auto">
        <p className="text-bark-700 text-sm">{t("media.cropHint")}</p>
        <RegionSelector
          src={media.urls.web}
          value={crop}
          onChange={setCrop}
          square
          label={t("media.setPortrait")}
        />
        <Alert kind="info">{t("media.cropNote")}</Alert>
        <ErrorAlert error={update.error} />
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>
            {t("common.cancel")}
          </Button>
          <Button
            busy={update.isPending}
            onClick={() =>
              update.mutate(
                { primary_photo_id: media.id, primary_photo_crop: crop },
                { onSuccess: onClose },
              )
            }
          >
            {t("common.save")}
          </Button>
        </div>
      </div>
    </Dialog>
  );
}
