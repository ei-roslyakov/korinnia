import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { Button, Card, Dialog, ErrorAlert, Field, Input, Select, TextArea } from "@/components/ui";
import { useDeleteCitation, useSaveCitation, useSources } from "@/features/collab/api";
import { citationTargetLabel } from "@/features/collab/labels";
import { formatPartialDate } from "@/lib/dates";
import {
  CITATION_QUALITIES,
  type Citation,
  type CitationQuality,
  type CitedEntity,
  type PersonDetail,
  type Source,
} from "@/lib/genealogy";

import { SourceDialog } from "./SourceDialog";

const PERSON_FIELDS = ["occupation", "education", "religion", "nationality", "biography"];

/** Editor tab: attach sources to the person's facts. */
export function SourcesTab({ treeId, person }: { treeId: string; person: PersonDetail }) {
  const { t } = useTranslation();
  const del = useDeleteCitation(treeId);
  const [editing, setEditing] = useState<Citation | "new" | null>(null);
  return (
    <div className="space-y-4">
      <p className="text-bark-700 text-sm">{t("collab.cite.hint")}</p>
      <Button onClick={() => setEditing("new")}>+ {t("collab.cite.add")}</Button>
      <ErrorAlert error={del.error} />
      {person.citations.length === 0 && (
        <p className="text-bark-700 text-sm">{t("collab.cite.none")}</p>
      )}
      <ul className="space-y-2">
        {person.citations.map((c) => (
          <li key={c.id}>
            <Card className="flex flex-wrap items-center justify-between gap-2 text-sm">
              <div>
                <div className="font-medium">{citationTargetLabel(t, c.target, c.field)}</div>
                <div className="text-bark-700">
                  {c.source.title}
                  {c.page && ` · ${c.page}`} · {t(`collab.quality.${c.quality}`)}
                </div>
              </div>
              <div className="flex gap-1">
                <Button variant="secondary" onClick={() => setEditing(c)}>
                  {t("builder.edit")}
                </Button>
                <Button variant="ghost" className="text-red-700" onClick={() => del.mutate(c.id)}>
                  {t("common.remove")}
                </Button>
              </div>
            </Card>
          </li>
        ))}
      </ul>
      {editing && (
        <CitationDialog
          treeId={treeId}
          person={person}
          citation={editing === "new" ? null : editing}
          onClose={() => setEditing(null)}
        />
      )}
    </div>
  );
}

