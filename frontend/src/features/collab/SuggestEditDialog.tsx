import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { Alert, Button, Dialog, ErrorAlert, Field, Input, TextArea } from "@/components/ui";
import type { PersonDetail } from "@/lib/genealogy";

import { useCreateSuggestion } from "./api";

const FIELDS = [
  "short_summary",
  "occupation",
  "education",
  "religion",
  "nationality",
  "biography",
  "notes_for_descendants",
] as const;
type FieldName = (typeof FIELDS)[number];

/** Contributors propose changes; an editor approves them in the moderation queue. */
export function SuggestEditDialog({
  treeId,
  person,
  onClose,
}: {
  treeId: string;
  person: PersonDetail;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const create = useCreateSuggestion(treeId);
  const initial = Object.fromEntries(FIELDS.map((f) => [f, person[f] ?? ""])) as Record<
    FieldName,
    string
  >;
  const [values, setValues] = useState(initial);
  const [comment, setComment] = useState("");
  const changed = FIELDS.filter((f) => values[f] !== initial[f]);

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    const patch = Object.fromEntries(changed.map((f) => [f, values[f].trim() || null]));
    create.mutate({
      entity_type: "person",
      entity_id: person.id,
      patch,
      comment: comment.trim() || undefined,
    });
  };

  return (
    <Dialog open title={t("collab.suggest.title", { name: person.display_name })} onClose={onClose}>
      {create.isSuccess ? (
        <div className="space-y-3">
          <Alert kind="success">{t("collab.suggest.sent")}</Alert>
          <div className="flex justify-end">
            <Button onClick={onClose}>{t("media.done")}</Button>
          </div>
        </div>
      ) : (
        <form onSubmit={onSubmit} className="max-h-[75vh] space-y-3 overflow-y-auto pr-1">
          <p className="text-bark-700 text-sm">{t("collab.suggest.hint")}</p>
          {FIELDS.map((f) => (
            <Field key={f} label={t(`collab.fields.${f}`)}>
              {(id) =>
                f === "biography" || f === "notes_for_descendants" ? (
                  <TextArea
                    id={id}
                    rows={f === "biography" ? 8 : 3}
                    value={values[f]}
                    onChange={(e) => setValues({ ...values, [f]: e.target.value })}
                  />
                ) : (
                  <Input
                    id={id}
                    value={values[f]}
                    onChange={(e) => setValues({ ...values, [f]: e.target.value })}
                  />
                )
              }
            </Field>
          ))}
          <Field label={t("collab.suggest.comment")}>
            {(id) => (
              <TextArea
                id={id}
                rows={2}
                value={comment}
                onChange={(e) => setComment(e.target.value)}
              />
            )}
          </Field>
          <ErrorAlert error={create.error} />
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={onClose}>
              {t("common.cancel")}
            </Button>
            <Button type="submit" busy={create.isPending} disabled={changed.length === 0}>
              {t("collab.suggest.send")}
            </Button>
          </div>
        </form>
      )}
    </Dialog>
  );
}
