import { useTranslation } from "react-i18next";

import { usePerson } from "@/features/person/api";
import { PersonCombobox } from "@/features/person/PersonCombobox";

/** A chosen person shown as a removable chip, or a search box to choose one. */
export function PersonFilter({
  treeId,
  personId,
  onChange,
  label,
}: {
  treeId: string;
  personId: string | null;
  onChange: (id: string | null) => void;
  label: string;
}) {
  const { t } = useTranslation();
  const person = usePerson(treeId, personId);
  if (!personId) {
    return <PersonCombobox treeId={treeId} label={label} onSelect={(p) => onChange(p.id)} />;
  }
  return (
    <span className="border-bark-100 bg-bark-50 inline-flex items-center gap-2 rounded-full border px-3 py-1 text-sm">
      {person.data?.display_name ?? "…"}
      <button
        type="button"
        aria-label={t("insights.clearPerson")}
        className="text-bark-700 hover:text-bark-900"
        onClick={() => onChange(null)}
      >
        ✕
      </button>
    </span>
  );
}
