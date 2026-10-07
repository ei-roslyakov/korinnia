import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { Button, Dialog, ErrorAlert, Field, Input, Select, TextArea } from "@/components/ui";
import { useSaveSource } from "@/features/collab/api";
import { SOURCE_TYPES, type Source, type SourceType } from "@/lib/genealogy";

export function SourceDialog({
  treeId,
  source,
  initialTitle = "",
  onClose,
  onSaved,
}: {
  treeId: string;
  source: Source | null;
  initialTitle?: string;
  onClose: () => void;
  onSaved?: (s: Source) => void;
}) {
  const { t } = useTranslation();
  const save = useSaveSource(treeId);
  const [v, setV] = useState({
    title: source?.title ?? initialTitle,
    type: (source?.type ?? "archive_document") as SourceType,
    author: source?.author ?? "",
    archive_name: source?.archive_name ?? "",
    reference_number: source?.reference_number ?? "",
    url: source?.url ?? "",
    notes: source?.notes ?? "",
  });
  const set = (patch: Partial<typeof v>) => setV({ ...v, ...patch });
  const orNull = (s: string) => s.trim() || null;

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    e.stopPropagation();
    save.mutate(
      {
        id: source?.id,
        title: v.title.trim(),
        type: v.type,
        author: orNull(v.author),
        archive_name: orNull(v.archive_name),
        reference_number: orNull(v.reference_number),
        url: orNull(v.url),
        notes: orNull(v.notes),
      },
      { onSuccess: (s) => (onSaved ? onSaved(s) : onClose()) },
    );
  };

  return (
    <Dialog open title={source ? source.title : t("collab.sourcesPage.new")} onClose={onClose}>
      <form onSubmit={onSubmit} className="max-h-[75vh] space-y-3 overflow-y-auto pr-1">
        <Field label={t("collab.sourcesPage.title")}>
          {(id) => (
            <Input
              id={id}
              required
              value={v.title}
              onChange={(e) => set({ title: e.target.value })}
            />
          )}
        </Field>
        <Field label={t("collab.sourcesPage.type")}>
          {(id) => (
            <Select
              id={id}
              value={v.type}
              onChange={(e) => set({ type: e.target.value as SourceType })}
            >
              {SOURCE_TYPES.map((x) => (
                <option key={x} value={x}>
                  {t(`collab.sourceTypes.${x}`)}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label={t("collab.sourcesPage.archive")}>
            {(id) => (
              <Input
                id={id}
                value={v.archive_name}
                onChange={(e) => set({ archive_name: e.target.value })}
              />
            )}
          </Field>
          <Field
            label={t("collab.sourcesPage.reference")}
            hint={t("collab.sourcesPage.referenceHint")}
          >
            {(id) => (
              <Input
                id={id}
                value={v.reference_number}
                onChange={(e) => set({ reference_number: e.target.value })}
              />
            )}
          </Field>
          <Field label={t("collab.sourcesPage.author")}>
            {(id) => (
              <Input id={id} value={v.author} onChange={(e) => set({ author: e.target.value })} />
            )}
          </Field>
          <Field label="URL">
            {(id) => (
              <Input
                id={id}
                type="url"
                value={v.url}
                onChange={(e) => set({ url: e.target.value })}
              />
            )}
          </Field>
        </div>
        <Field label={t("collab.sourcesPage.notes")}>
          {(id) => (
            <TextArea
              id={id}
              rows={3}
              value={v.notes}
              onChange={(e) => set({ notes: e.target.value })}
            />
          )}
        </Field>
        <ErrorAlert error={save.error} />
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>
            {t("common.cancel")}
          </Button>
          <Button type="submit" busy={save.isPending}>
            {t("common.save")}
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
