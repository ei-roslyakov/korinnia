import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import { Button, Card, Dialog, ErrorAlert, Field, Select } from "@/components/ui";
import { PersonCombobox } from "@/features/person/PersonCombobox";
import { formatPartialDate, lifeYears } from "@/lib/dates";
import {
  END_REASONS,
  PARENT_CHILD_TYPES,
  PARTNERSHIP_TYPES,
  type ParentChildType,
  type PartialDateInput as DateValue,
  type PartnerRef,
  type PartnershipType,
  type PersonDetail,
  type PersonSummary,
  type RelativeRelation,
} from "@/lib/genealogy";

import { AddRelativeDialog } from "./AddRelativeDialog";
import {
  useDeleteParentChild,
  useDeletePartnership,
  useSaveParentChild,
  useSavePartnership,
} from "./api";
import { fromPartialDate, toPayload } from "./helpers";
import { PartialDateInput } from "./PartialDateInput";

function PersonLabel({ treeId, person }: { treeId: string; person: PersonSummary }) {
  return (
    <span>
      <Link
        to={`/trees/${treeId}/people/${person.id}/edit`}
        className="text-leaf-700 font-medium hover:underline"
      >
        {person.display_name}
      </Link>{" "}
      <span className="text-bark-700 text-sm">
        {lifeYears(person.birth, person.death, person.is_living)}
      </span>
    </span>
  );
}

export function FamilyTab({ treeId, person }: { treeId: string; person: PersonDetail }) {
  const { t, i18n } = useTranslation();
  const savePc = useSaveParentChild(treeId);
  const delPc = useDeleteParentChild(treeId);
  const savePartnership = useSavePartnership(treeId);
  const delPartnership = useDeletePartnership(treeId);
  const [adding, setAdding] = useState<RelativeRelation | null>(null);
  const [editPartner, setEditPartner] = useState<PartnerRef | null>(null);
  const related = [
    person.id,
    ...person.parents.map((p) => p.person.id),
    ...person.children.map((p) => p.person.id),
    ...person.partners.map((p) => p.person.id),
  ];
  const error = savePc.error ?? delPc.error ?? savePartnership.error ?? delPartnership.error;

  const typeSelect = (id: string, type: ParentChildType) => (
    <Select
      aria-label={t("builder.add.linkType")}
      className="w-44"
      value={type}
      onChange={(e) => savePc.mutate({ id, type: e.target.value as ParentChildType })}
    >
      {PARENT_CHILD_TYPES.map((x) => (
        <option key={x} value={x}>
          {t(`builder.pcType.${x}`)}
        </option>
      ))}
    </Select>
  );
  const removeButton = (onConfirm: () => void) => (
    <Button
      variant="ghost"
      className="text-red-700"
      onClick={() => window.confirm(t("builder.family.confirmUnlink")) && onConfirm()}
    >
      {t("builder.family.unlink")}
    </Button>
  );

  const section = (
    title: string,
    relation: RelativeRelation,
    rows: React.ReactNode,
    linkExisting?: (p: PersonSummary) => void,
  ) => (
    <Card className="space-y-3">
      <h2 className="font-semibold">{title}</h2>
      <ul className="divide-bark-100 divide-y">{rows}</ul>
      <div className="flex flex-wrap items-center gap-2">
        <Button variant="secondary" onClick={() => setAdding(relation)}>
          + {t(`builder.family.new.${relation}`)}
        </Button>
        {linkExisting && (
          <PersonCombobox
            treeId={treeId}
            label={t("builder.family.linkExisting")}
            excludeIds={related}
            onSelect={linkExisting}
          />
        )}
      </div>
    </Card>
  );

  return (
    <div className="space-y-4">
      <ErrorAlert error={error} />
      {section(
        t("person.parents"),
        "parent",
        person.parents.map((r) => (
          <li
            key={r.relationship_id}
            className="flex flex-wrap items-center justify-between gap-2 py-2"
          >
            <PersonLabel treeId={treeId} person={r.person} />
            <div className="flex gap-1">
              {typeSelect(r.relationship_id, r.type)}
              {removeButton(() => delPc.mutate(r.relationship_id))}
            </div>
          </li>
        )),
        (p) => savePc.mutate({ parent_id: p.id, child_id: person.id, type: "biological" }),
      )}
      {section(
        t("person.partners"),
        "partner",
        person.partners.map((r) => (
          <li
            key={r.partnership_id}
            className="flex flex-wrap items-center justify-between gap-2 py-2"
          >
            <div>
              <PersonLabel treeId={treeId} person={r.person} />
              <div className="text-bark-700 text-sm">
                {[
                  t(`partnershipTypes.${r.type}`),
                  r.start_date &&
                    t("person.since", { date: formatPartialDate(r.start_date, t, i18n.language) }),
                  r.end_reason && t(`endReasons.${r.end_reason}`),
                ]
                  .filter(Boolean)
                  .join(", ")}
              </div>
            </div>
            <div className="flex gap-1">
              <Button variant="secondary" onClick={() => setEditPartner(r)}>
                {t("builder.edit")}
              </Button>
              {removeButton(() => delPartnership.mutate(r.partnership_id))}
            </div>
          </li>
        )),
        (p) =>
          savePartnership.mutate({ person_a_id: person.id, person_b_id: p.id, type: "marriage" }),
      )}
      {section(
        t("person.children"),
        "child",
        person.children.map((r) => (
          <li
            key={r.relationship_id}
            className="flex flex-wrap items-center justify-between gap-2 py-2"
          >
            <PersonLabel treeId={treeId} person={r.person} />
            <div className="flex gap-1">
              {typeSelect(r.relationship_id, r.type)}
              {removeButton(() => delPc.mutate(r.relationship_id))}
            </div>
          </li>
        )),
        (p) => savePc.mutate({ parent_id: person.id, child_id: p.id, type: "biological" }),
      )}
      {section(
        t("person.siblings"),
        "sibling",
        person.siblings.map((s) => (
          <li key={s.person.id} className="py-2">
            <PersonLabel treeId={treeId} person={s.person} />
            {s.half && <span className="text-bark-700 text-sm"> · {t("person.halfSibling")}</span>}
          </li>
        )),
      )}
      {adding && (
        <AddRelativeDialog
          treeId={treeId}
          relativeId={person.id}
          relation={adding}
          onClose={() => setAdding(null)}
          onCreated={() => setAdding(null)}
        />
      )}
      {editPartner && (
        <PartnershipDialog
          treeId={treeId}
          partner={editPartner}
          onClose={() => setEditPartner(null)}
        />
      )}
    </div>
  );
}

