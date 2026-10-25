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
  type PersonSummary,
  type PlaceSummary,
  type Region,
} from "@/lib/genealogy";
import { useErrorMessage } from "@/lib/hooks";

import {
  uploadMedia,
  type MediaPatch,
  useDeleteMedia,
  useReorderMedia,
  useReprocessMedia,
  useTagPerson,
  useUntagPerson,
  useUpdateMedia,
} from "./api";
import { RegionSelector } from "./RegionSelector";

/** A just-added photo waiting for its description (asked right away, saved once uploaded). */
interface Describing {
  key: string;
  file: File;
  uploaded: Promise<MediaItem | null>;
}

/** The person's closest family, offered first when choosing who else is in a photo. */
function relativesOf(person: PersonDetail): PersonSummary[] {
  const all = [
    ...person.partners.map((r) => r.person),
    ...person.parents.map((r) => r.person),
    ...person.children.map((r) => r.person),
    ...person.siblings.map((r) => r.person),
  ];
  return all.filter((p, i) => p.id !== person.id && all.findIndex((q) => q.id === p.id) === i);
}

const isImageFile = (f: File) => f.type.startsWith("image/") || /\.(heic|heif)$/i.test(f.name);

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
  const [describing, setDescribing] = useState<Describing[]>([]);
  const [describedCount, setDescribedCount] = useState(0);
  const update = useUpdateMedia(treeId);
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
      const item = await uploadMedia(treeId, file, {
        personId: person.id,
        kind: asDocument ? "document_scan" : undefined,
        allowDuplicate,
        onProgress: (progress) => setUpload(key, { progress }),
      });
      setUploads((list) => list.filter((u) => u.key !== key));
      onChanged();
      return item;
    } catch (err) {
      const dup =
        err instanceof ApiError && err.code === "duplicate_media"
          ? String((err.body as { media_id: string }).media_id)
          : undefined;
      setUpload(key, { error: err, duplicateOf: dup });
      return null;
    }
  };

  const addFiles = (files: FileList | File[]) => {
    const added: Describing[] = [];
    for (const file of Array.from(files)) {
      const key = `${file.name}-${file.size}-${Math.random()}`;
      setUploads((list) => [...list, { key, name: file.name, progress: 0, file }]);
      const uploaded = send(file, key);
      if (isImageFile(file)) added.push({ key, file, uploaded });
    }
    if (added.length) setDescribing((list) => [...list, ...added]);
  };

  // The upload keeps going while the editor types; the details and the other people in the
  // photo are saved when it is done.
  const finishDescribing = (entry: Describing, details: MediaPatch | null, people: string[]) => {
    setDescribing((list) => list.filter((d) => d.key !== entry.key));
    // Counts "2 of 3" within one batch; starts again once every photo is answered.
    setDescribedCount((n) => (describing.length > 1 ? n + 1 : 0));
    if (!details && !people.length) return;
    void entry.uploaded.then(async (item) => {
      if (!item) return;
      try {
        await Promise.all([
          details && update.mutateAsync({ id: item.id, ...details }),
          ...people.map((personId) =>
            tag.mutateAsync({ mediaId: item.id, personId, region: null }),
          ),
        ]);
      } catch {
        // Shown by the error alert below; the photo itself is saved.
      } finally {
        onChanged();
      }
    });
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

      <ErrorAlert
        error={
          reorder.error ??
          untag.error ??
          del.error ??
          reprocess.error ??
          update.error ??
          (describing.length ? null : tag.error)
        }
      />
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
      {describing[0] && (
        <DescribeDialog
          key={describing[0].key}
          treeId={treeId}
          person={person}
          file={describing[0].file}
          n={describedCount + 1}
          total={describedCount + describing.length}
          onDone={(details, people) => finishDescribing(describing[0]!, details, people)}
        />
      )}
      {editing && (
        <MediaMetaDialog treeId={treeId} media={editing} onClose={() => setEditing(null)} />
      )}
      {tagging && (
        <TagDialog
          treeId={treeId}
          media={media.find((m) => m.id === tagging.id) ?? tagging}
          suggestions={relativesOf(person)}
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

/** Asked right after photos are chosen: the description first (shown above the photo in the
 *  family album), the title, date, place and who else is in it optional. "Later" keeps the
 *  photo undescribed and linked only to this person. */
function DescribeDialog({
  treeId,
  person,
  file,
  n,
  total,
  onDone,
}: {
  treeId: string;
  person: PersonDetail;
  file: File;
  n: number;
  total: number;
  onDone: (details: MediaPatch | null, people: string[]) => void;
}) {
  const { t } = useTranslation();
  const [description, setDescription] = useState("");
  const [others, setOthers] = useState<PersonSummary[]>([]);
  const [title, setTitle] = useState("");
  const [date, setDate] = useState<DateValue | null>(null);
  const [place, setPlace] = useState<PlaceSummary | null>(null);
  // A local preview of the chosen file, released when the dialog moves on.
  const showPreview = (img: HTMLImageElement | null) => {
    if (!img || typeof URL.createObjectURL !== "function") return;
    const url = URL.createObjectURL(file);
    img.src = url;
    return () => URL.revokeObjectURL(url);
  };

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    const payloadDate = toPayload(date);
    const details: MediaPatch = {
      ...(description.trim() && { description: description.trim() }),
      ...(title.trim() && { title: title.trim() }),
      ...(payloadDate && { date: payloadDate }),
      ...(place && { place_id: place.id }),
    };
    onDone(
      Object.keys(details).length ? details : null,
      others.map((p) => p.id),
    );
  };
  const heading =
    total > 1
      ? `${t("media.describe.title")} (${t("media.describe.progress", { n, total })})`
      : t("media.describe.title");

  return (
    <Dialog open title={heading} onClose={() => onDone(null, [])}>
      <form onSubmit={onSubmit} className="max-h-[75vh] space-y-3 overflow-y-auto pr-1">
        <div className="flex items-center gap-3">
          <div className="bg-bark-100 size-20 shrink-0 overflow-hidden rounded">
            <img
              ref={showPreview}
              alt={t("media.describe.preview")}
              className="size-full object-cover"
              onError={(e) => (e.currentTarget.hidden = true)}
            />
          </div>
          <p className="text-bark-700 min-w-0 text-sm break-words">{file.name}</p>
        </div>
        <p className="text-bark-700 text-xs">{t("media.describe.hint")}</p>
        <Field label={t("builder.events.description")}>
          {(id) => (
            <TextArea
              id={id}
              rows={4}
              autoFocus
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          )}
        </Field>
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
        <PartialDateInput label={t("builder.events.date")} value={date} onChange={setDate} />
        <PlaceInput
          treeId={treeId}
          label={t("builder.events.place")}
          value={place}
          onChange={setPlace}
        />
        <fieldset className="space-y-2">
          <legend className="text-bark-900 mb-1 text-sm font-medium">
            {t("media.describe.people")}
          </legend>
          <ul aria-label={t("media.describe.people")} className="flex flex-wrap gap-1.5">
            <li className="border-bark-100 bg-bark-50 rounded-full border px-3 py-1 text-xs">
              {person.display_name}
            </li>
            {others.map((p) => (
              <li
                key={p.id}
                className="bg-leaf-700 text-on-leaf inline-flex items-center gap-1 rounded-full py-1 pr-1 pl-3 text-xs"
              >
                {p.display_name}
                <button
                  type="button"
                  aria-label={t("media.describe.removePerson", { name: p.display_name })}
                  onClick={() => setOthers((list) => list.filter((q) => q.id !== p.id))}
                  className="flex size-5 items-center justify-center rounded-full hover:bg-black/20"
                >
                  ✕
                </button>
              </li>
            ))}
          </ul>
          <PersonCombobox
            treeId={treeId}
            label={t("media.describe.addPerson")}
            excludeIds={[person.id, ...others.map((p) => p.id)]}
            suggestions={relativesOf(person)}
            suggestionsLabel={t("media.relatives")}
            onSelect={(p) => setOthers((list) => [...list, p])}
          />
        </fieldset>
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={() => onDone(null, [])}>
            {t("media.describe.later")}
          </Button>
          <Button type="submit">
            {n < total ? t("media.describe.saveNext") : t("common.save")}
          </Button>
        </div>
      </form>
    </Dialog>
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
  suggestions,
  onClose,
}: {
  treeId: string;
  media: MediaItem;
  suggestions: PersonSummary[];
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
          excludeIds={region ? [] : media.people.map((p) => p.person_id)}
          suggestions={suggestions}
          suggestionsLabel={t("media.relatives")}
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
