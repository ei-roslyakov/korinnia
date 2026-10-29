import { useTranslation } from "react-i18next";
import { Link, useParams, useSearchParams } from "react-router";

import { EmptyState } from "@/components/EmptyState";
import { TextSkeleton } from "@/components/Skeleton";
import { Card, ErrorAlert, Input, PageHeader } from "@/components/ui";

import { usePlaceIndex } from "./api";
import { historicalLabel } from "./names";

/** Every place of the tree, most events first; search covers historical names too (D116). */
export function PlacesPage() {
  const { t } = useTranslation();
  const { treeId = "" } = useParams();
  const [params, setParams] = useSearchParams();
  const q = params.get("q") ?? "";
  const index = usePlaceIndex(treeId, q.trim());

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <Link to={`/trees/${treeId}`} className="text-leaf-700 text-sm underline">
        ← {t("person.backToTree")}
      </Link>
      <PageHeader title={t("places.title")} />
      <Input
        type="search"
        aria-label={t("places.search")}
        placeholder={t("places.search")}
        value={q}
        onChange={(e) => setParams(e.target.value ? { q: e.target.value } : {}, { replace: true })}
      />
      {index.isPending && <TextSkeleton lines={4} label={t("common.loading")} />}
      <ErrorAlert error={index.error} />
      {index.data?.length === 0 && (
        <EmptyState
          title={t(q ? "places.noMatches" : "places.empty")}
          hint={t("places.emptyHint")}
        />
      )}
      {index.data && index.data.length > 0 && (
        <Card>
          <ul className="divide-bark-100 divide-y" aria-label={t("places.title")}>
            {index.data.map(({ place, events, people }) => (
              <li key={place.id} className="flex items-baseline justify-between gap-3 py-2">
                <div className="min-w-0">
                  <Link
                    to={`/trees/${treeId}/places/${place.id}`}
                    className="text-leaf-700 font-medium hover:underline"
                  >
                    {place.name}
                  </Link>
                  {(place.region || place.country) && (
                    <span className="text-bark-700 text-sm">
                      {" "}
                      ({[place.region, place.country].filter(Boolean).join(", ")})
                    </span>
                  )}
                  {place.historical_names.length > 0 && (
                    <div className="text-bark-700 truncate text-xs">
                      {place.historical_names.map((h) => historicalLabel(t, h)).join(" · ")}
                    </div>
                  )}
                </div>
                <span className="text-bark-700 shrink-0 text-sm tabular-nums">
                  {t("places.counts", { events, people })}
                </span>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}
