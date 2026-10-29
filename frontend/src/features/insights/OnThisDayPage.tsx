import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams, useSearchParams } from "react-router";

import { Button, Card, ErrorAlert, Input, PageHeader, Select } from "@/components/ui";
import { useMe } from "@/features/auth/api";
import { localIsoDate } from "@/lib/dates";
import type { Anniversary } from "@/lib/genealogy";

import { useOnThisDay } from "./api";
import { CalendarFeedDialog } from "./CalendarFeedDialog";
import { FactLine } from "./FactLine";
import { EmptyState } from "@/components/EmptyState";
import { TextSkeleton } from "@/components/Skeleton";

const RANGES = [0, 7, 30, 92] as const;

/** Birthdays, wedding anniversaries and memorial days of exactly dated facts. */
export function OnThisDayPage() {
  const { t, i18n } = useTranslation();
  const { treeId = "" } = useParams();
  const [params, setParams] = useSearchParams();
  const today = localIsoDate();
  const date = params.get("date") ?? today;
  const days = Number(params.get("days") ?? 0);
  const data = useOnThisDay(treeId, date, days);
  const me = useMe();
  const [subscribing, setSubscribing] = useState(false);
  // Members only: share-link visitors and demo accounts cannot have a feed (D115).
  const canSubscribe = Boolean(me.data && !me.data.is_sandbox);

  const set = (k: string, v: string | null) => {
    const next = new URLSearchParams(params);
    if (v) next.set(k, v);
    else next.delete(k);
    setParams(next, { replace: true });
  };

  const byDay: [string, Anniversary[]][] = [];
  for (const a of data.data?.items ?? []) {
    const last = byDay[byDay.length - 1];
    if (last && last[0] === a.on) last[1].push(a);
    else byDay.push([a.on, [a]]);
  }
  const dayTitle = (iso: string) =>
    new Intl.DateTimeFormat(i18n.language, {
      day: "numeric",
      month: "long",
      weekday: "long",
      timeZone: "UTC",
    }).format(new Date(`${iso}T00:00:00Z`));

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <Link to={`/trees/${treeId}`} className="text-leaf-700 text-sm underline">
        ← {t("person.backToTree")}
      </Link>
      <PageHeader
        title={t("insights.onThisDay.title")}
        actions={
          canSubscribe && (
            <Button variant="secondary" onClick={() => setSubscribing(true)}>
              <span aria-hidden="true">📅 </span>
              {t("calendarFeed.button")}
            </Button>
          )
        }
      />
      {subscribing && <CalendarFeedDialog treeId={treeId} onClose={() => setSubscribing(false)} />}
      <div className="flex flex-wrap items-center gap-3">
        <Input
          type="date"
          className="w-auto"
          aria-label={t("insights.onThisDay.date")}
          value={date}
          onChange={(e) =>
            set("date", e.target.value && e.target.value !== today ? e.target.value : null)
          }
        />
        <Select
          className="w-auto"
          aria-label={t("insights.onThisDay.range")}
          value={days}
          onChange={(e) => set("days", e.target.value === "0" ? null : e.target.value)}
        >
          {RANGES.map((r) => (
            <option key={r} value={r}>
              {t(`insights.onThisDay.ranges.${r}`)}
            </option>
          ))}
        </Select>
      </div>
      <p className="text-bark-700 text-xs">{t("insights.onThisDay.hint")}</p>

      {data.isPending && <TextSkeleton lines={3} label={t("common.loading")} />}
      <ErrorAlert error={data.error} />
      {data.data && byDay.length === 0 && (
        <EmptyState
          title={t("insights.onThisDay.empty")}
          hint={t("insights.onThisDay.emptyHint")}
        />
      )}
      {byDay.map(([day, items]) => (
        <Card key={day} className="space-y-2">
          <h2 className="font-semibold first-letter:uppercase">
            {dayTitle(day)}
            {day === today && (
              <span className="bg-leaf-700 text-on-leaf ml-2 rounded-full px-2 py-0.5 align-middle text-xs">
                {t("insights.onThisDay.today")}
              </span>
            )}
          </h2>
          <ul className="space-y-2">
            {items.map((a) => (
              <li
                key={`${a.fact.kind}-${a.fact.id}`}
                className="flex flex-wrap items-baseline gap-2"
              >
                <span className="text-leaf-700 min-w-24 text-sm font-semibold tabular-nums">
                  {t("insights.onThisDay.yearsAgo", { count: a.years })}
                </span>
                <FactLine fact={a.fact} treeId={treeId} />
              </li>
            ))}
          </ul>
        </Card>
      ))}
    </div>
  );
}
