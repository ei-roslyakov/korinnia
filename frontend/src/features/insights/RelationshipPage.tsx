import { useTranslation } from "react-i18next";
import { Link, useParams, useSearchParams } from "react-router";

import { Button, Card, ErrorAlert, PageHeader, Spinner } from "@/components/ui";
import { Avatar } from "@/features/person/Avatar";
import { lifeYears } from "@/lib/dates";
import type { PersonSummary, Relationship } from "@/lib/genealogy";

import { useRelationship } from "./api";
import { kinshipTerm } from "./kinship";
import { PersonFilter } from "./PersonFilter";

const EDGE_ICON = { parent: "↑", child: "↓", partner: "⚭" } as const;

function PersonChip({ treeId, person }: { treeId: string; person: PersonSummary }) {
  return (
    <Link
      to={`/trees/${treeId}/people/${person.id}`}
      className="border-bark-100 hover:border-leaf-600 flex items-center gap-2 rounded-lg border bg-white px-2 py-1"
    >
      <Avatar name={person.display_name} gender={person.gender} url={person.avatar_url} size="sm" />
      <span className="text-sm">
        <span className="block font-medium">{person.display_name}</span>
        <span className="text-bark-700 text-xs">
          {lifeYears(person.birth, person.death, person.is_living)}
        </span>
      </span>
    </Link>
  );
}

function Result({ treeId, r }: { treeId: string; r: Relationship }) {
  const { t, i18n } = useTranslation();
  return (
    <Card className="space-y-4">
      <div>
        <p className="text-bark-700 text-sm">
          {t("insights.kinship.whoIs", { b: r.b.display_name, a: r.a.display_name })}
        </p>
        <p
          className="font-serif text-3xl font-semibold first-letter:uppercase"
          data-testid="kinship-term"
        >
          {kinshipTerm(r, i18n.language)}
        </p>
        {r.non_biological && (
          <p className="mt-1 text-sm text-amber-800">{t("insights.kinship.nonBiological")}</p>
        )}
        {r.kind === "distant" && (
          <p className="text-bark-700 mt-1 text-sm">
            {t("insights.kinship.steps", { count: r.path.length - 1 })}
          </p>
        )}
      </div>
      {r.common_ancestors.length > 0 && r.up! > 0 && r.down! > 0 && (
        <div className="space-y-1">
          <h2 className="text-bark-700 text-xs font-semibold tracking-wide uppercase">
            {t("insights.kinship.commonAncestors")}
          </h2>
          <div className="flex flex-wrap gap-2">
            {r.common_ancestors.map((p) => (
              <PersonChip key={p.id} treeId={treeId} person={p} />
            ))}
          </div>
        </div>
      )}
      {r.path.length > 1 && (
        <div className="space-y-1">
          <h2 className="text-bark-700 text-xs font-semibold tracking-wide uppercase">
            {t("insights.kinship.path")}
          </h2>
          <ol className="flex flex-wrap items-center gap-1" aria-label={t("insights.kinship.path")}>
            {r.path.map((step) => (
              <li key={step.person.id} className="flex items-center gap-1">
                {step.edge && (
                  <span
                    className="text-bark-700 px-1 text-lg"
                    title={t(`insights.kinship.edges.${step.edge}`)}
                    aria-label={t(`insights.kinship.edges.${step.edge}`)}
                  >
                    {EDGE_ICON[step.edge]}
                  </span>
                )}
                <PersonChip treeId={treeId} person={step.person} />
              </li>
            ))}
          </ol>
          <p className="text-bark-700 text-xs">{t("insights.kinship.legend")}</p>
        </div>
      )}
    </Card>
  );
}

/** "How is B related to A?" — two pickers, the kinship term, common ancestors and the path. */
export function RelationshipPage() {
  const { t } = useTranslation();
  const { treeId = "" } = useParams();
  const [params, setParams] = useSearchParams();
  const a = params.get("a");
  const b = params.get("b");
  const rel = useRelationship(treeId, a, b);

  const set = (changes: Record<string, string | null>) => {
    const next = new URLSearchParams(params);
    for (const [k, v] of Object.entries(changes)) {
      if (v) next.set(k, v);
      else next.delete(k);
    }
    setParams(next, { replace: true });
  };

  return (
    <div className="mx-auto max-w-4xl space-y-4">
      <Link to={`/trees/${treeId}`} className="text-leaf-700 text-sm underline">
        ← {t("person.backToTree")}
      </Link>
      <PageHeader title={t("insights.kinship.title")} />
      <div className="flex flex-wrap items-end gap-3">
        <div className="space-y-1">
          <span className="block text-sm font-medium">{t("insights.kinship.personA")}</span>
          <PersonFilter
            treeId={treeId}
            personId={a}
            label={t("insights.kinship.choose")}
            onChange={(id) => set({ a: id })}
          />
        </div>
        <Button
          variant="ghost"
          aria-label={t("insights.kinship.swap")}
          title={t("insights.kinship.swap")}
          disabled={!a && !b}
          onClick={() => set({ a: b, b: a })}
        >
          ⇄
        </Button>
        <div className="space-y-1">
          <span className="block text-sm font-medium">{t("insights.kinship.personB")}</span>
          <PersonFilter
            treeId={treeId}
            personId={b}
            label={t("insights.kinship.choose")}
            onChange={(id) => set({ b: id })}
          />
        </div>
      </div>
      {!(a && b) && <p className="text-bark-700 text-sm">{t("insights.kinship.hint")}</p>}
      {rel.isFetching && !rel.data && <Spinner />}
      <ErrorAlert error={rel.error} />
      {rel.data && a && b && <Result treeId={treeId} r={rel.data} />}
    </div>
  );
}
