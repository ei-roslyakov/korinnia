import { useEffect, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { Button, Checkbox, ErrorAlert, Field, Input, Select, TextArea } from "@/components/ui";
import {
  GENDERS,
  type Gender,
  type PartialDateInput as DateValue,
  type PersonDetail,
  type PlaceSummary,
} from "@/lib/genealogy";

import { useUpdatePerson, type NameInput } from "./api";
import { cleanNames, clearDraft, fromPartialDate, toPayload } from "./helpers";
import { MarkdownEditor } from "./MarkdownEditor";
import { NamesEditor } from "./NamesEditor";
import { PartialDateInput } from "./PartialDateInput";
import { PlaceInput } from "./PlaceInput";

interface FormState {
  gender: Gender;
  is_living: boolean;
  research_status: string;
  names: NameInput[];
  birth: DateValue | null;
  birthPlace: PlaceSummary | null;
  death: DateValue | null;
  deathPlace: PlaceSummary | null;
  deathDescription: string;
  short_summary: string;
  occupation: string;
  education: string;
  religion: string;
  nationality: string;
  biography: string;
  notes_for_descendants: string;
}

function initial(p: PersonDetail): FormState {
  return {
    gender: p.gender,
    is_living: p.is_living,
    research_status: p.research_status,
    names: p.names.map((n) => ({
      type: n.type,
      first_name: n.first_name ?? "",
      middle_name: n.middle_name ?? "",
      patronymic: n.patronymic ?? "",
      last_name: n.last_name ?? "",
      maiden_name: n.maiden_name ?? "",
      script: n.script,
      is_primary: n.is_primary,
      notes: n.notes,
    })),
    birth: fromPartialDate(p.birth?.date),
    birthPlace: p.birth?.place ?? null,
    death: fromPartialDate(p.death?.date),
    deathPlace: p.death?.place ?? null,
    deathDescription: p.death?.description ?? "",
    short_summary: p.short_summary ?? "",
    occupation: p.occupation ?? "",
    education: p.education ?? "",
    religion: p.religion ?? "",
    nationality: p.nationality ?? "",
    biography: p.biography ?? "",
    notes_for_descendants: p.notes_for_descendants ?? "",
  };
}

const orNull = (s: string) => (s.trim() ? s : null);

export function PersonForm({
  treeId,
  person,
  onSaved,
}: {
  treeId: string;
  person: PersonDetail;
  /** Called after a successful save. The form remounts with fresh data, so the parent
   * shows the confirmation and any plausibility warnings. */
  onSaved: (saved: PersonDetail) => void;
}) {
  const { t } = useTranslation();
  const update = useUpdatePerson(treeId, person.id);
  const [form, setForm] = useState<FormState>(() => initial(person));
  const [dirty, setDirty] = useState(false);
  const set = (patch: Partial<FormState>) => {
    setForm((f) => ({ ...f, ...patch }));
    setDirty(true);
  };
  const bioKey = `korinnia.draft.${person.id}.biography`;
  const notesKey = `korinnia.draft.${person.id}.notes`;

  // Warn before leaving with unsaved edits.
  useEffect(() => {
    if (!dirty) return;
    const handler = (e: BeforeUnloadEvent) => e.preventDefault();
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [dirty]);

  const hasDeath = !form.is_living;

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    const birthDate = toPayload(form.birth);
    const deathDate = toPayload(form.death);
    update.mutate(
      {
        gender: form.gender,
        is_living: form.is_living,
        research_status: form.research_status,
        names: cleanNames(form.names),
        birth:
          birthDate || form.birthPlace
            ? { date: birthDate, place_id: form.birthPlace?.id ?? null }
            : null,
        death:
          hasDeath && (deathDate || form.deathPlace || form.deathDescription.trim())
            ? {
                date: deathDate,
                place_id: form.deathPlace?.id ?? null,
                description: orNull(form.deathDescription),
              }
            : null,
        short_summary: orNull(form.short_summary),
        occupation: orNull(form.occupation),
        education: orNull(form.education),
        religion: orNull(form.religion),
        nationality: orNull(form.nationality),
        biography: orNull(form.biography),
        notes_for_descendants: orNull(form.notes_for_descendants),
      },
      {
        onSuccess: (saved) => {
          setDirty(false);
          clearDraft(bioKey);
          clearDraft(notesKey);
          onSaved(saved);
        },
      },
    );
  };

  return (
    <form onSubmit={onSubmit} className="space-y-6">
      <section className="space-y-3">
        <h2 className="font-semibold">{t("person.names")}</h2>
        <NamesEditor names={form.names} onChange={(names) => set({ names })} />
      </section>

      <section className="grid gap-4 sm:grid-cols-3">
        <Field label={t("builder.gender")}>
          {(id) => (
            <Select
              id={id}
              value={form.gender}
              onChange={(e) => set({ gender: e.target.value as Gender })}
            >
              {GENDERS.map((g) => (
                <option key={g} value={g}>
                  {t(`gender.${g}`)}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field label={t("person.researchStatus")}>
          {(id) => (
            <Select
              id={id}
              value={form.research_status}
              onChange={(e) => set({ research_status: e.target.value })}
            >
              {(["unknown", "partial", "complete"] as const).map((r) => (
                <option key={r} value={r}>
                  {t(`research.${r}`)}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <div className="flex items-end pb-2">
          <Checkbox
            label={t("person.living")}
            checked={form.is_living}
            onChange={(e) => set({ is_living: e.target.checked })}
          />
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2">
        <div className="space-y-3">
          <PartialDateInput
            label={t("person.born")}
            value={form.birth}
            onChange={(birth) => set({ birth })}
          />
          <PlaceInput
            treeId={treeId}
            label={t("builder.birthPlace")}
            value={form.birthPlace}
            onChange={(birthPlace) => set({ birthPlace })}
          />
        </div>
        {hasDeath && (
          <div className="space-y-3">
            <PartialDateInput
              label={t("person.died")}
              value={form.death}
              onChange={(death) => set({ death })}
            />
            <PlaceInput
              treeId={treeId}
              label={t("builder.deathPlace")}
              value={form.deathPlace}
              onChange={(deathPlace) => set({ deathPlace })}
            />
            <Field label={t("builder.deathDescription")}>
              {(id) => (
                <Input
                  id={id}
                  value={form.deathDescription}
                  onChange={(e) => set({ deathDescription: e.target.value })}
                />
              )}
            </Field>
          </div>
        )}
      </section>

      <section className="grid gap-4 sm:grid-cols-2">
        <Field label={t("builder.shortSummary")}>
          {(id) => (
            <Input
              id={id}
              maxLength={500}
              value={form.short_summary}
              onChange={(e) => set({ short_summary: e.target.value })}
            />
          )}
        </Field>
        {(["occupation", "education", "religion", "nationality"] as const).map((k) => (
          <Field key={k} label={t(`person.${k}`)}>
            {(id) =>
              k === "occupation" || k === "education" ? (
                <TextArea
                  id={id}
                  rows={2}
                  value={form[k]}
                  onChange={(e) => set({ [k]: e.target.value })}
                />
              ) : (
                <Input id={id} value={form[k]} onChange={(e) => set({ [k]: e.target.value })} />
              )
            }
          </Field>
        ))}
      </section>

      <MarkdownEditor
        label={t("person.biography")}
        value={form.biography}
        onChange={(biography) => set({ biography })}
        draftKey={bioKey}
        rows={14}
      />
      <MarkdownEditor
        label={t("person.notesForDescendants")}
        value={form.notes_for_descendants}
        onChange={(notes_for_descendants) => set({ notes_for_descendants })}
        draftKey={notesKey}
        rows={5}
      />

      <div className="border-bark-100 bg-bark-50/95 sticky bottom-0 -mx-4 flex flex-wrap items-center gap-3 border-t px-4 py-3">
        <Button type="submit" busy={update.isPending} disabled={!dirty}>
          {t("common.save")}
        </Button>
        {dirty && <span className="text-sm text-amber-700">{t("builder.unsaved")}</span>}
        <div className="w-full">
          <ErrorAlert error={update.error} />
        </div>
      </div>
    </form>
  );
}
