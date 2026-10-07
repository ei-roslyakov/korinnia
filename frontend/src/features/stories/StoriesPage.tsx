import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router";

import { Badge, ErrorAlert, PageHeader } from "@/components/ui";
import { useStories } from "@/features/collab/api";
import { useTree } from "@/features/tree/api";
import { formatPartialDate } from "@/lib/dates";
import type { StoryStatus } from "@/lib/genealogy";
import { atLeast } from "@/lib/types";
import { EmptyState } from "@/components/EmptyState";
import { CardsSkeleton } from "@/components/Skeleton";
import { Logo } from "@/components/Logo";

const TABS: (StoryStatus | "all")[] = ["published", "pending_review", "draft"];

export function StoriesPage() {
  const { t, i18n } = useTranslation();
  const { treeId = "" } = useParams();
  const tree = useTree(treeId);
  const [tab, setTab] = useState<StoryStatus | "all">("published");
  const stories = useStories(treeId, tab === "all" ? {} : { status: tab });
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
          canWrite && (
            <Link
              to={`/trees/${treeId}/stories/new`}
              className="bg-leaf-700 hover:bg-leaf-600 text-on-leaf rounded-md px-3 py-1.5 text-sm font-medium"
            >
              + {t("collab.story.new")}
            </Link>
          )
        }
      />
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
      {stories.data?.items.length === 0 && (
        <EmptyState title={t("collab.story.none")} hint={t("collab.story.noneHint")} />
      )}
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
                    formatPartialDate(s.date, t, i18n.language),
                    s.narrator && t("collab.story.toldBy", { name: s.narrator }),
                    s.author?.display_name,
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
