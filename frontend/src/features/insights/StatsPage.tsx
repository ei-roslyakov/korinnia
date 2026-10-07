import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router";

import { Card, ErrorAlert, PageHeader, Spinner } from "@/components/ui";
import { lifeYears } from "@/lib/dates";
import type { NameCount, PersonSummary } from "@/lib/genealogy";

import { useTreeStats } from "./api";

function Figure({ value, label }: { value: ReactNode; label: string }) {
  return (
    <div className="border-bark-100 bg-surface rounded-lg border p-3 text-center">
      <div className="text-2xl font-semibold tabular-nums">{value}</div>
      <div className="text-bark-700 text-xs">{label}</div>
    </div>
  );
}

function Names({ names, empty }: { names: NameCount[]; empty: string }) {
  if (names.length === 0) return <p className="text-bark-700 text-sm">{empty}</p>;
  const max = names[0]!.count;
  return (
    <ul className="space-y-1">
      {names.map((n) => (
        <li
          key={n.name}
          className="grid grid-cols-[minmax(7rem,12rem)_1fr_2rem] items-center gap-2"
        >
          <span className="truncate text-sm" title={[n.name, ...n.variants].join(", ")}>
            {n.name}
            {n.variants.length > 0 && (
              <span className="text-bark-700 text-xs"> ({n.variants.join(", ")})</span>
            )}
          </span>
          <span className="bg-bark-100 h-2 rounded-full">
            <span
              className="bg-leaf-600 block h-2 rounded-full"
              style={{ width: `${(n.count / max) * 100}%` }}
            />
          </span>
          <span className="text-right text-sm tabular-nums">{n.count}</span>
        </li>
      ))}
    </ul>
  );
}

/** Numbers about the family: people, generations, notable ancestors, names, decades. */
export function StatsPage() {
  const { t } = useTranslation();
  const { treeId = "" } = useParams();
  const stats = useTreeStats(treeId);

  if (stats.isPending) return <Spinner />;
  if (stats.error) return <ErrorAlert error={stats.error} />;
  const s = stats.data;
  const person = (p: PersonSummary) => (
    <>
      <Link
        to={`/trees/${treeId}/people/${p.id}`}
        className="text-leaf-700 font-medium hover:underline"
      >
        {p.display_name}
      </Link>{" "}
      <span className="text-bark-700 text-sm">{lifeYears(p.birth, p.death, p.is_living)}</span>
    </>
  );
  const maxDecade = Math.max(1, ...s.by_decade.map((d) => Math.max(d.births, d.deaths)));

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <Link to={`/trees/${treeId}`} className="text-leaf-700 text-sm underline">
        ← {t("person.backToTree")}
      </Link>
      <PageHeader title={t("insights.stats.title")} />
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-6">
        <Figure value={s.persons} label={t("insights.stats.persons")} />
        <Figure value={s.generations} label={t("insights.stats.generations")} />
        <Figure
          value={s.earliest_year && s.latest_year ? `${s.earliest_year}–${s.latest_year}` : "—"}
          label={t("insights.stats.period")}
        />
        <Figure value={s.partnerships} label={t("insights.stats.partnerships")} />
        <Figure value={s.places} label={t("insights.stats.places")} />
        <Figure value={s.events} label={t("insights.stats.events")} />
        <Figure value={s.male} label={t("insights.stats.male")} />
        <Figure value={s.female} label={t("insights.stats.female")} />
        <Figure value={s.living} label={t("insights.stats.living")} />
        <Figure value={s.media} label={t("insights.stats.media")} />
        <Figure value={s.sources} label={t("insights.stats.sources")} />
        <Figure value={s.stories} label={t("insights.stats.stories")} />
      </div>

      <Card className="space-y-3">
        <h2 className="font-semibold">{t("insights.stats.notable")}</h2>
        <dl className="grid gap-x-4 gap-y-2 text-sm sm:grid-cols-[auto_1fr]">
          <dt className="text-bark-700">{t("insights.stats.oldestAncestor")}</dt>
          <dd>{s.oldest_ancestor ? person(s.oldest_ancestor.person) : "—"}</dd>
          <dt className="text-bark-700">{t("insights.stats.longestLived")}</dt>
          <dd>
            {s.longest_lived ? (
              <>
                {person(s.longest_lived.person)} ·{" "}
                {t("insights.stats.age", { count: s.longest_lived.years ?? 0 })}
              </>
            ) : (
              "—"
            )}
          </dd>
          <dt className="text-bark-700">{t("insights.stats.averageLifespan")}</dt>
          <dd>
            {s.average_lifespan !== null
              ? t("insights.stats.averageValue", {
                  years: s.average_lifespan,
                  count: s.lifespan_sample,
                })
              : "—"}
          </dd>
        </dl>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="space-y-3">
          <h2 className="font-semibold">
            {t("insights.stats.surnames")} ({s.surnames.length})
          </h2>
          <Names names={s.surnames} empty={t("insights.stats.none")} />
        </Card>
        <Card className="space-y-3">
          <h2 className="font-semibold">{t("insights.stats.firstNames")}</h2>
          <Names names={s.first_names} empty={t("insights.stats.none")} />
        </Card>
      </div>

      <Card className="space-y-3">
        <h2 className="font-semibold">{t("insights.stats.byDecade")}</h2>
        {s.by_decade.length === 0 ? (
          <p className="text-bark-700 text-sm">{t("insights.stats.none")}</p>
        ) : (
          <>
            <div
              className="flex h-48 items-end gap-1 overflow-x-auto pb-6"
              role="img"
              aria-label={t("insights.stats.byDecade")}
            >
              {s.by_decade.map((d) => (
                <div
                  key={d.decade}
                  className="relative flex h-full min-w-8 flex-1 items-end justify-center gap-0.5"
                >
                  <span
                    className="w-3 rounded-t bg-green-600"
                    style={{ height: `${(d.births / maxDecade) * 100}%` }}
                    title={`${d.decade}: ${t("insights.stats.births")} ${d.births}`}
                  />
                  <span
                    className="w-3 rounded-t bg-stone-500"
                    style={{ height: `${(d.deaths / maxDecade) * 100}%` }}
                    title={`${d.decade}: ${t("insights.stats.deaths")} ${d.deaths}`}
                  />
                  <span className="text-bark-700 absolute -bottom-5 text-[10px]">{d.decade}</span>
                </div>
              ))}
            </div>
            <div className="text-bark-700 flex gap-4 text-xs">
              <span>
                <span className="mr-1 inline-block size-2 rounded-full bg-green-600" />
                {t("insights.stats.births")}
              </span>
              <span>
                <span className="mr-1 inline-block size-2 rounded-full bg-stone-500" />
                {t("insights.stats.deaths")}
              </span>
            </div>
            <table className="sr-only">
              <caption>{t("insights.stats.byDecade")}</caption>
              <tbody>
                {s.by_decade.map((d) => (
                  <tr key={d.decade}>
                    <th>{d.decade}</th>
                    <td>{d.births}</td>
                    <td>{d.deaths}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
      </Card>
    </div>
  );
}
