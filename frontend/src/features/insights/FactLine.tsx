import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import { formatPartialDate } from "@/lib/dates";
import { factCategory, type Fact, type FactCategory } from "@/lib/genealogy";

import { CATEGORY_STYLE, factTypeLabel } from "./facts";

/** One fact: type badge, title, people (linked), place; optionally the date. */
export function FactLine({
  fact,
  treeId,
  showDate = true,
}: {
  fact: Fact;
  treeId: string;
  showDate?: boolean;
}) {
  const { t, i18n } = useTranslation();
  const style = CATEGORY_STYLE[factCategory(fact.type)];
  const where = fact.cemetery_name ?? fact.place?.name;
  return (
    <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5 text-sm">
      {showDate && fact.date && (
        <span className="text-bark-700 tabular-nums">
          {formatPartialDate(fact.date, t, i18n.language)}
        </span>
      )}
      <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${style.badge}`}>
        {factTypeLabel(t, fact.type)}
      </span>
      {fact.title && <span className="font-medium">{fact.title}</span>}
      <span>
        {fact.persons.map((p, i) => (
          <span key={p.id}>
            {i > 0 && (fact.kind === "event" ? ", " : " & ")}
            <Link to={`/trees/${treeId}/people/${p.id}`} className="text-leaf-700 hover:underline">
              {p.display_name}
            </Link>
          </span>
        ))}
      </span>
      {where && <span className="text-bark-700">· {where}</span>}
    </div>
  );
}

/** Toggle chips for fact categories; an empty selection means "all". */
export function CategoryFilter({
  value,
  onChange,
}: {
  value: FactCategory[];
  onChange: (v: FactCategory[]) => void;
}) {
  const { t } = useTranslation();
  const all = Object.keys(CATEGORY_STYLE) as FactCategory[];
  return (
    <div className="flex flex-wrap gap-1" role="group" aria-label={t("insights.categories.label")}>
      {all.map((c) => {
        const on = value.includes(c);
        return (
          <button
            key={c}
            type="button"
            aria-pressed={on}
            onClick={() => onChange(on ? value.filter((x) => x !== c) : [...value, c])}
            className={`rounded-full border px-3 py-1 text-xs ${on ? `${CATEGORY_STYLE[c].badge} border-transparent font-semibold` : "border-bark-100 text-bark-700 bg-surface"}`}
          >
            {t(`insights.categories.${c}`)}
          </button>
        );
      })}
    </div>
  );
}
