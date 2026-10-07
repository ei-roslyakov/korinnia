import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router";

import { Badge, Card, ErrorAlert, PageHeader, Spinner } from "@/components/ui";
import { useStories } from "@/features/collab/api";
import { useTree } from "@/features/tree/api";
import { formatPartialDate } from "@/lib/dates";
import type { StoryStatus } from "@/lib/genealogy";
import { atLeast } from "@/lib/types";

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
              className="bg-leaf-700 hover:bg-leaf-600 rounded-md px-3 py-1.5 text-sm font-medium text-white"
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
      {stories.isPending && <Spinner />}
      <ErrorAlert error={stories.error} />
      {stories.data?.items.length === 0 && (
        <p className="text-bark-700 text-sm">{t("collab.story.none")}</p>
      )}
      <ul className="space-y-3">
        {stories.data?.items.map((s) => (
          <li key={s.id}>
            <Card>
              <Link
                to={`/trees/${treeId}/stories/${s.id}`}
                className="text-leaf-700 font-serif text-lg font-semibold hover:underline"
              >
                {s.title}
              </Link>
              <div className="text-bark-700 text-xs">
                {[
                  formatPartialDate(s.date, t, i18n.language),
                  s.narrator && t("collab.story.toldBy", { name: s.narrator }),
                  s.author?.display_name,
                ]
                  .filter(Boolean)
                  .join(" · ")}{" "}
                {s.status !== "published" && (
                  <Badge tone="amber">{t(`collab.storyStatus.${s.status}`)}</Badge>
                )}
              </div>
              <p className="text-bark-700 mt-1 text-sm">{s.excerpt}</p>
            </Card>
          </li>
        ))}
      </ul>
    </div>
  );
}