function CitationDialog({
  treeId,
  person,
  citation,
  onClose,
}: {
  treeId: string;
  person: PersonDetail;
  citation: Citation | null;
  onClose: () => void;
}) {
  const { t, i18n } = useTranslation();
  const save = useSaveCitation(treeId);
  const [q, setQ] = useState("");
  const sources = useSources(treeId, q);
  const [creating, setCreating] = useState(false);
  const [source, setSource] = useState<{ id: string; title: string } | null>(
    citation?.source ?? null,
  );
  // Target = "<entity_type>|<entity_id>|<field>"
  const [target, setTarget] = useState(
    citation
      ? `${citation.target.entity_type}|${citation.target.entity_id}|${citation.field ?? ""}`
      : `person|${person.id}|`,
  );
  const [page, setPage] = useState(citation?.page ?? "");
  const [quality, setQuality] = useState<CitationQuality>(citation?.quality ?? "primary");
  const [notes, setNotes] = useState(citation?.notes ?? "");

  const options: [string, string][] = [
    [`person|${person.id}|`, t("collab.target.person")],
    ...PERSON_FIELDS.map((f): [string, string] => [
      `person|${person.id}|${f}`,
      t(`collab.fields.${f}`),
    ]),
    ...person.names.map((n): [string, string] => [
      `person_name|${n.id}|`,
      t("collab.target.name", { name: n.display }),
    ]),
    ...person.events.map((e): [string, string] => [
      `event|${e.id}|`,
      [t(`eventTypes.${e.type}`), formatPartialDate(e.date, t, i18n.language), e.title]
        .filter(Boolean)
        .join(" · "),
    ]),
    ...person.parents.map((r): [string, string] => [
      `parent_child|${r.relationship_id}|`,
      `${t("person.parents")}: ${r.person.display_name}`,
    ]),
    ...person.children.map((r): [string, string] => [
      `parent_child|${r.relationship_id}|`,
      `${t("person.children")}: ${r.person.display_name}`,
    ]),
    ...person.partners.map((r): [string, string] => [
      `partnership|${r.partnership_id}|`,
      `${t("person.partners")}: ${r.person.display_name}`,
    ]),
  ];

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!source) return;
    const [entity_type, entity_id, field] = target.split("|") as [CitedEntity, string, string];
    save.mutate(
      citation
        ? { id: citation.id, page: page.trim() || null, quality, notes: notes.trim() || null }
        : {
            source_id: source.id,
            entity_type,
            entity_id,
            field: field || null,
            page: page.trim() || null,
            quality,
            notes: notes.trim() || null,
          },
      { onSuccess: onClose },
    );
  };

  return (
    <>
      <Dialog
        open
        title={citation ? t("collab.cite.edit") : t("collab.cite.add")}
        onClose={onClose}
      >
        <form onSubmit={onSubmit} className="max-h-[75vh] space-y-3 overflow-y-auto pr-1">
          <Field label={t("collab.cite.supports")}>
            {(id) => (
              <Select
                id={id}
                value={target}
                disabled={Boolean(citation)}
                onChange={(e) => setTarget(e.target.value)}
              >
                {options.map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <div className="space-y-1">
            <span className="block text-sm font-medium">{t("collab.cite.source")}</span>
            {source ? (
              <div className="border-bark-100 bg-bark-50 flex items-center justify-between rounded-md border px-3 py-2 text-sm">
                {source.title}
                {!citation && (
                  <button
                    type="button"
                    aria-label={t("builder.place.clear")}
                    onClick={() => setSource(null)}
                  >
                    ✕
                  </button>
                )}
              </div>
            ) : (
              <>
                <Input
                  aria-label={t("collab.sourcesPage.search")}
                  placeholder={t("collab.sourcesPage.search")}
                  value={q}
                  onChange={(e) => setQ(e.target.value)}
                />
                <ul className="border-bark-100 max-h-40 overflow-y-auto rounded-md border">
                  {sources.data?.items.map((s: Source) => (
                    <li key={s.id}>
                      <button
                        type="button"
                        className="hover:bg-bark-100 w-full px-3 py-1.5 text-left text-sm"
                        onClick={() => setSource(s)}
                      >
                        {s.title}{" "}
                        <span className="text-bark-700 text-xs">
                          {t(`collab.sourceTypes.${s.type}`)}
                        </span>
                      </button>
                    </li>
                  ))}
                  <li>
                    <button
                      type="button"
                      className="text-leaf-700 hover:bg-bark-100 w-full px-3 py-1.5 text-left text-sm font-medium"
                      onClick={() => setCreating(true)}
                    >
                      + {t("collab.sourcesPage.new")}
                    </button>
                  </li>
                </ul>
              </>
            )}
          </div>
          <Field label={t("collab.cite.page")} hint={t("collab.cite.pageHint")}>
            {(id) => <Input id={id} value={page} onChange={(e) => setPage(e.target.value)} />}
          </Field>
          <Field label={t("collab.cite.quality")}>
            {(id) => (
              <Select
                id={id}
                value={quality}
                onChange={(e) => setQuality(e.target.value as CitationQuality)}
              >
                {CITATION_QUALITIES.map((x) => (
                  <option key={x} value={x}>
                    {t(`collab.quality.${x}`)}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <Field label={t("collab.sourcesPage.notes")}>
            {(id) => (
              <TextArea id={id} rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} />
            )}
          </Field>
          <ErrorAlert error={save.error} />
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={onClose}>
              {t("common.cancel")}
            </Button>
            <Button type="submit" busy={save.isPending} disabled={!source}>
              {t("common.save")}
            </Button>
          </div>
        </form>
      </Dialog>
      {/* A sibling, not a child: nested modal dialogs confuse focus and the top layer. */}
      {creating && (
        <SourceDialog
          treeId={treeId}
          source={null}
          initialTitle={q}
          onClose={() => setCreating(false)}
          onSaved={(s) => {
            setSource(s);
            setCreating(false);
          }}
        />
      )}
    </>
  );
}