function PartnershipDialog({
  treeId,
  partner,
  onClose,
}: {
  treeId: string;
  partner: PartnerRef;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const save = useSavePartnership(treeId);
  const [type, setType] = useState<PartnershipType>(partner.type);
  const [start, setStart] = useState<DateValue | null>(fromPartialDate(partner.start_date));
  const [end, setEnd] = useState<DateValue | null>(fromPartialDate(partner.end_date));
  const [reason, setReason] = useState<string>(partner.end_reason ?? "");

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    save.mutate(
      {
        id: partner.partnership_id,
        type,
        start_date: toPayload(start),
        end_date: toPayload(end),
        end_reason: reason || null,
      },
      { onSuccess: onClose },
    );
  };

  return (
    <Dialog open title={partner.person.display_name} onClose={onClose}>
      <form onSubmit={onSubmit} className="space-y-3">
        <Field label={t("builder.add.partnershipType")}>
          {(id) => (
            <Select
              id={id}
              value={type}
              onChange={(e) => setType(e.target.value as PartnershipType)}
            >
              {PARTNERSHIP_TYPES.map((x) => (
                <option key={x} value={x}>
                  {t(`partnershipTypes.${x}`)}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <PartialDateInput label={t("builder.family.start")} value={start} onChange={setStart} />
        <PartialDateInput label={t("builder.family.end")} value={end} onChange={setEnd} />
        <Field label={t("builder.family.endReason")}>
          {(id) => (
            <Select id={id} value={reason} onChange={(e) => setReason(e.target.value)}>
              <option value="">—</option>
              {END_REASONS.map((x) => (
                <option key={x} value={x}>
                  {t(`endReasons.${x}`)}
                </option>
              ))}
            </Select>
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
