import { useTranslation } from "react-i18next";

import { PersonCombobox } from "@/features/person/PersonCombobox";
import type { PersonSummary } from "@/lib/genealogy";

/** Canvas search: by any name variant (Cyrillic/Latin), place or year. */
export function SearchBox({
  treeId,
  onSelect,
}: {
  treeId: string;
  onSelect: (person: PersonSummary) => void;
}) {
  const { t } = useTranslation();
  return <PersonCombobox treeId={treeId} onSelect={onSelect} label={t("canvas.search")} />;
}
