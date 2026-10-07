import { useTranslation } from "react-i18next";
import { Link, useParams, useSearchParams } from "react-router";

import { Button, ErrorAlert, Input, PageHeader } from "@/components/ui";
import { FACT_CATEGORIES, type Fact, type FactCategory } from "@/lib/genealogy";

import { useTimeline } from "./api";
import { historyBetween, type HistoryEvent } from "./history";
import { CategoryFilter, FactLine } from "./FactLine";
import { parseCategories } from "./facts";
import { PersonFilter } from "./PersonFilter";
import { EmptyState } from "@/components/EmptyState";
import { TextSkeleton } from "@/components/Skeleton";

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

  // Family facts and (optionally) historical events, merged per decade.
  type Row = { fact: Fact } | { history: HistoryEvent };
  const showHistory = params.get("history") !== "0";
  const years = items.map((f) => f.date?.year).filter((y): y is number => typeof y === "number");
  const context =
    showHistory && years.length ? historyBetween(Math.min(...years), Math.max(...years)) : [];
  // [year, order within the year, row]: a historical event goes before the family's facts of
  // its first year.
  const rows: [number, number, Row][] = [
    ...items.map((fact): [number, number, Row] => [fact.date?.year ?? 0, 1, { fact }]),
    ...context.map((history): [number, number, Row] => [history.from, 0, { history }]),
  ].sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  const decades: [number, Row[]][] = [];
  for (const [year, , row] of rows) {
    const decade = Math.floor(year / 10) * 10;
    const last = decades[decades.length - 1];
    if (last && last[0] === decade) last[1].push(row);
    else decades.push([decade, [row]]);
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
            className="w-28"
            aria-label={t("insights.timeline.from")}
            placeholder={t("insights.timeline.from")}
            defaultValue={fromYear ?? ""}
            onBlur={(e) => update({ from: e.target.value || null })}
            onKeyDown={(e) => e.key === "Enter" && e.currentTarget.blur()}
          />
          <span>–</span>
          <Input
            type="number"
            className="w-28"
            aria-label={t("insights.timeline.to")}
            placeholder={t("insights.timeline.to")}
            defaultValue={toYear ?? ""}
            onBlur={(e) => update({ to: e.target.value || null })}
            onKeyDown={(e) => e.key === "Enter" && e.currentTarget.blur()}
          />
        </div>
      </div>

      <label className="text-bark-700 -mt-2 flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          className="border-bark-100 size-4 rounded"
          checked={showHistory}
          onChange={(e) => update({ history: e.target.checked ? null : "0" })}
        />
        {t("insights.history.show")}
      </label>
      {timeline.isPending && <TextSkeleton lines={8} label={t("common.loading")} />}
      <ErrorAlert error={timeline.error} />
      {summary && (
        <>
          {summary.total === 0 && (
            <EmptyState
              title={t("insights.timeline.empty")}
              hint={t("insights.timeline.emptyHint")}
            />
          )}
          <ol className="space-y-6">
            {decades.map(([decade, facts]) => (
              <li key={decade}>
                <h2 className="text-bark-700 border-bark-100 mb-2 border-b pb-1 font-serif text-lg font-semibold">
                  {t("insights.timeline.decade", { decade })}
                </h2>
                <ol className="border-leaf-600/30 space-y-2 border-l-2 pl-4">
                  {facts.map((row) =>
                    "fact" in row ? (
                      <li key={`${row.fact.kind}-${row.fact.id}`}>
                        <FactLine fact={row.fact} treeId={treeId} />
                      </li>
                    ) : (
                      <li
                        key={row.history.key}
                        className="-ml-4 border-l-4 border-amber-500/60 bg-amber-50/60 py-1 pl-3 text-sm italic"
                      >
                        <span className="text-bark-700 mr-2 text-xs not-italic tabular-nums">
                          {row.history.from === row.history.to
                            ? row.history.from
                            : `${row.history.from}–${row.history.to}`}
                        </span>
                        {t(`insights.history.${row.history.key}`)}
                      </li>
                    ),
                  )}
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
