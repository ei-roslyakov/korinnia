import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { Button, Checkbox, Dialog, ErrorAlert, Field, Input, Select } from "@/components/ui";
import { usePerson } from "@/features/person/api";
import {
  GENDERS,
  PARENT_CHILD_TYPES,
  PARTNERSHIP_TYPES,
  type Gender,
  type ParentChildType,
  type PartialDateInput as DateValue,
  type PartnershipType,
  type PersonDetail,
  type PlaceSummary,
  type RelativeRelation,
} from "@/lib/genealogy";

import { useCreatePerson } from "./api";
import { toPayload } from "./helpers";
import { PartialDateInput } from "./PartialDateInput";
import { PlaceInput } from "./PlaceInput";

/** Surname suggestion: children and siblings usually share the relative's surname. */
function suggestedLastName(
  relative: PersonDetail | undefined,
  relation: RelativeRelation | null,
): string {
  if (!relative || (relation !== "child" && relation !== "sibling")) return "";
  const primary = relative.names.find((n) => n.is_primary) ?? relative.names[0];
  return primary?.maiden_name && relation === "sibling"
    ? primary.maiden_name
    : (primary?.last_name ?? "");
}

/**
 * Quick form for a new person, optionally linked to an existing one (parent / child /
 * partner / sibling). The backend creates person + links atomically.
 */
export function AddRelativeDialog({
  treeId,
  relativeId,
  relation,
  onClose,
  onCreated,
}: {
  treeId: string;
  relativeId: string | null;
  relation: RelativeRelation | null;
  onClose: () => void;
  onCreated: (person: PersonDetail) => void;
}) {
  const { t } = useTranslation();
  const relative = usePerson(treeId, relativeId);
  const create = useCreatePerson(treeId);
  const [first, setFirst] = useState("");
  const [patronymic, setPatronymic] = useState("");
  const [last, setLast] = useState<string | null>(null);
  const [maiden, setMaiden] = useState("");
  const [gender, setGender] = useState<Gender>(relation === "parent" ? "male" : "unknown");
  const [birth, setBirth] = useState<DateValue | null>(null);
  const [birthPlace, setBirthPlace] = useState<PlaceSummary | null>(null);
  const [isDead, setIsDead] = useState(false);
  const [death, setDeath] = useState<DateValue | null>(null);
  const [pcType, setPcType] = useState<ParentChildType>("biological");
  const [pType, setPType] = useState<PartnershipType>("marriage");
  const [otherParent, setOtherParent] = useState<string>("");

  const lastName = last ?? suggestedLastName(relative.data, relation);
  const title = relation
    ? t(`builder.add.title.${relation}`, { name: relative.data?.display_name ?? "…" })
    : t("builder.add.title.person");
  // Candidates for the second parent: partners of the person (child) or their other parent (parent).
  const otherParentOptions =
    relation === "child"
      ? (relative.data?.partners.map((p) => p.person) ?? [])
      : relation === "parent"
        ? (relative.data?.parents.map((p) => p.person) ?? [])
        : [];

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    const deathPayload = isDead ? { date: toPayload(death), place_id: null } : undefined;
    create.mutate(
      {
        gender,
        names: [
          {
            type: maiden ? "married" : "birth",
            first_name: first.trim() || null,
            middle_name: null,
            patronymic: patronymic.trim() || null,
            last_name: lastName.trim() || null,
            maiden_name: maiden.trim() || null,
            script: "cyrillic",
            is_primary: true,
          },
        ].filter((n) => n.first_name || n.last_name || n.patronymic || n.maiden_name),
        birth:
          toPayload(birth) || birthPlace
            ? { date: toPayload(birth), place_id: birthPlace?.id ?? null }
            : undefined,
        death: deathPayload,
        is_living: isDead ? false : undefined,
        relative:
          relativeId && relation
            ? {
                person_id: relativeId,
                relation,
                parent_child_type: pcType,
                partnership_type: pType,
                other_parent_id: otherParent || null,
              }
            : undefined,
      },
      { onSuccess: onCreated },
    );
  };

  return (
    <Dialog open title={title} onClose={onClose}>
      <form onSubmit={onSubmit} className="max-h-[75vh] space-y-3 overflow-y-auto pr-1">
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label={t("builder.names.first_name")}>
            {(id) => (
              <Input id={id} autoFocus value={first} onChange={(e) => setFirst(e.target.value)} />
            )}
          </Field>
          <Field label={t("builder.names.patronymic")}>
            {(id) => (
              <Input id={id} value={patronymic} onChange={(e) => setPatronymic(e.target.value)} />
            )}
          </Field>
          <Field label={t("builder.names.last_name")}>
            {(id) => <Input id={id} value={lastName} onChange={(e) => setLast(e.target.value)} />}
          </Field>
          <Field label={t("builder.names.maiden_name")}>
            {(id) => <Input id={id} value={maiden} onChange={(e) => setMaiden(e.target.value)} />}
          </Field>
        </div>
        <Field label={t("builder.gender")}>
          {(id) => (
            <Select id={id} value={gender} onChange={(e) => setGender(e.target.value as Gender)}>
              {GENDERS.map((g) => (
                <option key={g} value={g}>
                  {t(`gender.${g}`)}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <PartialDateInput label={t("person.born")} value={birth} onChange={setBirth} />
        <PlaceInput
          treeId={treeId}
          label={t("builder.birthPlace")}
          value={birthPlace}
          onChange={setBirthPlace}
        />
        <Checkbox
          label={t("builder.deceased")}
          checked={isDead}
          onChange={(e) => setIsDead(e.target.checked)}
        />
        {isDead && <PartialDateInput label={t("person.died")} value={death} onChange={setDeath} />}

        {(relation === "parent" || relation === "child" || relation === "sibling") && (
          <Field label={t("builder.add.linkType")}>
            {(id) => (
              <Select
                id={id}
                value={pcType}
                onChange={(e) => setPcType(e.target.value as ParentChildType)}
              >
                {PARENT_CHILD_TYPES.map((x) => (
                  <option key={x} value={x}>
                    {t(`builder.pcType.${x}`)}
                  </option>
                ))}
              </Select>
            )}
          </Field>
        )}
        {relation === "partner" && (
          <Field label={t("builder.add.partnershipType")}>
            {(id) => (
              <Select
                id={id}
                value={pType}
                onChange={(e) => setPType(e.target.value as PartnershipType)}
              >
                {PARTNERSHIP_TYPES.map((x) => (
                  <option key={x} value={x}>
                    {t(`partnershipTypes.${x}`)}
                  </option>
                ))}
              </Select>
            )}
          </Field>
        )}
        {otherParentOptions.length > 0 && (
          <Field
            label={relation === "child" ? t("builder.add.otherParent") : t("builder.add.partnerOf")}
          >
            {(id) => (
              <Select id={id} value={otherParent} onChange={(e) => setOtherParent(e.target.value)}>
                <option value="">{t("builder.add.none")}</option>
                {otherParentOptions.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.display_name}
                  </option>
                ))}
              </Select>
            )}
          </Field>
        )}
        <ErrorAlert error={create.error} />
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>
            {t("common.cancel")}
          </Button>
          <Button type="submit" busy={create.isPending}>
            {t("common.create")}
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
