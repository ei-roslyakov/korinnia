import { useTranslation } from "react-i18next";

import { CATEGORY_STYLE, factTypeLabel } from "@/features/insights/facts";
import { factCategory, type LifeEvent, type PersonDetail } from "@/lib/genealogy";

const CURRENT_YEAR = new Date().getFullYear();

/** A horizontal life line from birth to death (or today), with a dot for each dated event. */
export function LifeBar({ person }: { person: PersonDetail }) {
  const { t } = useTranslation();
  const start = person.birth?.date?.year;
  const end = person.death?.date?.year ?? (person.is_living ? CURRENT_YEAR : null);
  if (!start || !end || end <= start) return null;
  const span = end - start;
  const dated = person.events.filter(
    (e): e is LifeEvent & { date: { year: number } } =>
      typeof e.date?.year === "number" && e.date.year >= start && e.date.year <= end,
  );
  const at = (year: number) => `${((year - start) / span) * 100}%`;
  return (
    <figure className="space-y-1" aria-label={t("person.lifeBar", { from: start, to: end })}>
      <div className="relative h-6">
        <div className="from-leaf-600/70 to-leaf-600/30 absolute top-1/2 right-0 left-0 h-1.5 -translate-y-1/2 rounded-full bg-gradient-to-r" />
        {dated.map((e) => (
          <span
            key={e.id}
            className="border-surface absolute top-1/2 size-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 shadow-sm"
            style={{
              left: at(e.date.year),
              background: CATEGORY_STYLE[factCategory(e.type)].color,
            }}
            title={`${e.date.year} · ${factTypeLabel(t, e.type)}${e.title ? `: ${e.title}` : ""}`}
          />
        ))}
      </div>
      <figcaption className="text-bark-700 flex justify-between text-xs tabular-nums">
        <span>{start}</span>
        <span>
          {person.death ? end : t("person.today")}
          {` · ${t("person.yearsLived", { count: span })}`}
        </span>
      </figcaption>
    </figure>
  );
}
