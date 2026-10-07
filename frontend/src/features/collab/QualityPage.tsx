import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router";

import { Card, ErrorAlert, PageHeader, Spinner } from "@/components/ui";
import { useTree } from "@/features/tree/api";
import { lifeYears } from "@/lib/dates";
import type { PersonSummary } from "@/lib/genealogy";
import { atLeast } from "@/lib/types";

import { useDataQuality } from "./api";

/** Research to-do list for the tree. */
export function QualityPage() {
  const { t } = useTranslation();
  const { treeId = "" } = useParams();
  const tree = useTree(treeId);
  const dq = useDataQuality(treeId);
  const canEdit = tree.data ? atLeast(tree.data.my_role, "editor") : false;
  const link = (p: PersonSummary) =>
    canEdit ? `/trees/${treeId}/people/${p.id}/edit` : `/trees/${treeId}/people/${p.id}`;

  if (dq.isPending) return <Spinner />;
  if (dq.error) return <ErrorAlert error={dq.error} />;
  const d = dq.data;
  const person = (p: PersonSummary, extra?: ReactNode) => (
    <li key={p.id} className="text-sm">
      <Link to={link(p)} className="text-leaf-700 hover:underline">
        {p.display_name}
      </Link>{" "}
      <span className="text-bark-700">{lifeYears(p.birth, p.death, p.is_living)}</span>
      {extra}
    </li>
  );
  const sections: [string, ReactNode[]][] = [
    [
      "date_problems",
      d.date_problems.map((x) =>
        person(
          x.person,
          <ul className="list-disc pl-5 text-xs text-amber-800">
            {x.warnings.map((w, i) => (
              <li key={i}>{t(`warnings.${w.code}`, { ...w.params, defaultValue: w.code })}</li>
            ))}
          </ul>,
        ),
      ),
    ],
    ["missing_birth", d.missing_birth.map((p) => person(p))],
    ["without_sources", d.without_sources.map((p) => person(p))],
    ["missing_photo", d.missing_photo.map((p) => person(p))],
    [
      "open_questions",
      d.open_questions.map((q) => (
        <li key={q.id} className="text-sm">
          <Link
            to={`/trees/${treeId}/people/${q.person_id}`}
            className="text-leaf-700 hover:underline"
          >
            {q.person_name}
          </Link>
          : {q.question}
        </li>
      )),
    ],
  ];
  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <Link to={`/trees/${treeId}`} className="text-leaf-700 text-sm underline">
        ← {t("person.backToTree")}
      </Link>
      <PageHeader title={t("collab.quality.title")} />
      <p className="text-bark-700 text-sm">
        {t("collab.quality.hint", { count: d.counts.people })}
      </p>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
        {sections.map(([key]) => (
          <a
            key={key}
            href={`#${key}`}
            className="border-bark-100 hover:border-leaf-600 bg-surface rounded-lg border p-3 text-center"
          >
            <div className="text-2xl font-semibold">{d.counts[key]}</div>
            <div className="text-bark-700 text-xs">{t(`collab.quality.${key}`)}</div>
          </a>
        ))}
      </div>
      {sections.map(([key, items]) => (
        <Card key={key}>
          <h2 id={key} className="mb-2 font-semibold">
            {t(`collab.quality.${key}`)} ({d.counts[key]})
          </h2>
          {items.length === 0 ? (
            <p className="text-sm text-green-700">{t("collab.quality.allGood")}</p>
          ) : (
            <ul className="space-y-1">{items}</ul>
          )}
        </Card>
      ))}
    </div>
  );
}
