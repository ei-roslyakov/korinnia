import type { TFunction } from "i18next";

import type { Citation } from "@/lib/genealogy";

/** Human label of what a citation supports ("Народження 1923-02-14", "Ім’я: …", …). */
export function citationTargetLabel(
  t: TFunction,
  target: Citation["target"],
  field: string | null,
): string {
  switch (target.entity_type) {
    case "person":
      return field
        ? t(`collab.fields.${field}`, { defaultValue: field })
        : t("collab.target.person");
    case "person_name":
      return t("collab.target.name", { name: target.label ?? "" });
    case "event":
      return [t(`eventTypes.${target.event_type ?? "custom"}`), target.date, target.label]
        .filter(Boolean)
        .join(" · ");
    default:
      return target.label ?? t(`collab.target.${target.entity_type}`);
  }
}
