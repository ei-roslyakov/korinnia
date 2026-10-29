import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams, useSearchParams } from "react-router";

import { Badge, ErrorAlert, Input, PageHeader } from "@/components/ui";
import { useStories } from "@/features/collab/api";
import { useTree } from "@/features/tree/api";
import { formatPartialDate } from "@/lib/dates";
import type { StoryKind, StoryStatus } from "@/lib/genealogy";
import { atLeast } from "@/lib/types";
import { EmptyState } from "@/components/EmptyState";
import { CardsSkeleton } from "@/components/Skeleton";
import { Logo } from "@/components/Logo";

const TABS: (StoryStatus | "all")[] = ["published", "pending_review", "draft"];
// "Recipes & traditions" (D117) is its own section of the stories page.
const SECTIONS: Record<"stories" | "recipes", StoryKind[]> = {
  stories: ["story"],
  recipes: ["recipe", "tradition"],
};

export function StoriesPage() {
  const { t, i18n } = useTranslation();
  const { treeId = "" } = useParams();
  const tree = useTree(treeId);
  const [tab, setTab] = useState<StoryStatus | "all">("published");
  const [params, setParams] = useSearchParams();
  const section = params.get("section") === "recipes" ? "recipes" : "stories";
  const q = params.get("q") ?? "";
  const stories = useStories(treeId, {
    ...(tab === "all" ? {} : { status: tab }),
    kind: SECTIONS[section],
    q: q.trim() || undefined,
  });
  const setParam = (k: string, v: string | null) => {
    const next = new URLSearchParams(params);
    if (v) next.set(k, v);
    else next.delete(k);
    setParams(next, { replace: true });
  };
  const role = tree.data?.my_role;
  const canWrite = role ? atLeast(role, "contributor") : false;

  return (
    <div className="mx-auto max-w-3xl">
      <Link to={`/trees/${treeId}`} className="text-leaf-700 text-sm underline">
        ← {t("person.backToTree")}
      </Link>
      <PageHeader
        title={t("collab.stories")}
        actions={
          canWrite &&
          (section === "stories" ? (
            <Link
              to={`/trees/${treeId}/stories/new`}
              className="bg-leaf-700 hover:bg-leaf-600 text-on-leaf rounded-md px-3 py-1.5 text-sm font-medium"
            >
              + {t("collab.story.new")}
            </Link>
          ) : (
            <>
              <Link
                to={`/trees/${treeId}/stories/new?kind=recipe`}
                className="bg-leaf-700 hover:bg-leaf-600 text-on-leaf rounded-md px-3 py-1.5 text-sm font-medium"
              >
                + {t("recipes.addRecipe")}
              </Link>
              <Link
                to={`/trees/${treeId}/stories/new?kind=tradition`}
                className="border-bark-100 hover:bg-bark-50 bg-surface rounded-md border px-3 py-1.5 text-sm"
              >
                + {t("recipes.addTradition")}
              </Link>
            </>
          ))
        }
      />
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="flex gap-1" role="group" aria-label={t("recipes.sections")}>
          {(["stories", "recipes"] as const).map((x) => (
            <button
              key={x}
              type="button"
              aria-pressed={section === x}
              className={`rounded-full border px-3 py-1 text-sm ${section === x ? "bg-leaf-700 text-on-leaf border-transparent" : "border-bark-100 bg-surface"}`}
              onClick={() => setParam("section", x === "recipes" ? "recipes" : null)}
            >
              {t(x === "recipes" ? "recipes.section" : "collab.stories")}
            </button>
          ))}
        </div>
        <Input
          type="search"
          className="w-auto flex-1"
          aria-label={t("recipes.search")}
          placeholder={t(section === "recipes" ? "recipes.searchRecipes" : "recipes.search")}
          value={q}
          onChange={(e) => setParam("q", e.target.value || null)}
        />
      </div>
      {canWrite && (
        <nav className="border-bark-100 mb-4 flex gap-1 border-b" role="tablist">
          {TABS.map((x) => (
            <button
              key={x}
              type="button"
              role="tab"
              aria-selected={tab === x}
              className={`-mb-px shrink-0 border-b-2 px-3 py-2 text-sm whitespace-nowrap ${tab === x ? "border-leaf-700 text-leaf-700 font-semibold" : "text-bark-700 border-transparent"}`}
              onClick={() => setTab(x)}
            >
              {t(`collab.storyStatus.${x}`)}
            </button>
          ))}
        </nav>
      )}
      {stories.isPending && <CardsSkeleton count={2} label={t("common.loading")} />}
      <ErrorAlert error={stories.error} />
      {stories.data?.items.length === 0 &&
        (section === "recipes" ? (
          <EmptyState title={t("recipes.none")} hint={t("recipes.noneHint")} />
        ) : (
          <EmptyState title={t("collab.story.none")} hint={t("collab.story.noneHint")} />
        ))}
      <ul className="space-y-4">
        {stories.data?.items.map((s) => (
          <li key={s.id}>
            <Link
              to={`/trees/${treeId}/stories/${s.id}`}
              className="group border-bark-100 bg-surface hover:border-leaf-600 flex gap-4 overflow-hidden rounded-lg border shadow-sm transition"
            >
              {s.cover_url ? (
                <img
                  src={s.cover_url}
                  alt=""
                  loading="lazy"
                  className="h-32 w-28 shrink-0 object-cover sm:w-40"
                />
              ) : (
                <div className="bg-bark-50 flex h-32 w-28 shrink-0 items-center justify-center sm:w-40">
                  <Logo className="size-14 opacity-50" />
                </div>
              )}
              <div className="min-w-0 py-3 pr-4">
                <h2 className="text-leaf-700 font-serif text-xl font-semibold group-hover:underline">
                  {s.title}
                </h2>
                <div className="text-bark-700 text-xs">
                  {[
                    s.kind && s.kind !== "story" && t(`recipes.kinds.${s.kind}`),
                    s.occasion,
                    formatPartialDate(s.date, t, i18n.language),
                    s.narrator &&
                      t(s.kind === "recipe" ? "recipes.from" : "collab.story.toldBy", {
                        name: s.narrator,
                      }),
                    s.author?.display_name,
                    s.kind !== "recipe" &&
                      t("collab.story.readingTime", { count: s.reading_minutes ?? 1 }),
                  ]
                    .filter(Boolean)
                    .join(" · ")}{" "}
                  {s.status !== "published" && (
                    <Badge tone="amber">{t(`collab.storyStatus.${s.status}`)}</Badge>
                  )}
                </div>
                <p className="text-bark-900 mt-1 line-clamp-3 font-serif text-sm">{s.excerpt}</p>
              </div>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
