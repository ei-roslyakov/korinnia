import { useTranslation } from "react-i18next";
import { Link, useParams, useSearchParams } from "react-router";

import { Button, ErrorAlert, Input, PageHeader, Spinner } from "@/components/ui";
import { FACT_CATEGORIES, type Fact, type FactCategory } from "@/lib/genealogy";

import { useTimeline } from "./api";
import { CategoryFilter, FactLine } from "./FactLine";
import { parseCategories } from "./facts";
import { PersonFilter } from "./PersonFilter";

/** All dated events and marriages of the family, oldest first, grouped by decade. */
export function TimelinePage() {
  const { t } = useTranslation();
  const { treeId = "" } = useParams();
  const [params, setParams] = useSearchParams();
  const categories = parseCategories(params.get("cat"));
  const personId = params.get("person");
  const fromYear = Number(params.get("from")) || null;
  const toYear = Number(params.get("to")) || null;
  const timeline = useTimeline(treeId, {
    types: categories.flatMap((c) => [...FACT_CATEGORIES[c]]),
    personId,
    fromYear,
    toYear,
  });
  const pages = timeline.data?.pages ?? [];
  const items = pages.flatMap((p) => p.items);
  const summary = pages[0];

  const update = (changes: Record<string, string | null>) => {
    const next = new URLSearchParams(params);
    for (const [k, v] of Object.entries(changes)) {
      if (v) next.set(k, v);
      else next.delete(k);
    }
    setParams(next, { replace: true });
  };

  const decades: [number, Fact[]][] = [];
  for (const fact of items) {
    const decade = Math.floor((fact.date?.year ?? 0) / 10) * 10;
    const last = decades[decades.length - 1];
    if (last && last[0] === decade) last[1].push(fact);
    else decades.push([decade, [fact]]);
  }

  return (
    <div className="mx-auto max-w-4xl space-y-4">
      <Link to={`/trees/${treeId}`} className="text-leaf-700 text-sm underline">
        ← {t("person.backToTree")}
      </Link>
      <PageHeader title={t("insights.timeline.title")} />
      <div className="flex flex-wrap items-center gap-3">
        <CategoryFilter
          value={categories}
          onChange={(v: FactCategory[]) => update({ cat: v.join(",") || null })}
        />
        <PersonFilter
          treeId={treeId}
          personId={personId}
          label={t("insights.timeline.person")}
          onChange={(id) => update({ person: id })}
        />
        <div className="flex items-center gap-2">
          <Input
            type="number"
            className="w-24"
            aria-label={t("insights.timeline.from")}
            placeholder={t("insights.timeline.from")}
            defaultValue={fromYear ?? ""}
            onBlur={(e) => update({ from: e.target.value || null })}
            onKeyDown={(e) => e.key === "Enter" && e.currentTarget.blur()}
          />
          <span>–</span>
          <Input
            type="number"
            className="w-24"
            aria-label={t("insights.timeline.to")}
            placeholder={t("insights.timeline.to")}
            defaultValue={toYear ?? ""}
            onBlur={(e) => update({ to: e.target.value || null })}
            onKeyDown={(e) => e.key === "Enter" && e.currentTarget.blur()}
          />
        </div>
      </div>

      {timeline.isPending && <Spinner />}
      <ErrorAlert error={timeline.error} />
      {summary && (
        <>
          {summary.total === 0 && (
            <p className="text-bark-700 text-sm">{t("insights.timeline.empty")}</p>
          )}
          <ol className="space-y-6">
            {decades.map(([decade, facts]) => (
              <li key={decade}>
                <h2 className="text-bark-700 border-bark-100 mb-2 border-b pb-1 font-serif text-lg font-semibold">
                  {t("insights.timeline.decade", { decade })}
                </h2>
                <ol className="border-leaf-600/30 space-y-2 border-l-2 pl-4">
                  {facts.map((f) => (
                    <li key={`${f.kind}-${f.id}`}>
                      <FactLine fact={f} treeId={treeId} />
                    </li>
                  ))}
                </ol>
              </li>
            ))}
          </ol>
          <div className="text-bark-700 flex flex-wrap items-center gap-3 text-sm">
            {summary.total > 0 && (
              <span>
                {t("insights.timeline.shown", { shown: items.length, total: summary.total })}
              </span>
            )}
            {timeline.hasNextPage && (
              <Button
                variant="secondary"
                busy={timeline.isFetchingNextPage}
                onClick={() => void timeline.fetchNextPage()}
              >
                {t("insights.timeline.more")}
              </Button>
            )}
            {summary.undated > 0 && (
              <span>{t("insights.timeline.undated", { count: summary.undated })}</span>
            )}
          </div>
        </>
      )}
    </div>
  );
}
